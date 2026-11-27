// AGR127 — fonctions pures de l'aperçu pompage serveur. Run :
//   node --test src/features/ventes/etudePompagePreview.test.mjs
// L'échantillon du contrat est LU dans le fichier partagé, jamais recopié.
import test from 'node:test'
import assert from 'node:assert/strict'
import { documentContrat, enTexte } from '../../test/fixtures/contractSamples.js'
import {
  construireCorpsPompage, manquantsPompage, alertesAffichables,
  libelleProvenance, nombreOuNull, besoinExprime, besoinDepuisDebitSouhaite,
  refusAutoRemplirPompage, etatPompageEcran, POMPAGE_SAISIE_VIDE, poserSaisie,
  messagePompeSansPrix,
} from './etudePompagePreviewPur.js'

const CONTRAT = documentContrat('ventes', 'etude_pompage_preview')

test('corps conforme à l’échantillon du contrat (nombres tapés en texte)', () => {
  const etat = enTexte(CONTRAT.corps)
  assert.deepEqual(construireCorpsPompage(etat), CONTRAT.corps)
})

test('corps : aucune valeur arrondie ni rejetée', () => {
  const etat = enTexte(CONTRAT.corps)
  etat.source.niveau_dynamique_m = '40,37'
  etat.distance_champ_m = '25.125'
  const corps = construireCorpsPompage(etat)
  assert.equal(corps.source.niveau_dynamique_m, 40.37)
  assert.equal(corps.distance_champ_m, 25.125)
})

test('état incomplet → null (aucun appel)', () => {
  assert.equal(construireCorpsPompage(null), null)
  assert.equal(construireCorpsPompage({}), null)
  const sansBesoin = enTexte(CONTRAT.corps)
  sansBesoin.besoin.volume_m3_jour = ''
  assert.equal(construireCorpsPompage(sansBesoin), null)
  const sansHauteur = enTexte(CONTRAT.corps)
  sansHauteur.source.niveau_dynamique_m = ''
  sansHauteur.source.niveau_statique_m = ''
  sansHauteur.hmt.saisie_m = ''
  assert.equal(construireCorpsPompage(sansHauteur), null)
  assert.deepEqual(manquantsPompage(sansHauteur),
    ['la hauteur (HMT ou niveau d\'eau)'])
})

test('champ vide → null, jamais un défaut', () => {
  const etat = enTexte(CONTRAT.corps)
  etat.distance_champ_m = ''
  etat.besoin.region = ''
  const corps = construireCorpsPompage(etat)
  assert.equal(corps.distance_champ_m, null)
  assert.equal(corps.besoin.region, null)
  assert.equal(nombreOuNull(''), null)
  assert.equal(nombreOuNull('abc'), null)
})

// AGQ27 (C-AGQ-026) — corps::test_mode_volume_n_envoie_pas_la_pompe_actuelle :
// seuls les champs du mode de besoin choisi partent ; une valeur tapée sous
// un autre mode part `null` (mutant : spread inconditionnel ⇒ rouge).
test('corps::test_mode_volume_n_envoie_pas_la_pompe_actuelle', () => {
  const etat = enTexte(CONTRAT.corps)
  etat.besoin.debit_actuel_m3h = '10'
  etat.besoin.heures_actuelles_jour = '6'
  const volume = construireCorpsPompage(etat).besoin
  assert.equal(volume.mode, 'volume_declare')
  assert.equal(volume.volume_m3_jour, 135)
  assert.equal(volume.debit_actuel_m3h, null)
  assert.equal(volume.heures_actuelles_jour, null)
  etat.besoin.mode = 'pompe_actuelle'
  const actuelle = construireCorpsPompage(etat).besoin
  assert.equal(actuelle.debit_actuel_m3h, 10)
  assert.equal(actuelle.heures_actuelles_jour, 6)
  assert.equal(actuelle.volume_m3_jour, null)
  // Débit souhaité, mois de pointe, région : servis quel que soit le mode.
  assert.equal(actuelle.mois_pointe, 7)
  assert.equal(actuelle.region, 'souss-massa')
})

test('mode neuve → plaque nulle ; mode existante → plaque transmise', () => {
  const etat = enTexte(CONTRAT.corps)
  etat.plaque = { kw: '5.5', tension_v: '380', phases: 'tri', cv: '', courant_a: '' }
  assert.equal(construireCorpsPompage(etat).plaque, null)
  etat.mode_pompe = 'existante'
  assert.deepEqual(construireCorpsPompage(etat).plaque,
    { kw: 5.5, tension_v: 380, phases: 'tri', cv: null, courant_a: null })
})

