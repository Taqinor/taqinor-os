/* ============================================================================
   MAGASIN (XSTK1) — logique métier PURE (sans JSX, testable au node).
   ----------------------------------------------------------------------------
   Miroir front des choix de statut backend (FG319–322 :
   `models_bin_location.py`, `models_putaway.py`, `models_picklist.py`,
   `models_colisage.py`) + petits helpers de regroupement/tri réutilisés par
   les écrans. Aucune dépendance React : vérifié par les tests unitaires.
   `prix_achat` n'apparaît NULLE PART ici (jamais exposé par ces
   serializers) — rien à filtrer côté front, mais on ne l'introduit jamais.
   ========================================================================== */

export const PUTAWAY_STATUTS = {
  a_ranger: 'À ranger',
  range: 'Rangé',
}

export const PICKLIST_STATUTS = {
  emis: 'Émis',
  en_cours: 'En cours',
  termine: 'Terminé',
}

export const COLIS_STATUTS = {
  preparation: 'En préparation',
  controle: 'Contrôlé',
  expedie: 'Expédié',
}

// Options {value,label} pour un <Select>/<Segmented> à partir d'un map de choix.
export function optionsFrom(map) {
  return Object.entries(map).map(([value, label]) => ({ value, label }))
}

/**
 * Regroupe une liste plate de casiers (`BinLocation`, FG319) en arborescence
 * emplacement → zone → allée → [casiers], triée par `ordre` puis `code` (le
 * backend trie déjà ainsi, on préserve l'ordre reçu). Casiers archivés inclus
 * seulement si `includeArchived`. Tolère `bins` undefined/null.
 */
export function buildBinTree(bins = [], { includeArchived = false } = {}) {
  const list = Array.isArray(bins) ? bins : []
  const byEmplacement = new Map()

  for (const bin of list) {
    if (!bin) continue
    if (bin.archived && !includeArchived) continue
    const empId = bin.emplacement ?? '—'
    const empLabel = bin.emplacement_nom || `Emplacement ${empId}`
    if (!byEmplacement.has(empId)) {
      byEmplacement.set(empId, { id: empId, label: empLabel, zones: new Map() })
    }
    const emp = byEmplacement.get(empId)
    const zoneKey = bin.zone || '—'
    if (!emp.zones.has(zoneKey)) {
      emp.zones.set(zoneKey, { id: zoneKey, label: bin.zone || 'Sans zone', allees: new Map() })
    }
    const zone = emp.zones.get(zoneKey)
    const alleeKey = bin.allee || '—'
    if (!zone.allees.has(alleeKey)) {
      zone.allees.set(alleeKey, { id: alleeKey, label: bin.allee || 'Sans allée', bins: [] })
    }
    zone.allees.get(alleeKey).bins.push(bin)
  }

  return Array.from(byEmplacement.values()).map((emp) => ({
    ...emp,
    zones: Array.from(emp.zones.values()).map((zone) => ({
      ...zone,
      allees: Array.from(zone.allees.values()),
    })),
  }))
}

/**
 * Compte le nombre total de casiers dans une arborescence construite par
 * `buildBinTree`. Utile pour un résumé/KPI sans re-parcourir la liste brute.
 */
export function countBinsInTree(tree = []) {
  let total = 0
  for (const emp of tree || []) {
    for (const zone of emp.zones || []) {
      for (const allee of zone.allees || []) {
        total += (allee.bins || []).length
      }
    }
  }
  return total
}

/**
 * Trie les lignes d'un bon de prélèvement par ordre de casier (FG321 :
 * `ordre` recopié au moment de la génération). Les lignes sans casier
 * (`ordre` absent) passent en dernier, comme documenté côté backend.
 */
export function sortPickListLignesByBin(lignes = []) {
  return [...(lignes || [])].sort((a, b) => {
    const oa = a?.ordre ?? Number.MAX_SAFE_INTEGER
    const ob = b?.ordre ?? Number.MAX_SAFE_INTEGER
    if (oa !== ob) return oa - ob
    return (a?.id ?? 0) - (b?.id ?? 0)
  })
}

/** Progression d'un bon de prélèvement : lignes cochées / total. */
export function pickListProgress(lignes = []) {
  const list = Array.isArray(lignes) ? lignes : []
  const total = list.length
  const done = list.filter((l) => l?.preleve).length
  return { done, total, pct: total > 0 ? Math.round((done / total) * 100) : 0 }
}

/** Progression d'un colis : lignes contrôlées / total. */
export function colisProgress(lignes = []) {
  const list = Array.isArray(lignes) ? lignes : []
  const total = list.length
  const done = list.filter((l) => l?.controle_ok).length
  return { done, total, pct: total > 0 ? Math.round((done / total) * 100) : 0 }
}
