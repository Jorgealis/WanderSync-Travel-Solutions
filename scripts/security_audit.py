"""Auditoría de la cadena de suministro (tareas 5.5 y 5.6).

    python scripts/security_audit.py antes      # informe en docs/seguridad/antes/
    python scripts/security_audit.py despues    # informe en docs/seguridad/despues/

Audita lo que REALMENTE se despliega (requiere las imágenes construidas: docker compose build):
1. pip-audit del inventario REAL de cada imagen Python propia (dependencias directas y transitivas
   instaladas, leídas con importlib.metadata porque las imágenes finales no traen pip).
2. npm audit del frontend: todas las dependencias y solo las de ejecución (--omit=dev).
3. Trivy sobre cada imagen (propias y de terceros): paquetes del sistema operativo y de
   lenguaje, y búsqueda de secretos incrustados.

Genera JSON compactos (evidencia) y un RESUMEN.md por ejecución.
"""

import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIP_AUDIT = "pip-audit==2.10.1"
TRIVY = "aquasec/trivy:0.75.0"

OWN_PYTHON_IMAGES = {
    "flights-service": "wandersync-flights-service:latest",
    "hotels-service": "wandersync-hotels-service:latest",
    "cars-service": "wandersync-cars-service:latest",
    "orders-service": "wandersync-orders-service:latest",
    "auth-service": "wandersync-auth-service:latest",
    "api-gateway": "wandersync-api-gateway:latest",
    "mock-car-rental": "wandersync-mock-car-rental:latest",
    "data-pipeline": "wandersync/data-pipeline:local",
}
OTHER_IMAGES = {
    "frontend": "wandersync-frontend:latest",
    "postgres": "postgres:16.15-alpine",
    "redis": "redis:7.4-alpine",
    "hasura": "hasura/graphql-engine:v2.51.0.cli-migrations-v3",
}
SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"]


