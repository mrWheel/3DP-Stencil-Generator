#!/usr/bin/env bash
set -euo pipefail

# Geef hier het pad op naar de plugin-bronmap
PROJECT_PATH="/Users/WillemA/3DP-Stencil-Generator-Next/3dp-stencil-generator"
TARGET_DIR="$HOME/Documents/KiCAD/9.0/scripting/plugins/3dp-stencil-generator"
INIT_FILE="$PROJECT_PATH/__init__.py"

if [[ ! -f "$INIT_FILE" ]]; then
  echo "Fout: bestand niet gevonden: $INIT_FILE"
  exit 1
fi

# 1) Controleer doelmap en maak aan indien nodig
mkdir -p "$TARGET_DIR"

# 2) Verhoog BUILD in __init__.py met 1
python3 - "$INIT_FILE" <<'PY'
import re
import sys
from pathlib import Path

init_file = Path(sys.argv[1])
content = init_file.read_text(encoding="utf-8")

pattern = re.compile(r'^(\s*BUILD\s*=\s*")(\d+)(".*)$', re.MULTILINE)
match = pattern.search(content)

if not match:
    print("Fout: BUILD-regel niet gevonden in __init__.py", file=sys.stderr)
    sys.exit(1)

new_build = str(int(match.group(2)) + 1)
updated = pattern.sub(lambda m: f'{m.group(1)}{new_build}{m.group(3)}', content, count=1)
init_file.write_text(updated, encoding="utf-8")
print(f"BUILD verhoogd naar {new_build}")
PY

# 3) Kopieer __init__.py naar KiCad plugin map
sudo cp "$INIT_FILE" "$TARGET_DIR/"

echo "Klaar: __init__.py gekopieerd naar $TARGET_DIR"
