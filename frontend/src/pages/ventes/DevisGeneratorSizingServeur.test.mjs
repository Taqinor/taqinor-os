// U3-900 / U3-MOTEUR (fondateur 29/08/2026, « ALL sizing goes through the new
// sizing tool, and i said ALL sizing ») — l'écran générateur ATTEND la
// recommandation (ou le refus NOMMÉ) du moteur horaire SERVEUR au lieu de
// deviner une taille. Le repli `estimerPanneaux` (panneaux / 900 MAD) a été
// supprimé le même jour, backend compris.
//
// QJR108 — CE FICHIER A CESSÉ DE LIRE LE SOURCE. Il mélangeait de vraies
// exécutions de `decisionSizing` et une dizaine d'épingles `readFileSync` sur
// `DevisGenerator.jsx`, `etudeHorairePreview.js`, `useSizingMoteur.js` et
// `useSizingMoteurPur.js` : la mise en page d'un `if`, le nombre d'occurrences
// d'un ternaire, la présence littérale d'une phrase. Une épingle de ce genre
// rougit sur un reformatage et reste VERTE sur une régression réelle. Les deux
// unités qui PORTENT ces règles sont pures et importables — `decisionSizing`
// (la garde de péremption sur les DEUX branches, l'ordre des motifs) et
// `sizingReducer` (`MOTEUR_A_REFUSE` : ce que le refus fait à l'écran) : tout
// est donc vérifié par EXÉCUTION.
//
// CE QUI RESTE HORS DE PORTÉE D'UN TEST PUR, et n'est donc PAS revendiqué ici
// (il faut un rendu React : c'est le domaine de
// DevisGeneratorRecalculerDimensionnementGuard.test.jsx) : le CÂBLAGE de
// l'écran (traduire `decision.action` en `dispatchSizing`), le rendu du bloc
// `data-testid="sizing-serveur-refus"` et sa condition « résidentiel
// uniquement », et le suivi de `cleErreur` par le hook React
// `useSizingMoteur`. Aucune de ces trois choses n'était réellement PROUVÉE par
// les regex qu'elles remplaçaient — elles étaient DÉCRITES.
//
// Run : node --test src/pages/ventes/DevisGeneratorSizingServeur.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  decisionSizing, motifRefus, REFUS_GENERIQUE,
} from '../../features/ventes/quote/hooks/useSizingMoteurPur.js'
import {
  sizingReducer, ETAT_INITIAL,
} from '../../features/ventes/quote/sizingReducer.js'

const CORPS = 'CORPS-COURANT'
const RECO = { panneaux: 12, kwc: 8.52, panel_watt: 710 }

/** Une décision sur le corps AFFICHÉ (succès et échec attribués au même). */
const surLeCorpsAffiche = (extra) => decisionSizing({
  attente: true, cleServie: CORPS, cleErreur: CORPS, cleCourante: CORPS,
  ...extra,
})

// ── LES SIX ISSUES DE LA DÉCISION ───────────────────────────────────────────

test('hors attente, la décision ne touche à RIEN', () => {
  assert.deepEqual(decisionSizing({ attente: false }), { action: 'rien' })
  assert.deepEqual(decisionSizing(), { action: 'rien' })
})

test('une frappe manuelle gagne TOUJOURS : l’attente se referme sans rien appliquer', () => {
  const d = surLeCorpsAffiche({
    toucheNbPanneaux: true, donnees: { dimensionnement: { recommandation: RECO } },
  })
  assert.equal(d.action, 'abandonner')
  assert.equal(d.raison, 'saisie-manuelle')
  assert.equal(d.recommandation, undefined, 'rien ne doit être appliqué par-dessus une frappe')
})

test('réponse EN VOL : on attend, on n’épingle aucun refus', () => {
  const d = surLeCorpsAffiche({ chargement: true })
  assert.equal(d.action, 'attendre')
  assert.equal(d.raison, 'en-vol')
})

test('succès frais : la recommandation SERVEUR est appliquée telle quelle', () => {
  const d = surLeCorpsAffiche({ donnees: { dimensionnement: { recommandation: RECO } } })
  assert.equal(d.action, 'appliquer')
  assert.deepEqual(d.recommandation, RECO, 'jamais une formule locale, jamais un arrondi maison')
})

test('refus frais : action « refuser », avec un motif', () => {
  const d = surLeCorpsAffiche({ donnees: { avertissements: ['ville manquante'] } })
  assert.equal(d.action, 'refuser')
  assert.equal(d.motif, 'ville manquante')
})

