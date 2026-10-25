#!/bin/sh
# Container entrypoint: start Scrapyd and deploy the project automatically.
set -e
cd /app

# Background job: wait until Scrapyd answers, then deploy the project.
(
  attempts=0
  until python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:6800/daemonstatus.json', timeout=2)" 2>/dev/null; do
    attempts=$((attempts + 1))
    if [ "$attempts" -ge 60 ]; then
      echo "[entrypoint] ERROR: Scrapyd did not start within 60 seconds"
      exit 1
    fi
    sleep 1
  done
  echo "[entrypoint] Scrapyd is up. Deploying project..."
  scrapyd-deploy || echo "[entrypoint] ERROR: project deployment failed"
) &

# Scrapyd runs in the foreground as the main process (receives docker stop signals).
exec scrapyd