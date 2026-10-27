// Revue chantier 26/10/2026 — appariement « Comparer » de ChantierPhotos.jsx
// (module à part : une page React n'exporte que des composants).

// Sujet d'un créneau : sa clé sans le suffixe de phase (`toiture_avant` →
// `toiture`) ; `null` pour une photo sans créneau.
// Alias : le créneau « avant » de la zone onduleur a pour pendant « après » la
// photo de l'onduleur installé.
const ALIAS_SUJET = { zone_onduleur: 'onduleur_installe' }
const sujetCreneau = (cle) => {
  if (!cle) return null
  const sujet = String(cle).replace(/_(avant|apres)$/, '')
  return ALIAS_SUJET[sujet] || sujet
}

// Paires avant/après : même sujet de créneau d'abord (libellé « Toiture avant
// pose → Toiture après pose »), puis repli par ordre d'ajout sur le reste
// (une photo sans créneau peut s'apparier avec n'importe quelle photo).
// Jamais une paire inventée : le surplus d'un côté reste listé à part.
export function apparierAvantApres(avant, apres) {
  const pairs = []
  const apresLibres = [...apres]
  const avantRestants = []
  for (const before of avant) {
    const sujet = sujetCreneau(before.slotCle)
    const idx = sujet
      ? apresLibres.findIndex((a) => sujetCreneau(a.slotCle) === sujet)
      : -1
    if (idx >= 0) {
      const [after] = apresLibres.splice(idx, 1)
      pairs.push({
        before, after,
        label: `${before.slotLibelle || before.slotCle} → ${after.slotLibelle || after.slotCle}`,
      })
    } else {
      avantRestants.push(before)
    }
  }
  // Repli par ordre d'ajout sur le reste : une paire est permise dès qu'AU
  // MOINS UN côté est sans créneau (une photo libre se range avec n'importe
  // quoi) ; deux photos AVEC créneau de sujets différents ne s'apparient
  // jamais. Pas de libellé : l'appariement est alors par ordre, pas par sujet.
  const prises = new Set()
  for (const before of avantRestants) {
    const idx = apresLibres.findIndex(
      (a) => !prises.has(a) && (!sujetCreneau(before.slotCle) || !sujetCreneau(a.slotCle)),
    )
    if (idx >= 0) {
      const after = apresLibres[idx]
      prises.add(before)
      prises.add(after)
      pairs.push({ before, after, label: null })
    }
  }
  return {
    pairs,
    surplusAvant: avantRestants.filter((p) => !prises.has(p)),
    surplusApres: apresLibres.filter((p) => !prises.has(p)),
  }
}
