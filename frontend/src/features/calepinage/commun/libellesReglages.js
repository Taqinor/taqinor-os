/* ============================================================================
   LA table des libellés des réglages du calepinage (T4-X3-005) : ce que les
   écrans de saisie (Réglages simulation, Allées, Retraits, Norme) disent, repris
   tel quel par les écrans de LECTURE (Sources des paramètres, Bibliothèque).
   Une seule copie : un écran de lecture ne réécrit jamais un libellé de saisie.
   Les libellés de lestage, de simulation et de champs de préréglage ne sont pas
   ici : ils viennent du serveur (`registre`, `champs_preset` de
   `contract_samples/parametres_calepinage.json`).
   ========================================================================== */

/** Les normes électriques proposées (même liste que le champ « Norme applicable »). */
export const NORMES = [
  { valeur: '', libelle: 'Aucune — calculs dépendant d’une norme omis' },
  { valeur: 'nf_c_15_100', libelle: 'NF C 15-100 / UTE C 15-712-1 / IEC 62548 (jeu français)' },
]

//: `services/degagements.py::TYPES_ARETE`, dans le même ordre.
export const TYPES_ARETE = [
  ['faitage', 'Faîtage'], ['noue', 'Noue'], ['arretier', 'Arêtier'],
  ['egout', 'Égout'], ['rive', 'Rive'],
]

/** Les dégagements à valeur unique de la section « dégagements ». */
export const LIBELLES_DEGAGEMENTS = {
  retrait_rive_m: 'Retrait de rive',
  allee_technique_m: 'Largeur d’allée technique par défaut',
}

/** Les coefficients de la norme (`services/norme.py::COEFFICIENTS`). */
export const LIBELLES_COEFFICIENTS_NORME = {
  chute_dc_cible_pct: 'Chute de tension continue visée',
  chute_dc_max_pct: 'Chute de tension continue maximale',
  chute_ac_cible_pct: 'Chute de tension alternative visée',
  chute_ac_max_pct: 'Chute de tension alternative maximale',
  coeff_isc_dimensionnement: 'Coefficient de courant de court-circuit pour les câbles',
  section_min_dc_mm2: 'Section minimale des câbles continus (mm²)',
}
