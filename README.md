# Proyecto 4: Pochoco Trader

Arquitectura de Computadores 2026-2, Universidad de los Andes. Grupo 15: Martin Heiremans,
Felix Svensson y Juan Pablo Saavedra. Profesor: Jorge Gómez Mir.

Agente de inversión en assembly para el Espino Core del Pochoco SoC, en la Go Board. Recibe el
precio por SPI en cada tick y responde comprar, vender o mantener. El informe está en
[docs/Informe_Proyecto4.pdf](docs/Informe_Proyecto4.pdf).

## Versiones

| Herramienta | Versión |
| --- | --- |
| oss-cad-suite | 2026-11-12 |
| Icarus Verilog | 14.0 (devel); el testbench del curso necesita 13 o más |
| Yosys | 0.70+385 |
| nextpnr-ice40 | 0.11.1-91-gf934534a |
| icepack, iceprog | los de oss-cad-suite 2026-11-12 |
| Python | 3.13, solo biblioteca estándar (matplotlib para la figura opcional de `make reporte`) |

## Instalación

Se usó Linux (Ubuntu 24.04, también sirve WSL):

```bash
curl -L -o oss-cad-suite.tgz https://github.com/YosysHQ/oss-cad-suite-build/releases/download/2026-11-12/oss-cad-suite-linux-x64-20261112.tgz
tar -xzf oss-cad-suite.tgz
source oss-cad-suite/environment
```

## Ensamblar trade.s

```bash
python3 tools/pochoasm.py sw/trade.s -o sw/trade.hex
```

`tools/pochoasm.py` es el assembler del grupo (Proyecto 2) con `-o`, los shifts y la instrucción
`ema` agregados.

## Sintetizar y programar la placa

```bash
make          # variante final: build/v0/pochoco_soc.bin
make prog     # iceprog
```

## Testbenches

```bash
make sim      # testbench del curso, tb/tb_proyecto_4.sv, con sw/trade.s (escribe decisiones.csv)
make test     # hardware agregado: tb/tb_shifter.sv y tb/tb_ema.sv
```

El comando del encabezado de `tb/tb_proyecto_4.sv` también funciona tal cual desde la raíz.

## Versión de referencia del algoritmo

```bash
python3 ref/trader.py                          # 2000 ticks, como el testbench
python3 ref/trader.py --ticks 20000            # serie completa
python3 ref/trader.py --csv ref.csv            # decisiones por tick
diff decisiones.csv ref.csv                    # después de make sim: sin diferencias
```

Imprime patrimonio final, órdenes, comisiones y pérdida máxima del algoritmo, de no operar y de
comprar y mantener.

## Variantes y mediciones

| Variante | Programa | Hardware |
| --- | --- | --- |
| 0, solo software (final) | `sw/trade.s` | Espino base |
| 1, shifter | `sw/trade_shifter.s` | SLL, SRL y SRA habilitados en `espino_alu.v` |
| 2, instrucción `ema` | `sw/trade_ema.s` | `rd = rs1 + ((rs2 - rs1) >>> k)` en custom-0, `espino_ema.v` |

La variante se elige con el parámetro `Variant` de `pochoco_soc` (por defecto 0).

```bash
make sintesis   # LUTs, BRAM y fmax de las 3 variantes en build/v*/ (la 1 no cabe en la HX1K)
make medir      # tb/tb_medicion.sv con la serie completa, unos 15 minutos por variante
make reporte    # tablas del informe: IC, ciclos, CPI, perfil, Amdahl, Ops/s y síntesis
```

`make medir NTICKS=2000` hace una medición más corta.
