# Claude Live relay. Stateless, no project data stored. One instance only (the plugin socket lives in memory).
ARG BASE=node:22-alpine
FROM ${BASE}
ENV NODE_ENV=production
WORKDIR /app
COPY package.json package-lock.json ./
# Optional: behind a TLS-inspecting proxy, build with `--secret id=cabundle,src=/path/ca.pem` (not stored in the image).
RUN --mount=type=secret,id=cabundle,required=false \
    if [ -f /run/secrets/cabundle ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/cabundle; fi; \
    npm ci --omit=dev && npm cache clean --force
COPY relay.js ./
USER node
EXPOSE 8080
ENV PORT=8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
CMD ["node", "relay.js"]
