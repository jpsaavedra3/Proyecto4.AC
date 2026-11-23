// Testbench del shifter de la variante 1 (espino_alu con Variant = 1):
// Fixed-8-bit extension: compare SLL8, SRL8 and SRA8 on all 32-bit operands.
//   iverilog -g2012 -s tb_shifter -o /tmp/tb_shifter rtl/espino_core/espino_alu.v tb/tb_shifter.sv
//   vvp -n /tmp/tb_shifter

module tb_shifter;

  localparam [3:0] ALU_SLL = 4'd5, ALU_SRL = 4'd6, ALU_SRA = 4'd7;

  logic [3:0]  op;
  logic [31:0] a, b, esperado;
  wire  [31:0] res;
  wire         cmp;

  espino_alu #(.Variant(1)) dut (
    .operator_i(op), .operand_a_i(a), .operand_b_i(b),
    .result_o(res), .cmp_result_o(cmp));

  int errores = 0;

  initial begin
    for (int i = 0; i < 30000; i++) begin
      a  = $urandom;
      b  = 32'd8;
      op = ALU_SLL + i % 3;
      case (op)
        ALU_SLL: esperado = a << b[4:0];
        ALU_SRL: esperado = a >> b[4:0];
        default: esperado = $signed(a) >>> b[4:0];
      endcase
      #1;
      if (res !== esperado) begin
        errores++;
        if (errores <= 5) $display("ERROR op=%0d a=%h shamt=%0d: %h, esperado %h", op, a, b[4:0], res, esperado);
      end
    end
    if (errores == 0) $display("PASS shifter: 30000 casos");
    else              $fatal(1, "FAIL shifter: %0d errores", errores);
    $finish;
  end

endmodule
