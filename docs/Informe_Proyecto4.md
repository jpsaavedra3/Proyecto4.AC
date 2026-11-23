# ÍNDICE

[[INDICE]]

# 1. ALGORITMO DE PREDICCIÓN Y DECISIÓN

La serie oficial de práctica contiene 20.000 precios de Meta normalizados entre 100 y 255. El archivo practica_meta.csv reemplaza a la serie anterior; el testbench del curso no cambia. La reversión a la media anterior termina esta nueva serie con $7.286. Por eso se compararon seguimiento de tendencia, ruptura, reversión, compra de caídas y selección adaptativa de expertos, conservando siempre la comisión y el retraso de un tick del protocolo.

Se eligió una ruptura de tendencia con histéresis: comprar cuando el precio supera claramente su media reciente y salir cuando cae bajo ella. Todo se calcula con enteros, con el precio en punto fijo Q8 (X = 256 · p). En cada tick:

- **Media:** E ← E + ((X − E) >> 8), media exponencial del precio con α = 1/256.
- **Desviación:** D = X − E, calculada después de actualizar la media.
- **Señal:** si D > 2.048 se entra; si D < −256 se sale. Entre ambos umbrales se conserva la posición objetivo. Equivalen a +8 y −1 unidades de precio.
- **Espera:** los primeros 32 precios son de calentamiento. Tras salir se esperan 32 precios; el contador se decrementa antes de comprobar una nueva entrada.

La histéresis reduce los cambios de posición por fluctuaciones de una unidad. El estado del indicador cabe en registros y no necesita multiplicador, divisor ni una serie de precios almacenada. El mismo programa se usa para cualquier empresa y período; no reconoce la acción ni utiliza fechas o datos externos.

Las familias y parámetros se compararon en bloques de los primeros 12.000 ticks y se contrastaron en los 4.000 siguientes. La configuración final se fijó antes de consultar los últimos 4.000 y se mantuvo después. También se probaron parámetros vecinos y escenarios sintéticos. Los dos bloques finales, reiniciando caja y estado, terminan en $9.553 y $9.882; una oscilación sinusoidal termina en $6.537. Son límites reales del seguimiento de tendencia. La serie ya se había observado al evaluar la versión anterior: esta separación no equivale a una muestra externa independiente ni garantiza el resultado en los períodos ocultos.

**Cantidad q.** Se escribe 0x7f (comprar 63) mientras la posición objetivo sea larga y 0xbf (vender 63) cuando se quiera salir. La maestra recorta cada compra a la caja disponible y cada venta al inventario; las órdenes vacías no pagan comisión, según su testbench. Repetir la orden permite completar posiciones mayores de 63. Así se elimina la copia de contabilidad en el procesador y las multiplicaciones y divisiones que necesitaba. La primera transacción devuelve 0x00. La orden calculada con p[n] se ejecuta a p[n+1], pagando $5 por orden no vacía; no hay deuda ni ventas en corto.

La Tabla 1 compara el algoritmo con las dos referencias en los primeros 2.000 ticks, que usa por defecto el testbench del curso, y en la serie completa. La pérdida máxima es la mayor caída del patrimonio desde su peak, calculada con la misma contabilidad oficial y una caja inicial de $10.000.

| Serie | Estrategia | Patrimonio final | Órdenes | Comisiones | Pérdida máxima |
| --- | --- | --- | --- | --- | --- |
| 2.000 ticks | Algoritmo | $10.976 | 2 | $10 | $696 |
|  | No operar | $10.000 | 0 | $0 | $0 |
|  | Comprar y mantener | $11.375 | 1 | $5 | $1.560 |
| 20.000 ticks | Algoritmo | $13.291 | 46 | $230 | $3.186 |
|  | No operar | $10.000 | 0 | $0 | $0 |
|  | Comprar y mantener | $9.695 | 1 | $5 | $9.300 |

Tabla 1: Algoritmo frente a no operar y comprar y mantener (ref/trader.py)

En la serie completa el algoritmo termina con $13.291 (+32,91 %), frente a $9.695 de comprar y mantener y $7.286 de la versión anterior. La pérdida máxima baja de $4.077 a $3.186 y las órdenes de 103 a 46. En los primeros 2.000 ticks obtiene $10.976, aunque comprar y mantener obtiene más: $11.375. La mejora acumulada no significa que todos los tramos sean ganadores.

# 2. IMPLEMENTACIÓN EN ASSEMBLY

sw/trade.s contiene 60 instrucciones (240 bytes), frente a las 135 de la implementación anterior. Se ensambla con tools/pochoasm.py, el assembler del grupo del Proyecto 2. El ciclo principal hace, en cada tick:

