// Revue chantier 26/10/2026 — appariement « Comparer » de ChantierPhotos.jsx
// (module à part : une page React n'exporte que des composants).

// Sujet d'un créneau : sa clé sans le suffixe de phase (`toiture_avant` →
// `toiture`) ; `null` pour une photo sans créneau.
const sujetCreneau = (cle) => (cle ? String(cle).replace(/_(avant|apres)$/, '') : null)

// Paires avant/après : même sujet de créneau d'abord (libellé « Toiture avant
// pose → Toiture après pose »), puis repli par ordre d'ajout sur le reste.
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
  const n = Math.min(avantRestants.length, apresLibres.length)
  for (let i = 0; i < n; i += 1) {
    pairs.push({ before: avantRestants[i], after: apresLibres[i], label: null })
  }
  return {
    pairs,
    surplusAvant: avantRestants.slice(n),
    surplusApres: apresLibres.slice(n),
  }
}
