FROM node:22-alpine AS build

WORKDIR /srv
COPY apps/dashboard/package.json apps/dashboard/package-lock.json /srv/apps/dashboard/
WORKDIR /srv/apps/dashboard
RUN npm ci

COPY apps/dashboard /srv/apps/dashboard
COPY packages/schemas/ts /srv/packages/schemas/ts

# Empty base: the browser calls same-origin /v1. Do not bake http://localhost:8000.
ARG VITE_API_BASE_URL=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# Local placeholder. Must match SWITCHBOARD_OPERATOR_TOKEN. Vite inlines it.
# Rebuild this image after changing it. This is not a production secret.
ARG VITE_OPERATOR_TOKEN=dev-operator-token
ENV VITE_OPERATOR_TOKEN=$VITE_OPERATOR_TOKEN

RUN npm run build

FROM nginx:1.27-alpine

COPY apps/dashboard/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /srv/apps/dashboard/dist /usr/share/nginx/html

EXPOSE 80
