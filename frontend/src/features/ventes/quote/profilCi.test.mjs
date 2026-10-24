// CIQ125 — le profil déclaré C&I : état d'écran ⇄ corps ⇄ entrées v2.
// Exécuté en CI : node --test src/features/ventes/quote/profilCi.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  profilCiVide, poserProfilCi, corpsCiDepuisProfil, entreesCiV2,
  profilDepuisEtude, CLES_ENTREES_CI_V2, profilCiAncre,
  lignesDepuisCompositionCi, avertissementsCompositionCi,
  semisCiDepuisLead, cleReprisDuChamp, LIBELLE_REPRIS_LEAD,
} from './profilCi.js'
import { withKeys } from './ligneFabrique.js'
import { lignesEcranVersPayload } from './lignesEcran.js'
import { devisVersEtat, etatVersEcritures } from './etatDevis.js'
import { documentContrat } from '../../../test/fixtures/contractSamples.js'

const CONTRAT = documentContrat('ventes', 'etude_ci_preview')
const KWH = CONTRAT.corps.consommation.kwh_mensuels

const profilSaisi = () => {
  let p = profilCiVide()
  KWH.forEach((v, i) => { p = poserProfilCi(p, `kwhMensuels.${i}`, String(v)) })
  for (const i of [0, 1, 2, 3, 4]) p = poserProfilCi(p, `joursOuverts.${i}`, true)
  p = poserProfilCi(p, 'plages.ouvre.debut', '8')
  p = poserProfilCi(p, 'plages.ouvre.fin', '18,5')
  p = poserProfilCi(p, 'fermetures', [{ du: '2026-08-01', au: '2026-08-15', motif: 'congés' }])
  p = poserProfilCi(p, 'talonKw', '8')
  p = poserProfilCi(p, 'typePose', 'toit_plat_leste')
  p = poserProfilCi(p, 'surfaceUtile', '650')
  p = poserProfilCi(p, 'couverture', 'beton')
  p = poserProfilCi(p, 'tension', 'mt')
  p = poserProfilCi(p, 'phases', 'tri')
  p = poserProfilCi(p, 'puissanceSouscrite', '72.125')
  p = poserProfilCi(p, 'revente', true)
  return p
}

test('12 kWh saisis ⇒ le corps porte consommation.kwh_mensuels tels quels', () => {
  const corps = corpsCiDepuisProfil(profilSaisi(), { mode: 'industriel' })
  assert.deepEqual(corps.consommation.kwh_mensuels, KWH)
  assert.equal(corps.mode, 'industriel')
  // la forme est celle du contrat : mêmes clés de tête que l'échantillon
  assert.deepEqual(Object.keys(corps).sort(), Object.keys(CONTRAT.corps).sort())
  assert.deepEqual(corps.rythme.jours_ouverts, [true, true, true, true, true, false, false])
  assert.deepEqual(corps.rythme.plages, { ouvre: [[8, 18.5]] })
  assert.equal(corps.puissance_souscrite_kva, 72.125)
  assert.equal(corps.contraintes.revente_choisie, true)
})

test('aucun jour coché d’office, aucun défaut : profil vide ⇒ aucun appel', () => {
  assert.equal(corpsCiDepuisProfil(profilCiVide(), { mode: 'commercial' }), null)
  assert.equal(profilCiAncre(profilCiVide()), false)
  // avec un lead, le serveur résout ce qui manque : le corps part
  const avecLead = corpsCiDepuisProfil(profilCiVide(), { mode: 'commercial', lead: 12 })
  assert.equal(avecLead.lead, 12)
  assert.equal(avecLead.rythme.jours_ouverts, null)
  assert.equal(avecLead.consommation.kwh_mensuels, null)
})

test('la revente n’existe qu’en MT : repasser en BT la retire', () => {
  const p = poserProfilCi(profilSaisi(), 'tension', 'bt')
  assert.equal(p.revente, false)
  assert.equal(corpsCiDepuisProfil(p, { mode: 'commercial' }).contraintes.revente_choisie, false)
})

test('une taille explicite seule ancre le calcul', () => {
  const p = poserProfilCi(profilCiVide(), 'tailleExplicite', '55')
  assert.equal(profilCiAncre(p), true)
  assert.equal(corpsCiDepuisProfil(p, { mode: 'industriel' }).taille_explicite_kwc, 55)
})

