import { defineConfig } from "orval";

// Contract-first: the typed client + Zod schemas are GENERATED from the backend
// OpenAPI — never hand-written (CLAUDE.md golden rule 5). Until backend resource
// endpoints land, `npm run generate:api` is effectively a no-op (only /health).
//
// Input points at the running backend's OpenAPI. Override with ORVAL_INPUT
// (e.g. a committed openapi.json) in CI where the backend isn't running.
const input = process.env.ORVAL_INPUT ?? "http://localhost:8000/openapi.json";

export default defineConfig({
  testsPlatform: {
    input,
    output: {
      mode: "tags-split",
      target: "src/api/generated/endpoints",
      schemas: "src/api/generated/model",
      client: "react-query",
      clean: true,
    },
  },
  testsPlatformZod: {
    input,
    output: {
      mode: "tags-split",
      target: "src/api/generated/zod",
      client: "zod",
      clean: true,
    },
  },
});
