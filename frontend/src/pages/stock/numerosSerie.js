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
