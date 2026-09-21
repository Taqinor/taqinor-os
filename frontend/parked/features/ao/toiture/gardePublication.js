/* AOF90 — Compteur de provenance et GARDE DE PUBLICATION.
   ----------------------------------------------------------------------------
   C'est la version applicative de l'`assert len(OBS) == 28` du script d'origine.
   Le relevé FRDISI a coûté 12 modules sur la seule aile en L parce que deux
   emprises venues du PLAN n'avaient jamais été relevées, et quatre souches
   avaient été purement INVENTÉES faute de photo lisible. Un assert dans un
   script ne protège que celui qui lance le script : ici la règle est portée par
   l'écran, en permanence, et elle BLOQUE.

   TROIS RÈGLES, toutes testables sans React (c'est ce que `gardePublication.test.mjs`
   interroge) :

   1. LE COMPTE ENGAGÉ N'EST PAS LE NOMBRE DE LIGNES. Un obstacle ÉCARTÉ garde sa
      géométrie en base (le retour arrière doit rester un one-liner et la marche
      de décomposition doit pouvoir CHIFFRER ce que la décision rapporte) mais il
      sort du compte. « 28 obstacles » veut dire 28 dans le compte, écartés non
      compris — et les écartés restent listés, filtrables, avec leur décision.

   2. TOUTE PROVENANCE N'EST PAS ENGAGEABLE. Mesuré et mesuré-douteux le sont
      (0,30 / 0,50 m de dégagement) ; relevé sur PLAN, DEVINÉ et DÉCLARÉ PAR LE
      CLIENT ne le sont pas — leur emprise réelle n'a jamais été constatée. C'est
      exactement le prédicat `engageable` du moteur ; l'écran ne s'invente pas une
      règle plus permissive que le calcul qu'il publie.

   3. LE BLOCAGE NOMME LES FAUTIFS. Un message « des obstacles sont incertains »
      n'a jamais fait bouger personne. On nomme le repère, la désignation et la
      provenance de chacun, et on propose la seule action qui débloque vraiment :
      poser la question au client — pré-remplie, prête à devenir une question Q/R. */
import { indexDepuisRepere, natureParCle } from './repereLettre.js'
import { aireM2 } from './repere.js'

/* ── Les six provenances du moteur ──────────────────────────────────────────── */

export const PROVENANCE_MESURE = 'MESURE'
export const PROVENANCE_MESURE_DOUTEUX = 'MESURE_DOUTEUX'
export const PROVENANCE_PLAN = 'PLAN'
export const PROVENANCE_DEVINE = 'DEVINE'
export const PROVENANCE_DECLARE_CLIENT = 'DECLARE_CLIENT'
export const PROVENANCE_ECARTE = 'ECARTE'
/* Septième valeur, volontaire : une provenance vide ou inconnue ne peut pas
   RETOMBER sur « mesuré ». Un défaut permissif ferait passer une saisie ratée
   pour un relevé — exactement ce que cette garde existe pour empêcher. Elle
   pèse donc sur le compte et bloque, jusqu'à ce que quelqu'un tranche. */
export const PROVENANCE_INCONNUE = 'INCONNUE'

