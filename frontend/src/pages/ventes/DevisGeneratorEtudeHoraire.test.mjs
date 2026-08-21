// CJ2b — l'écran générateur (résidentiel) appelle le moteur horaire serveur
// (CJ2a, `POST /ventes/etude-horaire/preview/`) au lieu de ne montrer QUE son
// miroir local `computeROI` : « on ne voit ni l'économie réelle calculée, ni
// les données PVGIS — cette donnée devrait être comparée à la courbe de
// consommation » (ordre fondateur, 20/08/2026).
//
// DevisGenerator.jsx est du JSX/ESM non exécutable par `node --test` sans
// node_modules (React, Redux dispatch réel) : ce test lit donc le SOURCE,
// même patron que DevisGeneratorOrdreLignes.test.mjs /
// DevisGeneratorFacturesSaisies.test.mjs.
//
// Run : node --test src/pages/ventes/DevisGeneratorEtudeHoraire.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const DG = readFileSync(join(HERE, 'DevisGenerator.jsx'), 'utf8')

const PUR = readFileSync(
  join(HERE, '..', '..', 'features', 'ventes', 'etudeHorairePreviewPur.js'),
  'utf8')

test("DevisGenerator : importe les 5 exports de etudeHorairePreview (jamais une copie locale)", () => {
  const idx = DG.indexOf("} from '../../features/ventes/etudeHorairePreview'")
  assert.ok(idx > -1, "l'import du pont moteur horaire est introuvable")
  const bloc = DG.slice(Math.max(0, idx - 300), idx)
  for (const nom of ['construireCorpsPreview', 'etiquetteSource',
    'lignesAffichables', 'useEtudeHorairePreview',
    'verdictBatteriePourTaille']) {
    assert.ok(bloc.includes(nom), `export « ${nom} » absent de l'import`)
  }
})

test("etudeHorairePreviewPur.js : AUCUN import — sinon les tests node --test meurent à l'import", () => {
  // `src/api/axios.js` déréférence `import.meta.env` AU CHARGEMENT : toute
  // chaîne d'import qui y mène jette hors de Vite, et un test qui importerait
  // cette chaîne échouerait avant d'avoir vérifié quoi que ce soit. Les
  // fonctions pures vivent donc dans un module SANS aucun import.
  assert.ok(!/^\s*import\s/m.test(PUR),
    'le module pur ne doit importer AUCUN module (ni react, ni le client API)')
  for (const nom of ['construireCorpsPreview', 'etiquetteSource',
    'lignesAffichables', 'verdictBatteriePourTaille']) {
    assert.match(PUR, new RegExp(`export function ${nom}\\b`))
  }
})

