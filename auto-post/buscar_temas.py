"""
buscar_temas.py — Busca tendencias tech do dia (HN + Dev.to)
Saida: JSON com lista de topics para o agente selecionar e escrever o post.
Uso: python buscar_temas.py
"""
import json, re, sys
import requests


def fetch_hn_top() -> list[dict]:
    try:
        ids = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10).json()[:30]
        stories = []
        for sid in ids:
            try:
                item = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=5).json()
                if item.get("score", 0) >= 50 and item.get("title"):
                    stories.append({
                        "fonte": "HN",
                        "titulo": item["title"],
                        "url": item.get("url", ""),
                        "score": item.get("score", 0),
                        "comentarios": item.get("descendants", 0),
                    })
            except:
                pass
            if len(stories) >= 15:
                break
        return stories
    except Exception as e:
        return [{"erro": str(e)}]


def fetch_devto_trending() -> list[dict]:
    try:
        resp = requests.get(
            "https://dev.to/api/articles?top=1&per_page=10",
            headers={"Accept": "application/json"},
            timeout=10,
        )
        return [
            {
                "fonte": "Dev.to",
                "titulo": a["title"],
                "tags": a.get("tag_list", []),
                "reacoes": a.get("public_reactions_count", 0),
            }
            for a in resp.json()
        ]
    except Exception as e:
        return [{"erro": str(e)}]


if __name__ == "__main__":
    hn = fetch_hn_top()
    devto = fetch_devto_trending()
    resultado = {"hn": hn, "devto": devto}
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
