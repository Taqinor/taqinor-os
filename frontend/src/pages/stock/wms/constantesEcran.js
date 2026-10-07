/* ASTK220/ASTK224 — constantes d'écran partagées des écrans entrepôt. */

export const SELECT_CLS =
  'h-9 rounded-md border border-[var(--border)] bg-[var(--background)] px-2 text-sm'

/** Une réponse liste DRF (tableau nu ou page `{results}`) → tableau. */
export const enListe = (d) => (Array.isArray(d) ? d : d?.results ?? [])

/** Champ de formulaire contrôlé : `champDe(setter)(clé)` → onChange. */
export const champDe = (setter) => (cle) => (e) => setter((f) => ({ ...f, [cle]: e.target.value }))
