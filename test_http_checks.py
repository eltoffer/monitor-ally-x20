import unittest
from unittest.mock import patch
from http_checks import Document, amazon_stock, asus_stock, check, matches, palacio_stock, schema_stock


class StockTests(unittest.TestCase):
    def test_wrong_edition_and_accessories_are_rejected(self):
        for name in ('Funda ROG Xbox Ally X20', 'ROG Xbox Ally X20 Bundle', 'ROG Xbox Ally X20 RC74XA-TW001W', 'ROG Xbox Ally X'):
            self.assertFalse(matches(name), name)
        self.assertTrue(matches('ROG Xbox Ally X20 RC74XA-TW009W'))

    def test_recommended_stock_does_not_override_main_amazon_product(self):
        html = '<span id="productTitle">ROG Xbox Ally X20</span><div id="outOfStock">Temporalmente agotado.</div><aside>Sólo queda 1 en stock</aside>'
        self.assertEqual(amazon_stock(Document(html))['status'], 'out_of_stock')

    def test_buy_button_alone_does_not_prove_stock(self):
        html = '<span id="productTitle">ROG Xbox Ally X20</span><input id="add-to-cart-button">'
        self.assertEqual(amazon_stock(Document(html))['status'], 'unknown')

    def test_explicit_schema_offer_confirms_asus_stock(self):
        html = '<script type="application/ld+json">{"@type":"Product","name":"ROG Xbox Ally X20","offers":{"availability":"https://schema.org/OutOfStock","price":26999}}</script>'
        self.assertEqual(schema_stock(Document(html))['status'], 'out_of_stock')

    def test_palacio_requires_consistent_stock_and_exact_product(self):
        p = {'id': '45809220', 'productName': 'ROG Xbox Ally X20', 'custom': {'model': 'RC74XA-TW009W'}, 'availability': {'seoSchema': 'http://schema.org/InStock'}, 'available': True, 'readyToOrder': True}
        self.assertEqual(palacio_stock({'product': p})['status'], 'available')
        p['available'] = False
        self.assertEqual(palacio_stock({'product': p})['status'], 'unknown')
        p['availability']['seoSchema'] = 'http://schema.org/OutOfStock'
        self.assertEqual(palacio_stock({'product': p})['status'], 'out_of_stock')
        p['id'] = 'other'
        self.assertEqual(palacio_stock({'product': p})['status'], 'unknown')

    def test_404_and_exact_search_absence_is_unlisted_not_sold_out(self):
        store = {'name': 'Liverpool', 'url': 'https://www.liverpool.com.mx/tienda/pdp/1210545022'}
        with patch('http_checks.fetch', side_effect=[(404, '', 'HTTP 404'), (200, '<h2>No encontramos nada para <span>RC74XA-TW009W</span></h2>', '')]):
            self.assertEqual(check(store)['status'], 'unlisted')

    def test_access_block_is_never_interpreted_as_sold_out(self):
        with patch('http_checks.fetch', return_value=(403, '', 'HTTP 403')):
            self.assertEqual(check({'name': 'ASUS', 'url': 'https://shop.asus.com/mx/rog/rog-xbox-ally-x20.html'})['status'], 'unknown')

    def test_asus_uses_exact_model_and_only_known_catalog_states(self):
        item = {'SalesModelName': 'RC74XA-TW009W', 'StockStatus': 'notify_me', 'SortPrice': '26999.000'}
        data = {'Status': '200', 'Result': {'ProductList': [item]}}
        self.assertEqual(asus_stock(data)['status'], 'out_of_stock')
        item['StockStatus'] = 'buy'
        self.assertEqual(asus_stock(data)['status'], 'available')
        item['SalesModelName'] = 'RC74XA-TW001W'
        self.assertEqual(asus_stock(data)['status'], 'unknown')
        item['SalesModelName'] = 'RC74XA-TW009W'
        item['StockStatus'] = 'unrecognized'
        self.assertEqual(asus_stock(data)['status'], 'unknown')

    def test_html_template_not_interpreted_as_real_amazon_buy_box(self):
        html = '<span id="productTitle">ROG Xbox Ally X20</span><script type="text/template"><div id="availability">En stock</div><input id="add-to-cart-button"></script>'
        self.assertEqual(amazon_stock(Document(html))['status'], 'unknown')


if __name__ == '__main__':
    unittest.main()
