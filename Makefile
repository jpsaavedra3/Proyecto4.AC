PYTHON ?= python3
VARIANT ?= 1
NTICKS ?= 20000
PERIOD ?= 100000
CHECK_FLAGS ?=

.PHONY: all prog sim test ref medir reporte sintesis verificar clean
all:
	$(PYTHON) tools/run_checks.py synth --variant $(VARIANT) $(CHECK_FLAGS)
prog: all
	$(PYTHON) tools/program_board.py --variant $(VARIANT) --flash
sim:
	$(PYTHON) tools/run_checks.py official $(CHECK_FLAGS)
test:
	$(PYTHON) tools/verify_isa.py
	$(PYTHON) tools/run_checks.py unit $(CHECK_FLAGS)
ref:
	$(PYTHON) ref/trader.py --ticks $(NTICKS) --csv build/ref.csv
medir:
	$(PYTHON) tools/run_checks.py sim --ticks $(NTICKS) --period $(PERIOD) $(CHECK_FLAGS)
sintesis:
	$(PYTHON) tools/run_checks.py synth $(CHECK_FLAGS)
verificar:
	$(PYTHON) tools/verify_isa.py
	$(PYTHON) tools/run_checks.py all --ticks $(NTICKS) --period $(PERIOD) $(CHECK_FLAGS)
reporte:
	$(PYTHON) tools/reporte.py
clean:
	$(PYTHON) -c "from pathlib import Path; import shutil; target=Path('build').resolve(); assert target.parent==Path.cwd().resolve() and target.name=='build'; shutil.rmtree(target,ignore_errors=True)"
