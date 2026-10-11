/* Réglages C&I / seuils 82-21 de l'écran Paramètres › Avancé : constantes et
   fonctions pures (hors composants, cf. AvanceSection.jsx). */

export const CHAMPS_SEUILS_8221 = [
  { champ: 'seuil_regime_declaration_kwc', cle: 'declaration',
    label: 'Surcharge du seuil « Déclaration » (kW)' },
  { champ: 'seuil_regime_anre_kwc', cle: 'autorisation',
    label: 'Surcharge du seuil « Autorisation » (kW)' },
]
const AIDE_SANS_VERDICT = "Vide : l'écart sera affiché sans verdict."
const AIDE_NON_ENGAGE = 'Vide : non engagé.'
export const REGLAGES_CI_NOMBRES = [
  { champ: 'recette_ecart_pmax_pct', label: 'Écart de recette toléré sur la puissance crête (%)', aide: AIDE_SANS_VERDICT },
  { champ: 'recette_echantillon_iv_pct', label: 'Échantillon de courbes I-V à la recette (%)', aide: AIDE_SANS_VERDICT },
  { champ: 'recette_pr_seuil_interne', label: 'Seuil interne de performance ratio (%) — alerte interne', aide: AIDE_SANS_VERDICT },
  { champ: 'delai_intervention_suivi_heures', label: "Délai d'intervention du suivi (heures)", aide: AIDE_NON_ENGAGE },
  { champ: 'delai_reception_definitive_mois', label: 'Délai de réception définitive (mois)', aide: AIDE_NON_ENGAGE },
]
export const REGLAGES_CI_BOOLEENS = [
  { champ: 'securite_obligatoire_avant_demarrage', label: 'Contrôle de sécurité obligatoire avant démarrage' },
  { champ: 'garantie_production_autorisee', label: 'Garantie de production autorisée' },
]
export const CHAMP_GARANTIE_VALIDATION = 'garantie_production_validation'
export const MESSAGE_GARANTIE_SANS_VALIDATION = (
  "La garantie de production ne peut être autorisée qu'avec sa validation "
  + 'écrite (assureur ou juriste : qui a validé et quand).')

export const versTexte = (v) => (v === null || v === undefined ? '' : String(v))
const nombreOuNul = (v) => {
  if (v === null || v === undefined) return null
  const t = String(v).trim().replace(',', '.')
  return t === '' ? null : t
}

/** Profil serveur → état du formulaire (vide = '' / false ; aucun défaut). */
export function formReglagesCi(profile = {}) {
  const p = profile || {}
  return {
    ...Object.fromEntries(CHAMPS_SEUILS_8221.map(({ champ }) => [champ, versTexte(p[champ])])),
    ...Object.fromEntries(REGLAGES_CI_NOMBRES.map(({ champ }) => [champ, versTexte(p[champ])])),
    ...Object.fromEntries(REGLAGES_CI_BOOLEENS.map(({ champ }) => [champ, !!p[champ]])),
    [CHAMP_GARANTIE_VALIDATION]: versTexte(p[CHAMP_GARANTIE_VALIDATION]),
  }
}

/** État du formulaire → PATCH : vide = null, tapé = tel quel. */
export function payloadReglagesCi(form = {}) {
  const f = form || {}
  return {
    ...Object.fromEntries(CHAMPS_SEUILS_8221.map(({ champ }) => [champ, nombreOuNul(f[champ])])),
    ...Object.fromEntries(REGLAGES_CI_NOMBRES.map(({ champ }) => [champ, nombreOuNul(f[champ])])),
    ...Object.fromEntries(REGLAGES_CI_BOOLEENS.map(({ champ }) => [champ, !!f[champ]])),
    [CHAMP_GARANTIE_VALIDATION]: versTexte(f[CHAMP_GARANTIE_VALIDATION]).trim(),
  }
}

/** Erreur locale de la garantie (même règle que le serveur), ou ''. */
export function erreurGarantieLocale(form = {}) {
  const f = form || {}
  return f.garantie_production_autorisee
    && versTexte(f[CHAMP_GARANTIE_VALIDATION]).trim() === ''
    ? MESSAGE_GARANTIE_SANS_VALIDATION : ''
}
