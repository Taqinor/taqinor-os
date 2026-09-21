/* AOF180 — constantes + helpers PURS de l'écran « Équipements retenus ».
   Extraits d'EquipementsPage.jsx (react-refresh/only-export-components : un
   fichier de composant ne doit exporter QUE des composants).

   **Tout ce qui est ici est RELU dans une source serveur** par
   `EquipementsPage.test.jsx` : les rôles viennent de `EquipementAO.Role`, les
   gravités de `fabrique/approvisionnement.py`, les motifs de suspect de
   `fabrique/bascule_rapport.py`. Un vocabulaire d'écran inventé est
   exactement ce qui a produit le défaut du module AO : des écrans verts en
   test qui lisent des champs qu'aucun sérialiseur n'a jamais produits. */

// Miroir EXACT de `EquipementAO.Role` (apps/ao/models.py) : mêmes clés, MÊME
// ordre de déclaration — relu par la garde de contrat du test.
export const ROLES = [
  ['module', 'Modules'],
  ['onduleur', 'Onduleurs'],
  ['batterie', 'Batteries'],
  ['coffret_dc', 'Coffrets DC'],
  ['coffret_ac', 'Coffrets AC'],
  ['tgpv', 'TGPV'],
  ['cable', 'Câbles'],
  ['structure', 'Structures'],
  ['ems', 'EMS'],
  ['station_meteo', 'Stations météo'],
  ['afficheur', 'Afficheurs'],
  ['variateur', 'Variateurs'],
]

/* AOF119 — les TROIS gravités de `fabrique/approvisionnement.py`
   (`INFO` / `AVERTISSEMENT` / `BLOCAGE`), et rien d'autre.

   L'écran affichait auparavant `approvisionnement.statut` / `.libelle` /
   `.delai_jours` / `.aucun_appro_nouveau` : QUATRE clés qu'aucun module
   serveur ne produit. Le résultat n'était même pas un écran faux, c'était un
   écran MUET — un badge vide, et un argument commercial qui ne pouvait jamais
   s'afficher (`aucun_appro_nouveau === true` testé sur `undefined`). */
export const GRAVITE_TONE = {
  info: 'success',
  avertissement: 'warning',
  blocage: 'danger',
}

export const GRAVITE_LABEL = {
  info: 'Approvisionnement contrôlé',
  avertissement: 'Avertissement',
  blocage: 'Blocage',
}

/* AOF142 — `emplacements_suspects()` code son motif (`ancienne_reference` /
   `ancien_prix`) ; l'écran le TRADUIT au lieu d'afficher l'identifiant brut. */
export const MOTIF_SUSPECT_LABEL = {
  ancienne_reference: 'porte encore l’ancienne référence',
  ancien_prix: 'porte encore l’ancien prix',
}

/**
 * `rapport_bascule()` renvoie `modifies` comme une liste de CHAÎNES
 * (`['bordereau ligne 12']`, cf. `test_aof_bascule_suspects.py`). Le repli sur
 * `.emplacement` n'est pas une tolérance de contrat : c'est la garantie qu'une
 * divergence future se lise À L'ÉCRAN au lieu de faire planter tout le rapport
 * (« Objects are not valid as a React child » — le crash déjà constaté sur le
 * tableau de bord AO).
 */
export function libelleEmplacement(entree) {
  if (entree == null) return ''
  if (typeof entree === 'string') return entree
  return String(entree.emplacement ?? entree.libelle ?? JSON.stringify(entree))
}
