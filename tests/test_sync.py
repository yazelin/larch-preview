import io, os, tempfile, threading, time, unittest, urllib.error
from unittest import mock
import sync

HTML = '<script type="module" crossorigin src="/assets/index-lg9nGv1N.js"></script><link rel="stylesheet" href="/assets/index-Ab_c.css">'
JS = 'const __vite__mapDeps=(i,m,d=(m.f||(m.f=["assets/pixi-engine-BjJSJWAc.js","assets/Preview-QqNq3ynq.css"])));import{r}from"./react-core-CuKebU_E.js";const x="./not-a-thing"'
CSS = '@font-face{src:url(/assets/noto-a.woff2) format("woff2")}.x{background:url(./bg-1.webp)}'

class Sync(unittest.TestCase):
    def test_refs(self):
        self.assertEqual(sync.extract_refs(HTML), ['index-Ab_c.css', 'index-lg9nGv1N.js'])
        self.assertEqual(sync.extract_refs(JS), ['Preview-QqNq3ynq.css', 'pixi-engine-BjJSJWAc.js', 'react-core-CuKebU_E.js'])
        self.assertEqual(sync.extract_refs(CSS), ['bg-1.webp', 'noto-a.woff2'])

    def test_root_refs(self):
        text = '<link rel="icon" href="/favicon.png?v=4">' + 'src:"/larch-mark.png",x=`url(/larch-coin.png)`,y="/assets/a.png",z="/api/x.png"'
        self.assertEqual(sync.extract_root_refs(text), ['favicon.png', 'larch-coin.png', 'larch-mark.png'])

    def test_plugin_static_refs(self):
        text = ('a="/plugins/rpg/ui/fusion-pixel/fusion-pixel-12px-proportional-zh_hant.otf.woff2",'
                'b=`/plugins/rpg/adventure-pack/cloud-kingdom.m4a`,c="/plugins/rpg/",d="/plugins/../etc/passwd.png"')
        self.assertEqual(sync.extract_root_refs(text), [
            'plugins/rpg/adventure-pack/cloud-kingdom.m4a',
            'plugins/rpg/ui/fusion-pixel/fusion-pixel-12px-proportional-zh_hant.otf.woff2'])

    def test_version(self):
        self.assertEqual(sync.version(HTML), 'index-lg9nGv1N.js')

class Crawl(unittest.TestCase):
    PAGES = {
        'https://larch.ink/assets/index-lg9nGv1N.js': b'import"./lazy-CkAB12_x.js";const s="./looks-like.js"',
        'https://larch.ink/assets/index-Ab_c.css': b'',
    }

    def fake_get(self, fail):
        def get(url):
            if url in fail:
                raise urllib.error.HTTPError(url, fail[url], 'x', {}, io.BytesIO())
            if url.endswith('.mp3') or url.endswith('.png') or url.endswith('.woff2'):
                return b'x'
            if url in self.PAGES:
                return self.PAGES[url]
            if url.endswith('lazy-CkAB12_x.js'):
                return b'1'
            raise urllib.error.HTTPError(url, 404, 'x', {}, io.BytesIO())
        return get

    def crawl(self, fail):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(sync, 'get', self.fake_get(fail)):
            sync.crawl(os.path.join(d, 'v'), HTML)
            return sorted(os.listdir(os.path.join(d, 'v', 'assets')))

    def test_nested_plugin_files_are_saved(self):
        page = 'https://larch.ink/assets/index-lg9nGv1N.js'
        self.PAGES = {**self.PAGES, page: self.PAGES[page] + b';f="/plugins/rpg/ui/px.otf.woff2"'}
        with tempfile.TemporaryDirectory() as d, mock.patch.object(sync, 'get', self.fake_get({})):
            sync.crawl(os.path.join(d, 'v'), HTML)
            self.assertTrue(os.path.exists(os.path.join(d, 'v', 'root', 'plugins', 'rpg', 'ui', 'px.otf.woff2')))

    def test_plain_404_on_filename_like_string_is_tolerated(self):
        self.assertIn('lazy-CkAB12_x.js', self.crawl({}))

    def test_rate_limit_is_fatal(self):
        with self.assertRaisesRegex(RuntimeError, 'lazy-CkAB12_x.js'):
            self.crawl({'https://larch.ink/assets/lazy-CkAB12_x.js': 429})

    def test_missing_hashed_chunk_is_fatal(self):
        with self.assertRaisesRegex(RuntimeError, 'lazy-CkAB12_x.js'):
            self.crawl({'https://larch.ink/assets/lazy-CkAB12_x.js': 404})

    def test_get_retries_server_errors(self):
        calls = []
        class R(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *a): pass
        def urlopen(req, timeout):
            calls.append(1)
            if len(calls) < 3:
                raise urllib.error.HTTPError(req.full_url, 503, 'x', {}, io.BytesIO())
            return R(b'ok')
        with mock.patch.object(sync.urllib.request, 'urlopen', urlopen), mock.patch.object(sync.time, 'sleep'):
            self.assertEqual(sync.get('https://larch.ink/x'), b'ok')
        self.assertEqual(len(calls), 3)


