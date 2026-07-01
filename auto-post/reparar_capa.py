"""
reparar_capa.py — Gera capa, faz upload no IDrive E2 e atualiza coverImageKey/coverImageUrl
no MongoDB para um post já existente (sem re-publicar, sem redes sociais).

Uso:
    python reparar_capa.py <slug> <titulo> <subtitulo>
"""
import sys
import uuid
import datetime
from pathlib import Path

import boto3
from botocore.client import Config

THIS_DIR = Path(__file__).parent
LOGS_DIR = THIS_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

MONGO_USER   = "curitibasoftware"
MONGO_PASS   = "Curitiba@2025+++"
MONGO_DB     = "curitibasoftware"
MONGO_COL    = "blogposts"

IDRIVE_URL    = "https://s3.us-east-1.idrivee2.com"
IDRIVE_KEY    = "W5HR4oX6jKc53WENnNUe"
IDRIVE_SECRET = "vRDJCcHHBk7vYLbQ05iEvvnWVD4zw3afMXsOQX0X"
IDRIVE_BUCKET = "curitibasoftware-blog"
PUBLIC_BASE   = "https://api.curitibasoftware.com.br/api/blog/image"

VPS_HOST = "31.97.252.45"
VPS_PORT = 2222
VPS_USER = "ubuntu"
SSH_KEY  = str(Path.home() / ".ssh" / "id_server_nopass")


def log(msg):
    print(f"[reparar_capa] {msg}", flush=True)


def gerar_capa(slug, titulo, subtitulo):
    output_path = str(LOGS_DIR / f"{datetime.date.today()}-{slug}-cover.jpg")
    log(f"Gerando capa via Flow para: {titulo}")
    try:
        sys.path.insert(0, str(THIS_DIR))
        from gerar_capa_flow import gerar_capa_flow
        result = gerar_capa_flow(titulo, output_path, subtitulo)
        if result and Path(result).exists() and Path(result).stat().st_size > 10_000:
            log(f"Flow OK: {result}")
            return result
        else:
            log("Flow retornou vazio — tentando Pillow fallback")
    except Exception as e:
        log(f"Flow falhou: {e} — tentando Pillow fallback")

    # Fallback Pillow
    try:
        from gerar_capa import gerar_capa as gerar_capa_pillow
        result = gerar_capa_pillow(titulo, subtitulo,
                                   "Saiba mais", "Leia o artigo completo",
                                   "Tecnologia", "Ferramentas de IA",
                                   "CuritibaBlog", "blog.curitibablog.com.br",
                                   output_path)
        if result and Path(result).exists():
            log(f"Pillow OK: {result}")
            return result
    except Exception as e:
        log(f"Pillow falhou: {e}")

    return None


def upload_capa(local_path):
    file_key = f"covers/{uuid.uuid4()}-cover.jpg"
    s3 = boto3.client(
        "s3",
        endpoint_url=IDRIVE_URL,
        aws_access_key_id=IDRIVE_KEY,
        aws_secret_access_key=IDRIVE_SECRET,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        region_name="us-east-1",
    )
    try:
        s3.head_bucket(Bucket=IDRIVE_BUCKET)
    except Exception:
        s3.create_bucket(Bucket=IDRIVE_BUCKET)
    s3.upload_file(local_path, IDRIVE_BUCKET, file_key, ExtraArgs={"ContentType": "image/jpeg"})
    public_url = f"{PUBLIC_BASE}/{file_key}"
    log(f"Upload OK: {file_key}")
    return file_key, public_url


def atualizar_mongodb(slug, cover_key, cover_url):
    import subprocess, time, pymongo
    from urllib.parse import quote_plus

    LOCAL_PORT = 27032

    proc = subprocess.Popen([
        "ssh", "-i", SSH_KEY,
        "-p", str(VPS_PORT),
        "-L", f"{LOCAL_PORT}:127.0.0.1:27017",
        "-N", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes",
        f"{VPS_USER}@{VPS_HOST}",
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(3)

    try:
        mongo = pymongo.MongoClient(
            f"mongodb://{quote_plus(MONGO_USER)}:{quote_plus(MONGO_PASS)}@127.0.0.1:{LOCAL_PORT}/admin?authSource=admin",
            serverSelectionTimeoutMS=10000,
        )
        db = mongo[MONGO_DB]
        result = db[MONGO_COL].update_one(
            {"slug": slug},
            {"$set": {"coverImageKey": cover_key, "coverImageUrl": cover_url}}
        )
        mongo.close()
        log(f"MongoDB atualizado: matched={result.matched_count} modified={result.modified_count}")
        return result.modified_count > 0
    finally:
        proc.terminate()


def main():
    if len(sys.argv) < 4:
        print("Uso: python reparar_capa.py <slug> <titulo> <subtitulo>")
        sys.exit(1)

    slug     = sys.argv[1]
    titulo   = sys.argv[2]
    subtitulo = sys.argv[3]

    # 1. Gerar capa
    cover_path = gerar_capa(slug, titulo, subtitulo)
    if not cover_path:
        log("ERRO: não foi possível gerar a capa")
        sys.exit(1)

    # 2. Upload IDrive E2 — imagem QUADRADA original (nao converter para 1200x630)
    cover_key, cover_url = upload_capa(cover_path)

    # 3. Atualizar MongoDB
    ok = atualizar_mongodb(slug, cover_key, cover_url)
    if ok:
        log(f"Capa atualizada com sucesso para: {slug}")
        log(f"coverImageUrl: {cover_url}")
        log(f"Verificar em: https://api.curitibasoftware.com.br/api/blog/cover/{slug}")
    else:
        log("AVISO: post não encontrado no MongoDB ou nenhum campo alterado")
        sys.exit(1)


if __name__ == "__main__":
    main()
