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
  // L-2OPT — et il gagne sur l'étude de SA branche (`etudeHoraireAnnuelAvec`),
  // jamais sur celle du kWc SANS : les deux optimiseurs peuvent diverger.
  assert.match(DG, /const apercuEcoAvec = etudeHoraireAnnuelAvec/)
  assert.match(DG, /batterieInvendableServeur \? null : etudeHoraireAnnuelAvec\.economie_avec_mad/)
  assert.match(DG, /: roiPourAvec\?\.eco_annuelle_avec/)
})

test('DevisGenerator : batterie non livrable -> AUCUN montant « avec batterie », la raison à la place', () => {
  // ORDRE FONDATEUR — l'omission honnête, jamais un zéro inventé. Sans cette
  // garde, `fmtNum(Math.round(null))` imprimait « 0 » : un chiffre FAUX sur
  // l'option que le catalogue ne peut pas livrer (trou réel exhumé par CJ2a).
  // L-2OPT — le verdict est demandé POUR LA TAILLE DE LA BRANCHE AVEC.
  assert.match(DG, /verdictBatteriePourTaille\(etudeHoraireLignesAvec, kwpAvec\)/)
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

// ── L-2OPT — chaque option son kWc, jamais un croisement ───────────────────
// Le bug corrigé : `kwp` restait le compte de la branche SANS (le rechargement
// d'un brouillon exclut les lignes taguées 'avec') pendant que
// `totals.totalAvec` et `batteryKwhFromLines` chiffraient la composition AVEC
// entière — payback « avec » affiché plusieurs fois trop long, et étude
// horaire serveur interrogée sur une chimère (kWc sans + batteries avec).

test('L-2OPT : `kwpAvec` est dérivé des LIGNES (règle backend variante \'\'+\'avec\')', () => {
  const idx = DG.indexOf('const kwpAvec = (() => {')
  assert.ok(idx > -1, 'kwpAvec introuvable')
  const bloc = DG.slice(idx, idx + 400)
  assert.match(bloc, /comptePanneauxOption\(lines, 'sans'\)/)
  assert.match(bloc, /comptePanneauxOption\(lines, 'avec'\)/)
  // NON DIVERGENT ⇒ `kwp` renvoyé TEL QUEL (aucune re-dérivation flottante) :
  // c'est ce qui garantit le comportement byte-identique à l'historique.
  assert.match(bloc, /if \(nSans <= 0 \|\| nAvec === nSans\) return kwp/)
})

test("L-2OPT : l'étude horaire de la branche AVEC porte SON kWc, et n'est demandée que si ça diverge", () => {
  const idx = DG.indexOf('const etudeHoraireCorpsAvec = ')
  assert.ok(idx > -1, 'etudeHoraireCorpsAvec introuvable')
  const bloc = DG.slice(idx, idx + 700)
  // Garde : aucun second appel réseau tant que rien ne diverge.
  assert.match(bloc, /kwpAvec !== kwp/)
  assert.match(bloc, /kwp: kwpAvec/)
  assert.match(DG, /useEtudeHorairePreview\(etudeHoraireCorpsAvec\)/)
  // Divergent : on lit UNIQUEMENT l'étude de la branche avec — retomber sur
  // celle du kWc SANS pendant le chargement recréerait le croisement.
  assert.match(DG, /const etudeHoraireDonneesPourAvec = etudeHoraireCorpsAvec\s*\n\s*\? etudeHoraireDonneesAvec\s*\n\s*: etudeHoraireDonnees/)
})

test('L-2OPT : le miroir local `roiAvec` est calculé au kWc AVEC, null quand rien ne diverge', () => {
  const idx = DG.indexOf('const roiAvec = useMemo(() => {')
  assert.ok(idx > -1, 'roiAvec introuvable')
  const bloc = DG.slice(idx, idx + 400)
  assert.match(bloc, /if \(dKwpAvec === dKwp\) return null/)
  assert.match(bloc, /kwp: dKwpAvec/)
  assert.match(DG, /const roiPourAvec = roiAvec \|\| roi/)
})

// ── FINDING 25/08 — l'ascension écran ne peut plus rider le plafond ────────
// `optimalKwcByPayback` ne plafonne l'économie à la consommation réelle que
// si on la lui donne. Les deux appels de l'écran ne la passaient pas :
// l'économie restait LINÉAIRE en kWc, chaque pas marginal se « remboursait »,
// et l'ascension finissait toujours au plafond du balayage (mesuré : besoin
// 100 kWc → 100 kWc retenus, 522 341 MAD).

test('FINDING 25/08 : les DEUX appels de dimensionnement passent la consommation réelle + le distributeur', () => {
  const idx = DG.indexOf('const computeAutoSizing = useCallback(')
  assert.ok(idx > -1, 'computeAutoSizing introuvable')
  const bloc = DG.slice(idx, DG.indexOf('sizingCacheRef.current = { key, result }', idx))
  // La consommation est DÉRIVÉE (barème), ou reprise du champ réel saisi —
  // jamais un chiffre posé.
  assert.match(bloc, /consoAnnuelleDepuisFactures\(factures, distributeurBalayage\)/)
  assert.match(bloc, /Number\(consoAnnuelleReelle\) > 0/)
  // Les DEUX optimiseurs (sans ET avec batterie) la reçoivent.
  const appels = bloc.match(/consoAnnuelleKwh: consoBalayage, utility: distributeurBalayage/g) || []
  assert.equal(appels.length, 2,
    'les deux appels optimalKwcByPayback (sans + avec batterie) doivent recevoir la conso réelle')
  // Le distributeur pilote le barème : il entre dans la clé de cache, sinon
  // le balayage resservirait un résultat calculé sur un autre barème.
  assert.match(bloc, /distributeurBalayage, consoAnnuelleReelle \?\? ''\]\.join\('\|'\)/)
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

// ── L-FRONT lot 4 — falaise/résiduel/remplissage/glitch/mini-balayage/estimation ──

test("DevisGenerator lot4 : importe les nouvelles aides pures (falaise/glitch/balayage/estimation)", () => {
  const idx = DG.indexOf("} from '../../features/ventes/etudeHorairePreview'")
  assert.ok(idx > -1)
  const bloc = DG.slice(Math.max(0, idx - 400), idx)
  for (const nom of ['falaiseAffichable', 'glitchAnnuel',
    'balayageStockageAffichable', 'estimationConsoAffichable', 'LIBELLES_MOIS']) {
    assert.ok(bloc.includes(nom), `export « ${nom} » absent de l'import`)
  }
})

test('DevisGenerator lot4 : les trois blocs dérivés sont memoïsés depuis le MÊME payload (aucun second appel réseau)', () => {
  assert.match(DG, /const etudeHoraireFalaise = useMemo\(\s*\n\s*\(\) => falaiseAffichable\(etudeHoraireDonnees\?\.dimensionnement\)/)
  assert.match(DG, /const etudeHoraireGlitch = useMemo\(\s*\n\s*\(\) => glitchAnnuel\(etudeHoraireDonnees\?\.etude\)/)
  assert.match(DG, /const etudeHoraireEstimationConso = useMemo\(\s*\n\s*\(\) => estimationConsoAffichable\(etudeHoraireDonnees\?\.estimation_conso\)/)
})

test('DevisGenerator lot4 : colonnes résiduel + remplissage batterie rendues dans le tableau de dimensionnement, omises sans donnée', () => {
  assert.match(DG, /data-testid="etude-horaire-residuel"/)
  assert.match(DG, /data-testid="etude-horaire-remplissage"/)
  const idxR = DG.indexOf('data-testid="etude-horaire-residuel"')
  const blocR = DG.slice(idxR, idxR + 250)
  assert.match(blocR, /residuelApres != null/)
  const idxM = DG.indexOf('data-testid="etude-horaire-remplissage"')
  const blocM = DG.slice(idxM, idxM + 250)
  assert.match(blocM, /remplissageMoyen != null/)
})

test('DevisGenerator lot4 : mini-balayage stockage — un bouton toggle par ligne, rendu seulement si des paliers existent', () => {
  assert.match(DG, /data-testid="etude-horaire-stockage-toggle"/)
  assert.match(DG, /paliersStockage\.length > 0/)
  assert.match(DG, /data-testid="etude-horaire-balayage-stockage"/)
  assert.match(DG, /balayageStockageAffichable\(ligne\)/)
})

test('DevisGenerator lot4 : bloc falaise tarifaire omis en entier quand falaiseAffichable renvoie null', () => {
  const idx = DG.indexOf('data-testid="etude-horaire-falaise"')
  assert.ok(idx > -1)
  const bloc = DG.slice(idx - 200, idx)
  assert.match(bloc, /\{etudeHoraireFalaise && \(/)
})

test('DevisGenerator lot4 : résumé glitch omis en entier quand glitchAnnuel renvoie null', () => {
  const idx = DG.indexOf('data-testid="etude-horaire-glitch"')
  assert.ok(idx > -1)
  const bloc = DG.slice(idx - 200, idx)
  assert.match(bloc, /\{etudeHoraireGlitch && \(/)
})

test('DevisGenerator lot4 : décomposition mensuelle estimation_conso omise en entier quand la clé est absente', () => {
  const idx = DG.indexOf('data-testid="etude-horaire-estimation-conso"')
  assert.ok(idx > -1)
  const bloc = DG.slice(idx - 400, idx)
  assert.match(bloc, /\{etudeHoraireEstimationConso && \(/)
  // Les lignes d'ajout ne sont posées que pour les clés réellement présentes.
  assert.match(DG, /etudeHoraireEstimationConso\.ajouts\.map\(\(a\) => \(/)
})

test('DevisGenerator lot4 : le formulaire garde noValidate — les nouveaux blocs n\'ajoutent aucun champ de saisie', () => {
  assert.match(DG, /noValidate/)
  // Les blocs lot4 (résiduel/remplissage/falaise/glitch/estimation/mini-
  // balayage) sont tous en LECTURE SEULE (<td>/<div> texte) : aucun <input>
  // ne peut donc y romprer la garde anti-snap step="any" des champs existants.
  for (const testid of ['etude-horaire-residuel', 'etude-horaire-remplissage',
    'etude-horaire-falaise', 'etude-horaire-glitch',
    'etude-horaire-estimation-conso', 'etude-horaire-balayage-stockage']) {
    const idx = DG.indexOf(`data-testid="${testid}"`)
    assert.ok(idx > -1, `bloc ${testid} introuvable`)
    const bloc = DG.slice(idx, idx + 1200)
    const fin = bloc.search(/\n {12}\)\}/) // fin approximative du bloc conditionnel
    const zone = fin > -1 ? bloc.slice(0, fin) : bloc.slice(0, 600)
    assert.doesNotMatch(zone, /<input\b/i, `${testid} ne doit porter aucun <input> brut`)
  }
})
