FROM node:22-alpine

WORKDIR /srv
COPY apps/dashboard/package.json apps/dashboard/package-lock.json /srv/apps/dashboard/
WORKDIR /srv/apps/dashboard
RUN npm ci

COPY apps/dashboard /srv/apps/dashboard
COPY packages/schemas/ts /srv/packages/schemas/ts

ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build
EXPOSE 5173
CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "5173"]
