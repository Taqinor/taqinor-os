// PV8 — logique PURE de complétude de fiche technique, hors de tout fichier
// composant : react-refresh/only-export-components interdit d'exporter des
// fonctions depuis un fichier de composants — la logique vit ici, le Badge
// (composant) reste dans CatalogueTable.jsx.
/* PV8 — Badge « complétude datasheet » : complet / partiel / absent, calculé
   à partir de la FicheTechnique (PV5) d'un produit et de son `type_fiche`.
   Champs requis alignés sur ce que le dimensionnement/calepinage consomme
   réellement (`apps.stock.selectors.specs_for_produit` côté backend) — pas
   un champ décoratif de plus. Un type non renseigné (fiche historique
   `type_fiche=''`, ou `autre`) est traité comme ABSENT : on ne peut pas dire
   ce qui manque sans savoir de quel bloc il s'agit. Exporté pour être
   réutilisé tel quel par ProduitDetail.jsx (fiche produit, même règle). */
export const FICHE_ABSENTE = 'absent'
export const FICHE_PARTIELLE = 'partiel'
export const FICHE_COMPLETE = 'complet'

export const CHAMPS_REQUIS_PAR_TYPE = {
  module: [
    ['longueur_mm', 'longueur'], ['largeur_mm', 'largeur'],
    ['pmax_wc', 'Pmax'], ['voc_v', 'Voc'], ['vmp_v', 'Vmp'],
    ['isc_a', 'Isc'], ['imp_a', 'Imp'],
    ['temp_coeff_pmax_pct_c', 'coefficient de température Pmax'],
  ],
  onduleur: [
    ['ond_n_mppt', 'nombre de MPPT'],
    ['ond_mppt_v_min', 'tension MPPT min'], ['ond_mppt_v_max', 'tension MPPT max'],
    ['ond_ac_kw', 'puissance AC'], ['ond_phases', 'phases'],
  ],
  batterie: [
    ['bat_kwh_nominal', 'capacité nominale'], ['bat_dod_pct', 'profondeur de décharge'],
  ],
}

export function completudeFiche(fiche) {
  const champs = fiche ? CHAMPS_REQUIS_PAR_TYPE[fiche.type_fiche] : null
  if (!champs) return { statut: FICHE_ABSENTE, manquants: [] }
  const manquants = champs
    .filter(([k]) => fiche[k] === null || fiche[k] === undefined || fiche[k] === '')
    .map(([, label]) => label)
  if (manquants.length === 0) return { statut: FICHE_COMPLETE, manquants: [] }
  // Un type déclaré mais AUCUN champ requis rempli = fiche vide : « absente »,
  // pas « partielle » — le badge ne doit jamais faire croire qu'un début de
  // datasheet existe quand il n'y a rien.
  if (manquants.length === champs.length) return { statut: FICHE_ABSENTE, manquants }
  return { statut: FICHE_PARTIELLE, manquants }
}

export const TON_FICHE = {
  [FICHE_COMPLETE]: 'success', [FICHE_PARTIELLE]: 'warning', [FICHE_ABSENTE]: 'neutral',
}
export const LABEL_FICHE = {
  [FICHE_COMPLETE]: 'Fiche complète', [FICHE_PARTIELLE]: 'Fiche partielle', [FICHE_ABSENTE]: 'Fiche absente',
}
