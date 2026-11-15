import io
import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import Mock, patch
import monitor


class DeliveryTests(unittest.TestCase):
    def env(self):
        return patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN': 'private-token', 'TELEGRAM_CHAT_ID': '123', 'TELEGRAM_TEST': '0'})

    def response(self):
        response = Mock()
        response.__enter__ = Mock(return_value=io.BytesIO(b'{"ok":true}'))
        response.__exit__ = Mock(return_value=False)
        return response

    def test_transient_connection_failure_retries(self):
        with self.env(), patch.object(monitor.urllib.request, 'urlopen', side_effect=[TimeoutError('private-token'), self.response()]) as send, patch.object(monitor.time, 'sleep') as sleep:
            monitor.notify('test')
        self.assertEqual(send.call_count, 2)
        sleep.assert_called_once_with(2)

    def test_rate_limit_honors_retry_after(self):
        error = urllib.error.HTTPError('https://api.telegram.org/botprivate-token/sendMessage', 429, 'limit', {}, io.BytesIO(b'{"parameters":{"retry_after":7}}'))
        with self.env(), patch.object(monitor.urllib.request, 'urlopen', side_effect=[error, self.response()]), patch.object(monitor.time, 'sleep') as sleep:
            monitor.notify('test')
        sleep.assert_called_once_with(7)

    def test_credentials_error_has_no_retry_and_no_token_leak(self):
        error = urllib.error.HTTPError('https://api.telegram.org/botprivate-token/sendMessage', 401, 'denied', {}, io.BytesIO(b'{}'))
        with self.env(), patch.object(monitor.urllib.request, 'urlopen', side_effect=error) as send, patch.object(monitor.time, 'sleep') as sleep:
            with self.assertRaises(RuntimeError) as caught:
                monitor.notify('test')
        self.assertEqual(send.call_count, 1)
        sleep.assert_not_called()
        self.assertNotIn('private-token', str(caught.exception))
        self.assertIn('401', str(caught.exception))

    def test_exhausted_retries_preserve_safe_diagnostic(self):
        with self.env(), patch.object(monitor.urllib.request, 'urlopen', side_effect=TimeoutError('private-token')) as send, patch.object(monitor.time, 'sleep'):
            with self.assertRaises(RuntimeError) as caught:
                monitor.notify('test')
        self.assertEqual(send.call_count, 3)
        self.assertNotIn('private-token', str(caught.exception))
        self.assertIn('TimeoutError', str(caught.exception))

    def test_report_and_pending_notice_survive_failure_then_recover(self):
        with tempfile.TemporaryDirectory() as folder, self.env(), patch.object(monitor, 'ROOT', Path(folder)), patch.object(monitor, 'check', return_value={'status': 'unknown', 'reason': 'HTTP 503'}), patch('builtins.print'):
            root = Path(folder)
            (root / 'config.json').write_text(json.dumps({'postal_code':'52168','stores':[{'name':'Example','url':'https://example.com'}]}))
            with patch.object(monitor, 'notify', side_effect=RuntimeError('Telegram HTTP 503')):
                with self.assertRaises(RuntimeError):
                    monitor.main()
            self.assertTrue((root / 'report.json').exists())
            self.assertEqual(json.loads((root / 'delivery.json').read_text())['pending'], 1)
            self.assertEqual(len(json.loads((root / 'state.json').read_text())['_pending_notifications']), 1)
            with patch.object(monitor, 'notify') as send:
                monitor.main()
            self.assertEqual(send.call_count, 1)
            self.assertEqual(json.loads((root / 'state.json').read_text())['_pending_notifications'], [])
            self.assertEqual(json.loads((root / 'delivery.json').read_text())['pending'], 0)
            with patch.object(monitor, 'notify') as send:
                monitor.main()
            send.assert_not_called()


if __name__ == '__main__':
    unittest.main()
