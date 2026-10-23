#!/usr/bin/env python3
"""larch-preview 靜態網頁與 GitHub Pages 匯出工具。

將任何 Larch 專案檔（包含突破大小上限的大型專案）打包成純靜態網頁（無後端）：
1. 可直接部署至 GitHub Pages、Cloudflare Pages、Vercel 等靜態空間。
2. 可在另一個 Larch 專案中使用「插件卡」（Plugin Card）全螢幕內嵌遊玩。

用法：
  python3 export_pages.py <project.json 或專案目錄> [輸出目錄] [--copy-assets]
"""
import argparse
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
VENDOR = os.path.join(ROOT, 'vendor', 'larch')
from lp import rewrite

POLYFILL_SCRIPT = """    <script>
      (function() {
        // 沙盒 (Sandboxed iframe) 環境下 localStorage / sessionStorage Polyfill
        try { var _ = window.localStorage; } catch (e) {
          var mem = {};
          var mock = {
            getItem: function(k) { return Object.prototype.hasOwnProperty.call(mem, k) ? mem[k] : null; },
            setItem: function(k, v) { mem[k] = String(v); },
            removeItem: function(k) { delete mem[k]; },
            clear: function() { mem = {}; },
            get length() { return Object.keys(mem).length; },
            key: function(i) { return Object.keys(mem)[i] || null; }
          };
          try {
            Object.defineProperty(window, 'localStorage', { value: mock, writable: true, configurable: true });
            Object.defineProperty(window, 'sessionStorage', { value: mock, writable: true, configurable: true });
          } catch (ex) {}
        }

        // 相對路徑基底與遊戲站點設定
        window.__LARCH_BASE__ = './';
        window.__LARCH_GAME_SITE__ = {
          appPath: '/play/market/local',
          origin: window.location.origin,
          host: window.location.host,
          larch: 'https://larch.ink'
        };

        // 攔截 API 呼叫，直接以本地 market.json 回應
        var origFetch = window.fetch;
        window.fetch = async function(resource, init) {
          var url = typeof resource === 'string' ? resource : (resource && resource.url) || '';
          if (url.indexOf('/api/marketplace/') !== -1) {
            try {
              var r = await origFetch('./market.json');
              var data = await r.json();
              return new Response(JSON.stringify(data), {
                status: 200,
                headers: { 'Content-Type': 'application/json' }
              });
            } catch (err) {
              return new Response(JSON.stringify({ error: err.message }), { status: 500 });
            }
          }
          if (url.indexOf('/api/') !== -1) {
            return new Response(JSON.stringify({ offline: true }), {
              status: 404,
              headers: { 'Content-Type': 'application/json' }
            });
          }
          return origFetch.apply(this, arguments);
        };
      })();
    </script>"""

def patch_js_files(assets_dir):
    """修補 Vite 打包的根路徑絕對參考，使之在 GitHub Pages 次目錄下正常運作。"""
    for fname in os.listdir(assets_dir):
        fpath = os.path.join(assets_dir, fname)
        if not fname.endswith('.js') or not os.path.isfile(fpath):
            continue

        if fname.startswith('preload-helper-'):
            with open(fpath, 'r', encoding='utf-8') as f:
                code = f.read()
            if 'v=function(l){return"/"+l}' in code:
                code = code.replace(
                    'v=function(l){return"/"+l}',
                    'v=function(l){return(window.__LARCH_BASE__||"./")+l}'
                )
                with open(fpath, 'w', encoding='utf-8') as f:
                    f.write(code)

        elif fname.startswith('index-'):
            with open(fpath, 'r', encoding='utf-8') as f:
                code = f.read()
            # 繞過首頁根路徑比對，使 GitHub Pages 子路徑直接啟動遊戲
            code = re.sub(
                r'function Re\(e=(?:window\.)?location\.pathname\)\{return M&&e==="/"\?M\.appPath:e\}',
                'function Re(e=window.location.pathname){return M?M.appPath:e}',
                code
            )
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(code)

        elif fname.startswith('Preview-'):
            with open(fpath, 'r', encoding='utf-8') as f:
                code = f.read()
            # 防止選項或文字是物件時拋出 (e || "").replace is not a function
            target = 'da=n.useCallback(e=>(e||"").replace('
            repl = 'da=n.useCallback(e=>(typeof e==="string"?e:(e?.text||e?.label||String(e||""))).replace('
            if target in code:
                code = code.replace(target, repl)
                with open(fpath, 'w', encoding='utf-8') as f:
                    f.write(code)

