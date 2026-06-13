/**
 * Résolution de la clé MapTiler PUBLIQUE exposée par /api/roof-config.
 *
 * Module pur (aucun import Cloudflare) → testé unitairement.
 *
 * Deux sources possibles, par robustesse :
 *  - RUNTIME : variable/secret Worker (cf.env.PUBLIC_MAPTILER_KEY) — modifiable
 *    sans rebuild ;
 *  - BUILD : variable de build Cloudflare, inlinée par Vite dans
 *    import.meta.env.PUBLIC_MAPTILER_KEY au moment du build.
 *
 * Le bug du 13/06/2026 : la clé était posée en variable de BUILD, mais
 * l'endpoint ne lisait que le runtime → toujours vide → repli affiché à tort.
 * On accepte désormais l'une OU l'autre ; le repli ne reste légitime que si
 * AUCUNE des deux n'apporte de clé.
 */
export function resolveMaptilerKey(runtime?: string, build?: string): string {
  return (runtime?.trim() || build?.trim() || '');
}