export const PROVENANCES = [
  {
    cle: PROVENANCE_MESURE,
    libelle: 'Mesuré',
    pluriel: 'mesurés',
    jeton: 'mesure',
    engageable: true,
    dansLeCompte: true,
  },
  {
    cle: PROVENANCE_MESURE_DOUTEUX,
    libelle: 'Mesuré, à confirmer',
    pluriel: 'à confirmer',
    jeton: 'confirmer',
    engageable: true,
    dansLeCompte: true,
  },
  {
    cle: PROVENANCE_PLAN,
    libelle: 'Relevé sur plan',
    pluriel: 'sur plan',
    jeton: 'deduit',
    engageable: false,
    dansLeCompte: true,
  },
  {
    cle: PROVENANCE_DEVINE,
    libelle: 'Deviné',
    pluriel: 'deviné',
    jeton: 'devine',
    engageable: false,
    dansLeCompte: true,
  },
  {
    cle: PROVENANCE_DECLARE_CLIENT,
    libelle: 'Déclaré par le client',
    pluriel: 'déclarés par le client',
    jeton: 'devine',
    engageable: false,
    dansLeCompte: true,
  },
  {
    cle: PROVENANCE_ECARTE,
    libelle: 'Écarté',
    pluriel: 'écartés',
    jeton: 'deduit',
    engageable: false,
    dansLeCompte: false,
  },
  {
    cle: PROVENANCE_INCONNUE,
    libelle: 'Provenance non renseignée',
    pluriel: 'sans provenance',
    jeton: 'devine',
    engageable: false,
    dansLeCompte: true,
  },
]

/* L'inspecteur d'AOF88 parle le vocabulaire court des JETONS de provenance
   (mesure / confirmer / deduit / devine) tandis que le moteur et l'API parlent
   les six clés ci-dessus. Une seule table de correspondance, ici : un écran qui
   traduirait dans son coin finirait par compter un `deduit` comme engageable. */
const ALIAS = {
  MESURE: PROVENANCE_MESURE,
  MESURE_DOUTEUX: PROVENANCE_MESURE_DOUTEUX,
  PLAN: PROVENANCE_PLAN,
  DEVINE: PROVENANCE_DEVINE,
  DECLARE_CLIENT: PROVENANCE_DECLARE_CLIENT,
  ECARTE: PROVENANCE_ECARTE,
  MESURE_DOUTEUSE: PROVENANCE_MESURE_DOUTEUX,
  CONFIRMER: PROVENANCE_MESURE_DOUTEUX,
  A_CONFIRMER: PROVENANCE_MESURE_DOUTEUX,
  DEDUIT: PROVENANCE_PLAN,
  DEDUITE: PROVENANCE_PLAN,
  DECLARE: PROVENANCE_DECLARE_CLIENT,
  CLIENT: PROVENANCE_DECLARE_CLIENT,
  ECARTEE: PROVENANCE_ECARTE,
}

/** Normalise n'importe quelle écriture de provenance ; l'inconnu reste INCONNUE. */
export function normaliserProvenance(valeur) {
  const brut = String(valeur ?? '')
    .trim()
    .toUpperCase()
    .replace(/[-\s]+/g, '_')
  return ALIAS[brut] ?? PROVENANCE_INCONNUE
}

export function provenanceInfo(valeur) {
  const cle = normaliserProvenance(valeur)
  return PROVENANCES.find((p) => p.cle === cle) ?? PROVENANCES[PROVENANCES.length - 1]
}

/** L'obstacle entre-t-il dans le compte engagé ? (un ÉCARTÉ n'y entre pas) */
export function dansLeCompte(obstacle) {
  return provenanceInfo(obstacle?.provenance).dansLeCompte
}

/** Sa provenance permet-elle d'ENGAGER un chiffre devant le maître d'ouvrage ? */
export function estEngageable(obstacle) {
  return provenanceInfo(obstacle?.provenance).engageable
}

/* ── Compteur de provenance ─────────────────────────────────────────────────── */

/**
 * Répartition par provenance.
 * `total` = obstacles DANS LE COMPTE (les écartés sont comptés à part) — ainsi
 * « 28 obstacles » désigne toujours les 28 qui pèsent sur le calepinage.
 */
