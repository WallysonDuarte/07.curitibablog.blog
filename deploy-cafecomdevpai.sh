#!/bin/bash
set -e

REMOTE_DIR="/opt/cafecomdevpai"
SSH="ssh -i ~/.ssh/id_server_nopass -p 2222 ubuntu@31.97.252.45"
SCP="scp -i ~/.ssh/id_server_nopass -P 2222"

if [[ "$1" != "--skip-build" ]]; then
  echo "==> Build cafecomdevpai.com.br..."
  PUBLIC_SITE_ID=cafecomdevpai PUBLIC_SITE_URL=https://cafecomdevpai.com.br npm run build
else
  echo "==> Deploy sem rebuild (usando dist atual)"
fi

echo "==> Compactando dist..."
tar -czf /tmp/cafecomdevpai.tar.gz -C dist .

echo "==> Enviando para servidor..."
$SCP /tmp/cafecomdevpai.tar.gz ubuntu@31.97.252.45:/tmp/

echo "==> Deploy no servidor..."
$SSH "
  sudo find $REMOTE_DIR -mindepth 1 -delete
  sudo tar -xzf /tmp/cafecomdevpai.tar.gz -C $REMOTE_DIR
  sudo chown -R www-data:www-data $REMOTE_DIR
  rm /tmp/cafecomdevpai.tar.gz
  echo 'Deploy concluido!'
"

rm -f /tmp/cafecomdevpai.tar.gz
echo "==> cafecomdevpai.com.br deployado em $REMOTE_DIR"