test('entrées v2 : seules les clés `ecran` du contrat, jamais une dérivée', () => {
  const contrat = CONTRAT.cles_etude_params_ci_v2.entrees.map((e) => e.cle)
  assert.deepEqual([...CLES_ENTREES_CI_V2].sort(), [...contrat].sort())
  const e = entreesCiV2(profilSaisi(), { mode: 'commercial' })
  assert.deepEqual(Object.keys(e).sort(), [...contrat].sort())
  for (const derivee of ['etude_ci', 'production_figee', 'taux_autoconso', 'payback']) {
    assert.equal(derivee in e, false)
  }
})

test('enregistrer → rouvrir → enregistrer sans toucher = objet serveur identique', () => {
  for (const mode of ['industriel', 'commercial']) {
    const etat1 = {
      mode, lignes: [], tauxTva: '20.00', discountPct: '0', echeancier: null,
      profilCi: profilSaisi(), ctxCi: { mode, ville: 'Marrakech' },
    }
    const ecr1 = etatVersEcritures(etat1, { etude: null, entrees: {} })
    const devis = {
      id: 5, mode_installation: mode, taux_tva: '20.00', remise_globale: '0',
      lignes: [], etude_params: ecr1.etude,
    }
    const etat2 = devisVersEtat(devis)
    const ecr2 = etatVersEcritures(etat2, { etude: null, entrees: {} })
    for (const cle of CLES_ENTREES_CI_V2) {
      assert.deepEqual(ecr2.etude[cle], ecr1.etude[cle], `${mode} : ${cle}`)
    }
    assert.deepEqual(profilDepuisEtude(ecr2.etude), profilDepuisEtude(ecr1.etude))
  }
})

test('factures MAD et total annuel : aller-retour exact', () => {
  let p = poserProfilCi(profilCiVide(), 'saisieConso', 'factures')
  p = poserProfilCi(p, 'factures', [{ mois: '2026-01', montant_ttc: '4200,5', kwh: '' }])
  const e = entreesCiV2(p, { mode: 'commercial' })
  assert.deepEqual(e.consommation.factures_mad, [{ mois: '2026-01', montant_ttc: 4200.5, kwh: null }])
  assert.deepEqual(entreesCiV2(profilDepuisEtude(e), { mode: 'commercial' }), e)

  let a = poserProfilCi(profilCiVide(), 'saisieConso', 'annuel')
  a = poserProfilCi(a, 'kwhAnnuel', '150000.75')
  const ea = entreesCiV2(a, { mode: 'industriel' })
  assert.equal(ea.consommation.kwh_annuel, 150000.75)
  assert.deepEqual(entreesCiV2(profilDepuisEtude(ea), { mode: 'industriel' }), ea)
})

// ── ADEV84 — lignes sans quantité : repères NOMMÉS, jamais enregistrés ──
const COMPOSITION_ADEV84 = {
  lignes: [
    { role: 'cable_dc', produit: 9, designation: 'Câble DC panneaux → onduleur', quantite: null,
      prix_connu: false, a_chiffrer_visite: true },
    { role: 'cable_ac', produit: null, designation: 'Câble AC onduleur → TGBT',
      prix_connu: false, a_chiffrer_visite: true },
    { role: 'pose_modules', produit: null, designation: 'Pose des modules', quantite: 1,
      prix_connu: false },
    { role: 'onduleur_string_tri', produit: 48, designation: 'Onduleur 50kW', quantite: 1, prix_connu: true },
  ],
  prix_a_renseigner: ['Pose des modules', 'Structure introuvable'],
  a_chiffrer_visite: ['Câble DC panneaux → onduleur', 'Câble AC onduleur → TGBT'],
}
const PRODUITS_84 = [{ id: 48, nom: 'Onduleur 50kW', prix_vente: '10000', tva: 20 }]

