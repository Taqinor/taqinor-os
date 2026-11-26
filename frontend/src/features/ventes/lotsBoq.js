// QJR667 — fonctions PURES des écrans « Lots / multi-sites » et « Ajouter le
// BOQ électrique » (contrats `devis_lots.json` / `devis_boq_electrique.json`).
// Module sans React : partagé par les deux composants et leurs tests.

/** Message FRANÇAIS d'un refus serveur des lots (`detail` ou erreur de champ). */
export function messageErreurLots(err) {
  const data = err?.response?.data
  if (!data) return 'Le serveur est injoignable. Réessayez.'
  if (typeof data.detail === 'string') return data.detail
  for (const cle of ['nom_lot', 'ordre', 'lignes', 'adresse_site']) {
    const v = data[cle]
    if (v) return Array.isArray(v) ? String(v[0]) : String(v)
  }
  return 'Le lot n’a pas pu être créé.'
}

/** Corps POST d'un lot depuis le formulaire : champs vides omis, ordre en nombre. */
export function corpsCreationLot(form) {
  const corps = { nom_lot: (form.nom_lot || '').trim() }
  const adresse = (form.adresse_site || '').trim()
  if (adresse) corps.adresse_site = adresse
  if (String(form.ordre ?? '').trim() !== '') corps.ordre = Number(form.ordre)
  if (form.lignes?.length) corps.lignes = [...form.lignes]
  return corps
}

/** Phrase de bilan FRANÇAISE d'une réponse « ajouter le BOQ électrique ». */
export function bilanBoq(data) {
  const creees = data?.creees ?? 0
  const manques = data?.manques?.length ?? 0
  const deja = data?.deja_presentes?.length ?? 0
  const morceaux = [creees === 0
    ? 'Aucune ligne ajoutée'
    : `${creees} ligne${creees > 1 ? 's' : ''} ajoutée${creees > 1 ? 's' : ''}`]
  if (manques) morceaux.push(`${manques} à chiffrer faute de produit au catalogue`)
  if (deja) morceaux.push(`${deja} déjà présente${deja > 1 ? 's' : ''}`)
  return `${morceaux.join(' · ')}.`
}

/** Une phrase servie, rendue en phrase : majuscule initiale, point final. */
const enPhrase = (texte) => {
  const t = String(texte || '').trim()
  if (!t) return ''
  const p = t.charAt(0).toUpperCase() + t.slice(1)
  return /[.!?…]$/.test(p) ? p : `${p}.`
}

/** T4-X6-019 (suite) — les phrases sous le bilan : chaque ligne REMPLACÉE
 *  (« X remplace Y ») puis les `avertissements` servis, tels quels en phrases. */
export function phrasesBoq(data) {
  const remplacees = (data?.remplacees ?? [])
    .filter((r) => r?.nouvelle && r?.ancienne)
    .map((r) => `« ${r.nouvelle} » remplace « ${r.ancienne} ».`)
  const avertissements = (data?.avertissements ?? []).map(enPhrase).filter(Boolean)
  return [...remplacees, ...avertissements]
}
