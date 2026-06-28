FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci && npm cache clean --force

COPY . .
RUN npm run build

# Stamp the build version into the image so the running container can report it
# (the root VERSION file isn't in this build context, so it's passed as an arg).
ARG VERSION=dev
LABEL org.opencontainers.image.version="$VERSION"
ENV APP_VERSION="$VERSION"
RUN echo "$VERSION" > /app/VERSION

RUN chown -R node:node /app
USER node

EXPOSE 4321
CMD ["node", "./dist/server/entry.mjs"]