test('attente ouverte mais AUCUNE réponse : on attend (jamais un refus par défaut)', () => {
  const d = surLeCorpsAffiche({})
  assert.equal(d.action, 'attendre')
  assert.equal(d.raison, 'aucune-reponse')
})

// ── LA GARDE DE PÉREMPTION, SUR LES DEUX BRANCHES ───────────────────────────
// Une réponse déjà partie quand une nouvelle facture est tapée arrive APRÈS,
// parfaitement valide, mais pour l'ANCIENNE facture. La consommer posait un
// nombre de panneaux RÉEL pour un AUTRE profil (facture 1200 → 3000 restait
// bloqué sur la taille du 1200). L'ancienne garde ne comparait la clé qu'en
// présence de `donnees` : la branche d'ÉCHEC refermait donc l'attente et
// épinglait le refus d'une facture qu'on venait de remplacer.

test('BRANCHE SUCCÈS — une réponse servie pour un AUTRE corps n’est ni appliquée ni consommée', () => {
  const d = decisionSizing({
    attente: true, donnees: { dimensionnement: { recommandation: RECO } },
    cleServie: 'CORPS-ANCIEN', cleCourante: CORPS,
  })
  assert.deepEqual(d, { action: 'attendre', raison: 'reponse-perimee' })
})

test('BRANCHE ÉCHEC — un échec servi pour un AUTRE corps n’épingle aucun refus et ne ferme pas l’attente', () => {
  const d = decisionSizing({
    attente: true, erreur: 'boom',
    cleErreur: 'CORPS-ANCIEN', cleCourante: CORPS,
  })
  assert.deepEqual(d, { action: 'attendre', raison: 'echec-perime' })
})

test('BRANCHE ÉCHEC — un échec NON ATTRIBUABLE à un corps est traité comme périmé, jamais comme un refus du corps courant', () => {
  const d = decisionSizing({
    attente: true, erreur: 'boom', cleErreur: null, cleCourante: CORPS,
  })
  assert.equal(d.action, 'attendre')
  assert.equal(d.raison, 'echec-perime')
})

test('les DEUX branches redeviennent consommables dès que la clé concorde', () => {
  assert.equal(
    surLeCorpsAffiche({ donnees: { dimensionnement: { recommandation: RECO } } }).action,
    'appliquer')
  assert.equal(surLeCorpsAffiche({ erreur: 'réseau indisponible' }).action, 'refuser')
})

test('la péremption prime sur l’application : la fraîcheur est vérifiée AVANT le chiffre', () => {
  const perime = decisionSizing({
    attente: true, donnees: { dimensionnement: { recommandation: RECO } },
    cleServie: 'CORPS-ANCIEN', cleCourante: CORPS,
  })
  assert.notEqual(perime.action, 'appliquer')
  assert.equal(perime.recommandation, undefined)
})

// ── L’ORDRE DES MOTIFS, ET LE TEXTE DU SERVEUR RENDU VERBATIM ───────────────
// F4 (revue Fable 29/08/2026) — le moteur décline de deux manières : avec
// `avertissements` (donnée d'entrée douteuse) OU proprement en
// `dimensionnement.motivation` (« aucune taille recommandable… »,
// `choisir_recommandation`), recommandation à `None` et AUCUN avertissement.
// Ne lire que la première forme remplaçait la cause NOMMÉE par le générique.

test('F4 — un avertissement du serveur PRIME sur la motivation quand les deux sont là', () => {
  assert.equal(motifRefus({
    avertissements: ['ville manquante'],
    dimensionnement: { motivation: 'catalogue incomplet' },
  }), 'ville manquante')
})

test('F4 — le refus PROPRE (motivation, sans aucun avertissement) est lu, pas remplacé par le générique', () => {
  assert.equal(motifRefus({ dimensionnement: { motivation: 'catalogue incomplet' } }),
               'catalogue incomplet')
  assert.notEqual(motifRefus({ dimensionnement: { motivation: 'catalogue incomplet' } }),
                  REFUS_GENERIQUE)
})

test('F4 — puis seulement l’erreur réseau, et le générique en TOUT DERNIER recours', () => {
  assert.equal(motifRefus(null, 'réseau indisponible'), 'réseau indisponible')
  assert.equal(motifRefus({ dimensionnement: {} }), REFUS_GENERIQUE)
  assert.equal(motifRefus(null, null), REFUS_GENERIQUE)
})

