"""
fix_pg_durable_acentos.py — Corrige acentuacao do post pg-durable no MongoDB via SSH tunnel.
"""
import sys, re, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from publicar_post import (
    _ACENTO_FIXES, _acento_repl, corrigir_acentos, _corrigir_campos_post,
    VPS_HOST, VPS_PORT, VPS_USER, SSH_KEY,
    MONGO_USER, MONGO_PASS, MONGO_DB, MONGO_COL
)

import paramiko, threading, socket, time
import pymongo
from urllib.parse import quote

SLUG = "pg-durable-microsoft-postgresql-execucao-duravel"

def _abrir_tunnel():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(VPS_HOST, port=VPS_PORT, username=VPS_USER, key_filename=SSH_KEY, timeout=30)
    transport = ssh.get_transport()
    local_port = 27021

    def _forward(local_sock):
        try:
            chan = transport.open_channel("direct-tcpip", ("127.0.0.1", 27017), ("127.0.0.1", local_port))
            while True:
                r, _, _ = __import__("select").select([local_sock, chan], [], [], 1)
                if local_sock in r:
                    data = local_sock.recv(1024)
                    if not data: break
                    chan.send(data)
                if chan in r:
                    data = chan.recv(1024)
                    if not data: break
                    local_sock.send(data)
        except: pass
        finally: local_sock.close()

    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", local_port))
    server.listen(1)
    server.settimeout(5)

    def _accept_loop():
        try:
            while True:
                try:
                    conn, _ = server.accept()
                    t = threading.Thread(target=_forward, args=(conn,), daemon=True)
                    t.start()
                except socket.timeout:
                    if not transport.is_active(): break
        except: pass

    threading.Thread(target=_accept_loop, daemon=True).start()
    time.sleep(0.5)
    return ssh, server, local_port

def main():
    print(f"Conectando ao MongoDB via SSH tunnel...")
    ssh, server, local_port = _abrir_tunnel()

    uri = f"mongodb://{MONGO_USER}:{quote(MONGO_PASS)}@127.0.0.1:{local_port}/admin?authSource=admin&authMechanism=SCRAM-SHA-1"
    client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=15000)
    db = client[MONGO_DB]
    col = db[MONGO_COL]

    doc = col.find_one({"slug": SLUG})
    if not doc:
        print(f"ERRO: post '{SLUG}' nao encontrado!")
        sys.exit(1)

    print(f"Post encontrado: _id={doc['_id']}")

    # Criar copia para aplicar correcoes
    campos = {
        "title": doc.get("title", ""),
        "summary": doc.get("summary", ""),
        "metaTitle": doc.get("metaTitle", ""),
        "metaDescription": doc.get("metaDescription", ""),
        "content": doc.get("content", ""),
        "faqs": doc.get("faqs", []),
        "blocks": doc.get("blocks", []),
    }

    total = _corrigir_campos_post(campos)
    print(f"Correcoes de acentuacao: {total}")

    if total == 0:
        print("Nenhuma correcao necessaria — post ja esta correto.")
        client.close(); server.close(); ssh.close()
        return

    # Update no MongoDB
    result = col.update_one(
        {"slug": SLUG},
        {"$set": {
            "title": campos["title"],
            "summary": campos["summary"],
            "metaTitle": campos["metaTitle"],
            "metaDescription": campos["metaDescription"],
            "content": campos["content"],
            "faqs": campos["faqs"],
            "blocks": campos["blocks"],
        }}
    )
    print(f"MongoDB updated: matched={result.matched_count}, modified={result.modified_count}")
    print(f"Titulo corrigido: {campos['title']}")

    client.close(); server.close(); ssh.close()
    print("Pronto!")

if __name__ == "__main__":
    main()