class CrawlRetries(unittest.TestCase):
    @staticmethod
    def page(hash_name):
        return f'<script type="module" src="/assets/index-{hash_name}.js"></script>'

    @staticmethod
    def missing(url):
        return urllib.error.HTTPError(url, 404, 'x', {}, io.BytesIO())

    def test_normal_crawl_succeeds_without_refreshing_homepage(self):
        html = self.page('aaaaaaaa')
        calls = []

        def fake_get(url):
            calls.append(url)
            return b''

        with tempfile.TemporaryDirectory() as d, mock.patch.object(sync, 'get', fake_get):
            result = sync.crawl_with_retries(os.path.join(d, 'vendor'), html)
            self.assertEqual(result, 'index-aaaaaaaa.js')
            self.assertTrue(os.path.exists(os.path.join(d, 'vendor', 'sfx', 'rain.mp3')))
        self.assertFalse(any('?sync=' in url for url in calls))

    def test_changed_homepage_version_restarts_with_new_html(self):
        html_a = self.page('aaaaaaaa')
        html_b = self.page('bbbbbbbb')
        calls = []
        failed_a = False

        def fake_get(url):
            nonlocal failed_a
            calls.append(url)
            if url == f'{sync.BASE}/assets/index-aaaaaaaa.js' and not failed_a:
                failed_a = True
                raise self.missing(url)
            if url.startswith(f'{sync.BASE}/?sync='):
                return html_b.encode()
            return b''

        with tempfile.TemporaryDirectory() as d, mock.patch.object(sync, 'get', fake_get):
            result = sync.crawl_with_retries(os.path.join(d, 'vendor'), html_a)
        self.assertEqual(result, 'index-bbbbbbbb.js')
        self.assertIn(f'{sync.BASE}/assets/index-bbbbbbbb.js', calls)
        self.assertTrue(any('?sync=' in url for url in calls))

    def test_unchanged_homepage_waits_then_retries(self):
        html = self.page('aaaaaaaa')
        calls = []
        failures = 0

        def fake_get(url):
            nonlocal failures
            calls.append(url)
            if url == f'{sync.BASE}/assets/index-aaaaaaaa.js' and failures == 0:
                failures += 1
                raise self.missing(url)
            if url.startswith(f'{sync.BASE}/?sync='):
                return html.encode()
            return b''

        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(sync, 'get', fake_get), \
                mock.patch.object(sync, 'RETRY_WAIT_SECONDS', 0), \
                mock.patch.object(sync.time, 'sleep') as sleep:
            result = sync.crawl_with_retries(os.path.join(d, 'vendor'), html)
        self.assertEqual(result, 'index-aaaaaaaa.js')
        sleep.assert_called_once_with(0)
        self.assertEqual(calls.count(f'{sync.BASE}/assets/index-aaaaaaaa.js'), 2)

    def test_four_failed_rounds_leave_existing_cache_untouched(self):
        html = self.page('aaaaaaaa')
        with tempfile.TemporaryDirectory() as d:
            vendor = os.path.join(d, 'larch')
            os.makedirs(vendor)
            with open(os.path.join(vendor, 'VERSION'), 'w') as f:
                f.write('index-bbbbbbbb.js\n')
            with open(os.path.join(vendor, 'sentinel.txt'), 'w') as f:
                f.write('既有快取')

            def fake_get(url):
                if url == f'{sync.BASE}/':
                    return html.encode()
                if url.startswith(f'{sync.BASE}/?sync='):
                    return html.encode()
                if url == f'{sync.BASE}/assets/index-aaaaaaaa.js':
                    raise self.missing(url)
                return b''

            with mock.patch.object(sync, 'VENDOR', vendor), \
                    mock.patch.object(sync, 'get', fake_get), \
                    mock.patch.object(sync, 'RETRY_WAIT_SECONDS', 0), \
                    mock.patch.object(sync.time, 'sleep'), \
                    mock.patch('sys.argv', ['sync.py']):
                with self.assertRaisesRegex(RuntimeError, 'index-aaaaaaaa.js'):
                    sync.main()

            with open(os.path.join(vendor, 'VERSION')) as f:
                self.assertEqual(f.read(), 'index-bbbbbbbb.js\n')
            with open(os.path.join(vendor, 'sentinel.txt')) as f:
                self.assertEqual(f.read(), '既有快取')
            self.assertFalse(os.path.exists(vendor + '.new'))

    def test_main_uses_last_successful_version_for_unchanged_check(self):
        html_a = self.page('aaaaaaaa')
        html_b = self.page('bbbbbbbb')
        with tempfile.TemporaryDirectory() as d:
            vendor = os.path.join(d, 'larch')
            os.makedirs(vendor)
            with open(os.path.join(vendor, 'VERSION'), 'w') as f:
                f.write('index-bbbbbbbb.js\n')
            with open(os.path.join(vendor, 'sentinel.txt'), 'w') as f:
                f.write('既有快取')
            failed_a = False

            def fake_get(url):
                nonlocal failed_a
                if url == f'{sync.BASE}/':
                    return html_a.encode()
                if url.startswith(f'{sync.BASE}/?sync='):
                    return html_b.encode()
                if url == f'{sync.BASE}/assets/index-aaaaaaaa.js' and not failed_a:
                    failed_a = True
                    raise self.missing(url)
                return b''

            with mock.patch.object(sync, 'VENDOR', vendor), \
                    mock.patch.object(sync, 'get', fake_get), \
                    mock.patch.object(sync, 'RETRY_WAIT_SECONDS', 0), \
                    mock.patch('sys.argv', ['sync.py']):
                sync.main()

            with open(os.path.join(vendor, 'VERSION')) as f:
                self.assertEqual(f.read(), 'index-bbbbbbbb.js\n')
            with open(os.path.join(vendor, 'sentinel.txt')) as f:
                self.assertEqual(f.read(), '既有快取')
            self.assertFalse(os.path.exists(vendor + '.new'))

    def test_main_writes_last_successful_round_version(self):
        html_a = self.page('aaaaaaaa')
        html_b = self.page('bbbbbbbb')
        with tempfile.TemporaryDirectory() as d:
            vendor = os.path.join(d, 'larch')
            os.makedirs(vendor)
            with open(os.path.join(vendor, 'VERSION'), 'w') as f:
                f.write('index-cccccccc.js\n')
            failed_a = False

            def fake_get(url):
                nonlocal failed_a
                if url == f'{sync.BASE}/':
                    return html_a.encode()
                if url.startswith(f'{sync.BASE}/?sync='):
                    return html_b.encode()
                if url == f'{sync.BASE}/assets/index-aaaaaaaa.js' and not failed_a:
                    failed_a = True
                    raise self.missing(url)
                return b''

            with mock.patch.object(sync, 'VENDOR', vendor), \
                    mock.patch.object(sync, 'get', fake_get), \
                    mock.patch('sys.argv', ['sync.py']):
                sync.main()

            with open(os.path.join(vendor, 'VERSION')) as f:
                self.assertEqual(f.read(), 'index-bbbbbbbb.js\n')
            self.assertTrue(os.path.exists(os.path.join(vendor, 'index.html')))
            self.assertFalse(os.path.exists(vendor + '.new'))

    def test_parallel_crawl_fetches_each_asset_only_once(self):
        html = ('<script src="/assets/index-aaaaaaaa.js"></script>'
                '<script src="/assets/shared-cccccccc.js"></script>'
                '<link href="/assets/style-dddddddd.css">')
        calls = []
        active = 0
        max_active = 0
        lock = threading.Lock()

        def fake_get(url):
            nonlocal active, max_active
            with lock:
                calls.append(url)
                active += 1
                max_active = max(max_active, active)
            try:
                time.sleep(0.01)
                if url.endswith('index-aaaaaaaa.js'):
                    return b'import "./shared-cccccccc.js"'
                if url.endswith('style-dddddddd.css'):
                    return b'url(/assets/shared-cccccccc.js)'
                return b''
            finally:
                with lock:
                    active -= 1

        with tempfile.TemporaryDirectory() as d, mock.patch.object(sync, 'get', fake_get):
            sync.crawl(os.path.join(d, 'vendor'), html)
        shared_url = f'{sync.BASE}/assets/shared-cccccccc.js'
        self.assertEqual(calls.count(shared_url), 1)
        self.assertGreater(max_active, 1)

if __name__ == '__main__':
    unittest.main()
