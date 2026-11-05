
# Étape 1 : Build React
FROM node:24-alpine AS build

WORKDIR /app

# Copier les dépendances Node.js
COPY package.json package-lock.json ./

# Installer les dépendances
RUN npm ci

# Copier le code frontend
COPY . .

# Construire l'application React
RUN npm run build

# Étape 2 : Nginx
FROM nginx:stable-alpine

# Copier l'application compilée
COPY --from=build /app/dist /usr/share/nginx/html

# Copier la configuration Nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Exposer le port HTTP
EXPOSE 80

# Démarrer Nginx
CMD ["nginx", "-g", "daemon off;"]
