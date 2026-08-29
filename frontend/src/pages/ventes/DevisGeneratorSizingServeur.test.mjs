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

test('DevisGenerator.jsx : les trois pré-remplissages (lead/profil site/facture) posent attenteSizingServeur au lieu de deviner', () => {
  const occurrences = DG.match(/attenteSizingServeur\.current = true/g) || []
  assert.equal(occurrences.length, 3,
    'applyLead, applySiteProfile et syncBillEstimator doivent chacun poser le drapeau (3 sites)')
})

test("U3-MOTEUR — les trois pré-remplissages attendent le moteur EN RÉSIDENTIEL sans condition de seuil ; le balayage local ne sert plus qu'aux marchés sans moteur", () => {
  // Chaque site pose le drapeau dans une branche `residentiel` inconditionnelle,
  // et n'appelle `computeAutoSizing` que dans son `else` (industriel/commercial).
  for (const [nom, ancre] of [
    ['applyLead', 'if (fromTaille <= 0) {'],
    ['applySiteProfile', 'if (!nbPanneauxTouched.current) {'],
  ]) {
    const idx = DG.indexOf(ancre)
    assert.ok(idx > -1, `ancre introuvable pour ${nom}`)
  }
  // Aucun des trois sites ne doit poser nbPanneaux depuis un balayage local
  // dans une branche résidentielle : le drapeau y précède toujours le `else`.
  const sites = DG.match(/if \(mode(Cible|Installation) === 'residentiel'\) \{\s*\n(?:[^\n]*\n){0,10}?\s*setSizingInfo\(null\)\s*\n\s*attenteSizingServeur\.current = true\s*\n\s*\} else \{/g) || []
  assert.equal(sites.length, 3,
    'applyLead, applySiteProfile et syncBillEstimator doivent chacun attendre le moteur en résidentiel, avec le balayage local relégué au `else`')
  // Et chaque `else` garde bien le balayage local pour les marchés sans moteur.
  const balayages = DG.match(/\} else \{\s*\n(?:[^\n]*\n){0,6}?\s*const sizing = computeAutoSizing\(hiver, ete\)/g) || []
  assert.equal(balayages.length, 3,
    'le balayage local doit rester la source des marchés sans moteur serveur (3 sites)')
})

test('DevisGenerator.jsx : un effet applique la recommandation SERVEUR ou son refus nommé, jamais pendant le chargement', () => {
  const idx = DG.indexOf('if (!attenteSizingServeur.current) return')
  assert.ok(idx > -1, "l'effet attenteSizingServeur est introuvable")
  const bloc = DG.slice(idx, idx + 3200)
  // Une frappe manuelle gagne toujours — même garde que partout ailleurs.
  assert.match(bloc, /if \(nbPanneauxTouched\.current\) \{ attenteSizingServeur\.current = false; return \}/)
  // Ne décide rien tant que la réponse est en vol.
  assert.match(bloc, /if \(etudeHoraireChargement\) return/)
  // Succès serveur → prérempli DEPUIS la réponse, jamais une formule locale.
  assert.match(bloc, /const reco = etudeHoraireDonnees\?\.dimensionnement\?\.recommandation/)
  assert.match(bloc, /setNbPanneaux\(String\(reco\.panneaux\)\)/)
  // Déclin serveur → message FRANÇAIS EXACT (avertissements), jamais un chiffre.
  assert.match(bloc, /setSizingServeurMessage\(\s*\n\s*etudeHoraireDonnees\?\.avertissements\?\.\[0\]/)
  assert.doesNotMatch(bloc, /setNbPanneaux\(String\(8\)\)/, 'aucun défaut forfaitaire (8 panneaux) ne doit être posé')
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
  // …et l'écran ne consomme la réponse que si elle décrit le corps AFFICHÉ.
  const idx = DG.indexOf('if (!attenteSizingServeur.current) return')
  assert.ok(idx > -1, "l'effet attenteSizingServeur est introuvable")
  const bloc = DG.slice(idx, idx + 3200)
  assert.match(bloc,
    /if \(etudeHoraireDonnees && etudeHoraireCorpsServi !== etudeHoraireCorpsKey\) return/,
    "une réponse servie pour un autre corps ne doit ni être appliquée ni fermer l'attente")
  // La comparaison porte sur la MÊME sérialisation que le hook.
  assert.match(DG, /const etudeHoraireCorpsKey = etudeHoraireCorps\s*\n?\s*\? JSON\.stringify\(etudeHoraireCorps\) : null/)
})

test('F4 — le refus serveur affiche la cause NOMMÉE : avertissements OU dimensionnement.motivation, jamais le générique quand le serveur a parlé', () => {
  const idx = DG.indexOf('if (!attenteSizingServeur.current) return')
  assert.ok(idx > -1, "l'effet attenteSizingServeur est introuvable")
  const bloc = DG.slice(idx, idx + 3200)
  // (le fichier source est en CRLF : on repère l'appel MULTILIGNE par regex)
  const setIdx = bloc.search(/setSizingServeurMessage\(\r?\n/)
  assert.ok(setIdx > -1, 'la pose du message de refus est introuvable')
  const chaine = bloc.slice(setIdx, setIdx + 500)
  // Forme (a) : un avertissement du serveur, en premier (le plus spécifique).
  assert.match(chaine, /etudeHoraireDonnees\?\.avertissements\?\.\[0\]/)
  // Forme (b) : le refus propre, NOMMÉ, sans avertissement.
  assert.match(chaine, /etudeHoraireDonnees\?\.dimensionnement\?\.motivation/)
  // Puis seulement l'erreur réseau, puis le générique en tout dernier recours.
  const ordre = ['avertissements', 'motivation', 'etudeHoraireErreur',
    'Dimensionnement indisponible']
  let pos = -1
  for (const jalon of ordre) {
    const p = chaine.indexOf(jalon)
    assert.ok(p > pos, `« ${jalon} » doit venir après « ${ordre[ordre.indexOf(jalon) - 1]} »`)
    pos = p
  }
  // Le texte serveur est rendu VERBATIM (aucune reformulation/concaténation).
  assert.doesNotMatch(chaine, /motivation[^\n]*\+/,
    'le message du serveur doit être rendu tel quel, jamais rhabillé')
})

test('DevisGenerator.jsx : le message de refus serveur est rendu, résidentiel uniquement, jamais quand il est null', () => {
  const idx = DG.indexOf('data-testid="sizing-serveur-refus"')
  assert.ok(idx > -1, 'le bloc de refus serveur est introuvable')
  const bloc = DG.slice(idx - 250, idx + 100)
  assert.match(bloc, /modeInstallation === 'residentiel' && sizingServeurMessage/)
})
