"""Read public stock responses without starting a browser or using account cookies."""
import json
import re
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

HEADERS = {'User-Agent': 'AllyStockMonitor/1.0', 'Accept': 'text/html,application/json', 'Accept-Language': 'es-MX,es;q=0.9'}
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}
MATCH = re.compile(r'RC74XA[\s-]*TW009W|(?:ROG\s+)?(?:XBOX\s+)?ALLY\s+X20\b', re.I)


def matches(text):
    return bool(MATCH.search(text)) and not re.search(r'\bbundle\b|\bpaquete\b|\bfunda\b|\bprotector\b|RC74XA[\s-]*TW(?!009W)[A-Z0-9]+', text, re.I)


class Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def text(self):
        return ' '.join(c.text() if isinstance(c, Node) else c for c in self.children if not isinstance(c, Node) or c.tag not in ('script', 'style', 'template'))

    def descendants(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.descendants()


class Document(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.feed(html)
        self.nodes = list(self.root.descendants())
        self.by_id = {n.attrs['id']: n for n in self.nodes if 'id' in n.attrs}

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag, attrs))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)

    def schemas(self):
        documents = []
        for node in self.nodes:
            if node.tag == 'script' and node.attrs.get('type') == 'application/ld+json':
                try:
                    documents.append(json.loads(''.join(c for c in node.children if isinstance(c, str))))
                except (ValueError, TypeError):
                    pass
        return documents


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def result(status='unknown', reason='', price='', **extra):
    return {'status': status, 'reason': reason, 'price': str(price), **extra}


def schema_stock(doc):
    candidates = []
    for document in doc.schemas():
        for item in walk(document):
            types = item.get('@type', [])
            types = [types] if isinstance(types, str) else types
            if 'Product' not in types or not matches(' '.join(str(item.get(k, '')) for k in ('name', 'sku', 'mpn', 'model'))):
                continue
            for offer in walk(item.get('offers', [])):
                stock = str(offer.get('availability', '')).rsplit('/', 1)[-1]
                if stock in ('InStock', 'LimitedAvailability', 'PreOrder'):
                    candidates.append(result('available', 'Oferta estructurada del producto exacto: ' + stock, offer.get('price', 'sin dato')))
                elif stock in ('OutOfStock', 'SoldOut', 'Discontinued'):
                    candidates.append(result('out_of_stock', 'Oferta estructurada del producto exacto: ' + stock, offer.get('price', '')))
    if candidates:
        return next((c for c in candidates if c['status'] == 'available'), candidates[0])
    return result(reason='Sin evidencia suficiente en los datos del producto')


def amazon_stock(doc):
    title = doc.by_id.get('productTitle')
    if not title or not matches(title.text()):
        return result(reason='No se confirmó el título del producto de Amazon')
    box = doc.by_id.get('outOfStock')
    stock = doc.by_id.get('availability')
    # Ignore recommendations, page templates and unrelated mentions of stock.
    if box and re.search(r'temporalmente agotado|no disponible|actualmente no disponible', box.text(), re.I):
        return result('out_of_stock', 'Amazon: caja de compra del producto agotada')
    buy = doc.by_id.get('add-to-cart-button')
    if stock and buy and 'disabled' not in buy.attrs:
        text = stock.text()
        if re.search(r'no disponible|agotado', text, re.I):
            return result('out_of_stock', 'Amazon: disponibilidad negativa del producto')
        if re.search(r'en stock|disponible|disponibles', text, re.I):
            return result('available', 'Amazon: disponibilidad positiva y compra habilitada', 'consultar ficha')
    return result(reason='Amazon: no se confirmó una oferta comprable')


def palacio_stock(data):
    product = data.get('product', {})
    identity = str(product.get('productName', '')) + ' ' + str(product.get('custom', {}).get('model', ''))
    if str(product.get('id')) != '45809220' or not matches(identity):
        return result(reason='Palacio: respuesta de otro producto o modelo')
    availability = product.get('availability', {})
    schema = str(availability.get('seoSchema', '')).rsplit('/', 1)[-1]
    price = product.get('price', {}).get('sales', {}).get('value', '')
    if schema in ('OutOfStock', 'SoldOut') and product.get('available') is False:
        return result('out_of_stock', 'Palacio: API del producto confirma OutOfStock y available=false', price)
    if schema in ('InStock', 'LimitedAvailability', 'PreOrder') and product.get('available') is True and product.get('readyToOrder') is True:
        return result('available', 'Palacio: API confirma inventario y producto listo para comprar', price)
    return result(reason='Palacio: señales insuficientes o contradictorias')


def fetch(url):
    request = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            content = response.read(5_000_001)
            if len(content) > 5_000_000:
                return None, '', 'Respuesta demasiado grande'
            text = content.decode(response.headers.get_content_charset() or 'utf-8', errors='replace')
            return response.status, text, ''
    except urllib.error.HTTPError as exc:
        return exc.code, '', 'HTTP ' + str(exc.code)
    except Exception as exc:
        return None, '', type(exc).__name__


def check(store):
    started = time.monotonic()
    endpoint = store.get('inventory_url', store['url'])
    code, text, error = fetch(endpoint)
    answer = None
    if code == 200:
        if store['name'] == 'Palacio de Hierro' and store.get('inventory_url'):
            try:
                answer = palacio_stock(json.loads(text))
            except (ValueError, TypeError, AttributeError):
                answer = result(reason='Palacio: respuesta de inventario inválida')
        else:
            doc = Document(text)
            title = next((n.text() for n in doc.nodes if n.tag == 'title'), '')
            if re.search(r'just a moment|un momento|access denied|robot check', title, re.I):
                answer = result(reason='El sitio pide verificación de acceso')
            else:
                answer = amazon_stock(doc) if store['name'] == 'Amazon' else schema_stock(doc)
    if store['name'] == 'Liverpool' and code == 404:
        # A deleted ficha is NOT proof that all store inventory is sold out.
        search_code, search_text, search_error = fetch('https://www.liverpool.com.mx/tienda?s=RC74XA-TW009W')
        if search_code == 200:
            doc = Document(search_text)
            visible = doc.root.text()
            links = [urljoin(store['url'], n.attrs['href']) for n in doc.nodes if n.tag == 'a' and 'href' in n.attrs and '/tienda/pdp/' in n.attrs['href'] and matches(n.text())]
            for link in list(dict.fromkeys(links))[:2]:
                if urlparse(link).hostname != 'www.liverpool.com.mx':
                    continue
                linked_code, linked_text, _ = fetch(link)
                if linked_code == 200:
                    candidate = schema_stock(Document(linked_text))
                    if candidate['status'] != 'unknown':
                        answer = {**candidate, 'product_url': link}
                        break
            if answer is None and re.search(r'no encontramos nada para', visible, re.I) and 'rc74xa-tw009w' in visible.lower():
                answer = result('unlisted', 'Liverpool: ficha HTTP 404 y búsqueda del modelo sin resultados; inventario no confirmado')
        if answer is None:
            answer = result(reason='Liverpool: ficha no encontrada; búsqueda sin evidencia concluyente (' + str(search_code) + ')')
    answer = answer or result(reason=error or 'Sin evidencia de inventario')
    return {**answer, 'method': 'http', 'http_status': code, 'seconds': round(time.monotonic() - started, 2)}