- **Esperar precio:** leer STATUS (0x8001_0000) hasta que el bit 0 indique un precio nuevo y luego leer PRICE (0x8001_0004), lo que borra ese bit.
- **Actualizar estado y predecir:** calcular X, actualizar E, obtener D y evaluar la ruptura con histéresis y los contadores de espera.
- **Decidir:** seleccionar comprar 63 o vender 63 según la posición objetivo. La contabilidad y los recortes los resuelve la maestra.
- **Escribir DECISION:** guardar el byte en 0x8001_0008 y volver a esperar. El byte queda preparado para la transacción siguiente.

**Registros y memoria.** Todo el estado vive en registros (Tabla 2). No se lee ni escribe RAM de datos; la memoria solo guarda el programa. Se redujo de 512 a 128 palabras, equivalentes a 512 bytes. El verificador ISA comprueba que las tres variantes quepan. Los únicos accesos de datos son los tres registros del esclavo SPI.

| Registro | Uso |
| --- | --- |
| x2 | Base del esclavo SPI, 0x8001_0000 |
| x3 | Media E del precio, en Q8 |
| x4 | Posición objetivo: 1 comprado, 0 fuera |
| x5, x6 | Calentamiento y espera tras una salida |
| x7 | Byte de decisión; temporal dentro de sra8_sw |
| x10 | Precio del tick |
| x1, x11 a x15 | Retorno y temporales de la actualización y del shift |

Tabla 2: Uso de registros de trade.s

**Punto fijo.** E y D están en Q8, con ocho bits fraccionarios. El precio máximo representable es 255 · 256 = 65.280. La diferencia cabe en 17 bits con signo. El desplazamiento aritmético redondea hacia −∞, igual que >> en Python, por lo que las tres implementaciones calculan los mismos valores.

**Operaciones que Espino no tiene.** En la versión solo software los shifts están deshabilitados. La multiplicación y la división se eliminaron del algoritmo de decisión:

- **Shift a la izquierda:** X = 256 · p se obtiene mediante ocho sumas sucesivas (x + x).
- **Shift aritmético a la derecha (sra8_sw):** recorre los bits desde el octavo mediante dos máscaras que se duplican. La diferencia de dos precios Q8 requiere como máximo ocho iteraciones. Para negativos usa x >> 8 = ~(~x >> 8).
- **Multiplicación y división:** las antiguas rutinas mul6 y div6 ya no se ejecutan porque el procesador no mantiene una réplica de caja e inventario.

**Igualdad con la referencia.** El testbench oficial aprueba 4/4 con los primeros 2.000 precios de Meta y su CSV coincide por completo con Python. El testbench de medición verifica los 20.000 precios en las tres variantes: decisión, caja, acciones y patrimonio coinciden en todos. También exige una respuesta por precio, MISO sin X/Z, ningún precio perdido y el deadline. Un intérprete independiente comprueba los HEX, los registros y las decisiones con la serie completa y casos constantes, extremos y aleatorios.

**Mediciones por tick.** Se cuentan ciclos e instrucciones retiradas desde byte_done sincronizado hasta la escritura de DECISION, a 25 MHz. latencias_v*.csv incluye la respuesta calculada de cada precio, también la última. El CSV de contabilidad registra la decisión ejecutada, correspondiente al precio anterior. El CPI agregado es la suma de ciclos dividida por la suma de instrucciones. La Tabla 3 resume la versión base.

| Programa | Caso | IC | Ciclos | CPI | Tiempo (µs) |
| --- | --- | --- | --- | --- | --- |
| trade.s | Promedio | 51,9 | 117,3 | 2,26 | 4,69 |
|  | Peor caso | 76,0 | 174,0 | 2,29 | 6,96 |

Tabla 3: IC, ciclos, CPI y tiempo por tick de trade.s (20.000 ticks)

Espino usa dos ciclos para una instrucción de ALU y tres en las cargas y los saltos tomados; por eso el CPI supera dos. La duración del shift software depende del valor del operando. La Tabla 4 compara el peor caso medido con el período de cada ronda, descontando la transacción SPI de 9,5 µs y redondeando a ciclos completos.

| Ronda | Período T | Ciclos disponibles | Peor caso de trade.s | Uso |
| --- | --- | --- | --- | --- |
| 1 | 10 ms | 249.762 | 174 | 0,07 % |
| 2 | 1 ms | 24.762 | 174 | 0,70 % |
| 3 | 0,1 ms | 2.262 | 174 | 7,69 % |

Tabla 4: Peor caso de trade.s frente al presupuesto de cada ronda

