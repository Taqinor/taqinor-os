// ODY2 — Recherche et regroupement de la grille d'apps (logique PURE).
// ----------------------------------------------------------------------------
// Séparé de `pages/home/HomeMenu.jsx` pour deux raisons : la règle fast-refresh
// interdit d'exporter des non-composants à côté d'un composant, et cette
// logique se teste sans React (ni jsdom, ni store). Aucune dépendance.

/* normalise — comparaison insensible à la casse ET aux accents : « devis »
   trouve « Devis », « appro » trouve « Approvisionnement », « humaines »
   trouve « Ressources humaines ». `normalize('NFD')` + suppression des
   diacritiques : disponible partout (navigateurs cibles et jsdom). */
export function normalise(value) {
  return String(value ?? '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .trim()
}

/* filtrerApps — ne garde que les apps dont le libellé, la clé ou la
   description contient la requête normalisée. Requête vide = liste inchangée
   (jamais un tri surprise sur une grille au repos). */
export function filtrerApps(apps, query) {
  const q = normalise(query)
  if (!q) return apps ?? []
  return (apps ?? []).filter((app) => (
    normalise(app.label).includes(q)
    || normalise(app.key).includes(q)
    || normalise(app.description).includes(q)
  ))
}

/* grouperApps — construit les sections affichées ET l'ordre de parcours
   clavier. Au repos : Favoris → 3 Récents → Toutes les applications, chaque
   app dans UNE seule section (pas de doublon dans la navigation clavier).
   En recherche : une seule section « Résultats » — comme Odoo, on ne
   fragmente pas un résultat de frappe en trois blocs. */
export function grouperApps(apps, { query = '', pinned = [], recent = [] } = {}) {
  const filtrees = filtrerApps(apps, query)
  if (normalise(query)) {
    // Une recherche sans résultat ne renvoie AUCUNE section (et surtout pas une
    // section vide) : c'est ce qui laisse l'appelant afficher son état vide
    // « Aucun résultat » au lieu d'une grille blanche sans explication.
    return filtrees.length ? [{ id: 'resultats', titre: 'Résultats', apps: filtrees }] : []
  }
  const byKey = new Map(filtrees.map((a) => [a.key, a]))
  const favoris = pinned.map((k) => byKey.get(k)).filter(Boolean)
  const pris = new Set(favoris.map((a) => a.key))
  const recents = recent
    .map((k) => byKey.get(k))
    .filter((a) => a && !pris.has(a.key))
  recents.forEach((a) => pris.add(a.key))
  const reste = filtrees.filter((a) => !pris.has(a.key))
  return [
    { id: 'favoris', titre: 'Favoris', apps: favoris },
    { id: 'recents', titre: 'Récents', apps: recents },
    { id: 'toutes', titre: 'Toutes les applications', apps: reste },
  ].filter((s) => s.apps.length > 0)
}
