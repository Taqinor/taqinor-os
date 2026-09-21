/* AOF87 — Cote DÉDUITE : bascule automatique en « à confirmer » + points à lever.
   ----------------------------------------------------------------------------
   Cas réel, tiré d'un relevé livré : la profondeur de la cage n'a JAMAIS été
   mesurée. Elle est DÉDUITE de la fermeture — 51,10 − 42,28 = 8,82 — alors que
   le client annonçait « à peu près 8,5 ». La règle du relevé est que la
   fermeture exacte fait foi : on garde 8,82, MAIS la cote passe en « à
   confirmer » (orange), l'écart avec la valeur annoncée est écrit en clair
   (+0,32 m), et le point entre tout seul dans la liste « à lever au relevé
   d'exécution ». Même chose pour une divergence mesuré/plan : 25,62 relevé
   contre 26,20 au plan → Δ 0,58 publié, jamais tu.

   Le point dur est le « tout seul » : aucune de ces bascules ne demande une
   intervention. Une cote déduite ne PEUT pas rester bleue (mesurée) — c'est
   `coherentes()` qui le prouve, et c'est ce qu'un opérateur pressé oublierait
   toujours de faire à la main. */

export const PROVENANCE_MESURE = 'mesure'
export const PROVENANCE_A_CONFIRMER = 'confirmer'
export const ORIGINE_DEDUCTION = 'deduction'

/* Divergence mesuré/annoncé au-delà de laquelle l'écart est PUBLIÉ et le point
   entre dans la liste. 5 cm : en deçà, c'est le bruit d'un relevé au mètre. */
export const SEUIL_DIVERGENCE_M = 0.05

/* `null` signifie « pas de valeur », et c'est DIFFÉRENT de zéro : une cote sans
   valeur annoncée ne doit pas se comparer à 0 (ce qui publierait un écart égal à
   la cote entière). `Number('')` valant 0, le cas vide est traité à part. */
function nombre(valeur) {
  if (valeur === null || valeur === undefined) return null
  const brut = typeof valeur === 'string' ? valeur.trim().replace(',', '.') : valeur
  if (brut === '') return null
  const n = Number(brut)
  return Number.isFinite(n) ? n : null
}

/**
 * Fabrique une cote DÉDUITE d'une fermeture : `total` moins la somme des
 * `connus`. La provenance n'est PAS un paramètre — une déduction est « à
 * confirmer », un point c'est tout.
 */
export function creerCoteDeduite({ id, libelle, total, connus = [], valeurAnnoncee = null }) {
  const t = nombre(total)
  const parts = connus.map(nombre).filter((v) => v !== null)
  if (t === null) throw new TypeError('`total` doit être un nombre (la cote de fermeture).')
  const somme = parts.reduce((s, v) => s + v, 0)
  const valeur = Math.round((t - somme) * 1000) / 1000
  return normaliserCote({
    id,
    libelle,
    valeur,
    origine: ORIGINE_DEDUCTION,
    provenance: PROVENANCE_MESURE, // volontairement « faux » en entrée…
    formule: `${t} − ${parts.join(' − ')} = ${valeur}`,
    valeurAnnoncee: nombre(valeurAnnoncee),
  })
  // …`normaliserCote` le corrige : la règle vit dans UN seul endroit.
}

/**
 * Normalise une cote : toute cote d'origine « déduction » bascule en « à
 * confirmer », quoi qu'ait mis l'appelant. C'est la bascule AUTOMATIQUE.
 */
export function normaliserCote(cote) {
  if (!cote) return cote
  if (cote.origine === ORIGINE_DEDUCTION && cote.provenance !== PROVENANCE_A_CONFIRMER) {
    return { ...cote, provenance: PROVENANCE_A_CONFIRMER }
  }
  return cote
}

/** Écart avec la valeur annoncée par le client / le plan — ou `null`. */
export function ecartAnnonce(cote) {
  const v = nombre(cote?.valeur)
  const a = nombre(cote?.valeurAnnoncee)
  if (v === null || a === null) return null
  const ecart = Math.round((v - a) * 1000) / 1000
  const ecartPct = a !== 0 ? Math.round((ecart / a) * 10000) / 100 : 0
  return {
    ecart,
    ecartPct,
    texte: `${ecart > 0 ? '+' : ''}${ecart.toFixed(2).replace('.', ',')} m par rapport aux ${a
      .toFixed(2)
      .replace('.', ',')} m annoncés`,
  }
}

/**
 * La section « à lever au relevé d'exécution », REMPLIE TOUTE SEULE :
 *   • toute cote déduite (motif `deduction`) ;
 *   • toute cote dont l'écart avec la valeur annoncée dépasse le seuil
 *     (motif `divergence`) — y compris une cote parfaitement mesurée : c'est
 *     l'écart qui doit être publié, pas la cote qui doit être suspectée.
 */
export function pointsALever(cotes = [], { seuil = SEUIL_DIVERGENCE_M } = {}) {
  const points = []
  for (const brute of cotes) {
    const cote = normaliserCote(brute)
    const e = ecartAnnonce(cote)
    if (cote.origine === ORIGINE_DEDUCTION) {
      points.push({
        id: cote.id,
        libelle: cote.libelle,
        valeur: cote.valeur,
        provenance: cote.provenance,
        motif: 'deduction',
        formule: cote.formule ?? null,
        ecart: e?.ecart ?? null,
        texteEcart: e?.texte ?? null,
      })
      continue
    }
    if (e && Math.abs(e.ecart) > seuil) {
      points.push({
        id: cote.id,
        libelle: cote.libelle,
        valeur: cote.valeur,
        provenance: cote.provenance,
        motif: 'divergence',
        formule: null,
        ecart: e.ecart,
        texteEcart: e.texte,
      })
    }
  }
  return points
}

/**
 * Garde : renvoie la liste des cotes déduites restées « mesurées » (bleues).
 * Vide = l'invariant tient. Non vide = un chemin a contourné `normaliserCote`,
 * et il faut le corriger, pas repeindre l'écran.
 */
export function coherentes(cotes = []) {
  return cotes.filter(
    (c) => c?.origine === ORIGINE_DEDUCTION && c?.provenance !== PROVENANCE_A_CONFIRMER,
  )
}

/** Export CSV (séparateur point-virgule, décimale française) de la section. */
export function exporterPointsALever(points = []) {
  const entete = 'Repère;Cote (m);Provenance;Motif;Écart (m);Détail'
  const lignes = points.map((p) =>
    [
      p.libelle ?? p.id ?? '',
      Number(p.valeur).toFixed(2).replace('.', ','),
      p.provenance === PROVENANCE_A_CONFIRMER ? 'à confirmer' : p.provenance,
      p.motif === 'deduction' ? 'cote déduite' : 'écart avec la valeur annoncée',
      p.ecart === null || p.ecart === undefined
        ? ''
        : Number(p.ecart).toFixed(2).replace('.', ','),
      (p.formule ?? p.texteEcart ?? '').replace(/;/g, ','),
    ].join(';'),
  )
  return [entete, ...lignes].join('\n')
}
