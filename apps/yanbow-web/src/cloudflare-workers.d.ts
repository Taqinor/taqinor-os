/**
 * Module virtuel fourni par l'exécution Cloudflare (workerd) et l'adaptateur
 * Astro au build — déclaré ici au plus juste pour `npm run check` (YBW54).
 */
declare module 'cloudflare:workers' {
  export const env: Record<string, unknown> | undefined;
  export function waitUntil(promise: Promise<unknown>): void;
}
