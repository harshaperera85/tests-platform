# Dev image for the Vite frontend. Compose mounts the source and runs the dev
# server with HMR. A production build would use a multi-stage build + nginx.
FROM node:20-slim

WORKDIR /app

COPY package.json package-lock.json ./
# Reproducible install from the committed lockfile.
RUN npm ci

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host"]
