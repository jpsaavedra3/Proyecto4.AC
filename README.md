# Proyecto 4: Pochoco Trader

Arquitectura de Computadores 2026-2, Universidad de los Andes. Grupo 15:
Martin Heiremans, Felix Svensson y Juan Pablo Saavedra. Profesor: Jorge Gómez Mir.

La versión actual usa la serie oficial **`tb/practica_meta.csv`**, que reemplaza a
`tb/practica.csv`. Implementa una ruptura de tendencia con EMA Q8, histéresis y
espera tras salir. El procesador Espino lee cada precio por SPI y escribe una orden
que la maestra ejecuta al precio siguiente. No se almacenan series en el diseño.

El informe vigente es [docs/Informe_Proyecto4.pdf](docs/Informe_Proyecto4.pdf), con
[fuente Markdown](docs/Informe_Proyecto4.md) y resultados en [docs/results](docs/results).
La mejora sobre la serie publicada no garantiza ganar las rondas ocultas.

## Herramientas

Se usó Python 3.12, OSS CAD Suite 2026-11-22 para Windows x64, Icarus 14 devel
(fd4a65b20), Yosys 0.71+77 (11d972c20), nextpnr-ice40 0.11.1-121 (15b77f5f),
icepack e iceprog de esa suite. Python usa biblioteca estándar, salvo `reportlab`
y `pypdf` para regenerar el PDF (`python -m pip install reportlab pypdf`).
El PDF ya está incluido. Conserva la portada y la estructura del informe original:
Arial de 11 puntos en el cuerpo, Calibri Bold de 12 en títulos principales y de 11
en subtítulos; tablas y leyendas en Arial de 10 puntos. El índice usa Calibri Bold
de 14 puntos y se actualiza al regenerar el PDF. Las fuentes se leen desde
`C:/Windows/Fonts`; en otro sistema, configurar `DOC_FONTS_DIR` con una carpeta
que contenga `arial.ttf`, `arialbd.ttf` y `calibrib.ttf`. El generador exige estas
fuentes para respetar el formato; no distribuye sus archivos en el repositorio.
La portada original y las medidas de referencia están en `docs/style/`.
El texto y las tablas mantienen el formato original; el gráfico conserva su
paleta original azul, naranja y verde, sin añadir colores a los títulos ni al texto.

Descarga oficial de herramientas: <https://github.com/YosysHQ/oss-cad-suite-build/releases/tag/2026-11-22>.
En Linux/WSL usa la distribución Linux y activa `source /ruta/oss-cad-suite/environment`.
Configura `OSS_CAD_SUITE` con la ruta a la carpeta de la suite para que el ejecutor
encuentre `share/yosys/ice40/cells_sim.v`. También acepta `--toolchain RUTA`.
En Windows configura igualmente `OSS_CAD_SUITE` y usa `python` en vez de `python3`
si ese es el nombre de tu intérprete; todos los ejecutores Python son portables.

## Ensamblado y referencia

```bash
python3 tools/generate_trade.py
python3 tools/pochoasm.py sw/trade.s -o sw/trade.hex
python3 tools/pochoasm.py sw/trade_shifter.s -o sw/trade_shifter.hex
python3 tools/pochoasm.py sw/trade_ema.s -o sw/trade_ema.hex
python3 ref/trader.py --ticks 20000 --csv build/ref.csv
python3 tools/verify_isa.py
```

`generate_trade.py` es la fuente común de las tres variantes; modificarlo y volver
a ejecutar el ensamblado mantiene sus decisiones equivalentes. Para cambiar la
estrategia también debe actualizarse `ref/trader.py` y repetirse la comparación.
`ref/legacy_trader.py` conserva el algoritmo anterior para comparaciones históricas.
El intérprete ISA verifica HEX, registros y decisiones; no sustituye la simulación RTL.

## Simulación y mediciones

```bash
python3 tools/run_checks.py unit
python3 tools/run_checks.py official
python3 tools/run_checks.py sim --ticks 20000 --period 100000
```

El testbench del curso se conserva sin cambios en `tb/tb_proyecto_4.sv`; `official`
genera una copia dentro de `build/` con la ruta oficial nueva y ejecuta sus 2.000 ticks.
Exige 4/4 y compara el CSV completo con Python. La prueba `sim` usa el testbench
ampliado: 20.000 ticks por variante, MISO sin X/Z, una respuesta por precio, sin
pérdidas, deadline y comparación de cada decisión y estado de contabilidad.

