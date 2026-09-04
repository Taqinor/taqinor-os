// QJR426 (DR5) — les treize cartes de métrique du générateur (bloc « Aperçu
// de la Simulation » + étude industrielle/commercial) portent la VALEUR
// SIGNÉE (QJR86) : `valeur={moteur(...)|apercu(...)|signerEcoOuRoi(...)}`
// plutôt que la prop littérale `value=` héritée — `CarteMetrique` (déjà
// câblée pour la voie signée depuis QJR100) reste le seul déballeur
// (`unwrap`), cet écran ne fait QUE signer.
//
// DevisGenerator.jsx est du JSX/ESM non exécutable par `node --test` sans
// node_modules : la partie « les 13 appels utilisent `valeur=`, aucune
// provenance inventée, rendu byte-identique » lit donc le SOURCE, même
// patron que DevisGeneratorProvenanceDV3.test.mjs /
// DevisGeneratorEstimationExemple.test.mjs. La partie « `unwrap()` refuse un
// nombre nu » importe et EXÉCUTE la vraie primitive `quote/valeur.js` (module
// pur, aucune dépendance) — c'est le test ROUGE→VERT réel de la tâche.
//
// Run : node --test src/pages/ventes/DevisGeneratorCartesValeurSignee.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { unwrap, moteur, apercu, saisie, absent, PUCE_APERCU } from '../../features/ventes/quote/valeur.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const DG = readFileSync(join(HERE, 'DevisGenerator.jsx'), 'utf8')

// ── ROUGE → VERT (exécuté) : unwrap() refuse un nombre nu ───────────────────
// Avant QJR426, AUCUNE des 13 cartes n'empruntait ce chemin (elles passaient
// toutes par `value=` littéral) : ce test aurait été GLOBALEMENT sans objet.
// Il ne l'est plus — `unwrap` est désormais le chemin RÉEL des 13 cartes, et
// cette garde est ce qui rend « aucun nombre nu ne se rend » exécutable.
test('QJR426 — unwrap() lève un TypeError si un nombre (ou toute valeur non signée) lui est passé', () => {
  assert.throws(() => unwrap(1234), TypeError)
  assert.throws(() => unwrap('1234 MAD'), TypeError)
  assert.throws(() => unwrap(null), TypeError)
  assert.throws(() => unwrap(undefined), TypeError)
  // Signée, elle passe — c'est la voie que les 13 cartes empruntent désormais.
  assert.doesNotThrow(() => unwrap(moteur(1234)))
  assert.doesNotThrow(() => unwrap(apercu('estimation')))
  assert.doesNotThrow(() => unwrap(saisie(42)))
  assert.doesNotThrow(() => unwrap(absent('motif de test')))
})

// ── Les 13 appels utilisent TOUS `valeur=`, plus jamais `value=` ────────────

const TOUTES_LES_CARTES_LABELS = [
  "Taux d'autoconsommation", 'Taux de couverture', 'Économies annuelles (étude)',
  'Payback (étude)', 'Production annuelle', "Taux d'autoconsommation (sans)",
  'Taux de couverture (sans)', 'Économies', 'ROI', 'Coût',
]

function tousLesBlocsDeLabel(label) {
  const blocs = []
  let from = 0
  for (;;) {
    const idx = DG.indexOf(`<CarteMetrique label="${label}"`, from)
    if (idx === -1) break
    blocs.push(DG.slice(idx, idx + 400))
    from = idx + 1
  }
  assert.ok(blocs.length > 0, `carte "${label}" introuvable`)
  return blocs
}

