// ema rd, rs1, rs2, 8: unsigned Q8 values in rs1[15:0], rs2[15:0].
// rd = zero_extend(acc + ((x-acc) >>> 8)). Difference is SIGNED 17 bits.
// Encoding custom-0, funct7=0, funct3=0. Not a general 32-bit EMA.

module espino_ema (
  input  wire [31:0] acc_i,     // rs1: media actual
  input  wire [31:0] x_i,       // rs2: muestra nueva
  output wire [31:0] result_o
);

  wire signed [16:0] diff = $signed({1'b0, x_i[15:0]}) - $signed({1'b0, acc_i[15:0]});
  wire signed [16:0] next_value = $signed({1'b0, acc_i[15:0]}) + (diff >>> 8);
  assign result_o = {16'b0, next_value[15:0]};

endmodule
