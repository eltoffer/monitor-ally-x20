"""Monitor público de inventario: consultas HTTP ligeras y avisos de cambios."""
import json
import os
import sys
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
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            if not json.load(response).get('ok'):
                raise RuntimeError('Telegram rechazó el aviso')
    except Exception:
        raise RuntimeError('No se pudo entregar el aviso por Telegram') from None


def main():
    config = json.loads((ROOT / 'config.json').read_text())
    state_path = ROOT / 'state.json'
    previous = json.loads(state_path.read_text()) if state_path.exists() else {}
    current = dict(previous)
    stores = config['stores']
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(check, stores))
    report = []
    for store, result in zip(stores, results):
        name, status = store['name'], result['status']
        url = result.get('product_url', store['url'])
        if previous.get(name) != status:
            if status == 'available':
                notify(f'🎮 Posible disponibilidad: ROG Xbox Ally X20\n{name}\nPrecio: {result.get("price", "sin dato")} MXN\n{url}\nConfirma vendedor y envío al CP {config["postal_code"]} antes de comprar. El monitor no confirma cobertura postal.')
            elif status in ('unknown', 'unlisted'):
                notify(f'⚠️ {name}: {LABELS[status]}.\n{result["reason"]}\n{url}')
        current[name] = status
        report.append({'store': name, 'url': url, 'checked_at': datetime.now(timezone.utc).isoformat(), **result})
    # Save only after all notifications succeed, so failed deliveries retry.
    temporary = state_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(current, indent=2))
    temporary.replace(state_path)
    (ROOT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if os.getenv('TELEGRAM_TEST') == '1':
        notify('Resultado del monitor por consultas directas:\n' + '\n'.join(r['store'] + ': ' + LABELS[r['status']] for r in report) + '\nEl envío a 52168 se confirma al comprar. Una ficha retirada no prueba falta de stock en sucursales.')


if __name__ == '__main__':
    main()