export function compterProvenances(obstacles = []) {
  const parProvenance = Object.fromEntries(PROVENANCES.map((p) => [p.cle, 0]))
  for (const o of obstacles || []) {
    parProvenance[provenanceInfo(o?.provenance).cle] += 1
  }
  const total = PROVENANCES.filter((p) => p.dansLeCompte).reduce(
    (t, p) => t + parProvenance[p.cle],
    0,
  )
  const nonEngageables = PROVENANCES.filter((p) => p.dansLeCompte && !p.engageable).reduce(
    (t, p) => t + parProvenance[p.cle],
    0,
  )
  return {
    total,
    lignes: (obstacles || []).length,
    engages: total - nonEngageables,
    nonEngageables,
    parProvenance,
  }
}

/**
 * « 28 obstacles — 26 mesurés, 2 à confirmer, 0 deviné ».
 * Les trois catégories de tête sont TOUJOURS écrites, y compris à zéro : « 0
 * deviné » est une affirmation, pas une absence d'information. Les catégories
 * restantes ne s'affichent que si elles existent.
 */
export function libelleCompteur(obstacles = []) {
  const c = Array.isArray(obstacles) ? compterProvenances(obstacles) : obstacles
  const n = c.parProvenance
  const parts = [
    `${n[PROVENANCE_MESURE]} mesurés`,
    `${n[PROVENANCE_MESURE_DOUTEUX]} à confirmer`,
    `${n[PROVENANCE_DEVINE]} deviné`,
  ]
  if (n[PROVENANCE_PLAN] > 0) parts.push(`${n[PROVENANCE_PLAN]} sur plan`)
  if (n[PROVENANCE_DECLARE_CLIENT] > 0) {
    parts.push(`${n[PROVENANCE_DECLARE_CLIENT]} déclarés par le client`)
  }
  if (n[PROVENANCE_INCONNUE] > 0) parts.push(`${n[PROVENANCE_INCONNUE]} sans provenance`)
  let texte = `${c.total} obstacles — ${parts.join(', ')}`
  if (n[PROVENANCE_ECARTE] > 0) texte += ` (+ ${n[PROVENANCE_ECARTE]} écartés)`
  return texte
}

/* ── Garde de publication ───────────────────────────────────────────────────── */

function designation(obstacle) {
  return (
    obstacle?.designation ||
    natureParCle(obstacle?.nature)?.libelle ||
    'obstacle sans désignation'
  )
}

/** Les obstacles qui entrent dans le compte engagé sans être engageables. */
export function obstaclesFautifs(obstacles = []) {
  return (obstacles || []).filter((o) => dansLeCompte(o) && !estEngageable(o))
}

/** « A (Cage d'escalier — relevé sur plan) » */
export function nommerFautif(obstacle) {
  return `${obstacle?.repere ?? '?'} (${designation(obstacle)} — ${provenanceInfo(
    obstacle?.provenance,
  ).libelle.toLowerCase()})`
}

/**
 * Question Q/R pré-remplie : le seul geste qui débloque vraiment la situation.
 * On rend l'objet, le corps et les repères concernés — l'écran des séries Q/R
 * n'a plus qu'à créer la question.
 */
export function questionPourFautifs(fautifs = []) {
  const reperes = fautifs.map((o) => o?.repere ?? '?')
  return {
    objet:
      reperes.length === 1
        ? `Emprise de l'obstacle ${reperes[0]} à confirmer`
        : `Emprises des obstacles ${reperes.join(', ')} à confirmer`,
    corps: [
      "Les emprises suivantes n'ont pas été relevées sur site et conditionnent le nombre de panneaux posables :",
      ...fautifs.map((o) => `- ${nommerFautif(o)}`),
      'Merci de confirmer leurs dimensions (ou de nous autoriser un relevé complémentaire) avant le dépôt.',
    ].join('\n'),
    reperes,
  }
}

/**
 * LA GARDE. Tant qu'un obstacle non engageable pèse sur le compte, la toiture
 * ne peut pas être marquée prête à publier.
 * → { pretAPublier, fautifs, compte, message, question }
 */
