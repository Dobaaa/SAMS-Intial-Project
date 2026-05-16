#!/usr/bin/env bash
# Install the fonts WeasyPrint needs to reproduce the BGCC 42-page
# subcontract agreement layout. Idempotent — safe to re-run.
#
# Installs:
#   * ttf-mscorefonts-installer — Times New Roman, Arial, Georgia,
#                                 Verdana, Tahoma fallback, Webdings, etc.
#   * fonts-crosextra-caladea   — metric-compatible substitute for Cambria
#
# Run on the VPS as a user with passwordless sudo:
#   ./scripts/install-fonts.sh
set -euo pipefail

if [[ $EUID -ne 0 ]] && ! sudo -n true 2>/dev/null; then
  echo "This script needs sudo. Run as root or as a sudoer." >&2
  exit 1
fi

SUDO=""
[[ $EUID -ne 0 ]] && SUDO="sudo"

echo "==> Pre-accepting MS core fonts EULA"
echo ttf-mscorefonts-installer msttcorefonts/accepted-mscorefonts-eula select true \
  | $SUDO debconf-set-selections

echo "==> Installing ttf-mscorefonts-installer + fonts-crosextra-caladea"
$SUDO apt-get update -qq
$SUDO DEBIAN_FRONTEND=noninteractive apt-get install -y \
  ttf-mscorefonts-installer \
  fonts-crosextra-caladea

echo "==> Refreshing font cache"
$SUDO fc-cache -f

echo "==> Verifying fonts available"
missing=0
for f in "Times New Roman" "Arial" "Georgia" "Caladea"; do
  match=$(fc-match "$f" | awk -F'"' '{print $2}')
  if [[ "$match" == "$f" ]] || { [[ "$f" == "Caladea" ]] && [[ "$match" == "Caladea" ]]; }; then
    echo "  ok   $f -> $match"
  else
    echo "  MISS $f -> $match"
    missing=$((missing+1))
  fi
done

if [[ $missing -gt 0 ]]; then
  echo "Some fonts did not resolve to themselves. Check the install output above." >&2
  exit 2
fi

echo "==> Done. WeasyPrint can now render with the BGCC source fonts."