def export_static_site(project_input, out_dir, copy_assets=False):
    project_input = os.path.abspath(project_input)
    if os.path.isdir(project_input):
        candidates = [
            os.path.join(project_input, 'project.json'),
            os.path.join(project_input, 'dist', 'project.json')
        ]
        pj_file = next((c for c in candidates if os.path.isfile(c)), None)
        if not pj_file:
            print(f"錯誤：在 {project_input} 中找不到 project.json", file=sys.stderr)
            sys.exit(1)
        base_dir = os.path.dirname(pj_file)
    else:
        pj_file = project_input
        base_dir = os.path.dirname(pj_file)

    os.makedirs(out_dir, exist_ok=True)
    out_assets = os.path.join(out_dir, 'assets')
    os.makedirs(out_assets, exist_ok=True)

    print(f"📦 讀取專案：{pj_file}")
    with open(pj_file, 'r', encoding='utf-8') as f:
        raw_pj = json.load(f)

    project = rewrite.fill_defaults(rewrite.unwrap(raw_pj))
    market_data = rewrite.wrap_market(project)

    # 將 market_data 中的資產路徑轉為相對路徑 ./assets/
    market_str = json.dumps(market_data, ensure_ascii=False)
    market_str = market_str.replace('/files/assets/', './assets/')
    market_str = market_str.replace('/files/', './assets/')

    market_json_path = os.path.join(out_dir, 'market.json')
    with open(market_json_path, 'w', encoding='utf-8') as f:
        f.write(market_str)
    print(f"✅ 生成 market.json ({os.path.getsize(market_json_path) / (1024*1024):.1f} MB)")

    # 複製 vendor 核心播放器檔案
    vendor_assets = os.path.join(VENDOR, 'assets')
    for item in os.listdir(VENDOR):
        s = os.path.join(VENDOR, item)
        d = os.path.join(out_dir, item)
        if item == 'assets':
            for a in os.listdir(vendor_assets):
                sa = os.path.join(vendor_assets, a)
                da = os.path.join(out_assets, a)
                if not os.path.exists(da):
                    shutil.copy2(sa, da)
        elif item == 'index.html':
            continue
        elif os.path.isdir(s) and not os.path.exists(d):
            shutil.copytree(s, d)
        elif not os.path.exists(d):
            shutil.copy2(s, d)

    # 處理 index.html：保留完整 vendor HTML，僅在 <head> 後注入沙盒 Polyfill 並轉換為相對路徑
    vendor_index_path = os.path.join(VENDOR, 'index.html')
    with open(vendor_index_path, 'r', encoding='utf-8') as f:
        vendor_index = f.read()

    # 將絕對路徑 /assets/ 轉成相對路徑 ./assets/
    vendor_index = vendor_index.replace('href="/assets/', 'href="./assets/')
    vendor_index = vendor_index.replace('src="/assets/', 'src="./assets/')
    vendor_index = vendor_index.replace('href="/favicon', 'href="./favicon')
    vendor_index = vendor_index.replace('href="/larch-', 'href="./larch-')
    vendor_index = vendor_index.replace('href="/manifest', 'href="./manifest')

    # 注入 Polyfill
    head_tag = '<head>'
    if head_tag in vendor_index:
        final_index = vendor_index.replace(head_tag, f"{head_tag}\n{POLYFILL_SCRIPT}\n", 1)
    else:
        final_index = f"{POLYFILL_SCRIPT}\n{vendor_index}"

    with open(os.path.join(out_dir, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(final_index)
    print("✅ 生成並修補 index.html")

    # 修補 assets 裡的 JS bundle
    patch_js_files(out_assets)
    print("✅ 修補 JS 模組預載入與路由 (支援 GitHub Pages 任意子目錄)")

    # 處理專案資產檔案 (assets)
    project_assets_dirs = [
        os.path.join(base_dir, 'assets'),
        os.path.join(base_dir, 'dist', 'assets')
    ]
    src_assets = next((d for d in project_assets_dirs if os.path.isdir(d)), None)

    if src_assets:
        count = 0
        for root, dirs, files in os.walk(src_assets):
            for file in files:
                rel = os.path.relpath(os.path.join(root, file), src_assets)
                dest = os.path.join(out_assets, rel)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                if not os.path.exists(dest):
                    if copy_assets:
                        shutil.copy2(os.path.join(root, file), dest)
                    else:
                        # 預設建立相對軟連結以省本機空間
                        os.symlink(os.path.join(root, file), dest)
                    count += 1
        mode_str = "實體複製" if copy_assets else "軟連結 (如需 git push 請加 --copy-assets)"
        print(f"✅ 匯入專案素材共 {count} 個檔案 ({mode_str})")

    print("\n🎉 打包完成！輸出目錄：", out_dir)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='打包 Larch 專案為純靜態 GitHub Pages 站點')
    parser.add_argument('project', help='project.json 路徑或專案目錄')
    parser.add_argument('output', nargs='?', default=None, help='輸出目錄 (預設為專案目錄下的 web_player)')
    parser.add_argument('--copy-assets', action='store_true', help='實體複製素材檔案 (若要 git push 請啟用)')
    args = parser.parse_args()

    out = args.output
    if not out:
        if os.path.isdir(args.project):
            out = os.path.join(args.project, 'web_player')
        else:
            out = os.path.join(os.path.dirname(os.path.abspath(args.project)), 'web_player')

    export_static_site(args.project, out, copy_assets=args.copy_assets)
