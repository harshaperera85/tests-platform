import { defineConfig } from "orval";

// Contract-first: the typed client + Zod schemas are GENERATED from the backend
// OpenAPI — never hand-written (CLAUDE.md golden rule 5).
//
// Default input is the committed snapshot (./openapi.json) so generation is
// reproducible without a running backend. Override with ORVAL_INPUT to point at a
// live server, e.g.
//   ORVAL_INPUT=http://localhost:8000/openapi.json npm run generate:api
const input = process.env.ORVAL_INPUT ?? "./openapi.json";

export default defineConfig({
  testsPlatform: {
    input,
    output: {
      mode: "tags-split",
      target: "src/api/generated/endpoints",
      schemas: "src/api/generated/model",
      client: "react-query",
      clean: true,
      override: {
        // All HTTP goes through one configured axios instance (baseURL, cancel).
        mutator: { path: "./src/api/mutator.ts", name: "customInstance" },
      },
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
