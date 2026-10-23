import os
import shutil
import tempfile
import unittest
from export_pages import export_static_site

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(ROOT, 'fixtures', 'minimal', 'project.json')

class TestExportPages(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_export_minimal(self):
        export_static_site(FIXTURE, self.tmp, copy_assets=False)
        self.assertTrue(os.path.exists(os.path.join(self.tmp, 'index.html')))
        self.assertTrue(os.path.exists(os.path.join(self.tmp, 'market.json')))
        self.assertTrue(os.path.exists(os.path.join(self.tmp, 'assets')))

        with open(os.path.join(self.tmp, 'index.html'), 'r', encoding='utf-8') as f:
            html = f.read()
        self.assertIn('__LARCH_GAME_SITE__', html)
        self.assertIn('window.localStorage', html)

if __name__ == '__main__':
    unittest.main()
