# syntax=docker/dockerfile:1.7
# =============================================================================
# OmniProctor WebClient frontend - multi-stage build.
#
# Stage 1 builds the React/Vite SPA into a static bundle.
# Stage 2 serves the bundle from nginx and writes a runtime /config.js so the
# same image can be deployed to dev / staging / production by only changing
# environment variables (no rebuild required).
#
# Build:    docker build -t omniproctor-frontend:latest .
# Run:      docker run -p 80:80 \
#               -e API_BASE_URL=https://omniproctor.example.com/api/v1 \
#               omniproctor-frontend:latest
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: build static assets
# -----------------------------------------------------------------------------
FROM node:20-alpine AS builder

WORKDIR /app

# Install deps first so the cache is reused when only source changes.
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund

# Vite reads VITE_* vars at build time. We deliberately leave
# VITE_API_BASE_URL unset here - the runtime entrypoint in stage 2 writes
# window.__APP_CONFIG__ which is what the SPA actually reads. Setting it at
# build time would lock the URL into the bundle and force per-environment
# rebuilds.
COPY . .
RUN npm run build

# -----------------------------------------------------------------------------
# Stage 2: serve via nginx
# -----------------------------------------------------------------------------
FROM nginx:1.27-alpine AS runtime

# Drop the default site config; ours handles SPA fallback + security headers.
RUN rm /etc/nginx/conf.d/default.conf

COPY nginx.conf /etc/nginx/conf.d/omniproctor.conf
COPY docker-entrypoint.sh /docker-entrypoint.d/40-write-runtime-config.sh

# nginx:alpine ships with /docker-entrypoint.d/ wired into its entrypoint,
# so just making the script executable is enough - it runs before nginx
# starts on every container start.
RUN chmod +x /docker-entrypoint.d/40-write-runtime-config.sh

COPY --from=builder /app/dist /usr/share/nginx/html

# Sensible runtime defaults; override with `-e` or compose `environment:`.
ENV API_BASE_URL="" \
    APP_NAME="OmniProctor"

EXPOSE 80

# nginx:alpine's stock CMD already runs `nginx -g 'daemon off;'`; keep it.
