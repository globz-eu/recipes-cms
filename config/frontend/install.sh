#!/bin/sh
# Install a recipes-frontend release into /dist (the volume nginx serves at
# /frontend/). Uses $FRONTEND_VERSION (e.g. v0.5.0) or the latest release.
set -eu

REPO=https://github.com/globz-eu/recipes-frontend

tag="${FRONTEND_VERSION:-}"
if [ -z "$tag" ]; then
  tag=$(curl -fsS -o /dev/null -w '%{redirect_url}' "$REPO/releases/latest")
  tag=${tag##*/}
fi
[ -n "$tag" ] || { echo "Could not determine the latest frontend release" >&2; exit 1; }

if [ "$(cat /dist/.version 2>/dev/null || true)" = "$tag" ] && [ -z "${FRONTEND_FORCE:-}" ]; then
  echo "Frontend $tag already installed"
  exit 0
fi

echo "Installing frontend $tag"
tmp=$(mktemp)
curl -fsSL -o "$tmp" "$REPO/releases/download/$tag/recipes-frontend-$tag.tar.gz"
find /dist -mindepth 1 -delete
tar -xzf "$tmp" -C /dist
echo "$tag" > /dist/.version
rm -f "$tmp"