La versión base usa como máximo el 7,69 % del presupuesto de la ronda 3. Una cota estructural conservadora, separada de la medición, cuenta las 60 instrucciones más siete repeticiones adicionales del bucle de seis instrucciones: 102 en total. Con cuatro ciclos por instrucción como margen y 12 de detección, la cota es 420 ciclos. No hay bucles aritméticos sin cota para precios válidos.

# 3. CO-DISEÑO HARDWARE/SOFTWARE

## 3.1 Dónde se gastan los ciclos

tb_medicion.sv también suma los ciclos de cada PC dentro de la misma ventana. El informe agrupa las instrucciones con las etiquetas del programa (Tabla 5). Las llamadas y el retorno se incluyen en el shift software; las filas de costo cero identifican el trabajo eliminado respecto a la versión anterior.

| Bloque | Ciclos por tick | Fracción | CPI |
| --- | --- | --- | --- |
| Shift en software (sra8_sw) | 56,3 | 48,0 % | 2,24 |
| Media y señal | 41,2 | 35,1 % | 2,25 |
| Espera del precio | 12,5 | 10,6 % | 2,44 |
| Decisión | 7,3 | 6,3 % | 2,20 |
| Contabilidad | 0,0 | 0,0 % | — |
| Multiplicación (mul6) | 0,0 | 0,0 % | — |
| División (div6) | 0,0 | 0,0 % | — |

Tabla 5: Perfil de trade.s por bloque (20.000 ticks)

El shift software cuesta 56,3 ciclos por tick: aproximadamente el 48,0 % del total. Por Amdahl, acelerar solo ese bloque tiene un máximo de 1,92 veces. La variante shifter acelera además las ocho sumas de X; por eso su fracción acelerada es mayor. Las alternativas atacan el costo aritmético identificado en la medición.

## 3.2 Alternativas de hardware

Las dos variantes se seleccionan con Variant de pochoco_soc; 0 es la versión solo software. tb_shifter.sv y tb_ema.sv aprueban 30.000 vectores cada uno. En la simulación completa las tres producen exactamente las mismas decisiones y contabilidad. La memoria reducida utiliza ocho BRAM en las tres.

**Variante 1, shifter.** Se sustituyó el barrel shifter general por desplazamientos fijos de ocho posiciones, que son los usados por el algoritmo. En Variant=1 se habilitan SLL8, SRL8 y SRA8 en espino_alu.v; otras cantidades no están implementadas. trade_shifter.s usa slli para X y srai para actualizar E. Tiene 37 instrucciones (148 bytes) y ya no necesita sra8_sw. El cableado fijo evita el costo del shifter general que antes no cabía.

**Variante 2, instrucción ema.** Se implementa ema rd, rs1, rs2, 8 en custom-0 (opcode 0x0B, formato R, funct7=0 y funct3=0). Toma los 16 bits bajos unsigned Q8 de ambos operandos y calcula rd = acc + ((x − acc) >>> 8), con una diferencia intermedia de 17 bits con signo y resultado extendido con ceros. No es una EMA general de 32 bits. El restador, el desplazamiento fijo y el sumador están en ID, junto a la ALU; el resultado llega al banco de registros por el selector de write-back. trade_ema.s contiene 42 instrucciones (168 bytes). Decoder, assembler y testbench comparten esta semántica.

La Tabla 6 resume la síntesis para la iCE40 HX1K, encapsulado VQ100, y la Tabla 7 las mediciones de la serie completa a 25 MHz. Se usó OSS CAD Suite 2026-11-22, Yosys 0.71+77 (11d972c20), nextpnr 0.11.1-121 (15b77f5f), seed 1, e icepack. Las tres variantes caben y cierran timing. No se usa PLL ni se cambia el presupuesto de ciclos.

| Variante | SB_LUT4 | Celdas lógicas de 1.280 | BRAM | fmax (MHz) |
| --- | --- | --- | --- | --- |
| 0, solo software | 910 | 1.079 (84 %) | 8 | 44,04 |
| 1, shifter fijo | 977 | 1.154 (90 %) | 8 | 40,53 |
| 2, instrucción ema | 976 | 1.145 (89 %) | 8 | 44,73 |

Tabla 6: Recursos y frecuencia máxima de cada variante

| Variante | Ciclos prom. | Ciclos peor | IC prom. | CPI | Ops/s | Speedup medido | Speedup Amdahl |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0, solo software | 117,3 | 174 | 51,9 | 2,26 | 1,07 M | 1,00 | 1,00 |
| 1, shifter fijo | 49,0 | 56 | 20,7 | 2,36 | 2,55 M | 2,39 | 2,39 |
| 2, instrucción ema | 59,0 | 66 | 25,7 | 2,29 | 2,12 M | 1,99 | 1,99 |

