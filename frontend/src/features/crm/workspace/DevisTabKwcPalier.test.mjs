// QJR41 (audit L3 29/08/2026, origine generator-frontend-13/R4-B2.14) — le
// calage à 5 kWc du chemin auto est la doctrine fondateur du 18/08
// (`autoQuote.js`, `arrondirAuPasKwc`) : aucun devis auto ne sort une
// taille hors palier de 5 kWc. Ce n'est PAS retiré ici. Le champ « Puissance
// cible (kWc) » de cet onglet (commentaire EZ5, `DevisTab.jsx`) promet lui-même
// « ce champ ne rejette ni n'arrondit jamais une saisie » — et RIEN dans
// l'interface ne disait au commercial qu'un 6,5 tapé deviendrait 5.
//
// QJR245 — la notice porte désormais sur la MÊME précédence que
// `createAutoQuote` (cible tapée pour CE devis, SINON `lead.
// taille_souhaitee_kwc`) et sa formulation vit UNE seule fois, dans
// `autoQuote.js::noticePalierKwc` — DevisTab.jsx et LeadDevisPanel.jsx ne
// font plus que l'appeler et rendre son résultat tel quel.
//
// DevisTab.jsx est du JSX/ESM non exécutable par `node --test` sans
// node_modules pour son propre rendu React : la partie « source » de ce test
// lit donc le fichier en texte, même patron que ToitureDesignCibleAvec.test.mjs
// / DevisGeneratorBuildDimensionnementAvec.test.mjs. `solar.js`, lui, est un
// module PUR (aucun JSX, aucune dépendance React — voir son en-tête
// « Pure functions, no I/O ») : la partie « comportement » importe donc la
// VRAIE fonction `arrondirAuPasKwc`, pas une réplique qui pourrait diverger.
//
// Run : node --test src/features/crm/workspace/DevisTabKwcPalier.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { arrondirAuPasKwc } from '../../ventes/solar.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const SRC = readFileSync(join(HERE, 'DevisTab.jsx'), 'utf8')

test('QJR245 — DevisTab.jsx importe noticePalierKwc de autoQuote.js (jamais une notice recopiée)', () => {
  assert.match(SRC, /import \{ noticePalierKwc \} from '\.\.\/\.\.\/ventes\/autoQuote'/,
    'DevisTab.jsx doit lire la notice depuis autoQuote.js, jamais une formule/texte propre')
  // La règle d'arrondi n'est plus importée directement ici : elle vit derrière
  // noticePalierKwc — un import direct de arrondirAuPasKwc serait une seconde porte.
  assert.doesNotMatch(SRC, /import \{ arrondirAuPasKwc \} from/,
    'arrondirAuPasKwc ne doit plus être importé directement par DevisTab.jsx')
})

test('QJR41 — le champ EZ5 « ne rejette ni n\'arrondit jamais une saisie » reste intact', () => {
  assert.match(SRC, /ce champ ne rejette ni n'arrondit jamais une saisie/,
    'le commentaire EZ5 doit rester : le champ continue de ne rien arrondir lui-même')
  // `value={kwcCible}` doit rester la valeur BRUTE tapée par le commercial —
  // jamais une valeur arrondie.
  assert.match(SRC, /value=\{kwcCible\}\s*\n\s*onChange=\{\(e\) => setKwcCible\(e\.target\.value\)\}/,
    'le champ doit continuer à porter/écrire la saisie brute, sans arrondi')
})

test('QJR245 — la précédence de la notice suit EXACTEMENT celle de createAutoQuote (cible du devis, sinon taille_souhaitee_kwc du lead)', () => {
  assert.match(
    SRC,
    /const kwcASaisir = parseFloat\(kwcCible\) > 0 \? kwcCible : state\.server\?\.taille_souhaitee_kwc/,
    'AVANT QJR245 : seule kwcCible (la saisie de CET écran) alimentait la notice — ' +
    'un lead à 6,5 kWc restait silencieux dès que le champ était laissé vide',
  )
  assert.match(SRC, /const noticeKwc = noticePalierKwc\(kwcASaisir\)/)
})

test('QJR245 — la notice est rendue TELLE QUELLE (texte unique de autoQuote.js), gardée par noticeKwc', () => {
  assert.match(SRC, /data-testid="lw-devis-kwc-palier"/,
    'la notice doit porter un data-testid stable')
  assert.match(SRC, /\{noticeKwc && \(/,
    'la notice doit être masquée quand noticePalierKwc rend null (saisie alignée ou vide)')
  assert.match(
    SRC,
    /<p className="gen-hint lw-devis-kwc-palier" data-testid="lw-devis-kwc-palier">\s*\n\s*\{noticeKwc\}\s*\n\s*<\/p>/,
    'le JSX doit rendre {noticeKwc} tel quel — aucun texte recopié ni assemblé ici',
  )
})

test('QJR245 — rejoué avec la VRAIE arrondirAuPasKwc importée de solar.js : la précédence choisit la bonne valeur', () => {
  // Reproduit la précédence verrouillée par le test ci-dessus, mais exécutée
  // avec l'implémentation réelle importée (pas une copie).
  const kwcASaisir = (kwcCible, tailleSouhaiteeLead) =>
    (parseFloat(kwcCible) > 0 ? kwcCible : tailleSouhaiteeLead)

  // Cas nommé par le Done= de QJR245 : cible vide, lead à 6,5 -> la notice
  // doit porter sur 6,5 (AVANT QJR245 elle restait totalement silencieuse).
  const saisiRetenue1 = kwcASaisir('', '6.5')
  assert.equal(saisiRetenue1, '6.5')
  assert.equal(arrondirAuPasKwc(parseFloat(saisiRetenue1)), 5)

  // La cible tapée pour CE devis reste prioritaire sur le lead (EZ5, inchangé).
  const saisiRetenue2 = kwcASaisir('8', '6.5')
  assert.equal(saisiRetenue2, '8')
  assert.equal(arrondirAuPasKwc(parseFloat(saisiRetenue2)), 10)

  // Ni cible ni lead : rien à arrondir, aucune notice possible.
  const saisiRetenue3 = kwcASaisir('', undefined)
  assert.equal(saisiRetenue3, undefined)
})
