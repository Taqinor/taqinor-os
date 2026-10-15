// ACHT63 — contrôle local d'une ligne AVANT tout envoi (règle serveur :
// DecimalField(12, 2) — 3 décimales ⇒ 400 sur la ligne, après création de la demande).
const nombreDe = (v) => Number(String(v).trim().replace(',', '.'))
const decimalesDe = (v) => {
  const m = String(v).trim().replace(',', '.').match(/\.(\d+)$/)
  return m ? m[1].length : 0
}
export function erreurLigne(l, rang) {
  const nom = `Ligne ${rang + 1}`
  const q = String(l.quantite ?? '').trim()
  const p = String(l.prix_estime ?? '').trim()
  if (q !== '' && (!Number.isFinite(nombreDe(q)) || nombreDe(q) < 0)) return `${nom} : quantité invalide.`
  if (q !== '' && decimalesDe(q) > 2) return `${nom} : la quantité accepte 2 décimales au plus.`
  if (p !== '' && (!Number.isFinite(nombreDe(p)) || nombreDe(p) < 0)) return `${nom} : prix estimé invalide.`
  if (p !== '' && decimalesDe(p) > 2) return `${nom} : le prix estimé accepte 2 décimales au plus.`
  return ''
}
