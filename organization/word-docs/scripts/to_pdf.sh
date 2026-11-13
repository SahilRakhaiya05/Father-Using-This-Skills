#!/usr/bin/env bash
# Convert an office file (.docx, .pptx, .xlsx, .odt …) to PDF next to the source.
# Usage: to_pdf.sh FILE [OUTDIR]
set -euo pipefail
f="$1"; out="$(cd "${2:-$(dirname "$f")}" && pwd)"   # absolute, so the printed path works from anywhere
profile="$(mktemp -d)"   # private LibreOffice profile avoids lock clashes
soffice -env:UserInstallation=file://"$profile" --headless --convert-to pdf --outdir "$out" "$f" >/dev/null 2>&1
rm -rf "$profile"
pdf="$out/$(basename "${f%.*}").pdf"
[ -f "$pdf" ] && echo "$pdf" || { echo "conversion failed" >&2; exit 1; }
