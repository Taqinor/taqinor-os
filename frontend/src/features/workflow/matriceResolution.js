/* ============================================================================
   NTWFL32 — logique de résolution PURE utilisée par `MatriceSimulator.jsx`.
   ----------------------------------------------------------------------------
   Port fidèle de `core.selectors.resoudre_matrice`
   (backend/django_core/core/selectors.py) : même couverture (`couvre`), même
   départage de spécificité (département ciblé > intervalle borné le plus
   étroit > id), même comportement quand aucune ligne active ne couvre le
   triplet (aucune chaîne — jamais une valeur inventée). Fichier séparé du
   composant (aucun export non-composant dans un fichier de composant —
   react-refresh/only-export-components).
   ========================================================================== */

// Port de `MatriceApprobation.couvre` (core/models.py).
function couvre(regle, montant, departement) {
  if (regle.departement) {
    if (!departement) return false
    if (regle.departement.trim().toLowerCase() !== String(departement).trim().toLowerCase()) {
      return false
    }
  }
  if (montant === null) {
    return regle.montant_min == null && regle.montant_max == null
  }
  const n = Number(montant)
  if (!Number.isFinite(n)) return false
  if (regle.montant_min != null && n < Number(regle.montant_min)) return false
  if (regle.montant_max != null && n > Number(regle.montant_max)) return false
  return true
}

// Port de `MatriceApprobation.largeur_intervalle`.
function largeurIntervalle(regle) {
  if (regle.montant_min == null || regle.montant_max == null) return null
  return Number(regle.montant_max) - Number(regle.montant_min)
}

// Port de `core.selectors.resoudre_matrice` : la ligne la plus SPÉCIFIQUE
// gagne — département+montant > département seul > montant seul > défaut.
export function resoudreMatriceSimulee(regles, typeObjet, montant, departement) {
  if (!typeObjet) return null
  const candidats = (regles || []).filter(
    (r) => r.actif && r.type_objet === typeObjet && couvre(r, montant, departement),
  )
  if (candidats.length === 0) return null

  const cle = (r) => {
    const departementSpecifique = r.departement ? 1 : 0
    const largeur = largeurIntervalle(r)
    const intervalleBorne = largeur !== null ? 1 : 0
    const largeurTri = largeur !== null ? -largeur : 0
    return [departementSpecifique, intervalleBorne, largeurTri, r.id]
  }

  const trie = [...candidats].sort((a, b) => {
    const ka = cle(a)
    const kb = cle(b)
    for (let i = 0; i < ka.length; i += 1) {
      if (ka[i] !== kb[i]) return kb[i] - ka[i] // reverse=True (le plus grand gagne)
    }
    return 0
  })
  return trie[0]
}
