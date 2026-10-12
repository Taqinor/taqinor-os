// ENF22 — helpers extraits de MaterielElectrique.jsx (react-refresh/only-export-components) : le fichier composant n'exporte plus que des composants.

/** Les trois rôles : clé du corps posté, clé de `materiel`, clé de `candidats`, libellé. */
export const ROLES = [
  { role: 'module', champ: 'module_produit', candidats: 'modules', libelle: 'Module photovoltaïque' },
  { role: 'onduleur', champ: 'onduleur_produit', candidats: 'onduleurs', libelle: 'Onduleur' },
  { role: 'optimiseur', champ: 'optimiseur_produit', candidats: 'optimiseurs', libelle: 'Optimiseur (facultatif)' },
]

/** La provenance rendue en FRANÇAIS ; `null` = rien de désigné. */
export function libelleProvenance(materiel) {
  if (!materiel) return 'à désigner'
  if (materiel.provenance === 'devis') return 'ligne du devis'
  if (materiel.provenance === 'explicite') return 'désigné'
  return 'à désigner'
}
