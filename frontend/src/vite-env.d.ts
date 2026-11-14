/// <reference types="vite/client" />

// stylis ships without type definitions; only `prefixer` is used (src/main.tsx).
declare module 'stylis' {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  export const prefixer: any;
}
