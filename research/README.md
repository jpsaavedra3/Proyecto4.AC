# Investigación reproducible

Estos archivos documentan la comparación exploratoria; el FPGA no lee ninguno.
Todos los modelos simulan comisión de $5 y la ejecución al precio siguiente.

```bash
python3 research/research_p4.py
python3 research/research_p4_v2.py
python3 research/research_ensemble_p4.py
python3 research/select_p4.py
```

Los dos primeros scripts seleccionan candidatos con los primeros 12.000 precios y
comparan familias en 12.000–15.999. `select_p4.py` registra la configuración elegida,
comprueba vecinos y evalúa 16.000–19.999 con los parámetros fijados. Los archivos
JSON conservan las corridas, incluidas pérdidas. La búsqueda de expertos es una
alternativa descartada; puntúa posiciones virtuales con el retraso correcto de un
tick. Sus resultados no justificaron agregar ese costo al programa de la FPGA.

La configuración final se mantuvo al observar el bloque final. Este procedimiento
reduce un tipo de ajuste, pero no convierte una única serie ya conocida en una
muestra externa independiente. El resultado acumulado de $13.291 no implica que
todos los tramos sean ganadores ni predice el resultado de empresas/períodos ocultos.
