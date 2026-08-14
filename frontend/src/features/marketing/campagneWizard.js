/* NTMKT29 — logique pure du wizard « Créer une campagne » (4 étapes).
 *
 * Séparée du composant React pour rester testable sans montage (comme
 * `campagneDetail.js`). ``buildPayload`` produit EXACTEMENT la même forme
 * que `CampagneForm.jsx` `emptyForm()` — un abandon à mi-parcours ne crée
 * jamais rien : seul l'appel explicite à `campagnes.create()` sur l'étape 4
 * (confirmation) écrit quoi que ce soit.
 */

export const OBJECTIFS = [
  { key: 'promo', label: 'Promotion', canal: 'email' },
  { key: 'newsletter', label: 'Newsletter', canal: 'email' },
  { key: 'relance', label: 'Relance', canal: 'sms' },
  { key: 'evenement', label: 'Événement', canal: 'email' },
]

export function emptyWizardState() {
  return {
    etape: 1,
    objectif: '',
    canal: 'email',
    listes: [],
    segmentId: '',
    objet: '',
    corps: '',
    planifiee_le: '',
  }
}

/** Étape 1 — l'objectif choisi pré-remplit le canal par défaut. */
export function choisirObjectif(state, objectifKey) {
  const objectif = OBJECTIFS.find(o => o.key === objectifKey)
  return {
    ...state,
    objectif: objectifKey,
    canal: objectif ? objectif.canal : state.canal,
  }
}

/** True si l'étape courante a les champs requis pour avancer. */
export function etapeValide(state) {
  switch (state.etape) {
    case 1:
      return !!state.objectif
    case 2:
      // Audience : au moins une liste OU un segment choisi (NTMKT4/5).
      return state.listes.length > 0 || !!state.segmentId
    case 3:
      return !!state.canal && (!!state.objet || state.canal !== 'email')
    default:
      return true
  }
}

/** Construit le payload `Campagne` — MÊME FORME que `CampagneForm` `emptyForm()`. */
export function buildPayload(state) {
  return {
    nom: `${labelObjectif(state.objectif)} — ${new Date().toLocaleDateString('fr-FR')}`,
    canal: state.canal,
    objet: state.objet,
    corps: state.corps,
    planifiee_le: state.planifiee_le,
    listes: state.listes,
    variantes_langue: {},
    ab_test: {},
  }
}

export function labelObjectif(key) {
  return (OBJECTIFS.find(o => o.key === key) || {}).label || 'Campagne'
}
