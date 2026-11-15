"""Monitor público de inventario: consultas HTTP ligeras y avisos persistentes."""
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from http_checks import check

ROOT = Path(__file__).parent
LABELS = {'available': 'posible disponibilidad', 'out_of_stock': 'agotado', 'unknown': 'no se pudo comprobar', 'unlisted': 'ficha retirada y modelo sin resultados'}


def notify(message):
    if '--dry-run' in sys.argv:
        print('AVISO SIMULADO: ' + message)
        return
    token = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
    chat = os.getenv('TELEGRAM_CHAT_ID', '').strip()
    if not token or not chat:
        raise RuntimeError('Faltan los secretos de Telegram')
    request = urllib.request.Request(
        f'https://api.telegram.org/bot{token}/sendMessage',
        data=json.dumps({'chat_id': chat, 'text': message, 'disable_web_page_preview': True}).encode(),
        headers={'Content-Type': 'application/json'})
    error = 'Error de conexión'
    for attempt in range(3):
        wait = 2 ** (attempt + 1)
        retryable = True
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            # Never include exception strings: their URL contains the bot token.
            error = 'Telegram HTTP ' + str(exc.code)
            retryable = exc.code == 429 or exc.code >= 500
            try:
                payload = json.loads(exc.read())
            except (ValueError, OSError):
                payload = {}
        except Exception as exc:
            payload = {}
            error = 'Conexión con Telegram: ' + type(exc).__name__
        else:
            if payload.get('ok'):
                return
            code = payload.get('error_code')
            error = 'Telegram rechazó el aviso (código ' + str(code) + ')'
            retryable = code == 429 or isinstance(code, int) and code >= 500
        delay = payload.get('parameters', {}).get('retry_after', wait)
        if not isinstance(delay, (int, float)) or delay < 0:
            delay = wait
        # Longer rate limits are retained in the queue for the next run.
        if not retryable or delay > 20 or attempt == 2:
            break
        time.sleep(delay)
    raise RuntimeError(error + '; aviso pendiente para la próxima ejecución') from None


def write_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    temporary.replace(path)


def main():
    config = json.loads((ROOT / 'config.json').read_text())
    state_path = ROOT / 'state.json'
    previous = json.loads(state_path.read_text()) if state_path.exists() else {}
    current = dict(previous)
    pending = list(previous.get('_pending_notifications', []))
    stores = config['stores']
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(check, stores))
    report = []
    now = datetime.now(timezone.utc).isoformat()

    def enqueue(message):
        key = hashlib.sha256(message.encode()).hexdigest()
        if not any(item['id'] == key for item in pending):
            pending.append({'id': key, 'message': message, 'observed_at': now})

    for store, result in zip(stores, results):
        name, status = store['name'], result['status']
        url = result.get('product_url', store['url'])
        if previous.get(name) != status:
            if status == 'available':
                enqueue(f'🎮 Posible disponibilidad: ROG Xbox Ally X20\n{name}\nPrecio: {result.get("price", "sin dato")} MXN\n{url}\nConfirma vendedor y envío al CP {config["postal_code"]} antes de comprar. El monitor no confirma cobertura postal.')
            elif status in ('unknown', 'unlisted'):
                enqueue(f'⚠️ {name}: {LABELS[status]}.\n{result["reason"]}\n{url}')
        current[name] = status
        report.append({'store': name, 'url': url, 'checked_at': now, **result})
    if os.getenv('TELEGRAM_TEST') == '1':
        enqueue('Resultado del monitor por consultas directas:\n' + '\n'.join(r['store'] + ': ' + LABELS[r['status']] for r in report) + '\nEl envío a 52168 se confirma al comprar. Una ficha retirada no prueba falta de stock en sucursales.')
    # Persist evidence and the outbox BEFORE attempting Telegram delivery.
    write_json(ROOT / 'report.json', report)
    current['_pending_notifications'] = pending
    write_json(state_path, current)
    errors = []
    for item in list(pending):
        try:
            notify(item['message'] + '\nObservado (UTC): ' + item['observed_at'])
        except RuntimeError as exc:
            errors.append(str(exc))
        else:
            pending.remove(item)
            current['_pending_notifications'] = pending
            write_json(state_path, current)
    write_json(ROOT / 'delivery.json', {'pending': len(pending), 'errors': errors, 'checked_at': now})
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if errors:
        raise RuntimeError('No se entregaron ' + str(len(errors)) + ' avisos. Se guardaron para reintentar. ' + '; '.join(errors))


if __name__ == '__main__':
    main()
