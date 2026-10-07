/**
 * Installé avant chaque fichier de test (vitest.config.ts → setupFiles, YBW14).
 *
 * `fetch` global qui LÈVE : aucun test ne doit toucher le réseau par accident.
 * Un test qui a besoin de `fetch` le simule explicitement
 * (`vi.stubGlobal('fetch', vi.fn(...))` ou `vi.spyOn(globalThis, 'fetch')`).
 */
export class FetchNonSimule extends Error {
  constructor(cible: string) {
    super(`fetch non simulé dans un test : ${cible} — simuler explicitement (vi.stubGlobal / vi.spyOn)`);
    this.name = 'FetchNonSimule';
  }
}

function cibleDe(input: unknown): string {
  if (typeof input === 'string') return input;
  if (input instanceof URL) return input.href;
  if (input && typeof input === 'object' && 'url' in input) return String((input as { url: unknown }).url);
  return String(input);
}

const fetchInterdit = (input: unknown): Promise<Response> => {
  throw new FetchNonSimule(cibleDe(input));
};

globalThis.fetch = fetchInterdit as typeof fetch;
