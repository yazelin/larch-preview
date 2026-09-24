import io, os, tempfile, unittest, urllib.error
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
            if url.endswith('.mp3') or url.endswith('.png'):
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

if __name__ == '__main__':
    unittest.main()
