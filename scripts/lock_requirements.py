"""Genera requirements.lock (todas las dependencias, transitivas incluidas, con hashes SHA-256).

    python scripts/lock_requirements.py

Tarea 5.6: cada imagen instala con `pip install --require-hashes -r requirements.lock`: si un
paquete publicado cambia (p. ej. un ataque a la cadena de suministro), la instalación falla.
`requirements.txt` sigue siendo la lista editable (versiones directas exactas); después de
cambiarla hay que regenerar el lock con este script.

Se resuelve dentro de un contenedor Linux con Python 3.12 (la plataforma de las imágenes).
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIRECTORIES = [
    "services/flights-service", "services/hotels-service", "services/cars-service",
    "services/orders-service", "services/auth-service", "services/api-gateway",
    "services/mock-car-rental", "data-pipeline",
]
PIP_TOOLS = "pip-tools==7.6.2"


def main() -> int:
    targets = sys.argv[1:] or DIRECTORIES
    commands = " && ".join(
        f"echo '== {d}' && cd /repo/{d} && pip-compile --quiet --generate-hashes --strip-extras --no-emit-index-url "
        f"--output-file requirements.lock requirements.txt"
        for d in targets
    )
    script = f"pip install --quiet --disable-pip-version-check '{PIP_TOOLS}' && {commands}"
    return subprocess.run([
        "docker", "run", "--rm", "-v", f"{ROOT.as_posix()}:/repo", "-e", "CUSTOM_COMPILE_COMMAND=python scripts/lock_requirements.py",
        "python:3.12-slim", "sh", "-c", script,
    ]).returncode


if __name__ == "__main__":
    raise SystemExit(main())