Tabla 7: Mediciones por tick de cada variante (20.000 ticks, 25 MHz)

**Ops/s.** Se cuentan cinco operaciones aritméticas útiles por precio: escalado X, diferencia, shift, actualización de E y desviación D. Las instrucciones que emulan una de ellas no agregan operaciones útiles. Ops/s = 5 dividido por el tiempo medio medido; las esperas, comparaciones y control sí consumen tiempo en ese denominador.

**Amdahl.** En la variante 1 la región reemplazada suma el shift software y las ocho sumas de X: 72,3 ciclos, f = 0,616. Se reemplaza por slli+srai, cuatro ciclos. El speedup predicho es 2,393 y el medido 2,393. En EMA8 se sustituyen el shift y la resta/suma de la media: 60,3 ciclos, f = 0,514, por una EMA8 de dos ciclos. El predicho es 1,988 y el medido 1,988. La mejora procede de reducir IC; diferencias pequeñas se explican por el polling y la fase de llegada del precio.

## 3.3 Roofline

Espino ejecuta como máximo una instrucción cada dos ciclos. El techo aritmético ideal es 12,5 Mops/s a 25 MHz; una EMA8 agrupa tres operaciones y eleva su techo ideal a 37,5 Mops/s. Es una cota, no la tasa sostenible del programa mixto. La envolvente del bus de datos/MMIO es 50 MB/s (sw de cuatro bytes cada dos ciclos); las cargas lw de tres ciclos tienen una cota menor, 33,33 MB/s.

La medición cuenta los bytes reales del mismo intervalo que los ciclos: 12 bytes por precio en cada variante. Se excluyen fetch de instrucciones y accesos internos al banco de registros. La intensidad es 5 / 12 = 0,417 ops/byte. El quiebre ideal está en 0,25 ops/byte para 0/1 y 0,75 para EMA8; la cota del modelo es 12,5 Mops/s en 0/1 y 20,83 en 2. El alcance del modelo es este bus, no una memoria externa, y la mezcla de cargas y escrituras no sostiene necesariamente toda la envolvente.

[[FIGURA_1]]

Figura 1: Roofline de Espino a 25 MHz con el kernel de las tres variantes

El rendimiento medido es 1,07, 2,55 y 2,12 Mops/s. Las tres quedan lejos de sus cotas por las instrucciones de control, la espera del precio y, en software, el bucle del shift. No se deduce un cuello de botella real únicamente por quedar a un lado del quiebre. Shifter y EMA8 acercan el kernel a su cota al eliminar instrucciones que no agregan operaciones útiles.

## 3.4 Variante final

Se elige la **variante 1, shifter fijo de ocho bits**, por tener el menor tiempo de procesamiento y por caber y cerrar timing. Utiliza 977 LUT4, 1.154 de 1.280 celdas lógicas (90 %) y ocho BRAM, con fmax de 40,53 MHz. A 25 MHz tarda 49,03 ciclos de media y 56 en el peor caso: 2,24 µs, el 2,48 % del presupuesto de la ronda 3. Es 2,39 veces más rápida que la nueva versión software. EMA8 usa nueve celdas menos y cierra a una frecuencia algo mayor, pero necesita más ciclos a la frecuencia fija de la placa.

Las tres variantes toman las mismas decisiones, por lo que acelerar no mejora el patrimonio cuando todas cumplen el deadline. La ganancia sobre Meta mejora por el cambio de estrategia; la aceleración aporta margen de tiempo. Los resultados no prueban que se ganará en las empresas y fechas ocultas y se conservan también los tramos perdedores en research/ y docs/results/.

El reset de encendido de la CPU dura 255 ciclos (10,2 µs) para dar margen a la inicialización de BRAM; el SPI sale de reset a los 16 ciclos. Entre rondas se debe reiniciar o reprogramar la placa para reiniciar el agente, además del reinicio de caja de la maestra. No hay una orden SPI de reinicio. La FPGA todavía no se ha programado y la competencia y conexión física con la maestra siguen pendientes.

**Reproducción.** README documenta ensamblado, Python, testbenches, síntesis y programación. Se usa Python 3.12 e Icarus 14 devel. En este Windows el compilador registra DONE y genera el archivo, pero cierra con 0xC0000005; la opción explícita --allow-compiler-exit-crash acepta solo ese archivo nuevo y exige después vvp correcto, aserciones aprobadas y coincidencia de todas las filas. No se ignoran otros fallos. Las trazas, logs, hashes e informe se dejan junto al código para revisión y commit; no se ha publicado ningún arreglo en GitHub.
