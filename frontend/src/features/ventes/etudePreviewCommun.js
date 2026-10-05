// Briques PARTAGÉES des aperçus serveur (C&I et pompage) : lecture des nombres
// tapés, libellés de provenance, alertes. Un seul code, jamais recopié.

/** Un nombre tapé → nombre, sinon `null` (jamais 0 inventé, jamais arrondi). */
export const nombreOuNull = (v) => {
  if (v === null || v === undefined || typeof v === 'boolean') return null
  if (typeof v === 'number') return Number.isFinite(v) ? v : null
  const brut = String(v).trim().replace(',', '.')
  if (brut === '') return null
  const n = Number(brut)
  return Number.isFinite(n) ? n : null
}

export const texteOuNull = (v) => {
  if (v === null || v === undefined) return null
  const t = String(v).trim()
  return t === '' ? null : t
}

/** Fabrique `libelleProvenance({origine, detail, date})` (jamais vide). */
export function creerLibelleProvenance(libellesOrigine, libellesDetailLead) {
  return function libelleProvenance(provenance) {
    const p = provenance || {}
    const base = libellesOrigine[p.origine] || 'origine inconnue'
    const detail = p.origine === 'lead' ? libellesDetailLead[p.detail] : null
    const texte = detail ? `${base} — ${detail}` : base
    return p.date ? `${texte} (${p.date})` : texte
  }
}

/**
 * TOUTES les alertes du serveur, dans l'ordre, aucune filtrée. Une alerte sans
 * message garde son code pour rester visible ; `complement(a)` ajoute des champs.
 */
export function alertesDuServeur(reponse, messageParDefaut, complement = () => ({})) {
  const alertes = Array.isArray(reponse?.alertes) ? reponse.alertes : []
  return alertes.map((a, i) => ({
    cle: `${a?.code || 'alerte'}-${a?.champ || ''}-${i}`,
    code: a?.code || null,
    champ: a?.champ || null,
    ...complement(a),
    message: a?.message || a?.code || messageParDefaut,
  }))
}