`build/medicion_v*.csv` contiene órdenes ejecutadas y contabilidad. `build/latencias_v*.csv`
contiene el costo y la decisión calculada de cada precio, incluida la última.
`build/perfil_v*.csv` contiene ciclos e instrucciones por PC. Los resultados de la
corrida de entrega también se conservan en `docs/results/`.

En este Windows se observó un fallo de Icarus después de registrar `DONE.` y generar
el archivo. Existe una recuperación **explícita**, desactivada por defecto:

```powershell
python tools/run_checks.py all --allow-compiler-exit-crash
```

Solo acepta el código Windows 0xC0000005 si el compilador registró `DONE.` y el
archivo se acaba de generar. Después exige que vvp finalice correctamente, que las
aserciones pasen y que todas las filas coincidan con Python. Otros errores siguen
siendo fatales. La recuperación se registra en cada log; no usa archivos antiguos.
En un entorno sin ese problema no hace falta la opción.

## Variantes y síntesis

| Variante | Programa | Hardware |
|---|---|---|
| 0 | `sw/trade.s` | Espino sin shifts; máscaras y sumas |
| **1, final** | `sw/trade_shifter.s` | Shifts fijos de ocho bits |
| 2 | `sw/trade_ema.s` | EMA8 unsigned Q8 de 16 bits, custom-0 |

La extensión de shifts admite únicamente cantidad ocho. EMA8 usa funct3=0,
funct7=0 y opcode 0x0b; la resta intermedia tiene 17 bits con signo. No son un
shifter general ni una EMA genérica de 32 bits. Sus tests reflejan este contrato.
Las tres variantes caben en la iCE40 HX1K y cierran timing a 25 MHz. El SoC
predeterminado conserva Variant=0 para ejecutar el testbench oficial con trade.hex;
la síntesis de entrega selecciona explícitamente **Variant=1** y trade_shifter.hex.

```bash
python3 tools/run_checks.py synth
python3 tools/run_checks.py all
python3 tools/reporte.py
python3 tools/render_report.py
```

La síntesis usa nextpnr seed 1, HX1K, VQ100, 25 MHz. Guarda logs, JSON, ASC y BIN
en `build/v0`, `build/v1` y `build/v2`. No se ignoran fallos de variantes.

El Makefile ofrece los mismos pasos: `make test`, `make sim`, `make medir`,
`make sintesis`, `make reporte`, `make verificar`. `make` genera la variante final 1.
En Windows puede usarse directamente Python sin instalar make.

## Programar la Go Board

Primero ejecutar todas las verificaciones y generar el bitstream. Conectar la placa
por USB y comprobar el driver FTDI de programación. El archivo final es
**`build/v1/pochoco_soc.bin`**. El programador verifica que el bitstream corresponda
a los fuentes y al HEX actuales y que exista una simulación aprobada de esa versión:

```bash
python3 tools/program_board.py --variant 1
python3 tools/program_board.py --variant 1 --flash
```

Sin `--flash` solo valida e imprime el comando. La segunda orden escribe la flash
mediante iceprog; debe ejecutarse con acceso USB desde el entorno utilizado.
Alternativamente, `make prog` sintetiza y llama a ese mismo verificador.

SPI de la maestra: CS_n pin 65, MOSI 64, MISO 63 y SCLK 62; conectar también tierra
común. SPI modo 0, MSB primero, SCLK hasta 1 MHz, niveles de 3,3 V. El reloj local
es 25 MHz. Reiniciar/reprogramar la placa entre rondas para reiniciar el estado del
agente; la maestra reinicia su caja e inventario por separado. El SoC no tiene una
orden SPI para reiniciar una ronda. La comprobación de conexión con la maestra y
la competencia presencial siguen siendo pruebas físicas distintas de la simulación.

## Revisar y hacer el commit

Los cambios se dejan sin commit para revisión. No se publica ni se programa nada
automáticamente al abrir la carpeta.

```bash
git status --short
git diff --check
git diff --stat
git add .
git commit -m "Optimize trader for official Meta series and verify FPGA variants"
```

No incluir `build/`, ejecutables de herramientas ni cachés. Sí incluir la nueva
serie oficial, assembly/HEX, RTL/tests, scripts, investigación e informe actualizado.
