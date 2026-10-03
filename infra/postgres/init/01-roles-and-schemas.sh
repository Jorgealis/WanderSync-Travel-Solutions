#!/bin/bash
# =============================================================================
# Inicialización de PostgreSQL — se ejecuta UNA sola vez, cuando el volumen
# `pgdata` está vacío (comportamiento estándar de la imagen oficial).
# Para re-ejecutarlo: docker compose down -v && docker compose up
#
# Crea (ver docs/contratos/modelo-datos.md, "Matriz de privilegios"):
#   - un usuario y un esquema por servicio (el usuario es dueño de su esquema);
#   - el usuario `ingest` (Dask) y `hasura_ro` (Hasura), con USAGE en los
#     esquemas de catálogo. Los GRANT a nivel de tabla/columna se hacen en las
#     migraciones Alembic de cada servicio, porque las tablas aún no existen;
#   - las bases auxiliares de Hasura (metadata) y Prefect.
# =============================================================================
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v db="$POSTGRES_DB" \
  -v flights_user="$FLIGHTS_DB_USER" -v flights_pass="$FLIGHTS_DB_PASSWORD" \
  -v hotels_user="$HOTELS_DB_USER"   -v hotels_pass="$HOTELS_DB_PASSWORD" \
  -v cars_user="$CARS_DB_USER"       -v cars_pass="$CARS_DB_PASSWORD" \
  -v orders_user="$ORDERS_DB_USER"   -v orders_pass="$ORDERS_DB_PASSWORD" \
  -v auth_user="$AUTH_DB_USER"       -v auth_pass="$AUTH_DB_PASSWORD" \
  -v ingest_user="$INGEST_DB_USER"   -v ingest_pass="$INGEST_DB_PASSWORD" \
  -v hasura_ro_user="$HASURA_RO_DB_USER" -v hasura_ro_pass="$HASURA_RO_DB_PASSWORD" \
  -v hasura_meta_db="$HASURA_METADATA_DB" \
  -v hasura_meta_user="$HASURA_METADATA_DB_USER" -v hasura_meta_pass="$HASURA_METADATA_DB_PASSWORD" \
  -v prefect_db="$PREFECT_DB" \
  -v prefect_user="$PREFECT_DB_USER" -v prefect_pass="$PREFECT_DB_PASSWORD" \
<<'EOSQL'
  -- ---------------------------------------------------------------------------
  -- Endurecimiento base: nadie se conecta ni crea objetos salvo que se le permita
  -- ---------------------------------------------------------------------------
  REVOKE ALL ON DATABASE :"db" FROM PUBLIC;
  REVOKE ALL ON SCHEMA public FROM PUBLIC;

  -- ---------------------------------------------------------------------------
  -- Usuarios de los microservicios: cada uno es dueño de su esquema
  -- ---------------------------------------------------------------------------
  CREATE ROLE :"flights_user" LOGIN PASSWORD :'flights_pass';
  CREATE ROLE :"hotels_user"  LOGIN PASSWORD :'hotels_pass';
  CREATE ROLE :"cars_user"    LOGIN PASSWORD :'cars_pass';
  CREATE ROLE :"orders_user"  LOGIN PASSWORD :'orders_pass';
  CREATE ROLE :"auth_user"    LOGIN PASSWORD :'auth_pass';

  CREATE SCHEMA flights AUTHORIZATION :"flights_user";
  CREATE SCHEMA hotels  AUTHORIZATION :"hotels_user";
  CREATE SCHEMA cars    AUTHORIZATION :"cars_user";
  CREATE SCHEMA orders  AUTHORIZATION :"orders_user";
  CREATE SCHEMA auth    AUTHORIZATION :"auth_user";

  -- ---------------------------------------------------------------------------
  -- Usuarios transversales: ingesta (Dask) y lectura de catálogo (Hasura)
  -- ---------------------------------------------------------------------------
  CREATE ROLE :"ingest_user"    LOGIN PASSWORD :'ingest_pass' CONNECTION LIMIT 40;
  CREATE ROLE :"hasura_ro_user" LOGIN PASSWORD :'hasura_ro_pass' CONNECTION LIMIT 20;

  GRANT USAGE ON SCHEMA flights, hotels, cars TO :"ingest_user", :"hasura_ro_user";

  -- hasura_ro es de solo lectura incluso si alguien le concede algo por error.
  ALTER ROLE :"hasura_ro_user" SET default_transaction_read_only = on;

  GRANT CONNECT ON DATABASE :"db" TO
    :"flights_user", :"hotels_user", :"cars_user", :"orders_user", :"auth_user",
    :"ingest_user", :"hasura_ro_user";

  -- ---------------------------------------------------------------------------
  -- Bases auxiliares: metadata de Hasura y estado de Prefect
  -- ---------------------------------------------------------------------------
  CREATE ROLE :"hasura_meta_user" LOGIN PASSWORD :'hasura_meta_pass';
  CREATE DATABASE :"hasura_meta_db" OWNER :"hasura_meta_user";
  REVOKE ALL ON DATABASE :"hasura_meta_db" FROM PUBLIC;
  GRANT CONNECT ON DATABASE :"hasura_meta_db" TO :"hasura_meta_user";

  CREATE ROLE :"prefect_user" LOGIN PASSWORD :'prefect_pass';
  CREATE DATABASE :"prefect_db" OWNER :"prefect_user";
  REVOKE ALL ON DATABASE :"prefect_db" FROM PUBLIC;
  GRANT CONNECT ON DATABASE :"prefect_db" TO :"prefect_user";

  -- Extensiones que Hasura y Prefect crean al arrancar; se crean aquí como
  -- superusuario para no depender de los permisos de sus usuarios.
  \connect :"hasura_meta_db"
  CREATE EXTENSION IF NOT EXISTS pgcrypto;
  \connect :"prefect_db"
  CREATE EXTENSION IF NOT EXISTS pg_trgm;
EOSQL

echo "[init] roles, schemas and auxiliary databases created"
