import os
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from lp import cloud


class TestCloud(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pj = os.path.join(self.tmp, 'project.json')
        with open(self.pj, 'w', encoding='utf-8') as f:
            json.dump({'id': 'test-pid', 'name': '本機專案'}, f)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_get_api_key(self):
        self.assertEqual(cloud.get_api_key('custom-123'), 'custom-123')
        with patch.dict(os.environ, {'LARCH_API_KEY': 'env-456'}):
            self.assertEqual(cloud.get_api_key(), 'env-456')

    def test_backup_file(self):
        bak = cloud.backup_file(self.pj)
        self.assertTrue(os.path.isfile(bak))
        self.assertIn('.bak.', bak)
        with open(bak, encoding='utf-8') as f:
            self.assertEqual(json.load(f)['name'], '本機專案')

    @patch('urllib.request.urlopen')
    def test_pull_project(self, mock_urlopen):
        remote_data = {'id': 'test-pid', 'name': '雲端拉取專案'}
        resp = MagicMock()
        resp.headers = {'ETag': '"rev-99"', 'X-Larch-Revision': '99'}
        resp.read.return_value = json.dumps(remote_data).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = resp

        res = cloud.pull(self.pj, 'test-pid', api_key='test-key')
        self.assertTrue(res['ok'])
        self.assertEqual(res['revision'], '99')
        self.assertTrue(os.path.isfile(res['backup']))

        with open(self.pj, encoding='utf-8') as f:
            loaded = json.load(f)
            self.assertEqual(loaded['name'], '雲端拉取專案')

    @patch('urllib.request.urlopen')
    def test_push_project(self, mock_urlopen):
        # 第一次 GET etag，第二次 PUT
        resp_get = MagicMock()
        resp_get.headers = {'ETag': '"rev-10"', 'X-Larch-Revision': '10'}
        resp_get.read.return_value = json.dumps({'id': 'test-pid'}).encode('utf-8')

        resp_put = MagicMock()
        resp_put.headers = {'ETag': '"rev-11"', 'X-Larch-Revision': '11'}
        resp_put.read.return_value = json.dumps({'id': 'test-pid', 'name': '本機專案'}).encode('utf-8')

        mock_urlopen.return_value.__enter__.side_effect = [resp_get, resp_put]

        res = cloud.push(self.pj, 'test-pid', api_key='test-key', summary='測試推送')
        self.assertTrue(res['ok'])
        self.assertEqual(res['revision'], '11')
        self.assertTrue(os.path.isfile(res['backup']))


if __name__ == '__main__':
    unittest.main()
