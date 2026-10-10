# Auditoría de dependencias — despues

Generado: 2026-10-10T08:25:17+00:00 · herramientas: pip-audit pip-audit==2.10.1, trivy aquasec/trivy:0.75.0, npm 10.9.3

## pip-audit (dependencias Python instaladas en cada imagen)

| Imagen | Paquetes | Vulnerabilidades |
|---|---|---|
| flights-service | 33 | 0 |
| hotels-service | 33 | 0 |
| cars-service | 33 | 0 |
| orders-service | 34 | 0 |
| auth-service | 40 | 0 |
| api-gateway | 38 | 0 |
| mock-car-rental | 20 | 0 |
| data-pipeline | 126 | 0 |

## npm audit (frontend)

| Alcance | critical | high | moderate | low | info |
|---|---|---|---|---|---|
| todas las dependencias | 0 | 10 | 0 | 0 | 0 |
| solo ejecución (--omit=dev) | 0 | 0 | 0 | 0 | 0 |

| Paquete | Severidad | Rango | Origen | ¿Corrección? |
|---|---|---|---|---|
| @graphql-codegen/cli | high | >=1.21.9-alpha-85a42cafa.0 | @graphql-tools/code-file-loader; @graphql-tools/git-loader; @graphql-tools/graphql-file-lo | sí |
| @graphql-tools/code-file-loader | high | >=6.3.2-alpha-07a30dd3.0 | globby | sí |
| @graphql-tools/git-loader | high | >=6.2.7-alpha-07a30dd3.0 | micromatch | sí |
| @graphql-tools/graphql-file-loader | high | >=6.2.8-alpha-07a30dd3.0 | globby | sí |
| @graphql-tools/json-file-loader | high | >=7.1.0 | globby | sí |
| braces | high | * | braces vulnerable to stack-exhaustion denial of service through deeply nested patterns | sí |
| fast-glob | high | * | micromatch | sí |
| globby | high | >=8.0.0 | fast-glob | sí |
| graphql-config | high | <=0.0.0-experimental-fc44e45.4b3 || 3.4.0 || >=4.0.0 | @graphql-tools/graphql-file-loader; @graphql-tools/json-file-loader | sí |
| micromatch | high | >=0.2.0 | braces | sí |

## Trivy (imágenes: SO + paquetes de lenguaje + secretos)

| Imagen | CRITICAL | HIGH | MEDIUM | LOW | UNKNOWN | con corrección disponible | secretos |
|---|---|---|---|---|---|---|---|
| flights-service | 0 | 44 | 58 | 61 | 1 | 0 | 0 |
| hotels-service | 0 | 44 | 58 | 61 | 1 | 0 | 0 |
| cars-service | 0 | 44 | 58 | 61 | 1 | 0 | 0 |
| orders-service | 0 | 44 | 58 | 61 | 1 | 0 | 0 |
| auth-service | 0 | 44 | 58 | 61 | 1 | 0 | 0 |
| api-gateway | 0 | 44 | 58 | 61 | 1 | 0 | 0 |
| mock-car-rental | 0 | 44 | 58 | 61 | 1 | 0 | 0 |
| data-pipeline | 0 | 44 | 58 | 61 | 1 | 0 | 0 |
| frontend | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| postgres | 1 | 24 | 28 | 3 | 5 | 61 | 0 |
| redis | 0 | 2 | 17 | 2 | 0 | 21 | 0 |
| hasura | 0 | 2 | 80 | 20 | 0 | 77 | 0 |

### CRITICAL y HIGH

