// Mide IC, ciclos y perfil por tick de una variante. Emula a la maestra igual que
// tb_proyecto_4.sv y agrega, por tick, los ciclos y las instrucciones entre que llega
// el precio (byte_done) y la escritura de DECISION.
// Ejemplo (variante 2, serie completa):
//   iverilog -g2012 -s tb_medicion -o /tmp/tb_med -Ptb_medicion.VARIANTE=2 \
//     -Ptb_medicion.PROGRAMA=\"sw/trade_ema.hex\" -Ptb_medicion.NTICKS=20000 \
//     $(yosys-config --datdir)/ice40/cells_sim.v rtl/*.v rtl/espino_core/*.v tb/tb_medicion.sv
//   vvp -n /tmp/tb_med

`timescale 1ns/1ps

module tb_medicion;

  parameter string PROGRAMA   = "sw/trade.hex";
  parameter string SERIE      = "tb/practica_meta.csv";
  parameter string SALIDA     = "medicion.csv";
  parameter string PERFIL     = "perfil.csv";
  parameter string LATENCIAS  = "latencias.csv";
  parameter int    VARIANTE   = 0;
  parameter int    PERIODO_NS = 100000;
  parameter int    NTICKS     = 20000;

  localparam int CAJA0    = 10000;
  localparam int COMISION = 5;
  localparam int SPI_NS   = 9500;

  logic clk = 0;
  always #20 clk = ~clk;

  logic sclk = 0, mosi = 0, cs_n = 1;
  wire  miso;

  pochoco_soc #(.MemFile(PROGRAMA), .Variant(VARIANTE)) dut (
    .i_Clk(clk), .o_LED(), .i_Switch(4'b0000),
    .o_Segment1_A(), .o_Segment1_B(), .o_Segment1_C(), .o_Segment1_D(),
    .o_Segment1_E(), .o_Segment1_F(), .o_Segment1_G(),
    .o_Segment2_A(), .o_Segment2_B(), .o_Segment2_C(), .o_Segment2_D(),
    .o_Segment2_E(), .o_Segment2_F(), .o_Segment2_G(),
    .i_SPI_SCLK(sclk), .i_SPI_MOSI(mosi), .i_SPI_CS_n(cs_n), .o_SPI_MISO(miso));

  int precio [20000];

  task automatic leer_serie;
    int fd, t, r;
    string encabezado;
    fd = $fopen(SERIE, "r");
    if (fd == 0) $fatal(1, "Cannot open %s", SERIE);
    r = $fgets(encabezado, fd);
    for (int n = 0; n < NTICKS; n++) begin
      r = $fscanf(fd, "%d,%d\n", t, precio[n]);
      if (r != 2 || t != n || precio[n] < 1 || precio[n] > 255)
        $fatal(1, "Invalid input row %0d in %s", n, SERIE);
    end
    $fclose(fd);
  endtask

  task automatic spi(input logic [7:0] enviar, output logic [7:0] recibido);
    cs_n = 0;
    #1000;
    for (int b = 7; b >= 0; b--) begin
      mosi = enviar[b];
      #500 sclk = 1;
      if (miso !== 1'b0 && miso !== 1'b1) $fatal(1, "MISO contains X/Z");
      recibido[b] = miso;
      #500 sclk = 0;
    end
    #500 cs_n = 1;
  endtask

  int caja = CAJA0, acciones = 0, w = CAJA0;

  task automatic ejecutar(input logic [7:0] decision, input int p);
    int q = decision[5:0];
    case (decision[7:6])
      2'b01: begin
        if (q > (caja - COMISION) / p) q = (caja - COMISION) / p;
        if (q > 0) begin caja -= q * p + COMISION; acciones += q; end
      end
      2'b10: begin
        if (q > acciones) q = acciones;
        if (q > 0 && caja + q * p >= COMISION) begin caja += q * p - COMISION; acciones -= q; end
      end
      default: ;
    endcase
    w = caja + acciones * p;
  endtask

  // Ventana de medicion: desde byte_done hasta la escritura de DECISION
  wire retira = dut.u_core.instr_valid_id & ~dut.u_core.stall;
  int ciclos = 0, instr = 0, ciclos_tick = 0, instr_tick = 0, precios = 0;
  bit midiendo = 0;
  longint perfil_ciclos [512];
  longint perfil_instr  [512];
  logic [31:0] pc_actual = 0;
  bit respuesta_pendiente = 0;
  int respuestas = 0;
  int bytes_moved = 0;
  int fl;

  always @(posedge clk) begin
    if (dut.u_core.instr_valid_id) pc_actual = dut.u_core.pc_id;
    if (dut.u_spi.byte_done) begin
      if (respuesta_pendiente) $fatal(1, "Missing decision before next price");
      if (dut.u_spi.new_price_q) $fatal(1, "Previous price was not read");
      respuesta_pendiente = 1;
      midiendo = 1; // include the final computed decision in LATENCIAS
      ciclos   = 0;
      instr    = 0;
      bytes_moved = 0;
      precios++;
    end else if (midiendo) begin
      ciclos++;
      // Scope: data/MMIO bus inside the same window; excludes instruction fetch.
      // All transfers issued by these programs are 32-bit lw/sw operations.
      if (dut.data_req) bytes_moved += 4;
      perfil_ciclos[pc_actual[10:2]]++;
      if (retira) begin
        instr++;
        perfil_instr[pc_actual[10:2]]++;
      end
      if (dut.u_spi.wr && dut.u_spi.off == 2) begin
        if (ciclos >= (PERIODO_NS-SPI_NS)/40) $fatal(1, "Deadline missed");
        midiendo    = 0;
        ciclos_tick = ciclos;
        instr_tick  = instr;
        $fdisplay(fl, "%0d,%0d,%0d,%0d,%0d,%02h", precios-1, dut.u_spi.price_q,
                  ciclos, instr, bytes_moved, dut.data_wdata[7:0]);
      end
    end
    if (dut.u_spi.wr && dut.u_spi.off == 2) begin
      if (!respuesta_pendiente) $fatal(1, "Duplicate or unsolicited decision");
      respuesta_pendiente = 0;
      respuestas++;
    end
  end

  logic [7:0] decision;
  int fd, fp;

  initial begin
    leer_serie();
    fd = $fopen(SALIDA, "w");
    fl = $fopen(LATENCIAS, "w");
    if (fd == 0 || fl == 0) $fatal(1, "Cannot open measurement output files");
    $fdisplay(fl, "tick,precio,ciclos,instrucciones,bytes,decision_calculada");
    $fdisplay(fd, "tick,precio,decision,caja,acciones,patrimonio,ciclos,instrucciones");
    #4000;
    for (int n = 0; n < NTICKS; n++) begin
      spi(precio[n], decision);
      ejecutar(decision, precio[n]);
      // ciclos e instrucciones con los que se calculo esta decision (tick anterior)
      if (n == 0) $fdisplay(fd, "%0d,%0d,%02h,%0d,%0d,%0d,,", n, precio[n], decision, caja, acciones, w);
      else        $fdisplay(fd, "%0d,%0d,%02h,%0d,%0d,%0d,%0d,%0d", n, precio[n], decision, caja, acciones, w, ciclos_tick, instr_tick);
      #(PERIODO_NS - SPI_NS);
      if (n % 1000 == 0) begin
        $fflush(fd); $fflush(fl);
        $display("Progress v%0d: %0d/%0d prices", VARIANTE, n+1, NTICKS);
      end
    end
    $fclose(fd);
    $fclose(fl);
    if (respuestas != NTICKS || respuesta_pendiente)
      $fatal(1, "Expected %0d responses, got %0d", NTICKS, respuestas);
    fp = $fopen(PERFIL, "w");
    $fdisplay(fp, "pc,ciclos,instrucciones");
    for (int i = 0; i < 512; i++)
      if (perfil_ciclos[i] != 0) $fdisplay(fp, "%0d,%0d,%0d", 4 * i, perfil_ciclos[i], perfil_instr[i]);
    $fclose(fp);
    $display("Variante %0d, %0d ticks: patrimonio final %0d. Detalle en %s y %s", VARIANTE, NTICKS, w, SALIDA, PERFIL);
    $finish;
  end

endmodule
