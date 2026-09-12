/* ============================================================================
   NTPRT34 — Langue du shell portail (FR / AR).
   ----------------------------------------------------------------------------
   PÉRIMÈTRE VOLONTAIREMENT ÉTROIT (c'est le cadrage explicite de la tâche) :
   la navigation et la chrome du shell portail, PAS une traduction complète de
   l'application. Un libellé sans traduction arabe retombe sur le français —
   jamais une clé technique affichée à un client.

   La préférence est SERVEUR (`/portail/ma-preference/`, NTPRT34) : elle suit
   le compte d'un appareil à l'autre. Aucun cookie, aucun localStorage — c'est
   littéralement le critère d'acceptation de la tâche.
   ========================================================================== */

export const LANGUE_PAR_DEFAUT = 'fr'
export const LANGUES = ['fr', 'ar']

/** Sens d'écriture de la langue — l'arabe se lit de droite à gauche. */
export function directionLangue(langue) {
  return langue === 'ar' ? 'rtl' : 'ltr'
}

/* Chrome du shell : les seules chaînes que PortalLayout rend lui-même. */
const CHROME = {
  fr: {
    deconnexion: 'Se déconnecter',
    navigation: 'Navigation du portail',
    langue: 'Langue',
  },
  ar: {
    deconnexion: 'تسجيل الخروج',
    navigation: 'تصفح البوابة',
    langue: 'اللغة',
  },
}

/** Chaîne de chrome dans `langue`, repli français. */
export function chrome(langue, cle) {
  const table = CHROME[langue] || CHROME[LANGUE_PAR_DEFAUT]
  return table[cle] || CHROME[LANGUE_PAR_DEFAUT][cle] || ''
}

/**
 * Libellé d'un élément de nav (ou d'un titre de shell) dans `langue`.
 * `source` est un objet portant `label` (FR, obligatoire) et `labelAr`
 * (facultatif). Sans traduction, on rend le français : un libellé vide serait
 * pire qu'un libellé non traduit.
 */
export function libelle(source, langue) {
  if (!source) return ''
  if (langue === 'ar' && source.labelAr) return source.labelAr
  return source.label || ''
}
