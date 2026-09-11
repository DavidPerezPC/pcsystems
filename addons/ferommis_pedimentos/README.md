# FEROMMIS · Pedimentos por PEPS

Repone el automatismo que Odoo 16 traía de fábrica en `l10n_mx_edi_landing` y que Odoo 19
sustituyó por un mecanismo basado en lotes.

## Por qué existe

En Odoo 16, al publicar la factura el sistema seguía la cadena PEPS del movimiento de
inventario hasta la recepción de compra y copiaba el número de pedimento del costo en
destino de esa recepción. No pedía nada al producto.

Odoo 19 eliminó ese código. El pedimento ahora viaja por **lotes**: al validar el costo en
destino se marcan los lotes recibidos, y de ahí el número llega a la factura. Para que un
producto entre a ese circuito tiene que cumplir las cuatro condiciones a la vez —
`tracking = 'lot'`, `lot_valuated = True`, `invoice_policy = 'delivery'` y la casilla
`l10n_mx_edi_use_customs_invoicing`. En FEROMMIS eso implicaría activar lotes en toda la
operación de almacén, cambiar la valuación de 138 productos importados y modificar el
proceso comercial.

Este módulo llega al mismo resultado sin ninguno de esos cambios.

## Cómo funciona

**Al validar la entrega** (`stock.move._action_done`) se lee la pila PEPS del producto con
`product._run_fifo_get_stack()`, el mismo helper que usa la valuación de Odoo, y se reparte
la cantidad entregada entre las recepciones que la surten. Cada tramo queda guardado como un
renglón de `ferommis.customs.origin`.

La lectura tiene que ocurrir **antes** de que el movimiento se marque como hecho, porque la
pila se arma a partir de la existencia actual. Es el mismo motivo por el que `stock_account`
calcula ahí el valor de las salidas.

**Al publicar la factura** (`account.move._post`) se recorren las líneas que aún no traen
pedimento, se buscan las capas PEPS de sus entregas y se resuelve el costo en destino de cada
recepción. Los números encontrados se escriben separados por coma, el más representativo
primero. `l10n_mx_edi_extended` los convierte en un nodo `InformacionAduanera` por pedimento
dentro del concepto del CFDI.

El pedimento **no** se congela al validar la entrega: se resuelve al facturar, porque es
frecuente que el costo en destino se capture días después de que la mercancía ya salió.

## Decisiones que conviene conocer

- **La recepción se liga al pedimento por línea de ajuste de valuación, no por albarán.**
  Un costo en destino puede amparar un albarán con productos que no entraron en su reparto;
  atribuirles el pedimento sería incorrecto ante una auditoría. Odoo 16 lo hacía por albarán.
- **No se pisa un pedimento capturado a mano.** Solo se escriben las líneas vacías.
- **Una línea de factura puede llevar varios pedimentos**, igual que en Odoo 16, cuando la
  mercancía entregada salió de más de una recepción.
- **El reparto se agrega por línea de venta, no por cantidad facturada.** Si una línea de
  venta se entrega en dos remisiones de pedimentos distintos y se factura en dos facturas,
  ambas líneas llevan los dos pedimentos. Es el comportamiento que traía Odoo 16.
- **Solo aplica a compañías mexicanas** (`company_id.country_code == 'MX'`) y a entregas de
  venta con producto almacenable.

## Limitación conocida

FEROMMIS factura por pedido, así que una factura puede publicarse antes de que la entrega
esté validada. En ese caso no hay capa PEPS que consultar y la línea sale sin pedimento
(en los datos de 2026 pasa en cerca del 3 % de las líneas).

Para esos casos está la acción **Asignar pedimento (PEPS)** en el menú Acciones de la
factura, que recalcula las líneas vacías. Solo cambia el CFDI si la factura todavía no se ha
timbrado.

## Qué NO hace

No corrige hacia atrás las facturas ya emitidas. La pila PEPS histórica ya no se puede
consultar, porque la existencia se movió; reconstruirla exige reproducir toda la historia
cronológicamente. Esa reconstrucción se entregó aparte, en el informe de pedimentos.

## Verificación

Probado sobre una copia de `19ferommis260910`:

| Caso | Resultado |
|---|---|
| Venta que consume una sola capa | pedimento correcto en la línea |
| Entrega que cruza dos pedimentos | ambos números, en orden de cantidad |
| Entrega parcial con backorder | solo se registra lo entregado |
| Producto sin pedimento en su historia | línea sin pedimento |
| Pedimento capturado a mano | se respeta, no se sobrescribe |
| Recepción de compra | no genera capas, sin cambios |
| Entrega de 15 líneas | 0.26 s en validar, 1.30 s en facturar y publicar |

## Instalación

Depende de `stock_account` y `l10n_mx_edi_landing`, ambos ya instalados en FEROMMIS.

```
odoo-bin -d <base> -i ferommis_pedimentos --stop-after-init
```
