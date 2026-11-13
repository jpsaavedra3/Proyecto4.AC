# Proyecto 4 - Pochoco Trader
#
#   make                 sintetiza la variante final y genera build/v0/pochoco_soc.bin
#   make prog            programa la Go Board
#   make sim             testbench del curso (tb/tb_proyecto_4.sv) con sw/trade.s
#   make test            testbenches del hardware agregado (shifter e instruccion ema)
#   make ref             version de referencia en Python (2000 ticks y serie completa)
#   make medir           IC, ciclos y perfil por tick de las 3 variantes
#   make reporte         tablas del informe (despues de make medir y make sintesis)
#   make sintesis        LUTs, BRAM y fmax de las 3 variantes
#
# VARIANT: 0 solo software (final), 1 shifter, 2 instruccion ema

TOP     := pochoco_soc
PCF     := goboard.pcf
VARIANT ?= 0
NTICKS  ?= 20000
SRC     := $(wildcard rtl/*.v rtl/espino_core/*.v)
CELLS    = $(shell yosys-config --datdir)/ice40/cells_sim.v

PROG_0 := sw/trade
PROG_1 := sw/trade_shifter
PROG_2 := sw/trade_ema
PROG   := $(PROG_$(VARIANT))
OUT    := build/v$(VARIANT)

.PHONY: all prog sim test ref medir reporte sintesis clean
.PRECIOUS: sw/%.hex

all: $(OUT)/$(TOP).bin

# trade.s -> trade.hex con el assembler del grupo
sw/%.hex: sw/%.s tools/pochoasm.py
	python3 tools/pochoasm.py $< -o $@

$(OUT)/$(TOP).json: $(SRC) $(PROG).hex
	mkdir -p $(OUT)
	yosys -q -l $(OUT)/yosys.log -p "read_verilog $(SRC); \
	  chparam -set Variant $(VARIANT) -set MemFile \"$(PROG).hex\" $(TOP); \
	  synth_ice40 -top $(TOP) -json $@; stat"

$(OUT)/$(TOP).asc: $(OUT)/$(TOP).json $(PCF)
	nextpnr-ice40 -q --hx1k --package vq100 --freq 25 --json $< --pcf $(PCF) \
	  --asc $@ -l $(OUT)/nextpnr.log

$(OUT)/$(TOP).bin: $(OUT)/$(TOP).asc
	icepack $< $@

prog: $(OUT)/$(TOP).bin
	iceprog $<

sim: sw/trade.hex
	mkdir -p build
	iverilog -g2012 -s tb_proyecto_4 -o build/tb_p4 $(CELLS) $(SRC) tb/tb_proyecto_4.sv
	vvp -n build/tb_p4

test:
	mkdir -p build
	iverilog -g2012 -s tb_shifter -o build/tb_shifter rtl/espino_core/espino_alu.v tb/tb_shifter.sv
	vvp -n build/tb_shifter
	iverilog -g2012 -s tb_ema -o build/tb_ema rtl/espino_core/espino_ema.v tb/tb_ema.sv
	vvp -n build/tb_ema

ref:
	python3 ref/trader.py
	python3 ref/trader.py --ticks 20000 --csv build/ref.csv

# Serie completa con el periodo de la ronda 3; cada variante toma unos 15 minutos
medir: sw/trade.hex sw/trade_shifter.hex sw/trade_ema.hex
	mkdir -p build
	for v in 0 1 2; do \
	  p=$$(case $$v in 0) echo $(PROG_0);; 1) echo $(PROG_1);; 2) echo $(PROG_2);; esac); \
	  iverilog -g2012 -s tb_medicion -o build/tb_med_v$$v -Ptb_medicion.VARIANTE=$$v \
	    -Ptb_medicion.PROGRAMA=\"$$p.hex\" -Ptb_medicion.NTICKS=$(NTICKS) \
	    -Ptb_medicion.SALIDA=\"build/medicion_v$$v.csv\" -Ptb_medicion.PERFIL=\"build/perfil_v$$v.csv\" \
	    $(CELLS) $(SRC) tb/tb_medicion.sv && vvp -n build/tb_med_v$$v || exit 1; \
	done

sintesis:
	-for v in 0 1 2; do $(MAKE) --no-print-directory VARIANT=$$v; done

reporte:
	python3 tools/reporte.py

clean:
	rm -rf build decisiones.csv
