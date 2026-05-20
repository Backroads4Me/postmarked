FROM node:22-alpine

ARG PUBLIC_GOOGLE_MAPS_API_KEY=
ARG PUBLIC_GOOGLE_MAPS_MAP_ID=

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci && npm cache clean --force

COPY . .
ENV PUBLIC_GOOGLE_MAPS_API_KEY=${PUBLIC_GOOGLE_MAPS_API_KEY}
ENV PUBLIC_GOOGLE_MAPS_MAP_ID=${PUBLIC_GOOGLE_MAPS_MAP_ID}
RUN npm run build

RUN chown -R node:node /app
USER node

EXPOSE 4321
CMD ["node", "./dist/server/entry.mjs"]
