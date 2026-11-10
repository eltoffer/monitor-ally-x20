# Monitor ROG Xbox Ally X20

Base preparada para RC74XA-TW009W y código postal 52168. No está activada ni se ha validado todavía contra las cinco tiendas. No confirma envío al código postal: este se incluye en el aviso para comprobarlo al comprar.

## Activación

1. En Telegram abre https://t.me/BotFather (cuenta oficial), envía `/newbot` y sigue sus instrucciones. Guarda el token en privado.
2. Abre tu nuevo bot y envíale `/start`.
3. Obtén tu chat ID consultando `getUpdates` de la API oficial de Telegram desde tu equipo. No compartas el token ni capturas de él. Documentación: https://core.telegram.org/bots/api#getupdates . El identificador está en `result[].message.chat.id`.
4. Crea en GitHub un repositorio dedicado y sube todos los archivos de esta carpeta, incluida `.github/workflows/monitor.yml`. La programación está configurada cada 15 minutos aproximadamente.
5. En Settings → Secrets and variables → Actions crea `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID` con sus valores.
6. En Actions ejecuta “Monitor Ally X20” con Run workflow. Revisa el informe descargable y los avisos de Telegram. Esta primera ejecución es necesaria para validar las tiendas; si una devuelve “unknown”, necesita ajustes antes de considerarla cubierta.

Los ejecutores estándar de GitHub Actions son gratuitos en repositorios públicos. En privados hay una cuota: no activar gastos y revisar el consumo; con navegador, 96 ejecuciones diarias pueden superar la cuota gratuita. En públicos, GitHub puede desactivar las programaciones después de 60 días sin actividad; revisar y reactivar si ocurre. La programación puede retrasarse.

## Qué detecta

Se examinan fichas de Liverpool y Amazon y se buscan enlaces al producto en ASUS, Coppel y Palacio de Hierro. Las URLs de búsqueda de Coppel y Palacio son candidatas pendientes de validación. Amazon también requiere confirmar que su ficha coincide. No se eluden CAPTCHA ni bloqueos.

Solo datos estructurados de un Product coincidente con una oferta InStock, LimitedAvailability o PreOrder producen un aviso de posible disponibilidad. No se usa el botón “comprar” como única evidencia. Agotado requiere evidencia explícita; lo demás se marca desconocido. La búsqueda no garantiza descubrir todos los productos nuevos. El precio no incluye necesariamente envío. El vendedor y la cobertura postal se confirman manualmente.

Los avisos se envían al cambiar el estado, incluida la primera detección de un problema. El estado se guarda en una rama dedicada `monitor-state`; no uses esa rama para otros archivos, se reemplaza en cada ejecución. Los errores de ejecución se consultan en Actions. Un estado unknown persistente no repite avisos. Si falla todo el flujo, Telegram no necesariamente recibe aviso.

## Estado de entrega

Verificación de sintaxis y pruebas del clasificador realizadas localmente. Pendiente: credenciales, primera ejecución real, adaptar sitios que no expongan datos estructurados y comprobar entrega de Telegram. El monitor aún no está operativo.
