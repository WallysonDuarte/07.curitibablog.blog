#!/bin/bash
set -e

REMOTE_DIR="/opt/levelupdev"
SSH="ssh -i ~/.ssh/id_server_nopass -p 2222 ubuntu@31.97.252.45"
SCP="scp -i ~/.ssh/id_server_nopass -P 2222"

echo "==> Build..."
npm run build

echo "==> Compactando dist..."
tar -czf /tmp/levelupdev.tar.gz -C dist .

echo "==> Enviando para servidor..."
$SCP /tmp/levelupdev.tar.gz ubuntu@31.97.252.45:/tmp/

echo "==> Deploy no servidor..."
$SSH "
  sudo rm -rf $REMOTE_DIR/*
  sudo tar -xzf /tmp/levelupdev.tar.gz -C $REMOTE_DIR
  sudo chown -R www-data:www-data $REMOTE_DIR
  rm /tmp/levelupdev.tar.gz
  echo 'Deploy concluído!'
"

rm /tmp/levelupdev.tar.gz
echo "==> LevelUpDev deployado em levelupdev.com.br"
