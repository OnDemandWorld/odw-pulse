/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Optional absolute API base URL; defaults to the relative "/api/v1". */
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