test('aucune alerte perdue', () => {
  const reponse = {
    alertes: [
      { code: 'couverture_insuffisante', champ: 'besoin', message: 'A' },
      { code: 'surdimensionnement', champ: 'champ', message: 'B' },
      { code: 'kw_plaque_a_relever', champ: 'plaque.kw', message: '' },
    ],
  }
  const vues = alertesAffichables(reponse)
  assert.equal(vues.length, 3)
  assert.deepEqual(vues.map((a) => a.code),
    ['couverture_insuffisante', 'surdimensionnement', 'kw_plaque_a_relever'])
  assert.equal(vues[2].message, 'kw_plaque_a_relever')
  assert.deepEqual(alertesAffichables(CONTRAT.exemple).length,
    CONTRAT.exemple.alertes.length)
  assert.deepEqual(alertesAffichables(null), [])
})

// Rejeu live AGQ41 (24/10) — PARITÉ avec le serveur (`pompage.py::_besoin`) : sans
// mode choisi, le débit souhaité seul fait le besoin ; le corps n'envoie QUE ce
// que le serveur lit pour ce cas (AGQ27 : volume et pompe actuelle à null).
test('besoin::test_debit_souhaite_seul_est_un_besoin_exprime', () => {
  assert.equal(besoinExprime({ mode: '', debit_souhaite_m3h: '10' }), true)
  assert.equal(besoinExprime({ debit_souhaite_m3h: 10 }), true)
  assert.equal(besoinExprime({ mode: 'debit_souhaite', debit_souhaite_m3h: '10' }), true)
  assert.equal(besoinExprime({ mode: '', debit_souhaite_m3h: '' }), false)
  assert.equal(besoinExprime({ mode: '', debit_souhaite_m3h: '0' }), false)
  // Un mode CHOISI garde sa règle : le débit souhaité ne remplace pas un volume vide.
  assert.equal(besoinExprime({ mode: 'volume_declare', volume_m3_jour: '', debit_souhaite_m3h: '10' }), false)
  assert.equal(besoinDepuisDebitSouhaite({ mode: 'pompe_actuelle', debit_souhaite_m3h: '10' }), false)
  const saisie = poserSaisie(POMPAGE_SAISIE_VIDE, 'mode_pompe', 'existante')
  const etat = etatPompageEcran(saisie, {
    pompeDebit: '10', pompeHmt: '40', farmHmtStatic: '40', pompeCv: '7',
  })
  assert.deepEqual(manquantsPompage(etat), [])
  const corps = construireCorpsPompage(etat)
  assert.equal(corps.besoin.mode, null)
  assert.equal(corps.besoin.debit_souhaite_m3h, 10)
  assert.equal(corps.besoin.volume_m3_jour, null)
  assert.equal(corps.besoin.debit_actuel_m3h, null)
  assert.equal(corps.besoin.heures_actuelles_jour, null)
})

test('refus::test_kit_sans_variateur_refuse_auto_remplir_avec_la_cause', () => {
  // Kit complet de l'exemple du contrat : rien ne s'oppose.
  assert.deepEqual(CONTRAT.exemple.roles_minimum_manquants, [])
  assert.equal(refusAutoRemplirPompage(CONTRAT.exemple), null)
  assert.equal(refusAutoRemplirPompage(null), null)
  // Pompe existante sans kW de plaque : variateur absent du kit.
  const donnees = {
    ...CONTRAT.exemple_pompe_existante,
    kit: {
      ...CONTRAT.exemple_pompe_existante.kit,
      inclus: CONTRAT.exemple_pompe_existante.kit.inclus.filter((l) => l.cle !== 'variateur'),
    },
    variateur: { produit: null, nom: null, motif: 'kW de plaque à relever (visite) : variateur non choisi' },
    roles_minimum_manquants: [
      { cle: 'variateur', libelle: 'Variateur', motif: 'aucun article au catalogue' },
    ],
  }
  const refus = refusAutoRemplirPompage(donnees)
  assert.match(refus, /^Auto-remplir indisponible/)
  assert.match(refus, /Variateur : kW de plaque à relever/)
  // Un article « prix à renseigner » reste une LIGNE du kit : pas de refus.
  const sansPrix = {
    kit: { inclus: [{ cle: 'pompe', produit: null, prix_connu: false }] },
    roles_minimum_manquants: [
      { cle: 'pompe', libelle: 'Pompe', motif: 'prix à renseigner au catalogue' },
    ],
  }
  assert.equal(refusAutoRemplirPompage(sansPrix), null)
})

