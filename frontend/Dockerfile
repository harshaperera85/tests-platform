# Dev image for the Vite frontend. Compose mounts the source and runs the dev
# server with HMR. A production build would use a multi-stage build + nginx.
FROM node:20-slim

WORKDIR /app

COPY package.json ./
# No lockfile committed yet (Phase 0); install resolves from package.json.
RUN npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host"]