export function evaluerGardePublication(obstacles = []) {
  const compte = compterProvenances(obstacles)
  const fautifs = obstaclesFautifs(obstacles)
  const pretAPublier = fautifs.length === 0
  const message = pretAPublier
    ? `Toiture publiable : les ${compte.total} obstacles du compte engagé sont mesurés ou explicitement à confirmer.`
    : `Publication bloquée — ${fautifs.length} obstacle${
        fautifs.length > 1 ? 's' : ''
      } ${fautifs.length > 1 ? 'entrent' : 'entre'} dans le compte engagé sans emprise relevée : ${fautifs
        .map(nommerFautif)
        .join(' · ')}. Mesurez-les, écartez-les avec leur décision, ou posez la question au client.`
  return {
    pretAPublier,
    fautifs,
    compte,
    message,
    question: pretAPublier ? null : questionPourFautifs(fautifs),
  }
}

/* ── Liste : tri et filtre ──────────────────────────────────────────────────── */

export const TRIS = [
  { cle: 'repere', libelle: 'Repère' },
  { cle: 'designation', libelle: 'Désignation' },
  { cle: 'nature', libelle: 'Nature' },
  { cle: 'provenance', libelle: 'Provenance' },
  { cle: 'surface', libelle: 'Surface' },
]

/** Surface d'emprise : rectangle (x0,x1,y0,y1) ou polygone (`sommets`). */
export function surfaceObstacle(obstacle) {
  if (Array.isArray(obstacle?.sommets) && obstacle.sommets.length >= 3) {
    return aireM2(obstacle.sommets)
  }
  const { x0, x1, y0, y1 } = obstacle ?? {}
  if ([x0, x1, y0, y1].every((v) => Number.isFinite(Number(v)))) {
    return Math.abs(Number(x1) - Number(x0)) * Math.abs(Number(y1) - Number(y0))
  }
  return 0
}

function cleDeTri(obstacle, cle) {
  if (cle === 'repere') return indexDepuisRepere(obstacle?.repere) ?? 1e9
  if (cle === 'surface') return surfaceObstacle(obstacle)
  if (cle === 'provenance') return provenanceInfo(obstacle?.provenance).libelle
  if (cle === 'nature') return natureParCle(obstacle?.nature)?.libelle ?? ''
  return designation(obstacle)
}

/** Tri stable, `repere` en ordre de tableur (Z avant AA), jamais alphabétique. */
export function trierObstacles(obstacles = [], cle = 'repere', sens = 'asc') {
  const signe = sens === 'desc' ? -1 : 1
  return [...(obstacles || [])]
    .map((o, i) => [o, i])
    .sort(([a, ia], [b, ib]) => {
      const va = cleDeTri(a, cle)
      const vb = cleDeTri(b, cle)
      if (typeof va === 'string' || typeof vb === 'string') {
        const d = String(va).localeCompare(String(vb), 'fr')
        return d !== 0 ? d * signe : ia - ib
      }
      return va !== vb ? (va - vb) * signe : ia - ib
    })
    .map(([o]) => o)
}

/**
 * Filtre de liste. `inclureEcartes` est VRAI par défaut : sans requête sur les
 * écartés, la marche de décomposition qui chiffre chaque décision est
 * irreproductible — un écarté se masque volontairement, jamais par défaut.
 */
export function filtrerObstacles(obstacles = [], options = {}) {
  const { provenance = 'toutes', inclureEcartes = true, recherche = '' } = options
  const q = String(recherche).trim().toLowerCase()
  return (obstacles || []).filter((o) => {
    const info = provenanceInfo(o?.provenance)
    if (!inclureEcartes && info.cle === PROVENANCE_ECARTE) return false
    if (provenance !== 'toutes' && info.cle !== normaliserProvenance(provenance)) return false
    if (q) {
      const foin = `${o?.repere ?? ''} ${designation(o)} ${info.libelle} ${
        o?.decision ?? ''
      }`.toLowerCase()
      if (!foin.includes(q)) return false
    }
    return true
  })
}
