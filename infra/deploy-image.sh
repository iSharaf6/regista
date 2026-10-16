#!/usr/bin/env bash
# Build and deploy the Regista image with no Docker and no ACR Tasks.
#
# `azd up` builds the Dockerfile in Azure Container Registry (remoteBuild), or locally when Docker is installed.
# Azure for Students and other free-credit subscriptions reject ACR Tasks (TasksOperationsNotAllowed), so this
# script reproduces the Dockerfile instead: the web app is built here, the Python packages are resolved as
# linux/amd64 CPython 3.12 wheels with uv, and both are appended as one layer to python:3.12-slim with crane,
# pushed to the environment's registry and rolled out to the Container App.
#
# Run after `azd provision`, from anywhere:  infra/deploy-image.sh
# Needs az (signed in), azd, uv, npm and crane (on PATH, or CRANE=/path/to/crane).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CRANE="${CRANE:-crane}"
cd "$ROOT"
eval "$(azd env get-values)"
: "${AZURE_CONTAINER_REGISTRY_ENDPOINT:?run azd provision first}"
REGISTRY="$AZURE_CONTAINER_REGISTRY_ENDPOINT"
RG="$AZURE_RESOURCE_GROUP"
APP="$(az containerapp list -g "$RG" --query "[?tags.\"azd-service-name\"=='regista'].name | [0]" -o tsv)"
IMAGE="$REGISTRY/regista/regista-$AZURE_ENV_NAME:deploy-$(date -u +%Y%m%d%H%M%S)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
export DOCKER_CONFIG="$WORK/docker"  # registry token lives only for this run

echo "==> web app"
(cd web && { [ -d node_modules ] || npm ci --no-audit --no-fund; } && npm run build)

echo "==> python packages (linux/amd64, CPython 3.12)"
uv build --quiet --wheel backend -o "$WORK/dist"
WHEEL="$(ls "$WORK"/dist/regista-*.whl)"
uv pip install --quiet --target "$WORK/app/site" --python-platform x86_64-manylinux_2_28 --python-version 3.12 \
  --only-binary :all: "$WHEEL[azure]"

echo "==> layer"
mkdir -p "$WORK/app/web"
cp README.md "$WORK/app/"
cp -R docs "$WORK/app/docs"
cp -R web/dist "$WORK/app/web/dist"
python3 -I - "$WORK/app" "$WORK/layer.tar" <<'PY'
import os, sys, tarfile
src, out = sys.argv[1], sys.argv[2]
def clean(ti):
    if "__pycache__" in ti.name.split("/"):
        return None
    ti.uid = ti.gid = 0
    ti.uname = ti.gname = "root"
    ti.mode = 0o755 if ti.isdir() or ti.mode & 0o111 else 0o644
    ti.mtime = 0
    return ti
with tarfile.open(out, "w", format=tarfile.PAX_FORMAT) as tar:
    tar.add(src, arcname="app", filter=clean)
print(f"layer {os.path.getsize(out) / 1e6:.1f} MB")
PY

echo "==> push $IMAGE"
TOKEN="$(az acr login -n "${REGISTRY%%.*}" --expose-token --query accessToken -o tsv 2>/dev/null)"
"$CRANE" auth login "$REGISTRY" -u 00000000-0000-0000-0000-000000000000 -p "$TOKEN" >/dev/null
"$CRANE" mutate --platform linux/amd64 python:3.12-slim --append "$WORK/layer.tar" \
  -e PYTHONPATH=/app/site -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONUNBUFFERED=1 -e HOME=/tmp \
  -e REGISTA_WEB_DIST=/app/web/dist -e REGISTA_DOCS=/app/docs \
  -w /app -u 65534:65534 --exposed-ports 8000 \
  --cmd python,-m,uvicorn,regista.api.app:app,--host,0.0.0.0,--port,8000,--proxy-headers \
  -t "$IMAGE"

echo "==> roll out to $APP"
if [ -z "$(az containerapp show -g "$RG" -n "$APP" --query "properties.configuration.registries[0].server" -o tsv)" ]; then
  # Bicep sets this; restore it if it was dropped, or the pull fails with "Authentication failed"
  UAMI="$(az containerapp show -g "$RG" -n "$APP" --query "keys(identity.userAssignedIdentities)[0]" -o tsv)"
  az containerapp registry set -g "$RG" -n "$APP" --server "$REGISTRY" --identity "$UAMI" -o none
fi
az containerapp update -g "$RG" -n "$APP" --image "$IMAGE" --query "properties.latestRevisionName" -o tsv
# keep this image when `azd provision` runs again (see fetch-image.bicep)
azd env set SERVICE_REGISTA_RESOURCE_EXISTS true
azd env set SERVICE_REGISTA_IMAGE_NAME "$IMAGE"
echo "==> https://$(az containerapp show -g "$RG" -n "$APP" --query properties.configuration.ingress.fqdn -o tsv)"
