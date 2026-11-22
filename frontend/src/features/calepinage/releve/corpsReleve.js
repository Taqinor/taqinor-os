/* ============================================================================
   LE CORPS DU RELEVÉ TERRAIN — partagé par le panneau de l'atelier
   (`atelier/PanneauReleve.jsx`, CALX25) et l'écran téléphone « Relevé de visite »
   (`releve/ReleveVisite.jsx`). Extrait de PanneauReleve SANS changement de
   comportement : les deux écrans envoient le MÊME document à la MÊME porte
   (`POST calepinages/<pk>/releve/`, `PATCH …/releve/<id>/`).
   ========================================================================== */

export const COTE_VIDE = () => ({ nom: '', valeur: '' })
export const CHAINE_VIDE = () => ({ nom: '', totalMesure: '', toleranceM: '', cotes: [COTE_VIDE(), COTE_VIDE()] })

export function nombreOuNull(brut) {
  if (brut === '' || brut === null || brut === undefined) return null
  const v = Number(brut)
  return Number.isFinite(v) ? v : null
}

/** Les postes du document envoyé au serveur — `null` = cote MANQUANTE. */
export function documentDesChaines(chaines) {
  return chaines.map((chaine) => ({
    nom: chaine.nom || undefined,
    total_mesure: nombreOuNull(chaine.totalMesure),
    tolerance_m: nombreOuNull(chaine.toleranceM),
    cotes: chaine.cotes.map((c) => ({ nom: c.nom, valeur: nombreOuNull(c.valeur) })),
  }))
}

/**
 * Le refus AVANT tout envoi : plus d'une cote manquante par chaîne (le noyau
 * ne peut en déduire qu'une), ou un azimut sans sa précision déclarée. Un
 * poste vide et non problématique n'est JAMAIS refusé — seule une chaîne
 * réellement inconsistante l'est, et l'erreur nomme les cotes manquantes.
 */
export function validerAvantEnvoi(chaines, azimutDeg, precisionDeg) {
  const erreurs = {}
  chaines.forEach((chaine, i) => {
    const manquantes = chaine.cotes.filter((c) => c.valeur === '' || c.valeur === null)
    if (manquantes.length > 1) {
      const noms = manquantes.map((c, rang) => c.nom || `cote ${rang + 1}`).join(', ')
      erreurs[`chaines[${i}]`] = `Chaîne « ${chaine.nom || `chaîne ${i + 1}`} » : `
        + `${manquantes.length} cotes sont manquantes (${noms}) — le solveur ne `
        + 'peut en déduire qu’UNE seule par fermeture. Mesurez-en au moins une, '
        + 'ou saisissez le total mesuré pour n’en laisser qu’une manquante.'
    }
  })
  if (azimutDeg !== '' && azimutDeg !== null && (precisionDeg === '' || precisionDeg === null)) {
    erreurs.precision_azimut_deg = 'Un azimut relevé à la boussole doit '
      + 'porter sa précision déclarée (± degrés) : sans elle, il se lirait '
      + 'comme une mesure exacte.'
  }
  return erreurs
}

/** Le relevé servi → l'état des champs du formulaire (aller-retour). */
export function champsDuReleve(releve) {
  const chaines = Array.isArray(releve?.chaines) && releve.chaines.length > 0
    ? releve.chaines.map((c) => ({
      nom: c.nom ?? '',
      totalMesure: c.total_mesure ?? '',
      toleranceM: c.tolerance_m ?? '',
      cotes: (c.cotes || []).map((k) => ({ nom: k.nom ?? '', valeur: k.valeur ?? '' })),
    }))
    : [CHAINE_VIDE()]
  return {
    releveLe: releve?.releve_le ?? '',
    notes: releve?.notes ?? '',
    azimutDeg: releve?.azimut ? String(releve.azimut.deg) : '',
    precisionDeg: releve?.azimut && releve.azimut.precision_deg != null
      ? String(releve.azimut.precision_deg) : '',
    chaines,
    photoIds: (releve?.photos || []).map((p) => p.id),
  }
}

/** LE corps envoyé par les deux écrans (création comme correction). */
export function corpsDuReleve({ releveLe, chaines, azimutDeg, precisionDeg, notes, photoIds }) {
  return {
    releve_le: releveLe || null,
    chaines: documentDesChaines(chaines),
    azimut_boussole_deg: nombreOuNull(azimutDeg),
    precision_azimut_deg: nombreOuNull(precisionDeg),
    notes,
    photo_ids: photoIds,
  }
}
