# Claude Live relay. Stateless, no project data stored. One instance only (the plugin socket lives in memory).
FROM node:22-alpine
ENV NODE_ENV=production
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force
COPY relay.js ./
USER node
EXPOSE 8080
ENV PORT=8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
CMD ["node", "relay.js"]
