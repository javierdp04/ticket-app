#!/bin/bash
set -e

echo "=== Deploy Eventum Spain — $(date) ==="

git pull origin main

source venv/bin/activate

pip install -r requirements.txt --quiet

sudo systemctl restart eventum

sudo systemctl status eventum --no-pager

echo "=== Deploy completado con exito ==="