def run(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", **kwargs)


# Inventario de lo instalado en la imagen (venv de la app + site-packages del sistema), sin pip:
# las imágenes finales ya no lo incluyen (tarea 5.7).
INVENTORY = (
    "import importlib.metadata as m, sys, sysconfig; "
    "paths = [sysconfig.get_paths()['purelib'], f'/usr/local/lib/python{sys.version_info[0]}.{sys.version_info[1]}/site-packages']; "
    "print('\\n'.join(sorted({f\"{d.metadata['Name']}=={d.version}\" for d in m.distributions(path=paths)})))"
)


def pip_audit(image: str) -> dict:
    """pip-audit del inventario de la imagen, ejecutado en un contenedor aparte."""
    inventory = run(["docker", "run", "--rm", "--entrypoint", "python", image, "-c", INVENTORY])
    if inventory.returncode != 0:
        return {"error": inventory.stderr[-500:]}
    script = (
        f"pip install -q --disable-pip-version-check --root-user-action=ignore '{PIP_AUDIT}' >/dev/null 2>&1 && "
        "cat > /tmp/installed.txt && "
        "pip-audit -r /tmp/installed.txt --no-deps --disable-pip --format json --progress-spinner off"
    )
    result = run(["docker", "run", "--rm", "-i", "python:3.12-slim", "sh", "-c", script], input=inventory.stdout)
    try:
        data = json.loads(result.stdout[result.stdout.index("{"):])
    except (ValueError, json.JSONDecodeError):
        return {"error": (result.stderr or result.stdout)[-500:]}
    unique = {}
    for dep in data.get("dependencies", []):
        for v in dep.get("vulns", []):
            # El mismo paquete puede aparecer dos veces (dos copias de metadatos): sin duplicados.
            unique[(dep["name"], dep["version"], v["id"])] = {
                "package": dep["name"], "version": dep["version"], "id": v["id"],
                "aliases": v.get("aliases", []), "fix_versions": v.get("fix_versions", [])}
    names = {dep["name"] for dep in data.get("dependencies", [])}
    return {"packages": len(names), "vulnerabilities": list(unique.values())}


def npm_audit(omit_dev: bool) -> dict:
    args = ["npm", "audit", "--json"] + (["--omit=dev"] if omit_dev else [])
    result = run(args, cwd=ROOT / "frontend", shell=sys.platform == "win32")
    data = json.loads(result.stdout or "{}")
    vulns = [
        {"package": name, "severity": info.get("severity"), "range": info.get("range"),
         "via": [v if isinstance(v, str) else v.get("title") for v in info.get("via", [])],
         "fix_available": bool(info.get("fixAvailable"))}
        for name, info in data.get("vulnerabilities", {}).items()
    ]
    return {"summary": data.get("metadata", {}).get("vulnerabilities", {}), "vulnerabilities": vulns}


def trivy(image: str) -> dict:
    base = ["docker", "run", "--rm", "-v", "/var/run/docker.sock:/var/run/docker.sock",
            "-v", "wandersync-trivy-cache:/root/.cache/", TRIVY,
            "image", "--quiet", "--scanners", "vuln,secret", "--format", "json"]
    # Si Trivy no puede leer una capa desde el daemon de Docker (pasó con Hasura), se descarga
    # la imagen directamente del registro (solo funciona con imágenes públicas).
    for extra in ([], ["--image-src", "remote"]):
        result = run([*base, *extra, image])
        try:
            data = json.loads(result.stdout)
            break
        except json.JSONDecodeError:
            continue
    else:
        return {"error": (result.stderr or result.stdout)[-500:]}
    vulns, secrets = [], []
    for target in data.get("Results", []):
        for v in target.get("Vulnerabilities") or []:
            vulns.append({"target": target.get("Target"), "type": target.get("Type"), "package": v.get("PkgName"),
                          "installed": v.get("InstalledVersion"), "fixed": v.get("FixedVersion") or "",
                          "id": v.get("VulnerabilityID"), "severity": v.get("Severity")})
        for s in target.get("Secrets") or []:
            secrets.append({"target": target.get("Target"), "rule": s.get("RuleID"), "severity": s.get("Severity")})
    return {"vulnerabilities": vulns, "secrets": secrets}


def severity_counts(vulns: list[dict]) -> dict:
    counts = Counter(v.get("severity", "UNKNOWN") for v in vulns)
    return {s: counts.get(s, 0) for s in SEVERITIES}


def main() -> int:
    label = sys.argv[1] if len(sys.argv) > 1 else "antes"
    out = ROOT / "docs" / "seguridad" / label
    out.mkdir(parents=True, exist_ok=True)
    report: dict = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "tools": {"pip-audit": PIP_AUDIT, "trivy": TRIVY, "npm": run(["npm", "--version"], shell=sys.platform == "win32").stdout.strip()},
                    "pip_audit": {}, "npm_audit": {}, "trivy": {}}

    for name, image in OWN_PYTHON_IMAGES.items():
        print(f"pip-audit {name}…", flush=True)
        report["pip_audit"][name] = pip_audit(image)
    print("npm audit…", flush=True)
    report["npm_audit"] = {"all": npm_audit(False), "runtime": npm_audit(True)}
    for name, image in {**OWN_PYTHON_IMAGES, **OTHER_IMAGES}.items():
        print(f"trivy {name}…", flush=True)
        report["trivy"][name] = trivy(image) | {"image": image}

    (out / "auditoria.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    (out / "RESUMEN.md").write_text(summary(label, report), encoding="utf-8")
    print(f"Informe en {out.relative_to(ROOT)}")
    return 0


def summary(label: str, report: dict) -> str:
    lines = [f"# Auditoría de dependencias — {label}", "",
             f"Generado: {report['generated_at']} · herramientas: {', '.join(f'{k} {v}' for k, v in report['tools'].items())}", "",
             "## pip-audit (dependencias Python instaladas en cada imagen)", "",
             "| Imagen | Paquetes | Vulnerabilidades |", "|---|---|---|"]
    python_findings = []
    for name, result in report["pip_audit"].items():
        if "error" in result:
            lines.append(f"| {name} | — | error: {result['error'][:80]} |")
            continue
        lines.append(f"| {name} | {result['packages']} | {len(result['vulnerabilities'])} |")
        python_findings += [(name, v) for v in result["vulnerabilities"]]
    if python_findings:
        lines += ["", "| Imagen | Paquete | Versión | ID | Corregido en |", "|---|---|---|---|---|"]
        lines += [f"| {n} | {v['package']} | {v['version']} | {v['id']} | {', '.join(v['fix_versions']) or '—'} |" for n, v in python_findings]

    lines += ["", "## npm audit (frontend)", "", "| Alcance | critical | high | moderate | low | info |", "|---|---|---|---|---|---|"]
    for scope, title in (("all", "todas las dependencias"), ("runtime", "solo ejecución (--omit=dev)")):
        s = report["npm_audit"][scope]["summary"]
        lines.append(f"| {title} | {s.get('critical', 0)} | {s.get('high', 0)} | {s.get('moderate', 0)} | {s.get('low', 0)} | {s.get('info', 0)} |")
    npm_findings = report["npm_audit"]["all"]["vulnerabilities"]
    if npm_findings:
        lines += ["", "| Paquete | Severidad | Rango | Origen | ¿Corrección? |", "|---|---|---|---|---|"]
        lines += [f"| {v['package']} | {v['severity']} | {v['range']} | {'; '.join(map(str, v['via']))[:90]} | {'sí' if v['fix_available'] else 'no'} |" for v in npm_findings]

    lines += ["", "## Trivy (imágenes: SO + paquetes de lenguaje + secretos)", "",
              "| Imagen | " + " | ".join(SEVERITIES) + " | con corrección disponible | secretos |",
              "|---|" + "---|" * (len(SEVERITIES) + 2)]
    for name, result in report["trivy"].items():
        if "error" in result:
            lines.append(f"| {name} | error: {result['error'][:80]} |")
            continue
        counts = severity_counts(result["vulnerabilities"])
        fixable = sum(1 for v in result["vulnerabilities"] if v["fixed"])
        lines.append(f"| {name} | " + " | ".join(str(counts[s]) for s in SEVERITIES) + f" | {fixable} | {len(result['secrets'])} |")
    high = [(n, v) for n, r in report["trivy"].items() for v in r.get("vulnerabilities", []) if v["severity"] in ("CRITICAL", "HIGH")]
    if high:
        lines += ["", "### CRITICAL y HIGH", "", "| Imagen | Paquete | Instalado | Corregido en | ID | Severidad |", "|---|---|---|---|---|---|"]
        seen = set()
        for n, v in high:
            key = (n, v["package"], v["id"])
            if key not in seen:
                seen.add(key)
                lines.append(f"| {n} | {v['package']} | {v['installed']} | {v['fixed'] or '—'} | {v['id']} | {v['severity']} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
