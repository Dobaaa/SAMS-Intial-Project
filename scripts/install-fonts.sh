#!/usr/bin/env bash
# Install the PDF-rendering dependencies the docx-based pipeline needs.
# Idempotent — safe to re-run.
#
# Installs:
#   * libreoffice (core + writer + headless) — converts the per-agreement
#     populated docx into the final PDF
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

echo "==> Installing LibreOffice + MS core fonts + Caladea + cabextract"
$SUDO apt-get update -qq
$SUDO DEBIAN_FRONTEND=noninteractive apt-get install -y \
  libreoffice-core \
  libreoffice-writer \
  libreoffice-common \
  ttf-mscorefonts-installer \
  fonts-crosextra-caladea \
  cabextract \
  wget

# Tahoma isn't in ttf-mscorefonts-installer (Microsoft never released it as
# part of the core web fonts). The IELPKTH.CAB cabinet from Microsoft's IE
# Thai language pack bundled Tahoma 2.60 — that file is preserved on the
# SourceForge corefonts mirror. Download + extract once. The BGCC source
# .docx declares Tahoma for body styles, so without it LibreOffice
# substitutes a wider font and inflates the page count.
TAHOMA_DIR=/usr/share/fonts/truetype/msttcorefonts
if [[ ! -f "$TAHOMA_DIR/tahoma.ttf" || ! -f "$TAHOMA_DIR/tahomabd.ttf" ]]; then
  echo "==> Installing Tahoma from IELPKTH.CAB"
  TMP=$(mktemp -d)
  trap 'rm -rf "$TMP"' EXIT
  cd "$TMP"
  wget -q https://master.dl.sourceforge.net/project/corefonts/OldFiles/IELPKTH.CAB
  cabextract -F 'tahoma*ttf' IELPKTH.CAB >/dev/null
  $SUDO install -m 644 tahoma.ttf tahomabd.ttf "$TAHOMA_DIR/"
  cd - >/dev/null
else
  echo "==> Tahoma already installed at $TAHOMA_DIR"
fi

echo "==> Refreshing font cache"
$SUDO fc-cache -f

echo "==> Verifying fonts available"
missing=0
for f in "Times New Roman" "Arial" "Georgia" "Caladea" "Tahoma"; do
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

echo "==> Verifying LibreOffice available"
if ! command -v libreoffice >/dev/null 2>&1; then
  echo "  MISS libreoffice not on PATH after install" >&2
  exit 2
fi
echo "  ok   $(libreoffice --version 2>&1 | head -1)"

echo "==> Done. SAMS docx-based PDF pipeline can now render with BGCC source fonts."