test('DevisGenerator : construit le corps de requête (résidentiel uniquement) et appelle le hook', () => {
  const idx = DG.indexOf('const etudeHoraireCorps = modeInstallation ===')
  assert.ok(idx > -1, 'etudeHoraireCorps introuvable')
  const bloc = DG.slice(idx, idx + 900)
  assert.match(bloc, /modeInstallation === 'residentiel'/)
  assert.match(bloc, /construireCorpsPreview\(\{/)
  const hookIdx = DG.indexOf('= useEtudeHorairePreview(etudeHoraireCorps)')
  assert.ok(hookIdx > idx, 'useEtudeHorairePreview(etudeHoraireCorps) introuvable après la construction du corps')
})

test('DevisGenerator : le serveur GAGNE sur le miroir local `roi` dès qu\'il a répondu (etude.annuel non nul)', () => {
  assert.match(DG, /const etudeHoraireAnnuel = etudeHoraireDonnees\?\.etude\?\.annuel \|\| null/)
  assert.match(DG, /const etudeHoraireSourceServeur = !!etudeHoraireAnnuel/)
  // Les 3 chiffres affichés (Production / Économies / ROI) préfèrent le
  // serveur, avec repli explicite sur `roi` (jamais supprimé).
  assert.match(DG, /const apercuProductionKwh = etudeHoraireSourceServeur\s*\n\s*\? etudeHoraireAnnuel\.production_kwh : roi\?\.production_annuelle_kwh/)
  assert.match(DG, /const apercuEcoSans = etudeHoraireSourceServeur\s*\n\s*\? etudeHoraireAnnuel\.economie_sans_mad : roi\?\.eco_annuelle_sans/)
  // CJ2b — « Avec batterie » porte EN PLUS le verdict de livrabilité de la
  // taille chiffrée : le serveur ne gagne que lorsque l'option est réellement
  // vendable, sinon la valeur est ABSENTE (voir le test d'omission suivant).
  assert.match(DG, /const apercuEcoAvec = etudeHoraireSourceServeur/)
  assert.match(DG, /batterieInvendableServeur \? null : etudeHoraireAnnuel\.economie_avec_mad/)
  assert.match(DG, /: roi\?\.eco_annuelle_avec/)
})

test('DevisGenerator : batterie non livrable -> AUCUN montant « avec batterie », la raison à la place', () => {
  // ORDRE FONDATEUR — l'omission honnête, jamais un zéro inventé. Sans cette
  // garde, `fmtNum(Math.round(null))` imprimait « 0 » : un chiffre FAUX sur
  // l'option que le catalogue ne peut pas livrer (trou réel exhumé par CJ2a).
  assert.match(DG, /verdictBatteriePourTaille\(etudeHoraireLignes, kwp\)/)
  assert.match(DG, /const batterieInvendableServeur = verdictBatterieServeur/)
  const idx = DG.indexOf('{batterieInvendableServeur ? (')
  assert.ok(idx > -1, "la branche d'omission « avec batterie » est introuvable")
  const bloc = DG.slice(idx, idx + 700)
  assert.match(bloc, /data-testid="etude-horaire-batterie-invendable"/)
  assert.match(bloc, /verdictBatterieServeur\.raison/)
  // Aucune carte chiffrée ne subsiste dans la branche d'omission.
  const omission = DG.slice(idx, DG.indexOf(') : (', idx))
  assert.ok(!/MetricCard/.test(omission),
    "aucune carte chiffrée ne doit subsister quand la batterie n'est pas livrable")
})

test('DevisGenerator : `roi` (computeROI, miroir local) reste appelé SANS changement — jamais supprimé', () => {
  assert.match(DG, /const roi = useMemo\(\(\) => \{/)
  assert.match(DG, /return computeROI\(\{/)
})

test('DevisGenerator : le nouveau bloc moteur horaire est gardé par modeInstallation === \'residentiel\'', () => {
  const idx = DG.indexOf('{modeInstallation === \'residentiel\' && etudeHoraireCorps && (')
  assert.ok(idx > -1, 'le garde résidentiel du bloc moteur horaire est introuvable')
  const bloc = DG.slice(idx, idx + 400)
  assert.match(bloc, /data-testid="etude-horaire-block"/)
})

test('DevisGenerator : rend le tableau de dimensionnement (paliers moteur horaire)', () => {
  assert.match(DG, /data-testid="etude-horaire-dimensionnement"/)
  assert.match(DG, /etudeHoraireLignes\.map\(\(ligne\) => \{/)
  // Honnêteté rule #1 — pas de chiffre "avec" quand la ligne n'est pas vendable.
  assert.match(DG, /ligne\.batterieVendable/)
  assert.match(DG, /ligne\.raisonBatterie/)
})

test('DevisGenerator : chaque ligne du tableau porte un bouton « Appliquer cette taille »', () => {
  assert.match(DG, /Appliquer cette taille/)
  assert.match(DG, /onClick=\{\(\) => appliquerTailleDimensionnement\(ligne\)\}/)
})

test('DevisGenerator : « Appliquer cette taille » pose nbPanneaux\\/panelW puis relance handleAutoFill (jamais une seconde règle de composition)', () => {
  const idx = DG.indexOf('const appliquerTailleDimensionnement = (ligne) => {')
  assert.ok(idx > -1, 'appliquerTailleDimensionnement introuvable')
  const bloc = DG.slice(idx, idx + 900)
  assert.match(bloc, /setNbPanneaux\(String\(ligne\.panneaux\)\)/)
  assert.match(bloc, /if \(ligne\.panel_watt\) setPanelW\(String\(ligne\.panel_watt\)\)/)
  assert.match(bloc, /appliquerTaillePending\.current = true/)
  // Le déclenchement effectif de la composition passe par handleAutoFill,
  // JAMAIS une réimplémentation d'autoFillLines ici.
  assert.match(bloc, /handleAutoFill\(\)/)
  assert.doesNotMatch(bloc, /autoFillLines\(/)
})

test('DevisGenerator : le détail saisonnier (production × consommation par saison) est rendu', () => {
  assert.match(DG, /data-testid="etude-horaire-saisons"/)
  assert.match(DG, /SAISON_LABELS/)
  assert.match(DG, /etudeHoraireDonnees\.etude\.saisons\[cle\]/)
})

test('DevisGenerator : les avertissements serveur sont affichés VERBATIM (jamais réécrits)', () => {
  const idx = DG.indexOf('data-testid="etude-horaire-avertissements"')
  assert.ok(idx > -1)
  const bloc = DG.slice(idx - 200, idx + 300)
  assert.match(bloc, /etudeHoraireDonnees\.avertissements\.map\(/)
})
