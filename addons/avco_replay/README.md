# AVCO Replay - Recálculo histórico de costo promedio

Módulo para Odoo 19 (compatible con v18/v17 con ajustes menores) que permite
reconstruir el costo promedio (AVCO) de productos replayando su historia de
`stock.move` desde una fecha de corte configurable.

## Características

- **Replay cronológico** desde fecha de corte.
- **Costo manual por producto** para ajustes sin costo propio.
- **Soporte completo de landed costs** (costos en destino): suma los ajustes
  de `stock.valuation.adjustment.lines` al costo unitario de entrada.
- **Modo simulación (dry-run)** con log detallado antes de aplicar.
- **Reescritura opcional** del campo `value` de cada `stock.move`.
- **Detección automática** del campo de valor según el build de v19.

## Instalación

1. Copia la carpeta `avco_replay` en el directorio de addons.
2. Reinicia el servicio Odoo con `--dev=all` o actualiza la lista de módulos.
3. Instala el módulo desde **Apps**.

## Uso

### Paso 1: Identifica productos afectados

Ve a **Inventario → Productos**, filtra los productos con AVCO descuadrado.

### Paso 2: Abre el wizard

Selecciona los productos, menú **Acción → Replay AVCO**.

### Paso 3: Configura parámetros

- **Fecha de corte**: fecha desde la cual reconstruir (ej. inicio de año fiscal).
- **Considerar landed costs**: déjalo activado salvo que no uses el módulo.
- **Aplicar cambios**: DESMARCADO en la primera corrida (solo simula).
- **Reescribir valor en stock.move**: solo si necesitas corregir también el
  valor histórico de cada movimiento (irreversible).

### Paso 4: Ajusta el costo manual por producto

En la tabla, cada línea tiene su **"Costo para ajustes manuales"**. Este
valor se usa ÚNICAMENTE cuando el `stock.move` es un ajuste sin fuente válida
(sin PO, sin factura, sin valor previo). Para entradas normales se usa:

1. Factura de proveedor + landed costs
2. Línea de PO + landed costs
3. Valor actual del move
4. Costo manual + landed costs (si aplica)
5. AVCO actual + landed costs (último recurso)

### Paso 5: Ejecuta simulación

Botón **Ejecutar**. Revisa el tab **Log de resultado** para ver la evolución
del AVCO movimiento por movimiento.

### Paso 6: Valida contra un producto sano

Corre el wizard sobre un producto que SÍ tiene el AVCO correcto. El AVCO
calculado debe coincidir con `standard_price` actual. Si coincide, tu lógica
de replay es correcta.

### Paso 7: Aplica cambios

Marca **Aplicar cambios** y **Reescribir valor en stock.move**, ejecuta
nuevamente sobre los productos descuadrados.

### Paso 8: Reconcilia contabilidad

Ve a **Contabilidad → Revisar → Valoración de inventario → Generar asiento**
para que la contabilidad refleje el nuevo valor de inventario.

## Notas técnicas

### Campo de valor en stock.move

En Odoo 19 el campo puede llamarse `value`, `stock_valuation` o similar. El
módulo detecta automáticamente. Si falla, edita `_get_value_field` en
`models/avco_replay.py` y agrega el nombre correcto.

### Landed costs

El módulo lee `stock.valuation.adjustment.lines` con `cost_id.state = 'done'`
y suma el `additional_landed_cost` prorrateado por unidad al costo de
entrada. Esto replica el comportamiento nativo de v19.

### Multi-compañía

El wizard usa `company_id` explícito. Corre una vez por compañía si aplica.

### Multi-variante

Si seleccionas desde `product.template`, el wizard expande a todas las
variantes (`product.product`) automáticamente.

## Advertencias

- **HAZ RESPALDO** antes de ejecutar con `apply_changes=True`.
- La reescritura de `stock.move.value` es IRREVERSIBLE.
- Este módulo NO genera asientos contables; hazlo desde
  **Contabilidad → Revisar** después del replay.
- Solo funciona para productos con método de costeo AVCO.

## Compatibilidad

- **Odoo 19**: nativo (este es el target principal).
- **Odoo 18/17**: debería funcionar cambiando `stock_move.value` por
  `stock.valuation.layer` en `_get_value_field` y ajustando el replay para
  leer de SVL en lugar de stock.move.

## Licencia

LGPL-3
