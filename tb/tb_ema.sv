// Testbench de la instruccion ema de la variante 2 (espino_ema):
// rd = rs1 + ((rs2 - rs1) >>> k) para k = 5 y k = 6.
//   iverilog -g2012 -s tb_ema -o /tmp/tb_ema rtl/espino_core/espino_ema.v tb/tb_ema.sv
//   vvp -n /tmp/tb_ema

module tb_ema;

  logic [31:0] acc, x, esperado;
  logic signed [31:0] paso;
  logic [2:0]  k;
  wire  [31:0] res;

  espino_ema dut (.acc_i(acc), .x_i(x), .k_i(k), .result_o(res));

  int errores = 0;

  initial begin
    for (int i = 0; i < 30000; i++) begin
      // la mitad con valores del rango del algoritmo (precios en Q8), la otra al azar
      acc = (i % 2) ? $urandom : $urandom_range(0, 65535);
      x   = (i % 2) ? $urandom : $urandom_range(0, 65535);
      k   = (i % 4 < 2) ? 3'd5 : 3'd6;
      paso     = $signed(x - acc) >>> k;    // en una variable con signo: shift aritmetico
      esperado = acc + paso;
      #1;
      if (res !== esperado) begin
        errores++;
        if (errores <= 5) $display("ERROR acc=%h x=%h k=%0d: %h, esperado %h", acc, x, k, res, esperado);
      end
    end
    if (errores == 0) $display("PASS ema: 30000 casos");
    else              $display("FAIL ema: %0d errores", errores);
    $finish;
  end

endmodule