test('ADEV84 — une ligne sans quantité devient un repère nommé « à chiffrer après visite »', () => {
  const rows = lignesDepuisCompositionCi(COMPOSITION_ADEV84, PRODUITS_84, 20)
  assert.equal(rows.length, 4, 'aucune ligne sautée en silence')
  const dc = rows[0]
  assert.equal(dc.designation, 'Câble DC panneaux → onduleur — à chiffrer après visite')
  assert.equal(dc.produit, '')
  assert.equal(dc.prix_unit_ttc, 0)
  assert.equal(dc.a_chiffrer_visite, true)
  assert.equal(rows[1].designation, 'Câble AC onduleur → TGBT — à chiffrer après visite')
  // les repères « prix à renseigner » et les lignes tarifées restent inchangés
  assert.equal(rows[2].designation, 'Pose des modules — prix à renseigner')
  assert.equal(rows[2].a_chiffrer_visite, undefined)
  assert.equal(rows[3].produit, '48')
})

test('ADEV84 — la TVA des repères est celle de la société, plus un 20 codé', () => {
  const rows = lignesDepuisCompositionCi(COMPOSITION_ADEV84, PRODUITS_84, 22)
  assert.equal(rows[0].taux_tva, 22)
  assert.equal(rows[1].taux_tva, 22)
  assert.equal(rows[2].taux_tva, 22)
  // taux société inconnu ⇒ le défaut nommé, jamais NaN
  assert.equal(lignesDepuisCompositionCi(COMPOSITION_ADEV84, PRODUITS_84)[0].taux_tva, 20)
})

test('lignesDepuisCompositionCi : un forfait au panneau suit le compte de la composition', () => {
  const produits = [
    { id: 5, nom: 'Panneau Jinko 550W', prix_vente: '1000', tva: 10, prix_fixe_ht: null, prix_par_panneau_ht: null },
    { id: 6, nom: 'Installation', prix_vente: '4000', tva: 20, prix_fixe_ht: '2000.00', prix_par_panneau_ht: '250.0000' },
  ]
  const composition = { lignes: [
    { role: 'panneau', produit: 5, designation: 'Panneau Jinko 550W', quantite: 40, prix_connu: true },
    { role: 'installation', produit: 6, designation: 'Installation', quantite: 1, prix_connu: true },
  ] }
  const rows = lignesDepuisCompositionCi(composition, produits, 20)
  assert.equal(rows[1].prixHtOrigine, '12000.00') // 2 000 + 250 × 40
  assert.equal(rows[1].prix_unit_ttc, 14400)
  assert.equal(rows[0].prixHtOrigine, '1000.00', 'produit sans barème : prix_vente inchangé')
})

test('ADEV84 — aucun repère n’est enregistré (jamais envoyé au serveur)', () => {
  const lignes = withKeys(lignesDepuisCompositionCi(COMPOSITION_ADEV84, PRODUITS_84, 20))
  const payload = lignesEcranVersPayload(lignes)
  assert.deepEqual(payload.map((l) => l.produit), [48])
})

test('ADEV84 — l’avertissement lie chaque poste : Paramètres (prestation) ou Stock, puis « à chiffrer après visite »', () => {
  const w = avertissementsCompositionCi(COMPOSITION_ADEV84)
  assert.deepEqual(w.aRenseigner, [
    { nom: 'Pose des modules', lien: '/parametres' },
    { nom: 'Structure introuvable', lien: '/stock' },
  ])
  assert.deepEqual(w.aChiffrerVisite,
    ['Câble DC panneaux → onduleur', 'Câble AC onduleur → TGBT'])
  // une ligne sans quantité absente de la liste serveur est quand même nommée
  const sans = avertissementsCompositionCi({ lignes: COMPOSITION_ADEV84.lignes, prix_a_renseigner: [] })
  assert.equal(sans.aChiffrerVisite.length, 2)
  assert.deepEqual(avertissementsCompositionCi(null), { aRenseigner: [], aChiffrerVisite: [] })
})

