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

// Règle de comptage UNIQUE des séries d'une ligne de réception (écran Réceptions
// et réception rapide de la fiche BCF) : message si plus de séries que de reçus,
// sinon null — jamais d'ajustement silencieux.
export function erreurComptageSeries(texte, quantiteRecue) {
  const nb = parseSeries(texte).length
  const qte = Number.isFinite(quantiteRecue) && quantiteRecue > 0 ? quantiteRecue : 0
  if (nb > 0 && nb > qte) {
    return `${nb} n° de série saisis pour ${qte} reçu(s) : retirez-en ${nb - qte}.`
  }
  return null
}
