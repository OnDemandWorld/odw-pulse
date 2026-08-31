# ---- build stage -----------------------------------------------------------
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY . .
RUN npm run build

# ---- runtime stage ---------------------------------------------------------
FROM nginx:alpine

# The nginx docker entrypoint renders /etc/nginx/templates/*.template into
# /etc/nginx/conf.d/*.conf with envsubst at container start, which lets us
# point /api at the right upstream per environment (compose vs k8s).
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

ENV API_UPSTREAM=http://pulse-api:8000

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
