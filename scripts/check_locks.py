"""Comprueba que cada requirements.lock esté al día con su requirements.txt (tarea 5.8).

    python scripts/check_locks.py

Las imágenes instalan desde requirements.lock (con hashes); requirements.txt es la lista que se
edita a mano o que actualiza Dependabot. Si una versión fijada en requirements.txt no aparece
igual en el lock, falla e indica regenerarlo con `python scripts/lock_requirements.py <dir>`.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lock_requirements import DIRECTORIES  # noqa: E402

PIN = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?\s*==\s*([^\s;#\\]+)")


def canonical(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def pins(path: Path) -> dict[str, str]:
    found = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = PIN.match(line)
        if match:
            found[canonical(match.group(1))] = match.group(2)
    return found


def main() -> int:
    stale = []
    for directory in DIRECTORIES:
        wanted = pins(ROOT / directory / "requirements.txt")
        lock_path = ROOT / directory / "requirements.lock"
        locked = pins(lock_path) if lock_path.exists() else {}
        for name, version in wanted.items():
            if locked.get(name) != version:
                stale.append(f"{directory}: {name}=={version} (lock: {locked.get(name, 'ausente')})")
    if stale:
        print("Locks desactualizados; regenerar con python scripts/lock_requirements.py <dir>:")
        print("\n".join(f"  - {s}" for s in stale))
        return 1
    print(f"OK: {len(DIRECTORIES)} locks al día con su requirements.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