// ── ADEV92 — le prix servi par le serveur (forfait Paramètres) prime le catalogue ──
test('ADEV92 — une prestation C&I porte le forfait société servi, pas le prix catalogue', () => {
  const composition = { lignes: [
    { role: 'pose_modules', produit: 77, designation: 'Pose des modules C&I', quantite: 1, unite: 'forfait',
      prix_connu: true, prix_unitaire_ht: '2500.00' },
    { role: 'onduleur_string_tri', produit: 48, designation: 'Onduleur 50kW', quantite: 1, prix_connu: true },
  ], prix_a_renseigner: [], a_chiffrer_visite: [] }
  const produits = [
    { id: 77, nom: 'Pose des modules C&I', prix_vente: '900', tva: 20 },
    { id: 48, nom: 'Onduleur 50kW', prix_vente: '10000', tva: 20 },
  ]
  const rows = lignesDepuisCompositionCi(composition, produits, 20)
  assert.equal(rows[0].prixHtOrigine, '2500.00', 'forfait Paramètres, jamais le 900 du catalogue')
  assert.equal(rows[0].prix_unit_ttc, 3000)
  // sans prix serveur : le prix catalogue du produit, comme avant
  assert.equal(rows[1].prixHtOrigine, '10000.00')
  assert.equal(rows[1].prix_unit_ttc, 12000)
})

// ── ADEV100 — le générateur s'ouvre pré-rempli depuis la fiche lead ──
const LEAD_PRO = documentContrat('crm', 'lead_pro').exemple
const LEAD_HOTEL = {
  ...LEAD_PRO, releve_conso: null, conso_mensuelle_kwh: '6000.00', raccordement: 'triphase',
  jours_ouverture: [1, 2, 3, 4, 5, 6], heure_debut: 8, heure_fin: 18, regime_equipes: '',
}
const COURANT_VIDE = { profil: profilCiVide(), categorie: 'non_precisee', reponses: {}, tarif: {} }

test('ADEV100 — un lead commercial sème catégorie, réponses, contrat, tension, phase, jours, heures, surface, kWh', () => {
  const s = semisCiDepuisLead(LEAD_HOTEL, COURANT_VIDE)
  assert.equal(s.categorie, 'hotel')
  assert.deepEqual(s.reponses, { chambres: 40, piscine: false })
  assert.deepEqual(s.tarif, { contrat: 'bt_patente', optionBiHoraire: false })
  let p = profilCiVide()
  for (const [chemin, valeur] of s.profil) p = poserProfilCi(p, chemin, valeur)
  assert.equal(p.tension, 'bt')
  assert.equal(p.phases, 'tri')
  assert.deepEqual(p.joursOuverts, [true, true, true, true, true, true, false])
  assert.deepEqual(p.plages.ouvre, { debut: '8', fin: '18' })
  assert.equal(p.surfaceUtile, '650')
  assert.equal(p.saisieConso, 'annuel')
  assert.equal(p.kwhAnnuel, '72000', 'kWh mensuel × 12, repris tel quel')
  assert.equal(p.typePose, '', 'une terrasse béton reste à déclarer (lestée ou fixée ?)')
  for (const cle of ['categorie', 'contrat', 'kwhAnnuel', 'tension', 'phases', 'joursOuverts', 'plages', 'surfaceUtile',
    'reponses.chambres', 'reponses.piscine']) {
    assert.ok(s.marques.includes(cle), cle)
  }
  assert.equal(LIBELLE_REPRIS_LEAD, 'repris du lead')
})

test('ADEV100 — rien n’est semé pour une valeur absente du lead, ni pour un lead hors C&I', () => {
  const nu = { type_installation: 'commercial' }
  assert.equal(semisCiDepuisLead(nu, COURANT_VIDE), null)
  assert.equal(semisCiDepuisLead({ ...LEAD_HOTEL, type_installation: 'residentiel' }, COURANT_VIDE), null)
  assert.equal(semisCiDepuisLead(null, COURANT_VIDE), null)
  // « ne sait pas » et le défaut visible du site web ne sont pas des réponses
  const flou = semisCiDepuisLead({
    type_installation: 'commercial', tension_raccordement: 'ne_sait_pas',
    contrat_electricite: 'ne_sait_pas', raccordement: 'inconnu', regime_equipes: 'ne_sait_pas',
  }, COURANT_VIDE)
  assert.equal(flou, null)
  assert.equal(semisCiDepuisLead({ type_installation: 'commercial', tension_raccordement: 'bt',
    tension_source: 'site_defaut_visible' }, COURANT_VIDE), null)
})

