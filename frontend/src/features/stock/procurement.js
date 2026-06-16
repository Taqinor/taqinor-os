// Helpers purs (sans réseau) pour l'approvisionnement fournisseur (N11-N13).
// Le prix d'ACHAT est INTERNE : il ne doit jamais alimenter un document client.

// Statuts du bon de commande fournisseur (alignés sur le backend stock).
export const BCF_STATUTS = {
  brouillon: 'Brouillon',
  envoye: 'Envoyé',
  recu: 'Reçu',
  annule: 'Annulé',
}

export function bcfStatutLabel(statut) {
  return BCF_STATUTS[statut] || statut || ''
}

// Total d'achat HT d'une liste de lignes BCF (interne).
export function totalAchat(lignes = []) {
  return (lignes || []).reduce((sum, l) => {
    const qte = Number(l.quantite) || 0
    const pu = Number(l.prix_achat_unitaire) || 0
    return sum + qte * pu
  }, 0)
}

// Quantité restante à recevoir d'une ligne (jamais négative).
export function quantiteRestante(ligne) {
  const qte = Number(ligne?.quantite) || 0
  const recue = Number(ligne?.quantite_recue) || 0
  return Math.max(qte - recue, 0)
}

// Le BCF est-il entièrement reçu ? (au moins une ligne, toutes soldées)
export function estEntierementRecu(lignes = []) {
  if (!lignes || lignes.length === 0) return false
  return lignes.every((l) => quantiteRestante(l) === 0)
}

// Construit le payload `receptions` pour l'action recevoir : map ligneId→qté.
// Ignore les quantités nulles/négatives ; plafonne au reste dû (idempotence).
export function buildReceptionPayload(lignes = [], saisies = {}) {
  const out = []
  for (const ligne of lignes) {
    const brut = Number(saisies[ligne.id])
    if (!Number.isFinite(brut) || brut <= 0) continue
    const qte = Math.min(Math.floor(brut), quantiteRestante(ligne))
    if (qte > 0) out.push({ ligne: ligne.id, quantite: qte })
  }
  return out
}

// Filtre les lignes de besoin matériel en pénurie (manque > 0).
export function lignesEnPenurie(items = []) {
  return (items || []).filter((it) => (Number(it.manque) || 0) > 0)
}

// Nombre d'articles en pénurie.
export function nbPenuries(items = []) {
  return lignesEnPenurie(items).length
}
