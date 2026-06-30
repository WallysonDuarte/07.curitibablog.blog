#!/bin/bash
set -e

REMOTE_DIR="/opt/curitibablog"
SSH="ssh -i ~/.ssh/id_server_nopass -p 2222 ubuntu@31.97.252.45"
SCP="scp -i ~/.ssh/id_server_nopass -P 2222"

# Build separado do deploy para evitar double-build que causa timeout de API
# Para buildar: npm run build
# Para deployar sem rebuild: bash deploy.sh --skip-build
if [[ "$1" != "--skip-build" ]]; then
  echo "==> Build..."
  npm run build
else
  echo "==> Deploy sem rebuild (usando dist atual)"
fi

echo "==> Compactando dist..."
tar -czf /tmp/curitibablog.tar.gz -C dist .

echo "==> Enviando para servidor..."
$SCP /tmp/curitibablog.tar.gz ubuntu@31.97.252.45:/tmp/

echo "==> Deploy no servidor..."
$SSH "
  sudo find $REMOTE_DIR -mindepth 1 -delete
  sudo tar -xzf /tmp/curitibablog.tar.gz -C $REMOTE_DIR
  sudo chown -R www-data:www-data $REMOTE_DIR
  rm /tmp/curitibablog.tar.gz
  echo 'Deploy concluído!'
"

rm /tmp/curitibablog.tar.gz
echo "==> CuritibaBlog deployado em curitibablog.com.br"
