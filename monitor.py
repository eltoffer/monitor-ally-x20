"""Conservative monitor: only matching Product/Offer structured data confirms stock."""
import asyncio
import sys
import json
import os
import re
import urllib.request
from pathlib import Path
from playwright.async_api import async_playwright

ROOT = Path(__file__).parent
MATCH = re.compile(r'RC74XA[\s-]*TW009W|(?:ROG\s+)?(?:XBOX\s+)?ALLY\s+X20\b', re.I)

def target(text):
    return bool(MATCH.search(text)) and not re.search(r'\bbundle\b|TW001W|\bfunda\b|\bprotector\b', text, re.I)

def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)

def classify(documents):
    for document in documents:
        for item in walk(document):
            types = item.get('@type', [])
            if isinstance(types, str):
                types = [types]
            if 'Product' not in types:
                continue
            identity = ' '.join(str(item.get(k, '')) for k in ('name', 'sku', 'model', 'mpn'))
            if not target(identity):
                continue
            offers = list(walk(item.get('offers', [])))
            available = [o for o in offers if str(o.get('availability', '')).rsplit('/', 1)[-1] in ('InStock', 'LimitedAvailability', 'PreOrder')]
            if available:
                return 'available', str(available[0].get('price', 'precio no publicado'))
            if any(str(o.get('availability', '')).rsplit('/', 1)[-1] in ('OutOfStock', 'SoldOut', 'Discontinued') for o in offers):
                return 'out_of_stock', ''
    return 'unknown', ''

async def inspect(page, url):
    response = await page.goto(url, wait_until='domcontentloaded', timeout=45000)
    await page.wait_for_timeout(3500)
    if not response or response.status >= 400:
        return {'status': 'unknown', 'reason': f'HTTP {response.status if response else "sin respuesta"}'}
    body = await page.locator('body').inner_text()
    if re.search(r'captcha|verify you are human|access denied|robot check', body, re.I):
        return {'status': 'unknown', 'reason': 'Bloqueo o CAPTCHA'}
    # Amazon's buy box exposes stock without Product JSON-LD. Scope to the
    # main title and buy box; recommendations elsewhere can have other stock.
    if 'amazon.com.mx' in url:
        title = page.locator('#productTitle')
        if await title.count() and target(await title.inner_text()):
            box = page.locator('#outOfStock')
            if await box.count() and await box.first.is_visible():
                stock_text = await box.first.inner_text()
                if re.search(r'agotado|no disponible', stock_text, re.I):
                    return {'status': 'out_of_stock', 'price': '', 'reason': 'Amazon: ficha coincidente y caja de compra agotada'}
            stock = page.locator('#availability')
            buy = page.locator('#add-to-cart-button')
            if await stock.count() and await buy.count() and await buy.first.is_visible() and await buy.first.is_enabled():
                stock_text = await stock.first.inner_text()
                if re.search(r'en stock|disponible|disponibles', stock_text, re.I) and not re.search(r'no disponible|agotado', stock_text, re.I):
                    price = page.locator('#corePrice_feature_div .a-offscreen')
                    return {'status': 'available', 'price': await price.first.inner_text() if await price.count() else 'sin dato', 'reason': 'Amazon: disponibilidad y botón de compra activos'}
    documents = []
    for raw in await page.locator('script[type="application/ld+json"]').all_text_contents():
        try:
            documents.append(json.loads(raw))
        except ValueError:
            pass
    status, price = classify(documents)
    return {'status': status, 'price': price, 'reason': 'Datos del producto' if status != 'unknown' else 'Sin evidencia suficiente de inventario'}

def notify(message):
    if '--dry-run' in sys.argv:
        print('AVISO SIMULADO: ' + message)
        return
    token, chat = os.getenv('TELEGRAM_BOT_TOKEN'), os.getenv('TELEGRAM_CHAT_ID')
    if not token or not chat:
        raise RuntimeError('Faltan los secretos de Telegram')
    request = urllib.request.Request(
        f'https://api.telegram.org/bot{token}/sendMessage',
        data=json.dumps({'chat_id': chat, 'text': message, 'disable_web_page_preview': True}).encode(),
        headers={'Content-Type': 'application/json'})
    # Never expose request URLs or exceptions containing the token in logs.
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if not json.load(response).get('ok'):
                raise RuntimeError('Telegram rechazó el aviso')
    except Exception:
        raise RuntimeError('No se pudo entregar el aviso por Telegram') from None

async def main():
    if os.getenv('TELEGRAM_TEST') == '1':
        notify('✅ Conexión de Telegram comprobada. Iniciando prueba de las cinco tiendas; la cobertura de inventario se informará por separado.')
    config = json.loads((ROOT / 'config.json').read_text())
    state_path = ROOT / 'state.json'
    previous = json.loads(state_path.read_text()) if state_path.exists() else {}
    current, report = dict(previous), []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(locale='es-MX')
        page = await context.new_page()
        for store in config['stores']:
            results = []
            try:
                result = await inspect(page, store['url'])
                results.append({**result, 'url': store['url']})
                if store['kind'] == 'search':
                    links = await page.locator('a[href]').evaluate_all('(links) => links.map(a => ({text:a.innerText, url:a.href}))')
                    from urllib.parse import urlparse
                    host = urlparse(store['url']).hostname
                    urls = list(dict.fromkeys(x['url'] for x in links if target(x['text']) and urlparse(x['url']).hostname == host and x['url'] != store['url']))[:5]
                    for url in urls:
                        results.append({**await inspect(page, url), 'url': url})
            except Exception as exc:
                results.append({'status': 'unknown', 'reason': type(exc).__name__, 'url': store['url']})
            best = next((r for r in results if r['status'] == 'available'), None)
            best = best or next((r for r in results if r['status'] == 'out_of_stock'), results[0])
            name, status = store['name'], best['status']
            # Discovery pages cannot establish that no listing exists.
            if store['kind'] == 'search' and status == 'out_of_stock':
                status = 'unknown'
                best = {**best, 'status': status, 'reason': 'No se confirmó stock en una ficha individual'}
            if previous.get(name) != status:
                if status == 'available':
                    notify(f'🎮 Posible disponibilidad: ROG Xbox Ally X20\n{name}\nPrecio: {best.get("price", "sin dato")}\n{best["url"]}\nConfirma vendedor y envío al CP {config["postal_code"]} antes de comprar. El monitor no confirma cobertura postal.')
                elif status == 'unknown':
                    notify(f'⚠️ No se pudo comprobar inventario en {name}.\n{best.get("reason", "Sin evidencia suficiente")}\n{store["url"]}')
            current[name] = status
            report.append({'store': name, **best})
        await browser.close()
    state_path.write_text(json.dumps(current, indent=2))
    (ROOT / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if os.getenv('TELEGRAM_TEST') == '1':
        labels = {'available': 'posible disponibilidad', 'out_of_stock': 'agotado', 'unknown': 'no se pudo comprobar'}
        notify('Resultado de la prueba del monitor:\n' + '\n'.join(r['store'] + ': ' + labels[r['status']] for r in report) + '\nLas consultas desconocidas aún no proporcionan cobertura de inventario.')

if __name__ == '__main__':
    asyncio.run(main())
