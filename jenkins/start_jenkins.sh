#!/usr/bin/env bash
# Build and start the Jenkins controller on http://localhost:8081
# Secrets are kept in ../.secrets (gitignored) and mounted read-only into /run/secrets.
set -euo pipefail
cd "$(dirname "$0")"
SECRETS_DIR="$(cd .. && pwd)/.secrets/jcasc"

docker network inspect ci-net >/dev/null 2>&1 || docker network create ci-net
docker build -t kartik-jenkins:lts .
docker rm -f jenkins >/dev/null 2>&1 || true
docker run -d --name jenkins --restart unless-stopped \
  --network ci-net \
  -p 8081:8080 -p 50001:50000 \
  -v jenkins_home:/var/jenkins_home \
  -v /var/run/docker.sock:/var/run/docker.sock \
  --group-add "$(stat -c %g /var/run/docker.sock)" \
  -v "${SECRETS_DIR}:/run/secrets:ro" \
  kartik-jenkins:lts
echo "Jenkins starting on http://localhost:8081"