test('ADEV100 — ce que la commerciale a déjà rempli n’est JAMAIS écrasé', () => {
  let profil = profilCiVide()
  profil = poserProfilCi(profil, 'tension', 'mt')
  profil = poserProfilCi(profil, 'surfaceUtile', '900')
  profil = poserProfilCi(profil, 'joursOuverts.0', true)
  profil = poserProfilCi(profil, 'kwhMensuels.0', '5000')
  const courant = {
    profil, categorie: 'restaurant', reponses: { chambres: '12' }, tarif: { contrat: 'mt_general' },
  }
  const s = semisCiDepuisLead(LEAD_HOTEL, courant)
  const chemins = s.profil.map(([c]) => c)
  for (const interdit of ['tension', 'surfaceUtile', 'joursOuverts', 'kwhAnnuel', 'saisieConso']) {
    assert.ok(!chemins.includes(interdit), `${interdit} déjà saisi`)
  }
  assert.equal(s.categorie, null, 'catégorie déjà choisie')
  assert.equal(s.reponses, null, 'les réponses du lead sont celles d’une autre catégorie')
  assert.equal(s.tarif, null, 'contrat déjà choisi')
  assert.ok(!s.marques.includes('categorie') && !s.marques.includes('contrat'))
})

test('ADEV100 — un relevé de factures du lead prime : le kWh mensuel n’est pas repris', () => {
  const s = semisCiDepuisLead({ ...LEAD_HOTEL, releve_conso: LEAD_PRO.releve_conso }, COURANT_VIDE)
  assert.ok(!s.profil.some(([c]) => c === 'kwhAnnuel'))
})

test('ADEV100 — type de pose affirmé seulement quand le lead le permet ; option bi-horaire de la force motrice', () => {
  const pose = (extra) => {
    const s = semisCiDepuisLead({ type_installation: 'industriel', ...extra }, COURANT_VIDE)
    return s && Object.fromEntries(s.profil).typePose
  }
  assert.equal(pose({ type_surface: 'ombriere' }), 'ombriere')
  assert.equal(pose({ type_surface: 'terrain' }), 'sol')
  assert.equal(pose({ type_surface: 'toiture', type_toiture: 'bac_acier' }), 'bac_acier')
  assert.equal(pose({ type_surface: 'toiture', type_toiture: 'tuiles' }), 'toiture_inclinee')
  assert.equal(pose({ type_surface: 'toiture', type_toiture: 'terrasse_beton' }), null)
  const fm = semisCiDepuisLead({ type_installation: 'industriel', contrat_electricite: 'bt_force_motrice',
    option_tarifaire_bt: 'bi_horaire' }, COURANT_VIDE)
  assert.deepEqual(fm.tarif, { contrat: 'bt_force_motrice', optionBiHoraire: true })
  assert.equal(fm.categorie, null, 'pas de catégorie commerciale en industriel')
})

test('ADEV100 — le profil semé donne le même corps d’aperçu que celui que le serveur résout du lead', () => {
  const s = semisCiDepuisLead(LEAD_HOTEL, COURANT_VIDE)
  let p = profilCiVide()
  for (const [chemin, valeur] of s.profil) p = poserProfilCi(p, chemin, valeur)
  const corps = corpsCiDepuisProfil(p, { mode: 'commercial', lead: 2207, categorie: s.categorie, reponses: s.reponses })
  assert.equal(corps.consommation.kwh_annuel, 72000)
  assert.equal(corps.rythme.categorie_commerciale, 'hotel')
  assert.deepEqual(corps.rythme.plages, { ouvre: [[8, 18]] })
  assert.equal(corps.phases, 'tri')
})

test('ADEV100 — modifier un champ semé retire son badge (la clé suit le champ d’écran)', () => {
  assert.equal(cleReprisDuChamp('joursOuverts.3'), 'joursOuverts')
  assert.equal(cleReprisDuChamp('plages.ouvre.debut'), 'plages')
  assert.equal(cleReprisDuChamp('kwhMensuels.4'), 'kwhAnnuel')
  assert.equal(cleReprisDuChamp('saisieConso'), 'kwhAnnuel')
  assert.equal(cleReprisDuChamp('surfaceUtile'), 'surfaceUtile')
})
