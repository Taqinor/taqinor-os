// VNT44 (Groupe VNT, D-VNT-3) — erreurs serveur de « Facturer la vente »
// (contrat `ventes/contract_samples/devis_facturer.json`) → erreurs NOMMÉES.
// Règle fondateur « erreurs → le champ fautif » : une erreur s'affiche SOUS son
// champ et un bandeau dit « Corrigez : … ». `hooks/useServerFieldErrors.js`
// (socle) ignore les listes d'objets (`{paiements:[{date_paiement:[…]}]}` ⇒ repli
// `detail`) : il n'est PAS modifié, ce module le complète.

const LIBELLES_CHAMPS = {
  montant_ttc: 'Montant',
  montant: 'montant',
  pourcentage: 'Pourcentage',
  nature: 'Nature',
  cle_attendue: 'Tranche',
  libelle: 'Libellé',
  emettre: 'Émission',
  paiements: 'Paiements',
  date_paiement: 'date',
  mode_paiement: 'mode de paiement',
  reference: 'référence',
}

const REPLI = 'Une erreur est survenue.'

const premier = (val) => {
  if (typeof val === 'string') return val
  if (Array.isArray(val)) return val.find((v) => typeof v === 'string') || ''
  return ''
}

function libelleChamp(nom) {
  return LIBELLES_CHAMPS[nom] || nom
}

/**
 * Aplatit une réponse d'erreur DRF en liste `[{cle, libelle, message, code?, …}]`.
 *  - `{champ: ['msg']}` / `{champ: 'msg'}`           → cle `champ`
 *  - `{paiements: [{date_paiement: ['msg']}, {}]}`   → cle `paiements.0.date_paiement`,
 *    libellé « Paiement 1 — date »
 *  - `{detail, code, …}` (409/403/400 métier)         → cle `submit`, `code` et les
 *    clés utiles (`successeur`, `brouillons`, `facture`, `cle_attendue`) conservés
 *  - rien d'exploitable                               → cle `submit`, message de repli
 */
export function aplatirErreurs(data) {
  if (data == null || typeof data !== 'object' || Array.isArray(data)) {
    const message = typeof data === 'string' && data
      ? data
      : (Array.isArray(data) ? premier(data) : '') || REPLI
    return [{ cle: 'submit', libelle: '', message }]
  }
  const sorties = []
  for (const [nom, val] of Object.entries(data)) {
    if (nom === 'detail' || nom === 'non_field_errors' || nom === 'code') continue
    if (nom === 'paiements' && Array.isArray(val) && val.some((v) => v && typeof v === 'object')) {
      val.forEach((ligne, i) => {
        if (!ligne || typeof ligne !== 'object') return
        for (const [sous, sval] of Object.entries(ligne)) {
          const message = premier(sval)
          if (!message) continue
          sorties.push({
            cle: `paiements.${i}.${sous}`,
            libelle: `Paiement ${i + 1} — ${libelleChamp(sous)}`,
            message,
          })
        }
      })
      continue
    }
    const message = premier(val)
    if (message) sorties.push({ cle: nom, libelle: libelleChamp(nom), message })
  }
  if (sorties.length > 0) return sorties
  const general = {
    cle: 'submit',
    libelle: '',
    message: premier(data.detail) || premier(data.non_field_errors) || REPLI,
  }
  if (data.code) general.code = data.code
  for (const extra of ['successeur', 'brouillons', 'facture', 'cle_attendue']) {
    if (data[extra] !== undefined) general[extra] = data[extra]
  }
  return [general]
}

/** `{cle: message}` — ce que `FormField error=` consomme, premier message par clé. */
export function erreursParChamp(liste) {
  const out = {}
  for (const e of Array.isArray(liste) ? liste : []) {
    if (!(e.cle in out)) out[e.cle] = e.message
  }
  return out
}

/**
 * Texte du bandeau `role=alert` : « Corrigez : Montant, Paiement 1 — date »
 * quand des champs sont nommés, sinon le message général (detail serveur).
 */
export function bandeau(liste) {
  const l = Array.isArray(liste) ? liste : []
  if (l.length === 0) return ''
  const nommes = l.filter((e) => e.cle !== 'submit' && e.libelle)
  if (nommes.length > 0) {
    const libelles = [...new Set(nommes.map((e) => e.libelle))]
    return `Corrigez : ${libelles.join(', ')}`
  }
  return l[0].message || REPLI
}
