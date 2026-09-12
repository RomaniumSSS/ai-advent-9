FROM node:22-bookworm-slim

ENV NODE_ENV=production
WORKDIR /app

COPY package.json package-lock.json ./
COPY api/package.json api/package.json
COPY zapier/package.json zapier/package.json
RUN npm ci --omit=dev --workspace api \
    && npm cache clean --force

COPY api api

USER node
EXPOSE 3100

CMD ["sh", "-c", "npm run migrate --workspace api && npm start --workspace api"]
