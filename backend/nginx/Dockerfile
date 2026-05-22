# backend/nginx/Dockerfile
FROM nginx:alpine

# Copie la configuration Nginx personnalisée
COPY nginx.conf /etc/nginx/nginx.conf

# Expose les ports HTTP et HTTPS
EXPOSE 80
EXPOSE 443

CMD ["nginx", "-g", "daemon off;"]
