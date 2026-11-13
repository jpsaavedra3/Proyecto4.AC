// Instruccion ema (custom-0) de la variante 2:
//   ema rd, rs1, rs2, k  ->  rd = rs1 + ((rs2 - rs1) >>> k),  k = funct3
// Un paso de media movil exponencial con alfa = 2^-k. Para que quepa en la
// HX1K solo se implementan k = 5 y k = 6, los que usa trade_ema.s.

module espino_ema (
  input  wire [31:0] acc_i,     // rs1: media actual
  input  wire [31:0] x_i,       // rs2: muestra nueva
  input  wire [2:0]  k_i,       // funct3: 5 o 6
  output wire [31:0] result_o
);

  wire signed [31:0] diff = x_i - acc_i;
  wire signed [31:0] step = k_i[0] ? (diff >>> 5) : (diff >>> 6);

  assign result_o = acc_i + step;

endmodule
