/* NTTRE24 — Détection AUTOMATIQUE du format d'un relevé bancaire.
   ----------------------------------------------------------------------------
   L'assistant « Nouveau rapprochement » ne demande plus le format à
   l'utilisateur : il le déduit de l'extension du fichier, puis de son en-tête
   (les deux, dans cet ordre — l'en-tête l'emporte quand il est concluant, une
   extension `.txt` couvrant aussi bien un MT940 qu'un CFONB120).

   Formats reconnus (ceux que le backend sait déjà parser, NTTRE1-3) :
     • `camt053`  — XML ISO 20022 (balise/namespace `camt.053`) ;
     • `mt940`    — relevé SWIFT (tags `:20:` / `:25:` / `:61:`) ;
     • `cfonb120` — enregistrements à largeur fixe de 120 caractères ;
     • `csv`      — relevé tabulaire, importé ligne à ligne par l'assistant via
                    l'endpoint `ligne-releve` existant (le backend n'a pas de
                    parseur CSV : l'assistant ne fabrique donc aucune route).
   Renvoie `null` quand rien n'est concluant — l'assistant le dit alors
   explicitement plutôt que de deviner. */

/** Extension en minuscules, sans le point (`''` si le nom n'en porte pas). */
export function extensionDe(nom) {
  const propre = String(nom || '')
  const point = propre.lastIndexOf('.')
  return point > 0 ? propre.slice(point + 1).toLowerCase() : ''
}

/**
 * Format du relevé déduit du nom de fichier et de son en-tête texte.
 * @param {string} nom    nom du fichier
 * @param {string} entete premiers caractères du fichier (2 ko suffisent)
 * @returns {'camt053'|'mt940'|'cfonb120'|'csv'|null}
 */
export function detecterFormatReleve(nom, entete = '') {
  const ext = extensionDe(nom)
  const texte = String(entete || '')

  // 1) En-tête concluant — il prime sur l'extension.
  if (/camt\.053/i.test(texte) || /<\s*BkToCstmrStmt/i.test(texte)) return 'camt053'
  if (/(^|\n):20:/.test(texte) || /(^|\n):61:/.test(texte)) return 'mt940'

  const lignes = texte.split(/\r?\n/).filter((l) => l.length > 0)
  if (lignes.length && lignes.every((l) => l.length === 120)) return 'cfonb120'

  // 2) Extension, en repli.
  if (ext === 'xml') return 'camt053'
  if (ext === 'sta' || ext === 'mt940') return 'mt940'
  if (ext === 'cfonb' || ext === 'cfonb120') return 'cfonb120'
  if (ext === 'csv') return 'csv'
  return null
}

/** Libellé FR du format, pour l'affichage dans l'assistant. */
export const LIBELLE_FORMAT = {
  camt053: 'camt.053 (XML ISO 20022)',
  mt940: 'MT940 (SWIFT)',
  cfonb120: 'CFONB 120',
  csv: 'CSV',
}

/* Séparateur le plus probable d'une ligne CSV : celui qui découpe l'en-tête
   en le plus de colonnes (les banques marocaines exportent en `;` comme en
   `,`). */
function separateurCsv(premiereLigne) {
  const candidats = [';', ',', '\t']
  let meilleur = ';'
  let colonnes = 0
  for (const sep of candidats) {
    const n = premiereLigne.split(sep).length
    if (n > colonnes) { colonnes = n; meilleur = sep }
  }
  return meilleur
}

/** Normalise un montant « 1 234,56 » / « 1,234.56 » / « -250 » en nombre. */
export function normaliserMontant(brut) {
  let texte = String(brut ?? '').trim().replace(/\s/g, '')
  if (!texte) return null
  const virgule = texte.lastIndexOf(',')
  const point = texte.lastIndexOf('.')
  if (virgule > point) texte = texte.replace(/\./g, '').replace(',', '.')
  else texte = texte.replace(/,/g, '')
  const valeur = Number(texte)
  return Number.isFinite(valeur) ? valeur : null
}

/** Date ISO depuis « AAAA-MM-JJ » ou « JJ/MM/AAAA » (sinon `null`). */
export function normaliserDate(brut) {
  const texte = String(brut ?? '').trim()
  if (/^\d{4}-\d{2}-\d{2}$/.test(texte)) return texte
  const fr = texte.match(/^(\d{2})[/-](\d{2})[/-](\d{4})$/)
  if (fr) return `${fr[3]}-${fr[2]}-${fr[1]}`
  return null
}

/**
 * Découpe un relevé CSV en lignes de relevé prêtes pour `ligne-releve`.
 * Colonnes attendues, dans cet ordre ou nommées en en-tête :
 * date, libellé, montant (signé), référence (facultative).
 * @returns {{lignes: Array, ignorees: number}}
 */
export function parserReleveCsv(texte) {
  const brutes = String(texte || '').split(/\r?\n/).filter((l) => l.trim())
  if (!brutes.length) return { lignes: [], ignorees: 0 }
  const sep = separateurCsv(brutes[0])
  const premiere = brutes[0].split(sep).map((c) => c.trim().toLowerCase())
  const aEntete = premiere.some(
    (c) => c.startsWith('date') || c.includes('libell') || c.includes('montant'))
  const index = {
    date: aEntete ? premiere.findIndex((c) => c.startsWith('date')) : 0,
    libelle: aEntete
      ? premiere.findIndex((c) => c.includes('libell') || c.includes('label'))
      : 1,
    montant: aEntete ? premiere.findIndex((c) => c.includes('montant')) : 2,
    reference: aEntete
      ? premiere.findIndex((c) => c.includes('ref'))
      : 3,
  }
  const lignes = []
  let ignorees = 0
  for (const brute of brutes.slice(aEntete ? 1 : 0)) {
    const cellules = brute.split(sep).map((c) => c.trim())
    const date = normaliserDate(cellules[index.date])
    const montant = normaliserMontant(cellules[index.montant])
    if (date === null || montant === null) { ignorees += 1; continue }
    lignes.push({
      date_operation: date,
      libelle: cellules[index.libelle] || '',
      montant,
      reference: index.reference >= 0 ? (cellules[index.reference] || '') : '',
    })
  }
  return { lignes, ignorees }
}
