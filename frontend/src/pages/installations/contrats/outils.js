// Outils purs de l'onglet « Contrats » : affichage seulement. Aucun montant
// n'est calculé ici — le serveur sert des chaînes décimales (« 98500.00 »),
// on les met en forme pour la lecture, sans jamais les convertir en nombre.

/** « 98500.00 » → « 98 500,00 DH » (chaîne en entrée, chaîne en sortie). */
export function formaterDh(montant) {
  if (montant === null || montant === undefined || montant === '') return 'à préciser'
  const [entier, decimales = '00'] = String(montant).split('.')
  const signe = entier.startsWith('-') ? '-' : ''
  const chiffres = entier.replace('-', '')
  const groupes = chiffres.replace(/\B(?=(\d{3})+(?!\d))/g, ' ')
  return `${signe}${groupes},${decimales.padEnd(2, '0')} DH`
}

/** Date ISO (« 2026-11-24 » ou horodatage) → « 24/11/2026 ». */
export function dateCourte(valeur) {
  if (!valeur) return ''
  const d = new Date(valeur)
  if (Number.isNaN(d.getTime())) return String(valeur)
  return new Intl.DateTimeFormat('fr-FR', {
    day: '2-digit', month: '2-digit', year: 'numeric', timeZone: 'Africa/Casablanca',
  }).format(d)
}

/** Date ISO (« 2037-01-23 ») → forme lisible dans la langue (affichage seul, rien n'est recalculé). */
export function dateLisible(iso, langue = 'fr') {
  if (!iso) return ''
  const d = new Date(`${String(iso).slice(0, 10)}T00:00:00Z`)
  if (Number.isNaN(d.getTime())) return String(iso)
  return new Intl.DateTimeFormat(langue === 'ar' ? 'ar-MA' : 'fr-FR', {
    day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC',
  }).format(d)
}

/** « 0.09 » → « 0,09 % » ; « 30.00 » → « 30 % » (mise en forme d'une chaîne du serveur, jamais un calcul). */
export function formaterPourcent(valeur) {
  if (valeur === null || valeur === undefined || valeur === '') return ''
  const texte = String(valeur).replace(',', '.')
  const [entier, decimales = ''] = texte.split('.')
  const utile = decimales.replace(/0+$/, '')
  return `${entier}${utile ? `,${utile}` : ''} %`
}

/** Le statut d'un acte, TOUJOURS en mots (jamais la couleur seule). */
export function libelleStatut(acte) {
  switch (acte.statut) {
    case 'brouillon':
      return 'Brouillon — le PDF porte la mention PROJET'
    case 'emis':
      return `Émis le ${dateCourte(acte.emis_le)}`
    case 'signe': {
      const par = acte.signataire_nom ? ` par ${acte.signataire_nom}` : ''
      const papier = acte.mode_signature === 'papier' ? ' (sur papier)' : ''
      return `Signé le ${dateCourte(acte.signe_le)}${par}${papier}`
    }
    case 'annule':
      return 'Annulé'
    default:
      return acte.statut
  }
}

/** Ton du badge selon le statut. */
export function tonStatut(acte) {
  if (acte.statut === 'signe') return 'success'
  if (acte.statut === 'emis') return 'info'
  if (acte.statut === 'annule') return 'danger'
  return 'neutral'
}

/**
 * Message d'un refus serveur `{detail, code}` — y compris quand la réponse est
 * un blob (téléchargement PDF refusé). Toujours le `detail` du serveur.
 */
export async function detailErreur(err) {
  let data = err?.response?.data
  if (data && typeof data.text === 'function') {
    data = await data.text().then(JSON.parse).catch(() => null)
  }
  if (typeof data?.detail === 'string' && data.detail) return data.detail
  if (data && typeof data === 'object') {
    const premier = Object.values(data).find((v) => typeof v === 'string' || Array.isArray(v))
    if (typeof premier === 'string') return premier
    if (Array.isArray(premier) && premier.length) return String(premier[0])
  }
  return 'Action impossible pour le moment. Réessayez.'
}

/** Textes à paragraphes : une ligne vide sépare deux paragraphes. */
export function paragraphesVersTexte(paragraphes) {
  return (paragraphes ?? []).join('\n\n')
}

export function texteVersParagraphes(texte) {
  return String(texte ?? '')
    .split(/\n[ \t]*\n/)
    .map((p) => p.replace(/\s+$/, '').replace(/^\s*\n/, ''))
    .filter((p) => p.trim() !== '')
}

/** Une valeur numérique TAPÉE : jamais arrondie ni refusée côté navigateur. */
export function nombreTape(texte) {
  const brut = String(texte ?? '').trim().replace(',', '.')
  if (brut === '') return null
  const n = Number(brut)
  return Number.isFinite(n) ? n : brut
}

/** Un acte `ecarte` par sa jumelle ? Les actes qui partagent un rang. */
export function grouperParRang(actes) {
  const etapes = []
  for (const acte of actes ?? []) {
    const etape = etapes.find((e) => e.rang === acte.rang)
    if (etape) etape.actes.push(acte)
    else etapes.push({ rang: acte.rang, actes: [acte] })
  }
  return etapes.sort((a, b) => a.rang - b.rang)
}

/** Le geste principal d'un acte (celui que « prochaine action » met en avant). */
export function actionPrincipale(acte) {
  if (acte.ecarte) return null
  if (acte.peut_emettre) return 'emettre'
  if (acte.peut_signer) return 'signer'
  return null
}

/** Id du titre d'un acte : les boutons de sa carte y sont reliés (aria-describedby). */
export const idTitreActe = (acte) => `contrats-acte-${acte.id}-titre`

export const LIBELLE_ACTION = {
  apercu: 'Aperçu (PDF)',
  modifier: 'Modifier',
  emettre: 'Émettre',
  signer: 'Faire signer sur place',
  papier: 'Signé sur papier',
  rouvrir: 'Rouvrir',
  telecharger: 'Télécharger',
}
