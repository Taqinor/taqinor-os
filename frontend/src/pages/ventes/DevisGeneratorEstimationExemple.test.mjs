// QJR35 (audit L3 29/08/2026, origine QJF2) — le useMemo `roi` (:900) tourne
// dès que dKwp > 0 && dMonthly.some(v => v > 0) — vrai AU MONTAGE avec
// DEFAULT_MONTHLY_BILLS, avant toute saisie — et alimente les cartes
// Économies/ROI (Sans/Avec batterie). Le graphique en dessous EST gardé par
// `facturesSaisies` (N4) ; les cartes ne l'étaient pas : elles pouvaient
// afficher un chiffre calculé sur des factures D'EXEMPLE sans jamais le dire.
//
// Correctif minimal (AVANT décomposition — QJR89/QJR90 la rendent
// structurelle) : quand la carte lit une valeur dérivée LOCALEMENT
// (!facturesSaisies && !etudeHoraireSourceServeur), une puce « estimation
// d'exemple » est rendue À CÔTÉ de la valeur — jamais la carte cachée,
// jamais un autre chiffre inventé à la place.
//
// DevisGenerator.jsx est du JSX/ESM non exécutable par `node --test` sans
// node_modules : ce test lit donc le SOURCE, même patron que
// DevisGeneratorFacturesSaisies.test.mjs / DevisGeneratorSizingServeur.test.mjs.
//
// Run : node --test src/pages/ventes/DevisGeneratorEstimationExemple.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const DG = readFileSync(join(HERE, 'DevisGenerator.jsx'), 'utf8')

test('QJR35 — apercuEstimationExemple est dérivé de !facturesSaisies && !etudeHoraireSourceServeur (une seule dérivation)', () => {
  assert.match(DG,
    /const apercuEstimationExemple = !facturesSaisies && !etudeHoraireSourceServeur/,
    'la dérivation attendue est introuvable telle quelle')
})

test('QJR35 — MetricCard accepte un prop `badge` et le rend À CÔTÉ de la valeur (jamais en cachant la carte)', () => {
  const idx = DG.indexOf('function MetricCard(')
  assert.ok(idx > -1, 'MetricCard introuvable')
  const bloc = DG.slice(idx, idx + 1200)
  assert.match(bloc, /function MetricCard\(\{ label, value, unit, recommended, accent, badge \}\)/,
    'MetricCard doit accepter un prop badge')
  // La carte reste TOUJOURS rendue (aucune condition badge && null autour de
  // gen-metric-value) : le badge est un AJOUT à côté de {value}, pas un
  // remplacement conditionnel de la carte entière.
  assert.match(bloc, /<div className="gen-metric-value">\s*\n\s*\{value\}/,
    'la valeur doit rester rendue inconditionnellement')
  assert.match(bloc, /\{badge && \(/, 'le badge doit être un ajout conditionnel, pas la carte entière')
  assert.match(bloc, /data-testid="gen-metric-badge-exemple"/,
    'le badge doit porter un data-testid stable pour les tests e2e')
  // Le texte « estimation d'exemple » lui-même n'est PAS en dur dans
  // MetricCard : il est passé par chaque appelant (badge={...}).
  assert.doesNotMatch(bloc, /estimation d'exemple/)
})

test('QJR35 — les 4 cartes Économies/ROI (Sans + Avec batterie) reçoivent le badge conditionnel, jamais les cartes Coût', () => {
  const titleIdxs = []
  let from = 0
  while (true) {
    const i = DG.indexOf('gen-compare-col-title', from)
    if (i === -1) break
    titleIdxs.push(i)
    from = i + 1
  }
  assert.equal(titleIdxs.length, 2, 'les deux colonnes gen-compare-col-title (Sans/Avec) sont introuvables')

  // Colonne "Sans batterie" (1ʳᵉ occurrence).
  const sansBloc = DG.slice(titleIdxs[0], titleIdxs[0] + 900)
  assert.match(sansBloc, /Sans batterie/)
  assert.match(sansBloc, /<MetricCard label="Économies"[\s\S]*?badge=\{apercuEstimationExemple \? 'estimation d\\'exemple' : null\} \/>/)
  assert.match(sansBloc, /<MetricCard label="ROI"[\s\S]*?badge=\{apercuEstimationExemple \? 'estimation d\\'exemple' : null\} \/>/)
  // La carte Coût (chiffre réel du devis, jamais dérivé du miroir local ROI)
  // ne doit PAS recevoir ce badge.
  const coutSansIdx = sansBloc.indexOf('<MetricCard label="Coût"')
  assert.ok(coutSansIdx > -1)
  const coutSansBloc = sansBloc.slice(coutSansIdx, coutSansIdx + 200)
  assert.doesNotMatch(coutSansBloc, /badge=/)

  // Colonne "Avec batterie" (2ᵉ occurrence).
  const avecBloc = DG.slice(titleIdxs[1], titleIdxs[1] + 1900)
  assert.match(avecBloc, /Avec batterie/)
  assert.match(avecBloc, /<MetricCard label="Économies"[\s\S]*?badge=\{apercuEstimationExemple \? 'estimation d\\'exemple' : null\} \/>/)
  assert.match(avecBloc, /<MetricCard label="ROI"[\s\S]*?badge=\{apercuEstimationExemple \? 'estimation d\\'exemple' : null\} \/>/)
  const coutAvecIdx = avecBloc.indexOf('<MetricCard label="Coût"')
  assert.ok(coutAvecIdx > -1)
  const coutAvecBloc = avecBloc.slice(coutAvecIdx, coutAvecIdx + 200)
  assert.doesNotMatch(coutAvecBloc, /badge=/)
})

test('QJR35 — rejoué : au montage (aucune facture saisie, aucune étude serveur) la puce est due ; dès qu\'une facture réelle ou l\'étude serveur existe, elle disparaît', () => {
  // Reproduit EXACTEMENT la dérivation verrouillée par le 1er test.
  const apercuEstimationExemple = (facturesSaisies, etudeHoraireSourceServeur) =>
    !facturesSaisies && !etudeHoraireSourceServeur

  // Montage : monthly == DEFAULT_MONTHLY_BILLS (facturesSaisies=false),
  // aucune réponse serveur encore reçue.
  assert.equal(apercuEstimationExemple(false, false), true,
    'au montage, sans rien saisi, la puce doit être due')
  // Une vraie facture saisie suffit à l'éteindre, même sans étude serveur
  // (marché non-résidentiel, ou étude non encore chargée).
  assert.equal(apercuEstimationExemple(true, false), false)
  // L'étude horaire serveur (résidentiel, PVGIS réel) l'éteint aussi.
  assert.equal(apercuEstimationExemple(false, true), false)
  assert.equal(apercuEstimationExemple(true, true), false)
})
