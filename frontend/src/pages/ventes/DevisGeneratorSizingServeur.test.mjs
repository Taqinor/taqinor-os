// U3-900 (fondateur 29/08/2026, « ALL sizing goes through the new sizing
// tool, and i said ALL sizing ») — verrouille le remplacement du repli
// `estimerPanneaux` (panneaux/900 MAD, supprimé du backend le même jour) dans
// l'écran générateur : l'écran attend/affiche la recommandation (ou le refus
// nommé) du moteur horaire SERVEUR au lieu de deviner une taille.
//
// U3-MOTEUR (même ordre fondateur, 29/08/2026) — cette attente n'est plus
// conditionnée au seuil de facture : en RÉSIDENTIEL, les trois
// pré-remplissages attendent le moteur DANS TOUS LES CAS. Au-dessus du seuil,
// l'écran chiffrait encore lui-même les paliers de 5 kWc — le dernier
// contournement du moteur.
//
// DevisGenerator.jsx est du JSX/ESM non exécutable par `node --test` sans
// node_modules (React, Redux dispatch réel) : ce test lit donc le SOURCE,
// même patron que DevisGeneratorEtudeHoraire.test.mjs.
//
// Run : node --test src/pages/ventes/DevisGeneratorSizingServeur.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

// QJR99 — LA BASCULE a déplacé la décision de dimensionnement dans le module
// PUR `useSizingMoteurPur` (garde de péremption sur les DEUX branches, ordre
// des motifs, priorité de la frappe manuelle). Ce fichier garde donc les mêmes
// exigences, mais les vérifie là où elles vivent : par EXÉCUTION du module pur
// (plus fort qu'une regex) pour la décision, et par lecture du source pour le
// câblage de l'écran. Aucune assertion n'est relâchée.
import { decisionSizing, REFUS_GENERIQUE } from '../../features/ventes/quote/hooks/useSizingMoteurPur.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const DG = readFileSync(join(HERE, 'DevisGenerator.jsx'), 'utf8')

test("DevisGenerator.jsx : n'importe plus estimerPanneaux (repli 900 MAD retiré)", () => {
  const idx = DG.indexOf("} from '../../features/ventes/solar'")
  assert.ok(idx > -1, "l'import de solar.js est introuvable")
  const bloc = DG.slice(Math.max(0, idx - 300), idx)
  assert.ok(!/\bestimerPanneaux\b/.test(bloc),
    'estimerPanneaux ne doit plus être importé')
  assert.ok(!/estimerPanneaux\(/.test(DG),
    'aucun appel estimerPanneaux(...) ne doit subsister dans le fichier')
})

test("DevisGenerator.jsx : les trois pré-remplissages (lead/profil site/facture) n'ont AUCUN balayage local en résidentiel — ils attendent le moteur", () => {
  // QJR99 — l'attente elle-même (`attenteMoteur`) est posée par les
  // transitions du reducer (LEAD_APPLIQUE / PROFIL_SITE_APPLIQUE), testées
  // dans features/ventes/quote/sizingReducer.test.mjs. Ce qui reste vérifiable
  // ICI — et qui est le vrai risque de contournement — c'est que les trois
  // sites de l'écran ne RÉSOLVENT aucun balayage local en résidentiel.
  const sites = DG.match(/modeCible !== 'residentiel'\)\s*\n\s*\? computeAutoSizing\(hiver, ete\) : null/g) || []
  assert.equal(sites.length, 2,
    'applyLead et applySiteProfile doivent chacun réserver le balayage local aux marchés sans moteur')
  assert.match(DG, /const sizingLocal = modeInstallation === 'residentiel'\s*\n\s*\? null : computeAutoSizing\(hiver, ete\)/,
    'syncBillEstimator doit lui aussi réserver le balayage local aux marchés sans moteur')
  // Les trois sites passent par une transition du reducer, jamais par une
  // écriture directe des champs.
  const dispatches = DG.match(/dispatchSizing\(\{ type: 'LEAD_APPLIQUE', lead, sizingLocal \}\)|dispatchSizing\(\{ type: 'PROFIL_SITE_APPLIQUE', profil: p, sizingLocal \}\)|type: 'PROFIL_SITE_APPLIQUE',/g) || []
  assert.equal(dispatches.length, 3,
    'les trois pré-remplissages doivent passer par une transition du reducer (3 sites)')
})

