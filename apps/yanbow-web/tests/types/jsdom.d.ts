/**
 * Déclaration minimale de `jsdom` pour les tests (le paquet ne livre pas ses
 * types ; on évite une dépendance @types de plus). Seule l'API utilisée ici.
 */
declare module 'jsdom' {
  export class JSDOM {
    constructor(html?: string, options?: Record<string, unknown>);
    readonly window: Window & typeof globalThis;
  }
}
