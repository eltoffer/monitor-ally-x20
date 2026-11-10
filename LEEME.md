# Monitor ROG Xbox Ally X20

Base preparada para RC74XA-TW009W y código postal 52168. Configurada en el repositorio eltoffer/monitor-ally-x20; conexión de Telegram comprobada. Validación local: Amazon agotado y Coppel disponible por $26,999; Liverpool, ASUS y Palacio devuelven HTTP 403. La cobertura de esas tres tiendas sigue pendiente. No confirma envío al código postal: este se incluye en el aviso para comprobarlo al comprar.

## Activación

1. En Telegram abre https://t.me/BotFather (cuenta oficial), envía `/newbot` y sigue sus instrucciones. Guarda el token en privado.
2. Abre tu nuevo bot y envíale `/start`.
3. Obtén tu chat ID consultando `getUpdates` de la API oficial de Telegram desde tu equipo. No compartas el token ni capturas de él. Documentación: https://core.telegram.org/bots/api#getupdates . El identificador está en `result[].message.chat.id`.
4. Crea en GitHub un repositorio dedicado y sube todos los archivos de esta carpeta, incluida `.github/workflows/monitor.yml`. La programación está configurada cada 15 minutos aproximadamente.
5. En Settings → Secrets and variables → Actions crea `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID` con sus valores.
6. En Actions ejecuta “Monitor Ally X20” con Run workflow. Revisa el informe descargable y los avisos de Telegram. Esta primera ejecución es necesaria para validar las tiendas; si una devuelve “unknown”, necesita ajustes antes de considerarla cubierta.

Los ejecutores estándar de GitHub Actions son gratuitos en repositorios públicos. En privados hay una cuota: no activar gastos y revisar el consumo; con navegador, 96 ejecuciones diarias pueden superar la cuota gratuita. En públicos, GitHub puede desactivar las programaciones después de 60 días sin actividad; revisar y reactivar si ocurre. La programación puede retrasarse.

## Qué detecta

Se examinan fichas individuales verificadas de las cinco tiendas. Amazon tiene además una lectura específica de su caja de compra y su título principal. No se eluden CAPTCHA ni bloqueos.

Los datos estructurados de un Product coincidente con una oferta InStock, LimitedAvailability o PreOrder producen un aviso de posible disponibilidad. Amazon también permite detectar stock por la caja de compra, con título coincidente y evidencia de disponibilidad. No se usa el botón “comprar” como única evidencia. Agotado requiere evidencia explícita; lo demás se marca desconocido. La búsqueda no garantiza descubrir todos los productos nuevos. El precio no incluye necesariamente envío. El vendedor y la cobertura postal se confirman manualmente.

Los avisos se envían al cambiar el estado, incluida la primera detección de un problema. El estado se guarda en una rama dedicada `monitor-state`; no uses esa rama para otros archivos, se reemplaza en cada ejecución. Los errores de ejecución se consultan en Actions. Un estado unknown persistente no repite avisos. Si falla todo el flujo, Telegram no necesariamente recibe aviso.

## Estado de entrega

Sintaxis y seis pruebas verificadas, incluida la ficha real de Amazon para evitar confusión con recomendaciones. Primera ejecución real y entrega de Telegram comprobadas. Pendiente: completar cobertura de Liverpool, ASUS y Palacio, bloqueadas con HTTP 403. La prueba manual envía un resumen; las ejecuciones periódicas avisan de cambios.
