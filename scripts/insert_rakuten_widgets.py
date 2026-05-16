"""
楽天アフィリエイト商品ウィジェット 自動挿入スクリプト
------------------------------------------------------
使い方:
  cd /Users/moritamika/Desktop/Claude/pet-nutrition-care-blog
  python3 scripts/insert_rakuten_widgets.py
"""

import os
import json
import time
import urllib.request
import urllib.parse
import re
from pathlib import Path

# ─── 設定 ────────────────────────────────────────────
BLOG_DIR = Path(__file__).parent.parent / "src/content/blog"
ENV_FILE = Path(__file__).parent.parent / ".env"

# 記事ごとの検索キーワード
ARTICLE_KEYWORDS = {
    "dog-food-ingredients-guide.md":  "ドッグフード 無添加 国産",
    "dog-allergy-food.md":            "犬 アレルギー対応 ドッグフード",
    "puppy-food-guide.md":            "子犬 ドッグフード パピー",
    "dog-senior-food-guide.md":       "シニア犬 ドッグフード 老犬",
    "dog-weight-loss-food.md":        "犬 ダイエット ドッグフード 低カロリー",
    "dog-supplement-guide.md":        "犬 サプリメント 関節 グルコサミン",
    "cat-food-ingredients-guide.md":  "キャットフード 無添加 国産",
    "cat-urinary-tract-diet.md":      "猫 泌尿器 キャットフード",
    "cat-wet-vs-dry.md":              "猫 ウェットフード",
    "senior-cat-kidney-diet.md":      "猫 腎臓 療法食",
    "cat-weight-management.md":       "猫 ダイエット キャットフード",
    "kitten-food-guide.md":           "子猫 キャットフード キトン",
    "grain-free-pet-food-truth.md":   "グレインフリー ドッグフード",
}

# ─── .env 読み込み ─────────────────────────────────
def load_env():
    env = {}
    if not ENV_FILE.exists():
        raise FileNotFoundError(f".envファイルが見つかりません: {ENV_FILE}")
    with open(ENV_FILE) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env

# ─── 楽天API検索（新エンドポイント）─────────────────
def search_rakuten(keyword, app_id, access_key):
    params = urllib.parse.urlencode({
        "applicationId": app_id,
        "keyword": keyword,
        "hits": 5,
        "sort": "-reviewCount",
        "imageFlag": 1,
        "formatVersion": 2,
    })
    url = f"https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260401?{params}"
    req = urllib.request.Request(url, headers={
        "accessKey": access_key,
        "Origin": "https://petnutritioncare.com",
    })
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=10) as res:
                return json.loads(res.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 2:
                wait = (attempt + 1) * 15
                print(f"  ⏳ レート制限。{wait}秒待機してリトライ（{attempt+1}/3）...")
                time.sleep(wait)
                req = urllib.request.Request(url, headers={
                    "accessKey": access_key,
                    "Origin": "https://petnutritioncare.com",
                })
            else:
                print(f"  ⚠️  API エラー: {e}")
                return None
        except Exception as e:
            print(f"  ⚠️  API エラー: {e}")
            return None
    return None

# ─── ウィジェットHTML生成 ─────────────────────────
def make_widget(item, affiliate_id):
    name     = item.get("itemName", "")
    name_short = name[:60] + ("..." if len(name) > 60 else "")
    price    = f"{item.get('itemPrice', 0):,}"
    item_url = item.get("itemUrl", "")
    images   = item.get("mediumImageUrls", [])
    img_url  = images[0] if images else ""

    aff_url = (
        f"https://hb.afl.rakuten.co.jp/ichiba/{affiliate_id}/?"
        f"pc={urllib.parse.quote(item_url, safe='')}"
        f"&link_type=picttext"
    )

    return f"""
<div class="rakuten-widget">
  <a href="{aff_url}" target="_blank" rel="nofollow sponsored noopener">
    <img src="{img_url}" alt="{name_short}">
  </a>
  <div class="rakuten-widget-info">
    <a href="{aff_url}" target="_blank" rel="nofollow sponsored noopener">{name_short}</a>
    <p class="rakuten-widget-price">価格：{price}円（税込）</p>
    <a href="{aff_url}" target="_blank" rel="nofollow sponsored noopener" class="rakuten-buy-btn">楽天で購入</a>
  </div>
</div>
<p class="cta-note">※ 楽天市場へのリンクです（アフィリエイト）</p>
"""

# ─── 記事更新 ────────────────────────────────────
OLD_CTA = re.compile(r'\n<div class="cta-wrap">.*?</div>\s*\n<p class="cta-note">.*?</p>', re.DOTALL)
OLD_WIDGET = re.compile(r'\n<div class="rakuten-widget">.*?\n<p class="cta-note">.*?</p>', re.DOTALL)

def update_article(filepath, widget_html):
    content = filepath.read_text(encoding="utf-8")
    if OLD_WIDGET.search(content):
        new_content = OLD_WIDGET.sub(widget_html, content)
    elif OLD_CTA.search(content):
        new_content = OLD_CTA.sub(widget_html, content)
    else:
        new_content = content.rstrip() + "\n" + widget_html
    filepath.write_text(new_content, encoding="utf-8")

# ─── メイン ──────────────────────────────────────
def main():
    env = load_env()
    app_id       = env.get("RAKUTEN_APP_ID", "")
    access_key   = env.get("RAKUTEN_ACCESS_KEY", "")
    affiliate_id = env.get("RAKUTEN_AFFILIATE_ID", "")

    if not all([app_id, access_key, affiliate_id]):
        print("❌ .envファイルの値が不足しています。確認してください。")
        return

    print(f"✅ 認証情報ロード完了")
    print(f"   APP_ID: {app_id[:8]}...")
    print(f"   AFFILIATE_ID: {affiliate_id}\n")

    success = 0
    for filename, keyword in ARTICLE_KEYWORDS.items():
        filepath = BLOG_DIR / filename
        if not filepath.exists():
            print(f"⚠️  スキップ（ファイルなし）: {filename}")
            continue

        print(f"📄 {filename}")
        print(f"   🔍 「{keyword}」で検索中...")

        result = search_rakuten(keyword, app_id, access_key)
        if not result or not result.get("Items"):
            print("   ❌ 商品が見つかりませんでした\n")
            continue

        item = result["Items"][0]
        print(f"   ✅ {item.get('itemName','')[:40]}...")
        print(f"      {item.get('itemPrice',0):,}円 / レビュー{item.get('reviewCount',0)}件")

        widget = make_widget(item, affiliate_id)
        update_article(filepath, widget)
        success += 1
        print()
        time.sleep(2)  # レート制限対策

    print(f"{'='*50}")
    print(f"🎉 完了！{success}/{len(ARTICLE_KEYWORDS)} 記事を更新しました")
    print(f"\n次のコマンドでデプロイ：")
    print(f"cd /Users/moritamika/Desktop/Claude/pet-nutrition-care-blog")
    print(f"git add -A && git commit -m 'Add Rakuten product widgets' && git push origin main")

if __name__ == "__main__":
    main()
