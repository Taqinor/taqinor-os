// CJ2b — l'écran générateur (résidentiel) appelle le moteur horaire SERVEUR
// (`POST /ventes/etude-horaire/preview/`) au lieu de ne montrer que son miroir
// local : « on ne voit ni l'économie réelle calculée, ni les données PVGIS —
// cette donnée devrait être comparée à la courbe de consommation » (ordre
// fondateur, 20/08/2026).
//
// QJR109 — CE FICHIER A CESSÉ DE LIRE LE SOURCE. Il épinglait par expression
// régulière la présence des noms importés, la position d'un `indexOf` par
// rapport à un autre, et la forme littérale d'une vingtaine de blocs JSX. Ce
// qu'il ne faisait NULLE PART, c'était exécuter la CHAÎNE que l'écran
// enchaîne réellement.
//
// CE QUE CE FICHIER TESTE MAINTENANT : cette chaîne, de bout en bout, avec le
// SERVICE RÉSEAU MOCKÉ EN PUR.
//
//     construireCorpsPreview  →  service (mock)  →  decisionSizing  →  reducer
//
// Chaque maillon est un module pur du dépôt ; le seul faux est le service, qui
// rend ici ce que `useEtudeHorairePreview` rendrait
// (`{ donnees, chargement, erreur, corpsServi }`) et COMPTE ses appels — ce
// qui permet de prouver la propriété la plus importante de CJ2b : quand rien
// n'ancre un calcul réel, l'écran n'appelle même pas le serveur.
//
// PAS DE DOUBLON : les fonctions pures d'`etudeHorairePreviewPur.js` ont déjà
// leur suite propre et complète (`features/ventes/etudeHorairePreview.test.mjs`,
// 104 assertions) — ce fichier ne les re-teste pas, il les ENCHAÎNE.
//
// CE QUI RESTE HORS DE PORTÉE D'UN TEST PUR (pas revendiqué ici) : tous les
// rendus — tableau de dimensionnement, boutons « Appliquer cette taille »,
// détail saisonnier, blocs falaise / glitch / estimation mensuelle,
// mémoïsation des blocs dérivés, `noValidate` du formulaire. Ce sont des specs
// RTL ; les regex retirées ici les DÉCRIVAIENT, elles ne les prouvaient pas.
//
// Run : node --test src/pages/ventes/DevisGeneratorEtudeHoraire.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  construireCorpsPreview, verdictBatteriePourTaille, lignesAffichables,
  etiquetteSource,
} from '../../features/ventes/etudeHorairePreviewPur.js'
import {
  decisionSizing,
} from '../../features/ventes/quote/hooks/useSizingMoteurPur.js'
import {
  sizingReducer, ETAT_INITIAL,
} from '../../features/ventes/quote/sizingReducer.js'

/**
 * LE SERVICE, MOCKÉ EN PUR. Même forme de sortie que
 * `useEtudeHorairePreview` ; `appels` enregistre chaque corps réellement
 * envoyé — un corps `null` n'est JAMAIS envoyé, exactement comme le hook.
 */
function serviceMock(reponses = {}) {
  const appels = []
  return {
    appels,
    interroger(corps) {
      if (corps === null) return { donnees: null, chargement: false, erreur: null, corpsServi: null }
      const cle = JSON.stringify(corps)
      appels.push(cle)
      const r = reponses[cle] ?? reponses['*'] ?? {}
      return {
        donnees: r.donnees ?? null,
        chargement: r.chargement ?? false,
        erreur: r.erreur ?? null,
        corpsServi: 'corpsServi' in r ? r.corpsServi : cle,
      }
    },
  }
}

