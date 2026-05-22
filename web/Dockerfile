FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci && npm cache clean --force

COPY . .
RUN npm run build

RUN chown -R node:node /app
USER node

EXPOSE 4321
CMD ["node", "./dist/server/entry.mjs"]