test("U3-MOTEUR — les trois pré-remplissages attendent le moteur EN RÉSIDENTIEL sans condition de seuil", () => {
  // Aucun des trois sites ne conditionne le passage au moteur à un seuil de
  // facture : la seule condition est le MARCHÉ (et, pour applyLead, la taille
  // souhaitée du lead qui reste prioritaire — comportement historique).
  assert.doesNotMatch(DG, /besoinKwc\s*<=?\s*0[\s\S]{0,80}attente/i,
    'aucun seuil de facture ne doit conditionner le passage au moteur')
  // Et le balayage local n'est JAMAIS résolu pour le résidentiel.
  assert.doesNotMatch(DG, /modeCible === 'residentiel'[\s\S]{0,120}computeAutoSizing\(/,
    'le résidentiel ne doit jamais chiffrer de palier localement')
})

test('DevisGenerator.jsx : la décision applique la recommandation SERVEUR ou son refus nommé, jamais pendant le chargement', () => {
  // Câblage de l'écran : la décision du hook est traduite en transitions, et
  // RIEN d'autre n'écrit ces champs.
  assert.match(DG, /if \(actionMoteur === 'appliquer'\) \{\s*\n\s*dispatchSizing\(\{ type: 'MOTEUR_A_REPONDU', recommandation: recoMoteur \}\)/)
  assert.match(DG, /\} else if \(actionMoteur === 'refuser'\) \{\s*\n\s*dispatchSizing\(\{ type: 'MOTEUR_A_REFUSE', motif: motifMoteurServeur \}\)/)
  assert.match(DG, /\} else if \(actionMoteur === 'abandonner'\) \{/)
  assert.doesNotMatch(DG, /String\(8\)/, 'aucun défaut forfaitaire (8 panneaux) ne doit être posé')

  // Comportement, prouvé par EXÉCUTION du module pur qui possède la décision.
  const reco = { panneaux: 12, kwc: 8.52 }
  const corps = 'CORPS-A'
  // Ne décide rien tant que la réponse est en vol.
  assert.equal(decisionSizing({
    attente: true, chargement: true, cleCourante: corps,
  }).action, 'attendre')
  // Une frappe manuelle gagne toujours — même garde que partout ailleurs.
  assert.equal(decisionSizing({
    attente: true, toucheNbPanneaux: true, donnees: { dimensionnement: { recommandation: reco } },
    cleServie: corps, cleCourante: corps,
  }).action, 'abandonner')
  // Succès serveur → la recommandation SERVEUR, jamais une formule locale.
  const ok = decisionSizing({
    attente: true, donnees: { dimensionnement: { recommandation: reco } },
    cleServie: corps, cleCourante: corps,
  })
  assert.equal(ok.action, 'appliquer')
  assert.deepEqual(ok.recommandation, reco)
  // Déclin serveur → message FRANÇAIS EXACT, jamais un chiffre.
  assert.deepEqual(decisionSizing({
    attente: true, donnees: { avertissements: ['ville manquante'] },
    cleServie: corps, cleCourante: corps,
  }), { action: 'refuser', motif: 'ville manquante' })
})

// F4 (revue Fable 29/08/2026) — LES DEUX FORMES DE REFUS. Le moteur décline de
// deux manières :
//   (a) avec `avertissements` (donnée d'entrée douteuse) ;
//   (b) PROPREMENT, en `dimensionnement.motivation` — « aucune taille
//       recommandable : le catalogue ne compose aucune variante chiffrable et
//       électriquement conforme pour ce profil » (choisir_recommandation,
//       backend/django_core/apps/ventes/dimensionnement.py) — recommandation
//       à `None` et AUCUN avertissement.
// Ne lire que (a) affichait le message générique de repli à la place de la
// cause NOMMÉE par le serveur.
// U3-MOTEUR — RÉPONSE EN VOL. Une réponse déjà partie quand une nouvelle
// facture est tapée arrive APRÈS, parfaitement valide, mais pour l'ANCIENNE
// facture. La consommer posait un nombre de panneaux RÉEL pour un AUTRE
// profil, ET refermait le drapeau d'attente avant l'arrivée de la bonne
// réponse (bug reproduit : facture 1200 → 3000 restait bloqué sur la taille
// du 1200 — voir DevisGeneratorRecalculerDimensionnementGuard.test.jsx).
test("U3-MOTEUR — l'effet n'applique QUE la réponse du corps affiché (aucune réponse en vol d'une facture précédente)", () => {
  // Le hook expose le corps qui a produit la réponse…
  const HOOK = readFileSync(
    join(HERE, '../../features/ventes/etudeHorairePreview.js'), 'utf8')
  assert.match(HOOK, /setCorpsServi\(debouncedKey\)/,
    'le hook doit mémoriser le corps qui a produit la réponse')
  assert.match(HOOK, /return \{ donnees, chargement, erreur, corpsServi \}/,
    'le hook doit exposer corpsServi à ses appelants')
  // …et la décision ne consomme la réponse que si elle décrit le corps AFFICHÉ.
  // QJR99 — la garde couvre désormais les DEUX branches (succès ET échec) :
  // l'ancienne version ne comparait la clé qu'en présence de `donnees`, si bien
  // que la branche d'ÉCHEC refermait l'attente et épinglait le refus d'une
  // facture qu'on venait de remplacer.
  const reco = { panneaux: 12, kwc: 8.52 }
  const perime = decisionSizing({
    attente: true, donnees: { dimensionnement: { recommandation: reco } },
    cleServie: 'CORPS-ANCIEN', cleCourante: 'CORPS-COURANT',
  })
  assert.deepEqual(perime, { action: 'attendre', raison: 'reponse-perimee' },
    "une réponse servie pour un autre corps ne doit ni être appliquée ni fermer l'attente")
  const echecPerime = decisionSizing({
    attente: true, erreur: 'boom',
    cleErreur: 'CORPS-ANCIEN', cleCourante: 'CORPS-COURANT',
  })
  assert.deepEqual(echecPerime, { action: 'attendre', raison: 'echec-perime' },
    "un ÉCHEC servi pour un autre corps ne doit ni épingler un refus ni fermer l'attente")
  // Le hook fournit la clé du corps EN VOL pour attribuer l'échec.
  const HOOK_SIZING = readFileSync(
    join(HERE, '../../features/ventes/quote/hooks/useSizingMoteur.js'), 'utf8')
  assert.match(HOOK_SIZING, /const cleCourante = corps \? JSON\.stringify\(corps\) : null/,
    'la comparaison doit porter sur la MÊME sérialisation que le hook réseau')
  assert.match(HOOK_SIZING, /cleServie: corpsServi/)
})

test('F4 — le refus serveur affiche la cause NOMMÉE : avertissements OU dimensionnement.motivation, jamais le générique quand le serveur a parlé', () => {
  const corps = 'CORPS-A'
  const refus = (donnees, erreur) => decisionSizing({
    attente: true, donnees, erreur,
    cleServie: corps, cleErreur: corps, cleCourante: corps,
  })
  // Forme (a) : un avertissement du serveur, en premier (le plus spécifique) —
  // il PRIME sur la motivation quand les deux sont présents.
  assert.equal(refus({
    avertissements: ['ville manquante'],
    dimensionnement: { motivation: 'catalogue incomplet' },
  }).motif, 'ville manquante')
  // Forme (b) : le refus propre, NOMMÉ, sans aucun avertissement.
  assert.equal(refus({ dimensionnement: { motivation: 'catalogue incomplet' } }).motif,
    'catalogue incomplet')
  // Puis seulement l'erreur réseau…
  assert.equal(refus(null, 'réseau indisponible').motif, 'réseau indisponible')
  // …et le générique en tout dernier recours.
  assert.equal(refus({ dimensionnement: {} }).motif, REFUS_GENERIQUE)
  // Le texte serveur est rendu VERBATIM (aucune reformulation/concaténation).
  const PUR = readFileSync(
    join(HERE, '../../features/ventes/quote/hooks/useSizingMoteurPur.js'), 'utf8')
  assert.doesNotMatch(PUR, /motivation[^\n]*\+\s*'/,
    'le message du serveur doit être rendu tel quel, jamais rhabillé')
  // Et l'écran ne fabrique plus aucun message de refus lui-même.
  assert.doesNotMatch(DG, /Dimensionnement indisponible/,
    'le motif de refus vient du module pur, jamais d\'une phrase écrite dans l\'écran')
})

test('DevisGenerator.jsx : le message de refus serveur est rendu, résidentiel uniquement, jamais quand il est null', () => {
  const idx = DG.indexOf('data-testid="sizing-serveur-refus"')
  assert.ok(idx > -1, 'le bloc de refus serveur est introuvable')
  const bloc = DG.slice(idx - 250, idx + 100)
  assert.match(bloc, /modeInstallation === 'residentiel' && sizingServeurMessage/)
})
