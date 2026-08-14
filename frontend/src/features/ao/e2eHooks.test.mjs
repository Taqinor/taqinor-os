// AOF8 — Contrat de hooks DOM `data-ao-*`.
// Zéro dépendance (node:test + node:fs, comme urgency.test.mjs/contrast.test.mjs) :
// exécutable via `node --test` sans npm/vitest installés.
//
// Deux garanties :
//  1. Aucun hook du contrat ne peut disparaître de `E2E_HOOKS.md` ni y perdre
//     son propriétaire/sa sémantique, et `E2E_HOOKS.md` n'en documente aucun
//     qui ne soit pas dans `ALL_HOOKS` (les deux listes sont tenues égales).
//  2. Aucun écran de `features/ao/**` ne peut introduire un `data-ao-*` hors de
//     cette liste (garde anti-invention).
//
// Le socle transverse figé avant le premier écran comptait 11 noms ; les
// écrans de l'atelier de toiture (AOF78→AOF91) l'ont étendu DÉLIBÉRÉMENT —
// chaque ajout est passé par `E2E_HOOKS.md` + `ALL_HOOKS` dans le même commit,
// jamais par un composant seul. C'est la seule façon d'étendre le contrat.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const DOC_PATH = join(HERE, 'E2E_HOOKS.md')

// Source de vérité normative (AOF8) — la SEULE liste qui grandit le contrat ;
// toute extension passe par une nouvelle entrée ICI + dans E2E_HOOKS.md, dans
// le MÊME commit (le 3e test compare les deux listes et refuse la divergence).
//
// Le socle transverse d'AOF8 (11 noms) reste PRIORITAIRE : un écran qui a
// besoin d'un repère générique prend le nom du socle. Les groupes suivants
// sont l'extension délibérée du contrat par les écrans de l'atelier de
// toiture (AOF78→AOF91), publiés après le gel du socle : ils portent des
// repères par entité et par action que onze noms génériques ne peuvent pas
// exprimer. Ordre : socle, puis un groupe par écran dans l'ordre des tâches,
// alphabétique à l'intérieur de chaque groupe.
export const ALL_HOOKS = [
  // ── PACT166/167/170 — atelier toiture + questions terrain ────────────────
  'data-ao-annotation-serie',
  'data-ao-note-question',
  'data-ao-legende-provenance',
  'data-ao-enveloppe-arc-retenue',
  'data-ao-question-proposee',
  'data-ao-atelier-note',
  // ── Groupe PV — studio (plan imposé), liste des calepinages, synthèse ────
  'data-ao-impose',
  'data-ao-impose-verdict',
  'data-ao-ecart-optimum',
  'data-ao-variante-retenue',
  'data-ao-raisons-non-publiabilite',
  'data-ao-synthese-calepinage',
  'data-ao-synthese-toitures',
  // ── Socle transverse (AOF8) ──────────────────────────────────────────────
  'data-ao-canvas',
  'data-ao-outil',
  'data-ao-verdict',
  'data-ao-compte',
  'data-ao-tiroir',
  'data-ao-variante',
  'data-ao-piece',
  'data-ao-controle',
  'data-ao-repere',
  'data-ao-provenance',
  'data-ao-etat',

  // ── Wizard « Nouvelle toiture » — AOF78 ──────────────────────────────────
  'data-ao-porte',
  'data-ao-porte-panneau',
  'data-ao-toiture-wizard',
  'data-ao-wizard-creer',

  // ── Calque de fond (underlay PDF / image) — AOF79 ────────────────────────
  'data-ao-underlay',
  'data-ao-underlay-erreur',
  'data-ao-underlay-rotation',

  // ── Calibration 2 points — AOF80 ─────────────────────────────────────────
  'data-ao-calibration',
  'data-ao-calibration-alerte',
  'data-ao-calibration-motif',
  'data-ao-calibration-surface',
  'data-ao-calibration-valider',
  'data-ao-echelle',

  // ── Import DXF — AOF81 ───────────────────────────────────────────────────
  'data-ao-dxf-apercu',
  'data-ao-dxf-calques',
  'data-ao-dxf-degrade',
  'data-ao-dxf-importer',
  'data-ao-dxf-repli',
  'data-ao-import-dxf',

  // ── Reprise depuis la carte — AOF82 ──────────────────────────────────────
  'data-ao-carte-repli',
  'data-ao-carte-reprendre',
  'data-ao-reprise-carte',

  // ── Outil de tracé from scratch — AOF84 ──────────────────────────────────
  'data-ao-outil-trace',
  'data-ao-trace-annuler',
  'data-ao-trace-direction',
  'data-ao-trace-erreur',
  'data-ao-trace-etat',
  'data-ao-trace-fermer',
  'data-ao-trace-sommets',

  // ── Chaînes de cotes — AOF85 ─────────────────────────────────────────────
  'data-ao-chaine',
  'data-ao-chaine-axe',
  'data-ao-chaine-edition',
  'data-ao-chaine-nouvelle',
  'data-ao-chaine-somme',
  'data-ao-chaines',
  'data-ao-chaines-planche',
  'data-ao-cote',
  'data-ao-cote-axe',
  'data-ao-cote-provenance',
  'data-ao-cote-texte',

  // ── Fermetures et arbitrage — AOF86 ──────────────────────────────────────
  'data-ao-arbitrage',
  'data-ao-fermeture',
  'data-ao-fermeture-accepter',
  'data-ao-fermeture-apercu',
  'data-ao-fermeture-appliquer',
  'data-ao-fermeture-motif',
  'data-ao-fermeture-prorata',
  'data-ao-fermeture-residu',
  'data-ao-fermeture-residu-pct',
  'data-ao-fermeture-statut',
  'data-ao-fermetures',
  'data-ao-fermetures-calepiner',
  'data-ao-fermetures-verrou',

  // ── Points à lever — AOF87 ───────────────────────────────────────────────
  'data-ao-point',
  'data-ao-point-motif',
  'data-ao-point-provenance',
  'data-ao-points-lever',
  'data-ao-points-lever-export',
  'data-ao-points-lever-invariant',
  'data-ao-points-lever-vide',

  // ── Obstacles : outils et inspecteur — AOF88 ─────────────────────────────
  'data-ao-inspecteur',
  'data-ao-obstacle',
  'data-ao-obstacle-brouillon',
  'data-ao-obstacle-degagement',
  'data-ao-obstacle-halo',
  'data-ao-obstacle-nature',
  'data-ao-obstacle-rendre-derive',
  'data-ao-obstacle-surcharge',
  'data-ao-obstacles-doublons',
  'data-ao-obstacles-planche',
  'data-ao-outil-terminer',
  'data-ao-outils-obstacles',

  // ── Zones (interdite / réservée / préférée) — AOF89 ──────────────────────
  'data-ao-zone',
  'data-ao-zone-ajouter-point',
  'data-ao-zone-brouillon',
  'data-ao-zone-erreur',
  'data-ao-zone-legende',
  'data-ao-zone-ligne',
  'data-ao-zone-nature',
  'data-ao-zone-outil',
  'data-ao-zone-terminer',
  'data-ao-zones',
  'data-ao-zones-compte',
  'data-ao-zones-legende',
  'data-ao-zones-planche',
  'data-ao-zones-regle',
  'data-ao-zones-surface-retiree',

  // ── Liste d'obstacles et garde de publication — AOF90 ────────────────────
  'data-ao-fautif',
  'data-ao-obstacles',
  'data-ao-obstacles-vide',
  'data-ao-poser-question',
  'data-ao-survole',

  // ── Enveloppes non rectangulaires (L et arc) — AOF91 ─────────────────────
  'data-ao-arc-a-cheval',
  'data-ao-arc-developpe',
  'data-ao-arc-muret',
  'data-ao-arc-muret-reel',
  'data-ao-arc-pas',
  'data-ao-arc-refus',
  'data-ao-arc-rendu',
  'data-ao-arc-segment',
  'data-ao-arc-segment-reel',
  'data-ao-arc-valider',
  'data-ao-enveloppe',
  'data-ao-l-aire',
  'data-ao-l-bande',
  'data-ao-l-bande-traversante',
  'data-ao-l-incomplet',
  'data-ao-l-perte',
  'data-ao-l-refus',
  'data-ao-l-regle',
  'data-ao-l-sommets',
  'data-ao-l-valider',

  // ── Fiche affaire : frontière de chargement d'un panneau — 03/08/2026 ────
  'data-ao-panneau-differe',
]