/** LA CHAÎNE de l'écran : corps → service → décision → transition. */
function tourDEcran(etat, champs, service) {
  const corps = construireCorpsPreview(champs)
  const cleCourante = corps ? JSON.stringify(corps) : null
  const { donnees, chargement, erreur, corpsServi } = service.interroger(corps)
  const decision = decisionSizing({
    attente: etat.attenteMoteur,
    toucheNbPanneaux: etat.touche.nbPanneaux,
    chargement, donnees, erreur,
    cleServie: corpsServi, cleErreur: erreur ? corpsServi : null, cleCourante,
  })
  let suivant = etat
  if (decision.action === 'appliquer') {
    suivant = sizingReducer(etat,
      { type: 'MOTEUR_A_REPONDU', recommandation: decision.recommandation })
  } else if (decision.action === 'refuser') {
    suivant = sizingReducer(etat, { type: 'MOTEUR_A_REFUSE', motif: decision.motif })
  }
  return { corps, decision, etat: suivant }
}

const RESIDENTIEL = { modeInstallation: 'residentiel', fHiver: '3000' }
const RECO = { panneaux: 12, kwc: 8.52, panel_watt: 710 }
const enAttente = () => sizingReducer(ETAT_INITIAL, {
  type: 'PROFIL_SITE_APPLIQUE',
  profil: { type_installation: 'residentiel', facture_hiver: 3000 },
})

// ── CJ2b — QUAND RIEN N'ANCRE UN CALCUL, LE SERVEUR N'EST MÊME PAS APPELÉ ───

test('hors résidentiel, aucun corps n’est construit et le service n’est jamais interrogé', () => {
  const service = serviceMock()
  for (const marche of ['industriel', 'commercial', 'agricole']) {
    const { corps, decision } = tourDEcran(
      enAttente(), { ...RESIDENTIEL, modeInstallation: marche }, service)
    assert.equal(corps, null, `marché ${marche}`)
    assert.equal(decision.action, 'attendre')
  }
  assert.deepEqual(service.appels, [], 'aucun appel réseau ne doit partir')
})

test('sans facture, sans devis et sans lead, l’écran n’appelle pas non plus : on omet, on n’approxime pas', () => {
  const service = serviceMock()
  const { corps } = tourDEcran(enAttente(), { modeInstallation: 'residentiel' }, service)
  assert.equal(corps, null)
  assert.equal(service.appels.length, 0)
})

test('une facture d’hiver suffit à ancrer : UN appel, et le corps demande le dimensionnement', () => {
  const service = serviceMock()
  const { corps } = tourDEcran(enAttente(), RESIDENTIEL, service)
  assert.deepEqual(corps, { dimensionner: true, facture_hiver: 3000 })
  assert.equal(service.appels.length, 1)
})

// ── LA CHAÎNE COMPLÈTE, TOUR PAR TOUR ──────────────────────────────────────

test('réponse EN VOL : rien n’est posé, l’attente reste ouverte', () => {
  const service = serviceMock({ '*': { chargement: true } })
  const { decision, etat } = tourDEcran(enAttente(), RESIDENTIEL, service)
  assert.equal(decision.action, 'attendre')
  assert.equal(decision.raison, 'en-vol')
  assert.equal(etat.nbPanneaux, '', 'aucun chiffre pendant l’aller-retour')
  assert.equal(etat.attenteMoteur, true)
})

test('réponse FRAÎCHE : la recommandation SERVEUR est posée telle quelle et l’attente se referme', () => {
  const service = serviceMock({
    '*': { donnees: { dimensionnement: { recommandation: RECO } } } })
  const { decision, etat } = tourDEcran(enAttente(), RESIDENTIEL, service)
  assert.equal(decision.action, 'appliquer')
  assert.equal(etat.nbPanneaux, '12')
  assert.equal(etat.kwcCible, '8.52')
  assert.equal(etat.panelW, '710')
  assert.equal(etat.attenteMoteur, false)
  assert.equal(etat.motifMoteur, null)
})

test('REFUS du serveur : le motif FR est épinglé VERBATIM, aucun chiffre posé', () => {
  const service = serviceMock({
    '*': { donnees: { avertissements: ['Ville du lead absente.'] } } })
  const { decision, etat } = tourDEcran(enAttente(), RESIDENTIEL, service)
  assert.equal(decision.action, 'refuser')
  assert.equal(etat.motifMoteur, 'Ville du lead absente.')
  assert.equal(etat.nbPanneaux, '', 'un refus est un vide honnête')
  assert.equal(etat.attenteMoteur, false)
})

