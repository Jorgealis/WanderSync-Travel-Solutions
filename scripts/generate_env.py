"""Genera .env a partir de .env.example reemplazando cada `change-me` por un secreto aleatorio.

    python scripts/generate_env.py           # no sobrescribe un .env existente
    python scripts/generate_env.py --force   # regenera (¡invalida la BD existente!)

Si se regenera el .env con un volumen de Postgres ya creado, las contraseñas nuevas
no coincidirán con las guardadas: ejecutar `docker compose down -v` antes de levantar.
"""

import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / ".env.example"
TARGET = ROOT / ".env"
PLACEHOLDER = "change-me"


def main() -> int:
    if TARGET.exists() and "--force" not in sys.argv:
        print(f"{TARGET.name} ya existe. Usa --force para regenerarlo.")
        return 1

    lines = []
    for line in EXAMPLE.read_text(encoding="utf-8").splitlines():
        while PLACEHOLDER in line:
            # token_hex: sin caracteres que haya que escapar en URLs de conexión.
            line = line.replace(PLACEHOLDER, secrets.token_hex(24), 1)
        lines.append(line)

    TARGET.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{TARGET.name} generado con secretos aleatorios.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
