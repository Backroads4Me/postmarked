FROM node:22-alpine AS runtime

WORKDIR /app

# For dev, we just mount the code. For prod this would build and serve.
# Since Phase 0 is foundation, we'll install deps and start dev server if command is not overridden.
COPY package.json package-lock.json ./
RUN npm install

COPY . .

EXPOSE 4321
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
