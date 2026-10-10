# syntax=docker/dockerfile:1
# Frontend de WanderSync. Contexto de build: raíz del repositorio (necesita el contrato GraphQL).

# --- Etapa 1: build (codegen desde el contrato + typecheck + Vite) -----------
FROM node:22.23.3-alpine AS build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY docs/contratos/schema.graphql /app/docs/contratos/schema.graphql
COPY frontend/ ./
RUN npm run build

# --- Etapa 2: Nginx sin root sirviendo los estáticos --------------------------
FROM nginxinc/nginx-unprivileged:1.31.6-alpine AS runtime
# Parches de seguridad de Alpine publicados después de la imagen base (p. ej. tiff, zlib).
USER root
RUN apk upgrade --no-cache
USER 101
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html
EXPOSE 8080