test('RÉPONSE PÉRIMÉE : la facture a changé, la réponse de l’ANCIENNE n’est ni posée ni consommée', () => {
  const service = serviceMock({
    '*': {
      donnees: { dimensionnement: { recommandation: RECO } },
      // Le service répond pour un corps qui n'est plus celui à l'écran.
      corpsServi: JSON.stringify({ dimensionner: true, facture_hiver: 1200 }),
    },
  })
  const { decision, etat } = tourDEcran(
    enAttente(), { ...RESIDENTIEL, fHiver: '3000' }, service)
  assert.equal(decision.action, 'attendre')
  assert.equal(decision.raison, 'reponse-perimee')
  assert.equal(etat.nbPanneaux, '', 'c’est le bug « 1200 → 3000 restait bloqué sur la taille du 1200 »')
  assert.equal(etat.attenteMoteur, true, 'l’attente doit rester ouverte pour la BONNE réponse')
})

test('ÉCHEC PÉRIMÉ : l’échec d’une facture remplacée n’épingle aucun refus', () => {
  const service = serviceMock({
    '*': { erreur: 'réseau indisponible',
           corpsServi: JSON.stringify({ dimensionner: true, facture_hiver: 1200 }) },
  })
  const { decision, etat } = tourDEcran(enAttente(), RESIDENTIEL, service)
  assert.equal(decision.action, 'attendre')
  assert.equal(decision.raison, 'echec-perime')
  assert.equal(etat.motifMoteur, null)
  assert.equal(etat.attenteMoteur, true)
})

test('une frappe pendant l’aller-retour GAGNE : la réponse arrive et est abandonnée', () => {
  const service = serviceMock({
    '*': { donnees: { dimensionnement: { recommandation: RECO } } } })
  const tape = sizingReducer(enAttente(),
    { type: 'SAISI', champ: 'nbPanneaux', valeur: '14' })
  const { decision, etat } = tourDEcran(tape, RESIDENTIEL, service)
  assert.equal(decision.action, 'abandonner')
  assert.equal(etat.nbPanneaux, '14')
})

test('deux tours successifs : une réponse fraîche APRÈS une périmée est bien consommée', () => {
  const cleCourante = JSON.stringify({ dimensionner: true, facture_hiver: 3000 })
  const perime = serviceMock({
    '*': { donnees: { dimensionnement: { recommandation: RECO } },
           corpsServi: JSON.stringify({ dimensionner: true, facture_hiver: 1200 }) } })
  const tour1 = tourDEcran(enAttente(), RESIDENTIEL, perime)
  assert.equal(tour1.etat.attenteMoteur, true)

  const frais = serviceMock({
    '*': { donnees: { dimensionnement: { recommandation: { panneaux: 21, kwc: 14.9 } } },
           corpsServi: cleCourante } })
  const tour2 = tourDEcran(tour1.etat, RESIDENTIEL, frais)
  assert.equal(tour2.decision.action, 'appliquer')
  assert.equal(tour2.etat.nbPanneaux, '21')
})

// ── CJ2b — LE CORPS PORTE CE QUI ANCRE LE CALCUL ───────────────────────────

test('FINDING 25/08 — le corps transporte ville et raccordement quand ils existent, jamais fabriqués', () => {
  const avec = construireCorpsPreview({
    ...RESIDENTIEL, ville: 'Casablanca', raccordement: 'triphase', kwp: 8.52 })
  assert.equal(avec.ville, 'Casablanca')
  assert.equal(avec.raccordement, 'triphase')
  assert.equal(avec.kwc, 8.52)
  const sans = construireCorpsPreview(RESIDENTIEL)
  assert.equal('ville' in sans, false, 'aucune ville inventée')
  assert.equal('raccordement' in sans, false)
  assert.equal('kwc' in sans, false)
})

