// NTUX21 — ordre d'affichage des VUES PERSONNELLES (ViewsManagerPopover),
// persisté en localStorage — jamais côté serveur (contrairement aux favoris,
// NTUX12, dont l'ordre EST persisté côté serveur via `ordre`/`reordonner/`).
// Une clé PAR écran (comme la préférence `useServerSavedViews.js`), jamais
// une clé globale : l'ordre choisi sur /crm/leads n'a pas de sens sur
// /ventes/devis. Best-effort, jamais bloquant (SSR/quota).
const PREFIX = 'taqinor.uxviews.ordrePerso.'

function key(ecran) {
  return `${PREFIX}${ecran}`
}

/** Liste d'ids (dans l'ordre choisi) pour `ecran`, ou `[]` si rien d'enregistré. */
export function readOrder(ecran) {
  try {
    const raw = localStorage.getItem(key(ecran))
    const arr = raw ? JSON.parse(raw) : []
    return Array.isArray(arr) ? arr : []
  } catch {
    return []
  }
}

export function writeOrder(ecran, ids) {
  try {
    localStorage.setItem(key(ecran), JSON.stringify(ids))
  } catch {
    // localStorage indisponible (SSR/quota) — best-effort, jamais bloquant.
  }
}

/**
 * Applique l'ordre mémorisé à `list` (tableau d'objets `{id, ...}`) : les
 * éléments connus de `order` viennent d'abord (dans cet ordre), puis tout
 * élément NOUVEAU (jamais vu, ex. une vue créée depuis) à la suite dans son
 * ordre serveur d'origine — jamais un élément perdu ou dupliqué.
 */
export function applyOrder(list, order) {
  if (!order.length) return list
  const parId = new Map(list.map((item) => [String(item.id), item]))
  const ordonnes = []
  const vus = new Set()
  for (const id of order) {
    const item = parId.get(String(id))
    if (item && !vus.has(String(id))) {
      ordonnes.push(item)
      vus.add(String(id))
    }
  }
  for (const item of list) {
    if (!vus.has(String(item.id))) ordonnes.push(item)
  }
  return ordonnes
}