| Imagen | Paquete | Instalado | Corregido en | ID | Severidad |
|---|---|---|---|---|---|
| flights-service | bsdutils | 1:2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| flights-service | bsdutils | 1:2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| flights-service | bsdutils | 1:2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| flights-service | bsdutils | 1:2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| flights-service | libacl1 | 2.3.2-2+b1 | — | CVE-2026-54369 | HIGH |
| flights-service | libblkid1 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| flights-service | libblkid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| flights-service | libblkid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| flights-service | libblkid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| flights-service | liblastlog2-2 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| flights-service | liblastlog2-2 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| flights-service | liblastlog2-2 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| flights-service | liblastlog2-2 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| flights-service | libmount1 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| flights-service | libmount1 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| flights-service | libmount1 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| flights-service | libmount1 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| flights-service | libncursesw6 | 6.5+20250216-2 | — | CVE-2025-69720 | HIGH |
| flights-service | libsmartcols1 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| flights-service | libsmartcols1 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| flights-service | libsmartcols1 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| flights-service | libsmartcols1 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| flights-service | libsystemd0 | 257.13-1~deb13u1 | — | CVE-2026-16742 | HIGH |
| flights-service | libtinfo6 | 6.5+20250216-2 | — | CVE-2025-69720 | HIGH |
| flights-service | libudev1 | 257.13-1~deb13u1 | — | CVE-2026-16742 | HIGH |
| flights-service | libuuid1 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| flights-service | libuuid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| flights-service | libuuid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| flights-service | libuuid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| flights-service | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| flights-service | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| flights-service | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| flights-service | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| flights-service | mount | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| flights-service | mount | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| flights-service | mount | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| flights-service | mount | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| flights-service | ncurses-base | 6.5+20250216-2 | — | CVE-2025-69720 | HIGH |
| flights-service | ncurses-bin | 6.5+20250216-2 | — | CVE-2025-69720 | HIGH |
| flights-service | perl-base | 5.40.1-6+deb13u1 | — | CVE-2026-9538 | HIGH |
| flights-service | util-linux | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| flights-service | util-linux | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| flights-service | util-linux | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| flights-service | util-linux | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| hotels-service | bsdutils | 1:2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| hotels-service | bsdutils | 1:2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| hotels-service | bsdutils | 1:2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| hotels-service | bsdutils | 1:2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| hotels-service | libacl1 | 2.3.2-2+b1 | — | CVE-2026-54369 | HIGH |
| hotels-service | libblkid1 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| hotels-service | libblkid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| hotels-service | libblkid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| hotels-service | libblkid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| hotels-service | liblastlog2-2 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| hotels-service | liblastlog2-2 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| hotels-service | liblastlog2-2 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| hotels-service | liblastlog2-2 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| hotels-service | libmount1 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| hotels-service | libmount1 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| hotels-service | libmount1 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| hotels-service | libmount1 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| hotels-service | libncursesw6 | 6.5+20250216-2 | — | CVE-2025-69720 | HIGH |
| hotels-service | libsmartcols1 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| hotels-service | libsmartcols1 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| hotels-service | libsmartcols1 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| hotels-service | libsmartcols1 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| hotels-service | libsystemd0 | 257.13-1~deb13u1 | — | CVE-2026-16742 | HIGH |
| hotels-service | libtinfo6 | 6.5+20250216-2 | — | CVE-2025-69720 | HIGH |
| hotels-service | libudev1 | 257.13-1~deb13u1 | — | CVE-2026-16742 | HIGH |
| hotels-service | libuuid1 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| hotels-service | libuuid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| hotels-service | libuuid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| hotels-service | libuuid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| hotels-service | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| hotels-service | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| hotels-service | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| hotels-service | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| hotels-service | mount | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| hotels-service | mount | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| hotels-service | mount | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| hotels-service | mount | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| hotels-service | ncurses-base | 6.5+20250216-2 | — | CVE-2025-69720 | HIGH |
| hotels-service | ncurses-bin | 6.5+20250216-2 | — | CVE-2025-69720 | HIGH |
| hotels-service | perl-base | 5.40.1-6+deb13u1 | — | CVE-2026-9538 | HIGH |
| hotels-service | util-linux | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| hotels-service | util-linux | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| hotels-service | util-linux | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| hotels-service | util-linux | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| cars-service | bsdutils | 1:2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| cars-service | bsdutils | 1:2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| cars-service | bsdutils | 1:2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| cars-service | bsdutils | 1:2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| cars-service | libacl1 | 2.3.2-2+b1 | — | CVE-2026-54369 | HIGH |
| cars-service | libblkid1 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| cars-service | libblkid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| cars-service | libblkid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| cars-service | libblkid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| cars-service | liblastlog2-2 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| cars-service | liblastlog2-2 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| cars-service | liblastlog2-2 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| cars-service | liblastlog2-2 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| cars-service | libmount1 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| cars-service | libmount1 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| cars-service | libmount1 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| cars-service | libmount1 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| cars-service | libncursesw6 | 6.5+20250216-2 | — | CVE-2025-69720 | HIGH |
| cars-service | libsmartcols1 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| cars-service | libsmartcols1 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| cars-service | libsmartcols1 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| cars-service | libsmartcols1 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| cars-service | libsystemd0 | 257.13-1~deb13u1 | — | CVE-2026-16742 | HIGH |
| cars-service | libtinfo6 | 6.5+20250216-2 | — | CVE-2025-69720 | HIGH |
| cars-service | libudev1 | 257.13-1~deb13u1 | — | CVE-2026-16742 | HIGH |
| cars-service | libuuid1 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| cars-service | libuuid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| cars-service | libuuid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| cars-service | libuuid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| cars-service | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| cars-service | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| cars-service | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| cars-service | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| cars-service | mount | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| cars-service | mount | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| cars-service | mount | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| cars-service | mount | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| cars-service | ncurses-base | 6.5+20250216-2 | — | CVE-2025-69720 | HIGH |
| cars-service | ncurses-bin | 6.5+20250216-2 | — | CVE-2025-69720 | HIGH |
| cars-service | perl-base | 5.40.1-6+deb13u1 | — | CVE-2026-9538 | HIGH |
| cars-service | util-linux | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| cars-service | util-linux | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| cars-service | util-linux | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| cars-service | util-linux | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| orders-service | bsdutils | 1:2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| orders-service | bsdutils | 1:2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| orders-service | bsdutils | 1:2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| orders-service | bsdutils | 1:2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| orders-service | libacl1 | 2.3.2-2+b1 | — | CVE-2026-54369 | HIGH |
| orders-service | libblkid1 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| orders-service | libblkid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| orders-service | libblkid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| orders-service | libblkid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| orders-service | liblastlog2-2 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| orders-service | liblastlog2-2 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| orders-service | liblastlog2-2 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| orders-service | liblastlog2-2 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| orders-service | libmount1 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| orders-service | libmount1 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| orders-service | libmount1 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| orders-service | libmount1 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| orders-service | libncursesw6 | 6.5+20250216-2 | — | CVE-2025-69720 | HIGH |
| orders-service | libsmartcols1 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| orders-service | libsmartcols1 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| orders-service | libsmartcols1 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| orders-service | libsmartcols1 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| orders-service | libsystemd0 | 257.13-1~deb13u1 | — | CVE-2026-16742 | HIGH |
| orders-service | libtinfo6 | 6.5+20250216-2 | — | CVE-2025-69720 | HIGH |
| orders-service | libudev1 | 257.13-1~deb13u1 | — | CVE-2026-16742 | HIGH |
| orders-service | libuuid1 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| orders-service | libuuid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| orders-service | libuuid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| orders-service | libuuid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| orders-service | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| orders-service | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| orders-service | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| orders-service | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| orders-service | mount | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| orders-service | mount | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| orders-service | mount | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| orders-service | mount | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| orders-service | ncurses-base | 6.5+20250216-2 | — | CVE-2025-69720 | HIGH |
| orders-service | ncurses-bin | 6.5+20250216-2 | — | CVE-2025-69720 | HIGH |
| orders-service | perl-base | 5.40.1-6+deb13u1 | — | CVE-2026-9538 | HIGH |
| orders-service | util-linux | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| orders-service | util-linux | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| orders-service | util-linux | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| orders-service | util-linux | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| auth-service | bsdutils | 1:2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| auth-service | bsdutils | 1:2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| auth-service | bsdutils | 1:2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| auth-service | bsdutils | 1:2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| auth-service | libacl1 | 2.3.2-2+b1 | — | CVE-2026-54369 | HIGH |
| auth-service | libblkid1 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| auth-service | libblkid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| auth-service | libblkid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| auth-service | libblkid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| auth-service | liblastlog2-2 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| auth-service | liblastlog2-2 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| auth-service | liblastlog2-2 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| auth-service | liblastlog2-2 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| auth-service | libmount1 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| auth-service | libmount1 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| auth-service | libmount1 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| auth-service | libmount1 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| auth-service | libncursesw6 | 6.5+20250216-2 | — | CVE-2025-69720 | HIGH |
| auth-service | libsmartcols1 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| auth-service | libsmartcols1 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| auth-service | libsmartcols1 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| auth-service | libsmartcols1 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| auth-service | libsystemd0 | 257.13-1~deb13u1 | — | CVE-2026-16742 | HIGH |
| auth-service | libtinfo6 | 6.5+20250216-2 | — | CVE-2025-69720 | HIGH |
| auth-service | libudev1 | 257.13-1~deb13u1 | — | CVE-2026-16742 | HIGH |
| auth-service | libuuid1 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| auth-service | libuuid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| auth-service | libuuid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| auth-service | libuuid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| auth-service | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| auth-service | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| auth-service | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| auth-service | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| auth-service | mount | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| auth-service | mount | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| auth-service | mount | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| auth-service | mount | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| auth-service | ncurses-base | 6.5+20250216-2 | — | CVE-2025-69720 | HIGH |
| auth-service | ncurses-bin | 6.5+20250216-2 | — | CVE-2025-69720 | HIGH |
| auth-service | perl-base | 5.40.1-6+deb13u1 | — | CVE-2026-9538 | HIGH |
| auth-service | util-linux | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| auth-service | util-linux | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| auth-service | util-linux | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| auth-service | util-linux | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| api-gateway | bsdutils | 1:2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| api-gateway | bsdutils | 1:2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| api-gateway | bsdutils | 1:2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| api-gateway | bsdutils | 1:2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| api-gateway | libacl1 | 2.3.2-2+b1 | — | CVE-2026-54369 | HIGH |
| api-gateway | libblkid1 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| api-gateway | libblkid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| api-gateway | libblkid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| api-gateway | libblkid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| api-gateway | liblastlog2-2 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| api-gateway | liblastlog2-2 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| api-gateway | liblastlog2-2 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| api-gateway | liblastlog2-2 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| api-gateway | libmount1 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| api-gateway | libmount1 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| api-gateway | libmount1 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| api-gateway | libmount1 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| api-gateway | libncursesw6 | 6.5+20250216-2 | — | CVE-2025-69720 | HIGH |
| api-gateway | libsmartcols1 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| api-gateway | libsmartcols1 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| api-gateway | libsmartcols1 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| api-gateway | libsmartcols1 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| api-gateway | libsystemd0 | 257.13-1~deb13u1 | — | CVE-2026-16742 | HIGH |
| api-gateway | libtinfo6 | 6.5+20250216-2 | — | CVE-2025-69720 | HIGH |
| api-gateway | libudev1 | 257.13-1~deb13u1 | — | CVE-2026-16742 | HIGH |
| api-gateway | libuuid1 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| api-gateway | libuuid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| api-gateway | libuuid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| api-gateway | libuuid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| api-gateway | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| api-gateway | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| api-gateway | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| api-gateway | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| api-gateway | mount | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| api-gateway | mount | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| api-gateway | mount | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| api-gateway | mount | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| api-gateway | ncurses-base | 6.5+20250216-2 | — | CVE-2025-69720 | HIGH |
| api-gateway | ncurses-bin | 6.5+20250216-2 | — | CVE-2025-69720 | HIGH |
| api-gateway | perl-base | 5.40.1-6+deb13u1 | — | CVE-2026-9538 | HIGH |
| api-gateway | util-linux | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| api-gateway | util-linux | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| api-gateway | util-linux | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| api-gateway | util-linux | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| mock-car-rental | bsdutils | 1:2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| mock-car-rental | bsdutils | 1:2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| mock-car-rental | bsdutils | 1:2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| mock-car-rental | bsdutils | 1:2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| mock-car-rental | libacl1 | 2.3.2-2+b1 | — | CVE-2026-54369 | HIGH |
| mock-car-rental | libblkid1 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| mock-car-rental | libblkid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| mock-car-rental | libblkid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| mock-car-rental | libblkid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| mock-car-rental | liblastlog2-2 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| mock-car-rental | liblastlog2-2 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| mock-car-rental | liblastlog2-2 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| mock-car-rental | liblastlog2-2 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| mock-car-rental | libmount1 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| mock-car-rental | libmount1 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| mock-car-rental | libmount1 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| mock-car-rental | libmount1 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| mock-car-rental | libncursesw6 | 6.5+20250216-2 | — | CVE-2025-69720 | HIGH |
| mock-car-rental | libsmartcols1 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| mock-car-rental | libsmartcols1 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| mock-car-rental | libsmartcols1 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| mock-car-rental | libsmartcols1 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| mock-car-rental | libsystemd0 | 257.13-1~deb13u1 | — | CVE-2026-16742 | HIGH |
| mock-car-rental | libtinfo6 | 6.5+20250216-2 | — | CVE-2025-69720 | HIGH |
| mock-car-rental | libudev1 | 257.13-1~deb13u1 | — | CVE-2026-16742 | HIGH |
| mock-car-rental | libuuid1 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| mock-car-rental | libuuid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| mock-car-rental | libuuid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| mock-car-rental | libuuid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| mock-car-rental | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| mock-car-rental | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| mock-car-rental | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| mock-car-rental | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| mock-car-rental | mount | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| mock-car-rental | mount | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| mock-car-rental | mount | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| mock-car-rental | mount | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| mock-car-rental | ncurses-base | 6.5+20250216-2 | — | CVE-2025-69720 | HIGH |
| mock-car-rental | ncurses-bin | 6.5+20250216-2 | — | CVE-2025-69720 | HIGH |
| mock-car-rental | perl-base | 5.40.1-6+deb13u1 | — | CVE-2026-9538 | HIGH |
| mock-car-rental | util-linux | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| mock-car-rental | util-linux | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| mock-car-rental | util-linux | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| mock-car-rental | util-linux | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| data-pipeline | bsdutils | 1:2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| data-pipeline | bsdutils | 1:2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| data-pipeline | bsdutils | 1:2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| data-pipeline | bsdutils | 1:2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| data-pipeline | libacl1 | 2.3.2-2+b1 | — | CVE-2026-54369 | HIGH |
| data-pipeline | libblkid1 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| data-pipeline | libblkid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| data-pipeline | libblkid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| data-pipeline | libblkid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| data-pipeline | liblastlog2-2 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| data-pipeline | liblastlog2-2 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| data-pipeline | liblastlog2-2 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| data-pipeline | liblastlog2-2 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| data-pipeline | libmount1 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| data-pipeline | libmount1 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| data-pipeline | libmount1 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| data-pipeline | libmount1 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| data-pipeline | libncursesw6 | 6.5+20250216-2 | — | CVE-2025-69720 | HIGH |
| data-pipeline | libsmartcols1 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| data-pipeline | libsmartcols1 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| data-pipeline | libsmartcols1 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| data-pipeline | libsmartcols1 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| data-pipeline | libsystemd0 | 257.13-1~deb13u1 | — | CVE-2026-16742 | HIGH |
| data-pipeline | libtinfo6 | 6.5+20250216-2 | — | CVE-2025-69720 | HIGH |
| data-pipeline | libudev1 | 257.13-1~deb13u1 | — | CVE-2026-16742 | HIGH |
| data-pipeline | libuuid1 | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| data-pipeline | libuuid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| data-pipeline | libuuid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| data-pipeline | libuuid1 | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| data-pipeline | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| data-pipeline | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| data-pipeline | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| data-pipeline | login | 1:4.16.0-2+really2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| data-pipeline | mount | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| data-pipeline | mount | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| data-pipeline | mount | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| data-pipeline | mount | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| data-pipeline | ncurses-base | 6.5+20250216-2 | — | CVE-2025-69720 | HIGH |
| data-pipeline | ncurses-bin | 6.5+20250216-2 | — | CVE-2025-69720 | HIGH |
| data-pipeline | perl-base | 5.40.1-6+deb13u1 | — | CVE-2026-9538 | HIGH |
| data-pipeline | util-linux | 2.41.5-0+deb13u1 | — | CVE-2026-76642 | HIGH |
| data-pipeline | util-linux | 2.41.5-0+deb13u1 | — | CVE-2026-78408 | HIGH |
| data-pipeline | util-linux | 2.41.5-0+deb13u1 | — | CVE-2026-78409 | HIGH |
| data-pipeline | util-linux | 2.41.5-0+deb13u1 | — | CVE-2026-78410 | HIGH |
| postgres | stdlib | v1.24.6 | 1.24.13, 1.25.7, 1.26.0-rc.3 | CVE-2025-68121 | CRITICAL |
| postgres | stdlib | v1.24.6 | 1.24.12, 1.25.6 | CVE-2025-61726 | HIGH |
| postgres | stdlib | v1.24.6 | 1.24.11, 1.25.5 | CVE-2025-61729 | HIGH |
| postgres | stdlib | v1.24.6 | 1.25.8, 1.26.1 | CVE-2026-25679 | HIGH |
| postgres | stdlib | v1.24.6 | 1.25.11, 1.26.4 | CVE-2026-27145 | HIGH |
| postgres | stdlib | v1.24.6 | 1.25.9, 1.26.2 | CVE-2026-32280 | HIGH |
| postgres | stdlib | v1.24.6 | 1.25.9, 1.26.2 | CVE-2026-32281 | HIGH |
| postgres | stdlib | v1.24.6 | 1.25.9, 1.26.2 | CVE-2026-32283 | HIGH |
| postgres | stdlib | v1.24.6 | 1.25.10, 1.26.3 | CVE-2026-33811 | HIGH |
| postgres | stdlib | v1.24.6 | 1.25.10, 1.26.3 | CVE-2026-33814 | HIGH |
| postgres | stdlib | v1.24.6 | 1.25.13, 1.26.6, 1.27.0-rc.3 | CVE-2026-33818 | HIGH |
| postgres | stdlib | v1.24.6 | 1.25.10, 1.26.3 | CVE-2026-39820 | HIGH |
| postgres | stdlib | v1.24.6 | 1.25.13, 1.26.6, 1.27.0-rc.3 | CVE-2026-39821 | HIGH |
| postgres | stdlib | v1.24.6 | 1.25.12, 1.26.5, 1.27.0-rc.2 | CVE-2026-39822 | HIGH |
| postgres | stdlib | v1.24.6 | 1.25.10, 1.26.3 | CVE-2026-39836 | HIGH |
| postgres | stdlib | v1.24.6 | 1.25.10, 1.26.3 | CVE-2026-42499 | HIGH |
| postgres | stdlib | v1.24.6 | 1.25.11, 1.26.4 | CVE-2026-42504 | HIGH |
| postgres | stdlib | v1.24.6 | 1.25.13, 1.26.6, 1.27.0-rc.3 | CVE-2026-56853 | HIGH |
| postgres | stdlib | v1.24.6 | 1.25.13, 1.26.6, 1.27.0-rc.3 | CVE-2026-56858 | HIGH |
| postgres | stdlib | v1.24.6 | 1.25.13, 1.26.6, 1.27.0-rc.3 | CVE-2026-56859 | HIGH |
| postgres | stdlib | v1.24.6 | 1.25.13, 1.26.6, 1.27.0-rc.3 | CVE-2026-56860 | HIGH |
| postgres | stdlib | v1.24.6 | 1.25.13, 1.26.6, 1.27.0-rc.3 | CVE-2026-56862 | HIGH |
| postgres | stdlib | v1.24.6 | 1.26.9, 1.27.2 | CVE-2026-78667 | HIGH |
| postgres | stdlib | v1.24.6 | 1.26.9, 1.27.2 | CVE-2026-78669 | HIGH |
| postgres | stdlib | v1.24.6 | 1.26.9, 1.27.2 | CVE-2026-97031 | HIGH |
| redis | libcrypto3 | 3.3.7-r1 | 3.3.7-r2 | CVE-2026-84782 | HIGH |
| redis | libssl3 | 3.3.7-r1 | 3.3.7-r2 | CVE-2026-84782 | HIGH |
| hasura | libssl3t64 | 3.0.13-0ubuntu3.15 | 3.0.13-0ubuntu3.16 | CVE-2026-84782 | HIGH |
| hasura | openssl | 3.0.13-0ubuntu3.15 | 3.0.13-0ubuntu3.16 | CVE-2026-84782 | HIGH |
