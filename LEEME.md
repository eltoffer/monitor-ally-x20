# Monitor ROG Xbox Ally X20

Producto: RC74XA-TW009W. CP de referencia: 52168. Repositorio: https://github.com/eltoffer/monitor-ally-x20 . Avisos de Telegram conectados mediante secretos de GitHub.

## Funcionamiento

Cada 15 minutos aproximadamente, GitHub ejecuta consultas HTTP públicas en paralelo, sin abrir un navegador ni instalar paquetes. Solo se utiliza Python 3.12. Los avisos se envían al cambiar el estado y no se repiten mientras siga igual. Las ejecuciones manuales o cambios de código también envían un resumen de diagnóstico.

- ASUS: consulta pública ShopFilterResult del catálogo oficial, enlazada en los datos de la web ASUS. Se selecciona SalesModelName RC74XA-TW009W exacto; notify_me indica falta de compra disponible y buy indica compra ofrecida.
- Coppel: oferta estructurada de la ficha que coincide con el producto.
- Amazon: título del producto y caja principal de compra. Se ignoran las recomendaciones.
- Palacio de Hierro: consulta pública Product-Variation enlazada por la propia ficha. Se comprueban ID, modelo, disponibilidad y posibilidad de ordenar.
- Liverpool: ficha exacta. Si devuelve 404, se consulta la búsqueda del modelo exacto para localizar una ficha nueva. Si la búsqueda responde que no existe, el estado es `unlisted`; esto no confirma que todas sus sucursales carezcan de inventario.

Estados: `available` (posible disponibilidad), `out_of_stock` (agotado explícito), `unlisted` (ficha no encontrada y búsqueda sin resultados), `unknown` (no se pudo comprobar). Un bloqueo nunca se considera agotado.

La entrega al CP 52168 y el vendedor se verifican al comprar. El precio publicado no garantiza el total con envío. Las existencias pueden cambiar entre revisiones. No se garantiza el acceso permanente ni que la búsqueda descubra todas las publicaciones nuevas.

## Operación

Los secretos `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID` se guardan en Settings → Secrets and variables → Actions. No deben aparecer en archivos ni en mensajes públicos. El estado anterior y el último informe se guardan en la rama dedicada `monitor-state`, que el programa reemplaza en cada ejecución; no guardar otros archivos en ella.

Consultar Actions → Monitor Ally X20 para ver las pruebas y el informe de cada ejecución. La programación de GitHub puede retrasarse y desactivarse tras 60 días de inactividad. El uso de ejecutores estándar en repositorios públicos es gratuito según los límites de GitHub. No se han contratado servicios ni activado gastos.

Para probar localmente sin enviar avisos: `python3 monitor.py --dry-run`. Para verificar el detector: `python3 -m unittest discover -p 'test_*.py'`. La prueba local actualiza `state.json`; ese archivo está excluido de Git.

## Evidencia y límites

Nueve pruebas automatizadas incluyen: accesorios y ediciones distintas, recomendaciones de Amazon con stock, botón de compra sin evidencia de disponibilidad, señales contradictorias de Palacio, bloqueos y fichas retiradas de Liverpool. Las pruebas reales locales del nuevo método verificaron las cinco consultas en unos segundos: Coppel disponible, Amazon/ASUS/Palacio agotados y Liverpool sin ficha ni resultados del modelo. Consultar el último informe en GitHub para el estado más reciente.

Documentación: https://docs.python.org/3.12/library/urllib.request.html , https://schema.org/availability , https://core.telegram.org/bots/api , https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows .
