/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the order intake API, baked in at build time. */
  readonly VITE_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
