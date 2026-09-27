FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS build
WORKDIR /app
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_TURNSTILE_SITE_KEY
ARG NEXT_PUBLIC_STORAGE_ORIGIN
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL \
    NEXT_PUBLIC_TURNSTILE_SITE_KEY=$NEXT_PUBLIC_TURNSTILE_SITE_KEY \
    NEXT_PUBLIC_STORAGE_ORIGIN=$NEXT_PUBLIC_STORAGE_ORIGIN \
    NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS run
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN addgroup -S lookbook && adduser -S lookbook -G lookbook
COPY --from=build --chown=lookbook:lookbook /app/.next/standalone ./
COPY --from=build --chown=lookbook:lookbook /app/.next/static ./.next/static
COPY --from=build --chown=lookbook:lookbook /app/public ./public
USER lookbook
EXPOSE 3000
CMD ["node", "server.js"]
