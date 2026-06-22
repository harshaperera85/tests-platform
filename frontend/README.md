# Frontend — Tests Platform

React + TypeScript + Vite + Tailwind + React Query, with **Orval + Zod** for the
generated, typed API client.

```bash
npm install
npm run dev            # http://localhost:5173
npm run generate:api   # regenerate client from backend OpenAPI (needs backend up)
npm run lint           # tsc --noEmit
```

The API client under `src/api/generated/` is generated from the backend OpenAPI —
never hand-written (CLAUDE.md golden rule 5). It is gitignored and regenerated on
contract change. Phase 0 has only `/health`, so generation is effectively a no-op.