test('L-QA1 — un DEVIS en édition prime sur le lead (même chaîne de résolution que le serveur)', () => {
  const corps = construireCorpsPreview({
    modeInstallation: 'residentiel', editId: '42', leadId: '7' })
  assert.equal(corps.devis, 42)
  assert.equal('lead' in corps, false)
  const sansDevis = construireCorpsPreview({
    modeInstallation: 'residentiel', leadId: '7' })
  assert.equal(sansDevis.lead, 7)
})

test('un changement de facture change la CLÉ du corps — c’est ce qui rend la péremption détectable', () => {
  const a = JSON.stringify(construireCorpsPreview({ ...RESIDENTIEL, fHiver: '1200' }))
  const b = JSON.stringify(construireCorpsPreview({ ...RESIDENTIEL, fHiver: '3000' }))
  assert.notEqual(a, b)
  const bis = JSON.stringify(construireCorpsPreview({ ...RESIDENTIEL, fHiver: '3000' }))
  assert.equal(b, bis, 'la clé doit être STABLE pour un même corps, sinon tout paraît périmé')
})

// ── HONNÊTETÉ #1 — UNE BATTERIE NON LIVRABLE N’A PAS DE MONTANT ────────────

const DIMENSIONNEMENT = {
  tableau: [
    { kwc: 8.52, batterie_disponible: false, economie_avec_mad: 21000,
      cout_avec_ttc: 95000, payback_avec_annees: 6.2, couverture_avec: 0.8,
      taux_autoconso_avec: 0.7,
      verdicts_bloquants_avec: ['Aucune batterie compatible tarifée.'] },
    { kwc: 12.78, batterie_disponible: true, economie_avec_mad: 30000,
      cout_avec_ttc: 140000, payback_avec_annees: 5.4, couverture_avec: 0.9,
      taux_autoconso_avec: 0.85, verdicts_bloquants_avec: [] },
  ],
}

test('batterie non livrable pour la taille chiffrée : le verdict porte la RAISON, jamais un montant', () => {
  const lignes = lignesAffichables(DIMENSIONNEMENT)
  assert.equal(lignes[0].batterieVendable, false)
  assert.equal(lignes[0].raisonBatterie, 'Aucune batterie compatible tarifée.')
  for (const champ of ['economie_avec_mad', 'cout_avec_ttc',
                       'payback_avec_annees', 'couverture_avec',
                       'taux_autoconso_avec']) {
    assert.equal(lignes[0][champ], null,
      `aucun chiffre d’une installation qu’on ne peut pas livrer : ${champ}`)
  }
  assert.equal(lignes[1].batterieVendable, true)
  assert.equal(lignes[1].economie_avec_mad, 30000, 'une taille livrable garde ses chiffres')
  assert.equal(lignes[1].raisonBatterie, '')
})

test('le verdict appliqué aux cartes est celui de la taille RÉELLEMENT chiffrée par le vendeur', () => {
  const lignes = lignesAffichables(DIMENSIONNEMENT)
  const petit = verdictBatteriePourTaille(lignes, 8.52)
  assert.equal(petit.vendable, false)
  assert.equal(petit.raison, 'Aucune batterie compatible tarifée.')
  const grand = verdictBatteriePourTaille(lignes, 12.78)
  assert.equal(grand.vendable, true)
  assert.equal(verdictBatteriePourTaille(lignes, 999), null,
    'le moteur n’a rien dit sur cette taille : on ne suppose pas')
})

// ── HONNÊTETÉ #2 — UNE ESTIMATION SE DIT ESTIMATION ────────────────────────

test('une facture répétée sur 12 mois est ÉTIQUETÉE estimation ; une vraie variation ne l’est pas', () => {
  assert.equal(etiquetteSource('facture_hiver').estimation, true)
  assert.equal(etiquetteSource('facture_hiver_ete').estimation, true)
  assert.equal(etiquetteSource('factures_mensuelles_reelles').estimation, false)
  assert.equal(etiquetteSource('kwh_mensuels_saisis').estimation, false)
  assert.equal(typeof etiquetteSource('une_source_inconnue').libelle, 'string')
})
