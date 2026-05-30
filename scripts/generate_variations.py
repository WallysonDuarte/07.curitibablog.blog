#!/usr/bin/env python3
"""
Gera variações de conteúdo por blog para todos os posts publicados.
Usa Ollama qwen2.5:7b direto + salva no MongoDB.
Pula overrides já existentes (resumível).
Paralelismo: 3 threads simultâneas.

Uso:
  python3 generate_variations.py [--only-field title|summary|content] [--only-site devlevelup] [--threads N]
"""
import sys
import json
import time
import argparse
import urllib.request
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

try:
    from pymongo import MongoClient
except ImportError:
    print("pymongo nao instalado. Execute: pip3 install pymongo")
    sys.exit(1)

MONGO_URI = "mongodb://curitibasoftware:Curitiba%402025%2B%2B%2B@127.0.0.1:27017/admin?retryWrites=true&loadBalanced=false&connectTimeoutMS=10000&authSource=admin&authMechanism=SCRAM-SHA-1"
DB_NAME = "curitibasoftware"
COLLECTION = "blogposts"
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODEL = "qwen2.5:7b"

SITES = {
    "devlevelup":    "DevLevelUp — blog para desenvolvedores intermediários/avançados, foco em código, arquitetura e boas práticas",
    "blogdudu":      "BlogDudu — blog tech descontraído e informal, linguagem leve e bem-humorada",
    "dozeroaojunior":"DoZeroAoJunior — blog para iniciantes em programação, linguagem simples e didática",
    "levelupdev":    "LevelUpDev — blog motivacional para devs que querem evoluir na carreira",
    "hidra":         "Hidra Blog — blog da plataforma Hidra, foco em tecnologia, SaaS e empreendedorismo digital",
}

FIELD_PROMPTS = {
    "title":   "Reescreva o título do artigo abaixo para o público do {blog_desc}. Retorne APENAS o título, sem aspas, sem explicações. Máximo 80 caracteres.",
    "summary": "Reescreva o resumo/subtítulo do artigo abaixo para o público do {blog_desc}. Retorne APENAS o resumo, sem aspas, sem explicações. Máximo 200 caracteres.",
    "content": "Reescreva o artigo abaixo para o público do {blog_desc}. Mantenha as informações principais, mas adapte o tom, linguagem e exemplos para o perfil do leitor. Retorne APENAS o conteúdo HTML reescrito, mantendo as tags HTML do original.",
}

print_lock = Lock()
counter_lock = Lock()
counters = {"done": 0, "errors": 0, "skipped": 0}


def log(msg):
    with print_lock:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def ollama_generate(system_prompt: str, user_prompt: str, retries: int = 3) -> str | None:
    payload = json.dumps({
        "model": MODEL,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    }).encode("utf-8")
    req = urllib.request.Request(OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"})
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                data = json.loads(resp.read())
                return data["message"]["content"].strip()
        except Exception as e:
            log(f"[ERRO Ollama tentativa {attempt}/{retries}] {e}")
            if attempt < retries:
                time.sleep(30)
    return None


def process_task(task, col, dry_run, total):
    post_id, slug, field, site_id, site_desc, base_text = task
    system_prompt = FIELD_PROMPTS[field].format(blog_desc=site_desc)
    limit = 4000 if field == "content" else 2000
    user_prompt = f"Artigo original:\n\n{base_text[:limit]}"

    with counter_lock:
        counters["done"] += 1
        n = counters["done"]

    log(f"[{n}/{total}] {slug[:35]:<35} | {site_id:<16} | {field:<8}", )

    if dry_run:
        with counter_lock:
            counters["skipped"] += 1
        return

    result = ollama_generate(system_prompt, user_prompt)
    if result:
        col.update_one({"_id": post_id}, {"$set": {f"siteOverrides.{site_id}.{field}": result}})
        log(f"  ✓ {slug[:30]} | {site_id} | {field} ({len(result)} chars)")
    else:
        with counter_lock:
            counters["errors"] += 1
        log(f"  ✗ {slug[:30]} | {site_id} | {field} ERRO")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only-field", choices=["title", "summary", "content"], default=None)
    parser.add_argument("--only-site", choices=list(SITES.keys()), default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--threads", type=int, default=3)
    args = parser.parse_args()

    fields = [args.only_field] if args.only_field else ["title", "summary", "content"]
    sites  = {args.only_site: SITES[args.only_site]} if args.only_site else SITES

    client = MongoClient(MONGO_URI)
    col = client[DB_NAME][COLLECTION]

    posts = list(col.find({"isPublished": True}, {
        "_id": 1, "title": 1, "summary": 1, "content": 1, "slug": 1, "siteOverrides": 1
    }))
    log(f"{len(posts)} posts publicados | sites: {list(sites.keys())} | fields: {fields} | threads: {args.threads}")

    # Montar fila apenas do que falta gerar
    tasks = []
    already_done = 0
    for post in posts:
        overrides = post.get("siteOverrides") or {}
        for site_id, site_desc in sites.items():
            site_ov = overrides.get(site_id) or {}
            for field in fields:
                if site_ov.get(field):
                    already_done += 1
                    continue
                base_text = post.get(field, "") or ""
                if not base_text.strip():
                    continue
                tasks.append((post["_id"], post.get("slug", str(post["_id"])), field, site_id, site_desc, base_text))

    total = len(tasks)
    log(f"{total} geracoes necessarias ({already_done} ja existem, puladas)\n")

    if total == 0:
        log("Nada a gerar. Tudo pronto!")
        client.close()
        return

    start = time.time()
    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        futures = [executor.submit(process_task, t, col, args.dry_run, total) for t in tasks]
        for f in as_completed(futures):
            f.result()  # propaga excecoes

    elapsed = time.time() - start
    client.close()
    log(f"\nConcluido em {elapsed/60:.1f} min | {total} geracoes | {counters['errors']} erros")


if __name__ == "__main__":
    main()