function readDoc() {
  return readFileSync(DOC_PATH, 'utf8')
}

// Extrait les lignes de tableau markdown `| \`data-ao-x\` | owner | sémantique |`.
function parseHookRows(doc) {
  const rows = new Map()
  const lineRe = /^\|\s*`(data-ao-[a-z-]+)`\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$/gm
  let m
  while ((m = lineRe.exec(doc)) !== null) {
    rows.set(m[1], { owner: m[2], semantique: m[3] })
  }
  return rows
}

test('E2E_HOOKS.md publie chaque hook normatif', () => {
  const rows = parseHookRows(readDoc())
  for (const hook of ALL_HOOKS) {
    assert.ok(rows.has(hook), `hook manquant dans E2E_HOOKS.md : ${hook}`)
  }
})

test('chaque hook listé porte un propriétaire ET une sémantique non vides', () => {
  const rows = parseHookRows(readDoc())
  for (const hook of ALL_HOOKS) {
    const row = rows.get(hook)
    assert.ok(row, `hook manquant : ${hook}`)
    assert.ok(row.owner.length > 0, `${hook} : propriétaire vide`)
    assert.ok(row.semantique.length > 0, `${hook} : sémantique vide`)
  }
})

test('E2E_HOOKS.md ne documente aucun hook hors de la liste normative (pas de dérive silencieuse)', () => {
  const rows = parseHookRows(readDoc())
  const documented = [...rows.keys()].sort()
  assert.deepEqual(documented, [...ALL_HOOKS].sort())
})

// ── Garde anti-invention : aucun `data-ao-*` dans le code d'écran ne sort de
//    la liste normative. Parcourt `features/ao/**` (ce dossier), en ignorant
//    les fichiers de contrat eux-mêmes. ────────────────────────────────────
function walk(dir, out = []) {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry)
    const st = statSync(full)
    if (st.isDirectory()) {
      walk(full, out)
    } else if (/\.(jsx?|mjs)$/.test(entry) && entry !== 'e2eHooks.test.mjs') {
      out.push(full)
    }
  }
  return out
}

test('aucun data-ao-* hors contrat dans features/ao/** (garde anti-invention)', () => {
  const attrRe = /data-ao-[a-z-]+/g
  const allowed = new Set(ALL_HOOKS)
  const offenders = []
  for (const file of walk(HERE)) {
    const src = readFileSync(file, 'utf8')
    const found = src.match(attrRe) || []
    for (const hook of found) {
      if (!allowed.has(hook)) offenders.push(`${hook} (${file})`)
    }
  }
  assert.deepEqual(offenders, [], `hooks hors contrat : ${offenders.join(', ')}`)
})
