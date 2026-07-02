#!/usr/bin/env python3
"""
traduzir_posts.py — Traduz title e summary de posts para EN e ES via Ollama.

Uso (rodar no VPS com nohup):
  nohup env PYTHONUNBUFFERED=1 python3 traduzir_posts.py > /tmp/traduz.log 2>&1 &

Flags:
  --lang en|es     Só este idioma
  --limit N        Para após N posts (testes)
  --with-content   Também traduz content (muito mais lento)
  --with-meta      Também traduz metaTitle, metaDescription, tags
"""

import sys, json, re, time, argparse
import urllib.request
from pymongo import MongoClient

MONGO_URI = (
    "mongodb://curitibasoftware:Curitiba%402025%2B%2B%2B"
    "@127.0.0.1:27017/admin?authSource=admin"
)
DB_NAME   = "curitibasoftware"
COLL_NAME = "blogposts"
OLLAMA    = "http://127.0.0.1:11434/api/generate"
MODEL     = "qwen2.5:7b"
LANGS     = {"en": "English", "es": "Spanish"}


def ollama(prompt: str, timeout: int = 90) -> str:
    payload = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 1024}
    }).encode()
    req = urllib.request.Request(
        OLLAMA, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return (json.loads(r.read()).get("response") or "").strip()
    except Exception as e:
        print(f"  [OLLAMA ERR] {e}", flush=True)
        return ""


def tx(text: str, lang_name: str, max_tokens: int = 512) -> str:
    if not text or not text.strip():
        return ""
    payload = json.dumps({
        "model": MODEL,
        "prompt": (
            f"Translate to {lang_name}. Return ONLY the translation, no extra text.\n\n"
            f"{text}"
        ),
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": max_tokens}
    }).encode()
    req = urllib.request.Request(
        OLLAMA, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return (json.loads(r.read()).get("response") or "").strip()
    except Exception as e:
        print(f"  [TX ERR] {e}", flush=True)
        return ""


def tx_html(html: str, lang_name: str) -> str:
    """Translate HTML preserving tags, in chunks."""
    if not html or not html.strip():
        return ""
    MAX = 2000
    if len(html) <= MAX:
        return _tx_html_chunk(html, lang_name)
    parts = re.split(r'(?=<h[2-6][\s>])', html)
    return "\n".join(_tx_html_chunk(p, lang_name) for p in parts if p.strip())


def _tx_html_chunk(html: str, lang_name: str) -> str:
    payload = json.dumps({
        "model": MODEL,
        "prompt": (
            f"Translate HTML from Brazilian Portuguese to {lang_name}. "
            f"Preserve ALL HTML tags. Return ONLY translated HTML.\n\n{html}"
        ),
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 4096}
    }).encode()
    req = urllib.request.Request(
        OLLAMA, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return (json.loads(r.read()).get("response") or "").strip()
    except Exception as e:
        print(f"  [HTML ERR] {e}", flush=True)
        return html  # fallback: original


def needs(post: dict, lang: str, with_content: bool, with_meta: bool) -> bool:
    tr = (post.get("translations") or {}).get(lang) or {}
    if not tr.get("title") or not tr.get("summary"):
        return True
    if with_meta and (not tr.get("metaTitle") or not tr.get("metaDescription")):
        return True
    if with_content and not tr.get("content"):
        return True
    return False


def process(post: dict, langs: list, with_content: bool, with_meta: bool, coll):
    slug = post.get("slug", "")

    # Always read fresh to avoid overwrite race between langs
    fresh = coll.find_one({"_id": post["_id"]}, {"translations": 1}) or {}
    all_tr = dict(fresh.get("translations") or {})

    for lang in langs:
        lang_name = LANGS[lang]
        tr = dict(all_tr.get(lang) or {})

        # --- title + summary (core, always) ---
        if not tr.get("title"):
            r = tx(post.get("title", ""), lang_name, 128)
            if r:
                tr["title"] = r
                print(f"  [{lang.upper()}] {r[:70]}", flush=True)

        if not tr.get("summary"):
            r = tx(post.get("summary", ""), lang_name, 512)
            if r:
                tr["summary"] = r

        # --- optional meta ---
        if with_meta:
            if not tr.get("metaTitle"):
                r = tx(post.get("metaTitle") or post.get("title", ""), lang_name, 128)
                if r: tr["metaTitle"] = r
            if not tr.get("metaDescription"):
                r = tx(post.get("metaDescription") or post.get("summary", ""), lang_name, 256)
                if r: tr["metaDescription"] = r
            if not tr.get("tags"):
                tags = post.get("tags") or []
                if tags:
                    r = tx(", ".join(tags), lang_name, 128)
                    if r: tr["tags"] = [t.strip() for t in r.split(",") if t.strip()]

        # --- optional content ---
        if with_content and not tr.get("content"):
            content = post.get("content", "")
            if content.strip():
                print(f"  [{lang.upper()}] content ({len(content)} chars)...", flush=True)
                r = tx_html(content, lang_name)
                if r: tr["content"] = r

        all_tr[lang] = tr

    coll.update_one({"_id": post["_id"]}, {"$set": {"translations": all_tr}})
    print(f"  saved.", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", choices=["en", "es"], default=None)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--with-content", action="store_true")
    parser.add_argument("--with-meta", action="store_true")
    args = parser.parse_args()

    target_langs = [args.lang] if args.lang else list(LANGS.keys())

    client = MongoClient(MONGO_URI)
    coll = client[DB_NAME][COLL_NAME]

    posts = list(coll.find({"isPublished": True}, {
        "_id": 1, "slug": 1, "title": 1, "summary": 1,
        "content": 1, "metaTitle": 1, "metaDescription": 1,
        "tags": 1, "faqs": 1, "translations": 1
    }).sort("publishedAt", -1))

    print(f"Found {len(posts)} published posts", flush=True)

    done = 0
    for i, post in enumerate(posts):
        if args.limit and done >= args.limit:
            break

        pending = [
            l for l in target_langs
            if needs(post, l, args.with_content, args.with_meta)
        ]
        if not pending:
            continue

        print(f"\n[{i+1}/{len(posts)}] {post.get('slug','')[:70]}", flush=True)
        process(post, pending, args.with_content, args.with_meta, coll)
        done += 1

    print(f"\nDone. {done} posts processed.", flush=True)
    client.close()


if __name__ == "__main__":
    main()
