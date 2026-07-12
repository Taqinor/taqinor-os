# backend/nginx/Dockerfile
FROM nginx:1.27-alpine

# Copie la configuration Nginx personnalisée
COPY nginx.conf /etc/nginx/nginx.conf

# VX200 — CSP par environnement : gettext fournit `envsubst`, utilise par
# docker-entrypoint.sh pour rendre security-headers.conf.template (l'origine
# MinIO réelle remplace le défaut dev http://localhost:9000, HSTS toujours
# émis) dans /etc/nginx/generated/, un chemin JAMAIS bind-monté (contrairement
# à nginx.conf lui-même, monté verbatim en lecture seule par docker-compose.yml).
RUN apk add --no-cache gettext
COPY security-headers.conf.template /etc/nginx/templates/security-headers.conf.template
COPY docker-entrypoint.sh /docker-entrypoint.sh
# `sed -i 's/\r$//'` : defense en profondeur — un checkout Windows avec
# core.autocrlf=true peut livrer ce fichier en CRLF, ce qui casserait le
# shebang au runtime (`/bin/sh^M: bad interpreter`). Rendu robuste quel que
# soit l'OS/la config git de qui build l'image (le blob commite reste LF,
# mais le build peut partir d'un working tree local sur une autre machine).
RUN sed -i 's/\r$//' /docker-entrypoint.sh && chmod +x /docker-entrypoint.sh

# Expose les ports HTTP et HTTPS
EXPOSE 80
EXPOSE 443

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
