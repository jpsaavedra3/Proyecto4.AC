// Testbench de la instruccion ema de la variante 2 (espino_ema):
// EMA8 with unsigned low-16-bit Q8 operands and a signed 17-bit difference.
//   iverilog -g2012 -s tb_ema -o /tmp/tb_ema rtl/espino_core/espino_ema.v tb/tb_ema.sv
//   vvp -n /tmp/tb_ema

module tb_ema;

  logic [31:0] acc, x, esperado;
  logic signed [31:0] paso; // sign-extend before adding to the unsigned 32-bit acc
  wire  [31:0] res;

  espino_ema dut (.acc_i(acc), .x_i(x), .result_o(res));

  int errores = 0;

  initial begin
    for (int i = 0; i < 30000; i++) begin
      // la mitad con valores del rango del algoritmo (precios en Q8), la otra al azar
      acc = $urandom_range(0, 65535);
      x   = $urandom_range(0, 65535);
      if (i == 0) begin acc = 0; x = 65535; end
      if (i == 1) begin acc = 65535; x = 0; end
      paso     = ($signed({1'b0, x[15:0]}) - $signed({1'b0, acc[15:0]})) >>> 8;
      esperado = acc + paso;
      #1;
      if (res !== esperado) begin
        errores++;
        if (errores <= 5) $display("ERROR acc=%h x=%h: %h, esperado %h", acc, x, res, esperado);
      end
    end
    if (errores == 0) $display("PASS ema: 30000 casos");
    else              $fatal(1, "FAIL ema: %0d errores", errores);
    $finish;
  end

endmodule