test('QJR426 — les 13 sites CarteMetrique du générateur portent `valeur=`, aucun `value=` littéral ne subsiste', () => {
  const total = (DG.match(/<CarteMetrique label=/g) || []).length
  assert.equal(total, 13, 'le nombre de cartes CarteMetrique a changé — revoir le périmètre QJR426')
  for (const label of TOUTES_LES_CARTES_LABELS) {
    for (const bloc of tousLesBlocsDeLabel(label)) {
      assert.match(bloc, /\bvaleur=\{/, `carte "${label}" : doit porter la prop \`valeur=\``)
      assert.doesNotMatch(bloc, /\bvalue=\{/, `carte "${label}" : le \`value=\` littéral doit avoir disparu`)
      // Chaque `valeur=` doit être signée par une des trois primitives — pas
      // une expression nue passée telle quelle (ce que `unwrap` refuserait à
      // l'exécution, et que le second test ci-dessous vérifie déjà runtime).
      assert.match(bloc, /valeur=\{(moteur|apercu|signerEcoOuRoi)\(/,
        `carte "${label}" : la valeur doit être signée (moteur/apercu/signerEcoOuRoi), jamais nue`)
    }
  }
})

test('QJR426 — `moteur`/`apercu` sont importés de quote/valeur.js dans DevisGenerator.jsx', () => {
  assert.match(DG, /import \{ moteur, apercu \} from '\.\.\/\.\.\/features\/ventes\/quote\/valeur'/)
})

// ── Marque de provenance là où elle n'est pas évidente (et nulle part une
// provenance INVENTÉE) ──────────────────────────────────────────────────────
//
// Les 4 cartes indus/commercial (étude locale `computeEtudeIndustrielle`,
// QJR213/DV3) ne sont JAMAIS authoritatives : elles signent TOUJOURS avec
// `apercu()`, dont `unwrap()` dérive AUTOMATIQUEMENT la puce `PUCE_APERCU`
// (« estimation d'exemple ») — le même motif que l'ancien littéral
// `badge="estimation locale"` qu'elles portaient (chiffre local, pas une
// mesure), sous le libellé canonique de la primitive partagée plutôt qu'un
// texte ad hoc à elles.
const LABELS_TOUJOURS_APERCU = [
  "Taux d'autoconsommation", 'Taux de couverture',
  'Économies annuelles (étude)', 'Payback (étude)',
]

test('QJR426 — les 4 cartes de l’étude locale (DV3) signent TOUJOURS avec apercu() : la puce PUCE_APERCU est due', () => {
  for (const label of LABELS_TOUJOURS_APERCU) {
    const [bloc] = tousLesBlocsDeLabel(label)
    assert.match(bloc, /valeur=\{apercu\(/, `carte "${label}" : doit toujours signer apercu()`)
  }
  // La puce que `CarteMetrique`/`unwrap` posera est celle-ci, VÉRIFIÉE par
  // exécution — jamais un texte réinventé à la volée par l'écran.
  assert.equal(unwrap(apercu('x')).puce, PUCE_APERCU)
  assert.equal(PUCE_APERCU, "estimation d'exemple")
})

// Les cartes « Production annuelle » et les deux cartes horaires « (sans) »
// ne montraient AUCUNE puce hier (aucun `badge=`, quelle que soit la source
// réelle du chiffre) : `moteur()` reproduit ce silence à l'octet — jamais un
// nouveau badge introduit par ce changement de prop.
const LABELS_TOUJOURS_MOTEUR_SANS_PUCE = [
  'Production annuelle', "Taux d'autoconsommation (sans)", 'Taux de couverture (sans)',
]

test('QJR426 — les cartes toujours-serveur/toujours-certaines signent moteur() : aucune puce nouvelle (byte-identique)', () => {
  for (const label of LABELS_TOUJOURS_MOTEUR_SANS_PUCE) {
    const [bloc] = tousLesBlocsDeLabel(label)
    assert.match(bloc, /valeur=\{moteur\(/, `carte "${label}" : doit signer moteur() (aucune puce avant, aucune après)`)
  }
  assert.equal(unwrap(moteur('x')).puce, null)
})

// Économies/ROI (Sans + Avec) portaient hier un badge CONDITIONNEL à
// `apercuEstimationExemple` avec le texte EXACT « estimation d'exemple » —
// déjà, avant ce correctif, strictement identique à `PUCE_APERCU`.
// `signerEcoOuRoi` (défini une seule fois près de `apercuEstimationExemple`)
// reproduit ce même conditionnel via `apercu()`/`moteur()` : rendu
// byte-identique, jamais un texte différent.
test('QJR426 — Économies/ROI conditionnent leur puce EXACTEMENT comme hier, via signerEcoOuRoi', () => {
  assert.match(DG,
    /const signerEcoOuRoi = \(v\) => \(apercuEstimationExemple \? apercu\(v\) : moteur\(v\)\)/,
    'le discriminant doit reproduire exactement apercuEstimationExemple ? ... : ...')
  for (const label of ['Économies', 'ROI']) {
    for (const bloc of tousLesBlocsDeLabel(label)) {
      assert.match(bloc, /valeur=\{signerEcoOuRoi\(/, `carte "${label}" : doit passer par signerEcoOuRoi`)
    }
  }
  // Coût (les deux occurrences) ne passe JAMAIS par ce discriminant : c'est
  // le total réel des lignes du devis, jamais un repère de vente.
  for (const bloc of tousLesBlocsDeLabel('Coût')) {
    assert.doesNotMatch(bloc, /signerEcoOuRoi/, 'carte "Coût" : jamais de discriminant apercu/moteur conditionnel')
    assert.match(bloc, /valeur=\{moteur\(/, 'carte "Coût" : moteur() inconditionnel')
  }
})

// ── Troisième test — libellés et VALEURS (l'expression qui les calcule)
// identiques à l'octet à celles d'hier : la bascule ne touche que le nom de
// la prop et son enrobage (moteur/apercu/signerEcoOuRoi), jamais le calcul
// ni le texte affiché. ───────────────────────────────────────────────────
//
// Chaque entrée reproduit l'expression EXACTE qui vivait hier dans
// `value={...}` pour cette carte (avant QJR426) ; le test affirme qu'elle vit
// désormais, MOT POUR MOT, comme unique argument du signeur.
const EXPRESSIONS_INCHANGEES = [
  { label: "Taux d'autoconsommation", expr: '`${etudeCI.taux_autoconso} %`' },
  { label: 'Taux de couverture', expr: '`${etudeCI.taux_couverture} %`' },
  { label: 'Économies annuelles (étude)', expr: 'fmtNum(etudeCI.economies_annuelles)' },
  { label: 'Payback (étude)', expr: '`${etudeCI.payback} ans`' },
  { label: 'Production annuelle', expr: 'fmtNum(Math.round(apercuProductionKwh))' },
  {
    label: "Taux d'autoconsommation (sans)",
    expr: '`${formatNumber(etudeHoraireAnnuel.taux_autoconso_sans * 100, { decimals: 0 })} %`',
  },
  {
    label: 'Taux de couverture (sans)',
    expr: '`${formatNumber(etudeHoraireAnnuel.couverture_sans * 100, { decimals: 0 })} %`',
  },
]

test('QJR426 — les expressions de valeur des cartes à occurrence UNIQUE sont préservées mot pour mot', () => {
  for (const { label, expr } of EXPRESSIONS_INCHANGEES) {
    const [bloc] = tousLesBlocsDeLabel(label)
    assert.ok(bloc.includes(expr),
      `carte "${label}" : l'expression "${expr}" doit apparaître inchangée dans l'appel signé`)
  }
})

// Économies/ROI/Coût apparaissent deux fois (Sans/Avec) avec deux variables
// distinctes (apercuEcoSans/apercuEcoAvec, apercuPaybackSans/apercuPaybackAvec,
// totals.totalSans/totals.totalAvec) : vérifiées occurrence par occurrence.
test('QJR426 — Économies/ROI/Coût (Sans puis Avec) gardent leurs expressions EXACTES, dans cet ordre', () => {
  const economies = tousLesBlocsDeLabel('Économies')
  assert.ok(economies[0].includes('fmtNum(Math.round(apercuEcoSans))'))
  assert.ok(economies[1].includes('fmtNum(Math.round(apercuEcoAvec))'))

  const roi = tousLesBlocsDeLabel('ROI')
  assert.ok(roi[0].includes("apercuPaybackSans != null ? apercuPaybackSans + ' ans' : 'N/A'"))
  assert.ok(roi[1].includes("apercuPaybackAvec != null ? apercuPaybackAvec + ' ans' : 'N/A'"))

  const cout = tousLesBlocsDeLabel('Coût')
  assert.ok(cout[0].includes('fmtNum(Math.round(totals.totalSans))'))
  assert.ok(cout[1].includes('fmtNum(Math.round(totals.totalAvec))'))
})

// `unit`/`accent` (le reste du rendu visible d'une carte) ne bougent pas non
// plus — vérifié sur un échantillon représentatif (unité + accent).
test('QJR426 — unit/accent des cartes sont inchangés à l’octet', () => {
  assert.ok(tousLesBlocsDeLabel("Taux d'autoconsommation")[0]
    .includes('unit="part de la production consommée" accent'))
  assert.ok(tousLesBlocsDeLabel('Production annuelle')[0]
    .includes('unit="kWh / an" accent'))
  assert.ok(tousLesBlocsDeLabel('ROI')[0].includes('unit="retour sur invest." accent'))
  assert.ok(tousLesBlocsDeLabel('ROI')[1].includes('unit="retour sur invest." accent'))
  for (const bloc of tousLesBlocsDeLabel('Coût')) {
    assert.ok(bloc.includes('unit="MAD TTC"'))
  }
})
