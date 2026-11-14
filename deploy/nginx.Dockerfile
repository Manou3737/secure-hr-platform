FROM nginx:1.28-alpine

# Mettre à jour Alpine et supprimer les modules Nginx inutilisés.
# Notre reverse proxy utilise uniquement les fonctions Nginx standard.
RUN apk update \
    && apk del \
        nginx-module-acme \
        nginx-module-geoip \
        nginx-module-image-filter \
        nginx-module-njs \
        nginx-module-xslt \
    && sed -i 's/^nginx=.*/nginx/' /etc/apk/world \
    && apk upgrade --no-cache \
    && mkdir -p /run/nginx \
    && nginx -t

# Vérifier périodiquement que Nginx répond.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/api/schema/ || exit 1
