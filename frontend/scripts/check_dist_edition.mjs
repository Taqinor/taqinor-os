#!/usr/bin/env node
/* SOL6 — Garde : le dist d'une édition ne contient AUCUN vertical parqué.
   ----------------------------------------------------------------------------
   Le tree-shake par condition littérale (`__EDITION_SOLAIRE__` /
   `__EDITION_A_MRP__`, cf. `vite.config.js` + `src/router/moduleRoutes.jsx`)
   est SILENCIEUX quand il échoue : un import oublié rattache le vertical au
   graphe et le bundle solaire regrossit sans que rien ne casse. Cette garde
   rend cet échec BRUYANT.

   Elle ne cherche pas des noms de chunk (instables, hachés) mais des
   SIGNATURES DÉRIVÉES DE LA SOURCE : les chemins de route déclarés par le
   `module.config.jsx` de chaque vertical parqué. Si `/mrp/ordres-fabrication`
   apparaît dans le dist solaire, c'est que l'écran y est.

   Contrôle POSITIF inclus : une signature d'un module GARDÉ doit être présente
   — sans quoi un dist vide ou introuvable ferait passer la garde pour verte.

   Usage :
     node scripts/check_dist_edition.mjs [--edition solar] [--dist dist]
*/
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  ARBRES, EDITION_SOLAR, normaliserEdition, verticauxParques,
} from '../src/lib/editions.js'

const ICI = dirname(fileURLToPath(import.meta.url))
const FRONTEND = resolve(ICI, '..')

function arg(nom, defaut) {
  const i = process.argv.indexOf(`--${nom}`)
  return i !== -1 && process.argv[i + 1] ? process.argv[i + 1] : defaut
}

const EDITION = normaliserEdition(arg('edition', EDITION_SOLAR))
const DIST = resolve(FRONTEND, arg('dist', 'dist'))

/** Chemins de route (`path:` / `to:`) déclarés par un module.config. */
function signaturesDeModule(vertical) {
  const fichier = join(FRONTEND, 'src', 'features', vertical, 'module.config.jsx')
  let source
  try {
    source = readFileSync(fichier, 'utf8')
  } catch {
    return []
  }
  const trouvees = new Set()
  const motif = /\b(?:path|to):\s*'(\/[^']{5,})'/g
  let m
  while ((m = motif.exec(source)) !== null) {
    // Un chemin paramétré (`/x/:id`) n'apparaît pas tel quel dans le bundle
    // découpé : on garde son préfixe stable.
    const chemin = m[1].split('/:')[0]
    if (chemin.length >= 6) trouvees.add(chemin)
  }
  return [...trouvees]
}

/* Une signature n'est utilisable que si elle est EXCLUSIVE au vertical parqué.
   Beaucoup de chemins de route (`/mrp/oee`, `/sante/admissions`) apparaissent
   AUSSI comme chemins d'API dans `src/api/<x>Api.js` — un module GARDÉ, qui
   reste légitimement dans le dist. Sans ce filtre, la garde crierait au faux
   positif sur chaque build. On retire donc toute signature présente dans une
   source HORS des arbres parqués. */
function sourcesGardees() {
  const out = []
  const pile = [join(FRONTEND, 'src')]
  const parques = verticauxParques(EDITION)
  const estParque = (chemin) => {
    const norm = chemin.replace(/\\/g, '/')
    return ARBRES.some((arbre) => parques.some(
      (v) => norm.includes(`/src/${arbre}/${v}/`)))
  }
  while (pile.length) {
    const courant = pile.pop()
    let entrees
    try {
      entrees = readdirSync(courant)
    } catch {
      continue
    }
    for (const nom of entrees) {
      const chemin = join(courant, nom)
      if (statSync(chemin).isDirectory()) {
        pile.push(chemin)
      } else if (/\.(js|jsx|mjs)$/.test(nom) && !nom.includes('.test.')
                 && !estParque(chemin)) {
        out.push(readFileSync(chemin, 'utf8'))
      }
    }
  }
  return out
}

/* Noms de fichiers écran des arbres `pages/<v>` et `components/<v>`.
   Un nom de chunk Rollup dérive du BASENAME du module : si le même basename
   existe aussi dans un arbre GARDÉ (mesuré : `RessourcesPage` vit à la fois
   sous `pages/agriculture/` et sous `features/gestion_projet/pages/`), le
   chunk émis est ambigu. On ne garde donc que les basenames EXCLUSIFS au
   vertical parqué — même principe que pour les signatures de route. */
function ecransDuVertical(vertical, basenamesGardes) {
  const out = []
  for (const arbre of ARBRES.filter((a) => a !== 'features')) {
    const dossier = join(FRONTEND, 'src', arbre, vertical)
    let entrees
    try {
      entrees = readdirSync(dossier)
    } catch {
      continue
    }
    for (const nom of entrees) {
      if (!nom.endsWith('.jsx') || nom.includes('.test.')) continue
      const base = nom.replace(/\.jsx$/, '')
      if (!basenamesGardes.has(base)) out.push(base)
    }
  }
  return out
}

