// Découpe une saisie de n° de série (retours ligne, virgules, points-virgules),
// rogne, retire les vides et les doublons (ordre conservé).
export function parseSeries(texte) {
  const vus = new Set()
  const out = []
  for (const brut of String(texte ?? '').split(/[\n\r,;]+/)) {
    const v = brut.trim()
    if (v && !vus.has(v)) { vus.add(v); out.push(v) }
  }
  return out
}

// Règle de comptage des séries (écran Réceptions + réception rapide du BCF) :
// jamais plus de séries que de quantités reçues, jamais d'ajustement silencieux.
// `qte` = quantité reçue déjà plafonnée au reste (NaN/<=0 compte pour 0).
export function erreurComptageSeries(texte, qte) {
  const attendus = Number.isFinite(qte) && qte > 0 ? qte : 0
  const nb = parseSeries(texte).length
  if (nb > 0 && nb > attendus) {
    return `${nb} n° de série saisis pour ${attendus} reçu(s) : retirez-en ${nb - attendus}.`
  }
  return null
}