test('refus::T4-U3-021 — le rôle manquant nomme l’article SERVI en cause (jamais un prix)', () => {
  // Forme servie : contrat `etude_pompage_preview.json`, `roles_minimum_manquants[].articles[] = {id, nom}`.
  const servis = CONTRAT.exemple_aucune_pompe_chiffrable.roles_minimum_manquants
  assert.ok(servis.every((r) => Array.isArray(r.articles)))
  const donnees = {
    kit: { inclus: [] },
    roles_minimum_manquants: [
      { cle: 'structure', libelle: 'Structure au sol', motif: 'prix à renseigner au catalogue',
        articles: [{ id: 42, nom: 'Structure au sol pompage' }] },
      { cle: 'installation', libelle: 'Installation', motif: 'aucun article au catalogue', articles: [] },
    ],
  }
  const refus = refusAutoRemplirPompage(donnees)
  assert.match(refus, /Structure au sol : prix à renseigner au catalogue — article « Structure au sol pompage »/)
  // Sans article servi : rien d'ajouté.
  assert.match(refus, /Installation : aucun article au catalogue\)/)
  assert.doesNotMatch(refus, /42/)
})

test('libellés de provenance', () => {
  assert.equal(libelleProvenance({ origine: 'saisie', detail: null, date: null }), 'saisi')
  assert.equal(libelleProvenance({ origine: 'lead', detail: 'mesure_visite', date: '2026-09-15' }),
    'fiche lead — mesuré en visite (2026-09-15)')
  assert.equal(libelleProvenance(null), 'origine inconnue')
})

// AGRI-SITE (fondateur, 28/10/2026) — un devis agricole démarré d'un CLIENT
// sans lead : le corps porte l'id du client (le serveur lit son site sur la
// fiche) ; lead présent → les deux voyagent, le serveur fait primer le lead.
test('site::test_client_sans_lead_transmis_au_serveur', () => {
  const saisie = poserSaisie(POMPAGE_SAISIE_VIDE, 'mode_pompe', 'existante')
  const base = { pompeDebit: '10', pompeHmt: '40', farmHmtStatic: '40', pompeCv: '7' }
  const sansLead = construireCorpsPompage(etatPompageEcran(saisie, { ...base, clientId: '12' }))
  assert.equal(sansLead.client, 12)
  assert.equal('lead' in sansLead, false)
  assert.deepEqual(sansLead.localisation, { ville: null, lat: null, lon: null })
  const aucun = construireCorpsPompage(etatPompageEcran(saisie, { ...base, clientId: null }))
  assert.equal('client' in aucun, false)
  const avecLead = construireCorpsPompage(etatPompageEcran(saisie, { ...base, clientId: 12, leadId: 7 }))
  assert.equal(avecLead.lead, 7)
  assert.equal(avecLead.client, 12)
})

// T4-U3-004 — sans pompe chiffrable, l'écran nomme la pompe que retient le
// dimensionnement (la PREMIÈRE de `prix_a_renseigner`, servie du plus petit au
// plus gros kW par `core.pompage.selection.choisir_pompe`) et QUI peut saisir
// son prix — jamais une liste de dix pompes sans suite.
test('T4-U3-004 — pompe retenue sans prix : nommée, avec sa raison et qui saisit le prix', () => {
  const donnees = {
    pompe: { placeholder: true },
    hmt: { valeur_m: 80 },
    conception: { debit_conception_m3h: 20 },
    prix_a_renseigner: ['Pompe immergée OSP 30/11 — 12.5 CV', 'Pompe immergée OSP 30/13 — 15 CV'],
  }
  const m = messagePompeSansPrix(donnees)
  assert.match(m, /« Pompe immergée OSP 30\/11 — 12\.5 CV »/)
  assert.match(m, /plus petite pompe de la courbe qui donne 20 m³\/h à 80 m/)
  assert.match(m, /Modifier les prix du catalogue/)
  assert.match(m, /Directeur ou Administrateur/)
  assert.match(m, /OSP 30\/13/)
  // ACAL1256 — pompe chiffrée retenue : seules les AUTRES pompes à courbe manquent de prix.
  const autres = messagePompeSansPrix({ ...donnees, pompe: { placeholder: false, prix_connu: true } })
  assert.match(autres, /^D'autres pompes à courbe conviendraient mais n'ont pas de prix : .*OSP 30\/13/)
  assert.doesNotMatch(autres, /ne peut donc pas être chiffrée/)
  assert.match(messagePompeSansPrix({ ...donnees, pompe: { placeholder: false, prix_connu: false } }),
    /ne peut donc pas être chiffrée/)
  assert.equal(messagePompeSansPrix({ ...donnees, prix_a_renseigner: [] }), null)
  assert.equal(messagePompeSansPrix(null), null)
})