test('le texte du serveur est rendu VERBATIM — jamais rhabillé, préfixé ni concaténé', () => {
  const phraseServeur =
    'Aucune taille recommandable : le catalogue ne compose aucune variante '
    + 'chiffrable et électriquement conforme pour ce profil.'
  const d = surLeCorpsAffiche({ donnees: { dimensionnement: { motivation: phraseServeur } } })
  assert.equal(d.motif, phraseServeur)
  assert.equal(d.motif.startsWith(REFUS_GENERIQUE), false)
})

// ── CE QUE `MOTEUR_A_REFUSE` FAIT RÉELLEMENT À L’ÉCRAN ──────────────────────

test('MOTEUR_A_REFUSE épingle le motif VERBATIM et referme l’attente', () => {
  const attente = sizingReducer(ETAT_INITIAL, {
    type: 'PROFIL_SITE_APPLIQUE',
    profil: { type_installation: 'residentiel', facture_hiver: 3000 },
  })
  assert.equal(attente.attenteMoteur, true, 'le résidentiel doit ouvrir une attente')
  const refuse = sizingReducer(attente, {
    type: 'MOTEUR_A_REFUSE', motif: 'Ville du lead absente.' })
  assert.equal(refuse.motifMoteur, 'Ville du lead absente.')
  assert.equal(refuse.attenteMoteur, false)
})

test('U3-900 — un refus ne pose AUCUN nombre de panneaux : ni un forfait, ni facture/900', () => {
  const attente = sizingReducer(ETAT_INITIAL, {
    type: 'PROFIL_SITE_APPLIQUE',
    profil: { type_installation: 'residentiel', facture_hiver: 3600 },
  })
  assert.equal(attente.nbPanneaux, '', 'aucune taille ne doit être devinée depuis la facture')
  const refuse = sizingReducer(attente, { type: 'MOTEUR_A_REFUSE', motif: 'x' })
  assert.equal(refuse.nbPanneaux, '', 'un refus est un vide HONNÊTE, jamais un défaut forfaitaire')
  assert.equal(refuse.kwcCible, '')
  assert.equal(refuse.sizingInfo, null, 'aucun « palier retenu » local en résidentiel')
})

test('MOTEUR_A_REFUSE hors attente ne touche à rien (une réponse de trop ne casse pas l’écran)', () => {
  const etat = sizingReducer(ETAT_INITIAL, { type: 'MOTEUR_A_REFUSE', motif: 'x' })
  assert.equal(etat, ETAT_INITIAL)
  assert.equal(etat.motifMoteur, null)
})

test('MOTEUR_A_REFUSE après une frappe n’épingle aucun motif (invariant 1, branche refus)', () => {
  const etat = [
    { type: 'PROFIL_SITE_APPLIQUE',
      profil: { type_installation: 'residentiel', facture_hiver: 3000 } },
    { type: 'SAISI', champ: 'nbPanneaux', valeur: '14' },
    { type: 'MOTEUR_A_REFUSE', motif: 'Ville du lead absente.' },
  ].reduce(sizingReducer, ETAT_INITIAL)
  assert.equal(etat.motifMoteur, null,
    'refuser une taille que le vendeur a lui-même tapée n’a aucun sens')
  assert.equal(etat.nbPanneaux, '14')
  assert.equal(etat.attenteMoteur, false)
})

test('une recommandation ACCEPTÉE efface le motif de refus précédent', () => {
  const refuse = [
    { type: 'PROFIL_SITE_APPLIQUE',
      profil: { type_installation: 'residentiel', facture_hiver: 3000 } },
    { type: 'MOTEUR_A_REFUSE', motif: 'Ville du lead absente.' },
  ].reduce(sizingReducer, ETAT_INITIAL)
  assert.equal(refuse.motifMoteur, 'Ville du lead absente.')
  const relance = sizingReducer(refuse, {
    type: 'PROFIL_SITE_APPLIQUE',
    profil: { type_installation: 'residentiel', facture_hiver: 4200 } })
  assert.equal(relance.motifMoteur, null, 'une nouvelle demande efface le refus précédent')
  const applique = sizingReducer(relance, {
    type: 'MOTEUR_A_REPONDU', recommandation: RECO })
  assert.equal(applique.motifMoteur, null)
  assert.equal(applique.nbPanneaux, '12')
})
