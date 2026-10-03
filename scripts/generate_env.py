"""Genera o sincroniza .env a partir de .env.example.

    python scripts/generate_env.py           # crea .env; cada `change-me` pasa a ser un secreto aleatorio
    python scripts/generate_env.py --sync    # actualiza un .env existente tras cambios en .env.example
    python scripts/generate_env.py --force   # regenera desde cero (¡invalida la BD existente!)

--sync conserva los valores actuales de las claves que siguen existiendo (incluidos
los secretos), agrega las claves nuevas y elimina las obsoletas. Al final lista las
claves cuyo valor difiere del ejemplo, por si conviene actualizarlas a mano.

Si se regenera con --force y hay un volumen de Postgres ya creado, las contraseñas
nuevas no coincidirán con las guardadas: ejecutar `docker compose down -v` antes.
"""

import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / ".env.example"
TARGET = ROOT / ".env"
PLACEHOLDER = "change-me"


def fill_secrets(line: str) -> str:
    while PLACEHOLDER in line:
        # token_hex: sin caracteres que haya que escapar en URLs de conexión.
        line = line.replace(PLACEHOLDER, secrets.token_hex(24), 1)
    return line


def parse(lines: list[str]) -> dict[str, str]:
    """Devuelve {clave: línea completa} de las asignaciones KEY=VALUE."""
    entries = {}
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            entries[stripped.split("=", 1)[0].strip()] = line
    return entries


def value_of(line: str) -> str:
    value = line.split("=", 1)[1]
    if " #" in value and not value.lstrip().startswith('"'):
        value = value.split(" #", 1)[0]  # comentario en línea
    return value.strip()


def generate() -> None:
    lines = [fill_secrets(line) for line in EXAMPLE.read_text(encoding="utf-8").splitlines()]
    TARGET.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{TARGET.name} generado con secretos aleatorios.")


def sync() -> None:
    example_lines = EXAMPLE.read_text(encoding="utf-8").splitlines()
    current = parse(TARGET.read_text(encoding="utf-8").splitlines())
    example = parse(example_lines)

    output, added, differs = [], [], []
    for line in example_lines:
        stripped = line.strip()
        key = stripped.split("=", 1)[0].strip() if "=" in stripped and not stripped.startswith("#") else None
        if key is None:
            output.append(line)  # comentarios y líneas en blanco del ejemplo
        elif key in current:
            output.append(current[key])
            if PLACEHOLDER not in line and value_of(current[key]) != value_of(line):
                differs.append(key)
        else:
            output.append(fill_secrets(line))
            added.append(key)

    removed = sorted(set(current) - set(example))
    TARGET.write_text("\n".join(output) + "\n", encoding="utf-8")

    print(f"{TARGET.name} sincronizado (secretos conservados).")
    print("  agregadas:", ", ".join(added) or "ninguna")
    print("  eliminadas:", ", ".join(removed) or "ninguna")
    if differs:
        print("  con valor distinto al ejemplo (revisar):", ", ".join(differs))


def main() -> int:
    if "--sync" in sys.argv:
        if not TARGET.exists():
            print(f"{TARGET.name} no existe; ejecute sin --sync para crearlo.")
            return 1
        sync()
        return 0

    if TARGET.exists() and "--force" not in sys.argv:
        print(f"{TARGET.name} ya existe. Use --sync para actualizarlo o --force para regenerarlo.")
        return 1
    generate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
