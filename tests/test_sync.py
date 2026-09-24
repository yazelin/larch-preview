import unittest
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

if __name__ == '__main__':
    unittest.main()