/** Basenames de composants vivant HORS des arbres parqués (anti-collision). */
function basenamesGardes() {
  const out = new Set()
  const parques = verticauxParques(EDITION)
  const pile = [join(FRONTEND, 'src')]
  const estParque = (chemin) => {
    const norm = chemin.replace(/\\/g, '/')
    return ARBRES.some((arbre) => parques.some(
      (v) => norm.includes(`/src/${arbre}/${v}/`)))
  }
  while (pile.length) {
    const courant = pile.pop()
    let entrees
    try {
      entrees = readdirSync(courant)
    } catch {
      continue
    }
    for (const nom of entrees) {
      const chemin = join(courant, nom)
      if (statSync(chemin).isDirectory()) pile.push(chemin)
      else if (nom.endsWith('.jsx') && !nom.includes('.test.')
               && !estParque(chemin)) {
        out.add(nom.replace(/\.jsx$/, ''))
      }
    }
  }
  return out
}

function fichiersJs(racine) {
  const out = []
  const pile = [racine]
  while (pile.length) {
    const courant = pile.pop()
    let entrees
    try {
      entrees = readdirSync(courant)
    } catch {
      continue
    }
    for (const nom of entrees) {
      const chemin = join(courant, nom)
      if (statSync(chemin).isDirectory()) pile.push(chemin)
      else if (nom.endsWith('.js')) out.push(chemin)
    }
  }
  return out
}

function main() {
  const parques = verticauxParques(EDITION)
  if (parques.length === 0) {
    console.log(
      `check_dist_edition: edition '${EDITION}' ne parque aucun vertical `
      + '- rien a verifier.')
    return 0
  }

  const fichiers = fichiersJs(DIST)
  if (fichiers.length === 0) {
    console.error(
      `check_dist_edition: AUCUN fichier .js sous ${DIST} - le build n'a pas `
      + 'ete produit (ou le chemin --dist est faux).')
    return 1
  }

  const contenus = fichiers.map((f) => ({
    nom: f.slice(DIST.length + 1).replace(/\\/g, '/'),
    code: readFileSync(f, 'utf8'),
  }))

  const violations = []
  const gardees = sourcesGardees()
  const basesGardees = basenamesGardes()
  const estExclusive = (signature) =>
    !gardees.some((code) => code.includes(signature))

  for (const vertical of parques) {
    // (a) signatures de route EXCLUSIVES déclarées par le vertical.
    for (const signature of signaturesDeModule(vertical).filter(estExclusive)) {
      for (const { nom, code } of contenus) {
        if (code.includes(signature)) {
          violations.push(
            `vertical « ${vertical} » : la route « ${signature} » est encore `
            + `dans ${nom}`)
          break
        }
      }
    }
    // (b) noms de chunks dérivés des écrans `pages/<v>` / `components/<v>`.
    for (const ecran of ecransDuVertical(vertical, basesGardees)) {
      const chunk = contenus.find(
        ({ nom }) => new RegExp(`(^|/)${ecran}-[A-Za-z0-9_-]+\\.js$`).test(nom))
      if (chunk) {
        violations.push(
          `vertical « ${vertical} » : l'écran ${ecran} a produit le chunk `
          + `${chunk.nom}`)
      }
    }
  }

  // Contrôle POSITIF : un dist valide contient toujours les modules gardés.
  const temoins = ['/ventes/devis', '/crm/leads']
  const manquants = temoins.filter(
    (t) => !contenus.some(({ code }) => code.includes(t)))
  if (manquants.length) {
    console.error(
      'check_dist_edition: controle positif ECHOUE - routes gardees absentes '
      + `du dist (${manquants.join(', ')}). Le dist analyse n'est pas un build `
      + 'complet de l\'application ; la garde serait verte pour rien.')
    return 1
  }

  if (violations.length) {
    console.error(
      `check_dist_edition: ${violations.length} fuite(s) de vertical parque `
      + `dans le dist de l'edition '${EDITION}' :\n`)
    for (const v of violations) console.error(`  - ${v}`)
    console.error(
      "\nUn import depuis une surface gardee a rattache le vertical au graphe. "
      + "Chercher l'import fautif (la regle eslint SOL6 attrape les imports "
      + 'statiques ET dynamiques) ou verifier la condition litterale '
      + '(__EDITION_SOLAIRE__ / __EDITION_A_<X>__).')
    return 1
  }

  console.log(
    `check_dist_edition: OK - ${contenus.length} fichier(s) .js analyse(s), `
    + `aucun des ${parques.length} vertical(aux) parque(s) `
    + `(${parques.join(', ')}) n'est present dans le dist '${EDITION}'.`)
  return 0
}

process.exit(main())
