FROM node:22-alpine

RUN addgroup -S appuser && adduser -S appuser -G appuser

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci && npm cache clean --force

COPY . .
RUN npm run build

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 4321
CMD ["node", "./dist/server/entry.mjs"]
