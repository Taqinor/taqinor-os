import { libelleChamp } from '../equipements/FichesIncompletes.helpers'

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
  // Relecture E5 M3 — le matériel que la conception du lead retient (moteur unique, ACAL2013).
  if (materiel.provenance === 'moteur') return 'de la conception'
  if (materiel.provenance === 'explicite') return 'désigné'
  if (materiel.provenance === 'pose') return 'posé à l’étape Panneaux' // T4-B4-007 — le module choisi à l'étape 2
  return 'à désigner'
}

/** ACAL1740 (jumeau) — clés qui ne se déduisent pas du camelCase : le sens est celui de la table commune. */
const ALIAS_CLE = { vmaxDcV: 'v_max_abs' }

/** Le nom français d'un champ manquant servi par l'entrée électrique : la clé (camelCase ou snake_case) passe
    à la table UNIQUE de `FichesIncompletes.helpers.js::libelleChamp` — jamais une clé brute à l'écran. */
export function libelleChampManquant(cle, famille) {
  const brut = String(cle ?? '')
  const snake = ALIAS_CLE[brut] ?? brut.replace(/([a-z0-9])([A-Z])/g, '$1_$2').toLowerCase()
  return libelleChamp(snake, famille)
}
