/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL for the API. Empty -> same-origin (Vite proxy forwards /api). */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
