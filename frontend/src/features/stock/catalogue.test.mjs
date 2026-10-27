// Tests de la taxonomie d'affichage CATÉGORIE → MARQUE → ARTICLES.
// Run with: node --test src/features/stock/
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  groupCatalogue, searchCatalogue, keySpec, sansPrix, MARQUE_GENERIQUE,
  typeOfProduit, familleAttendue, categorieIcone,
  ROLES_CI_PRESTATION, etatPrixCi, produitCiACompleter, raisonCiACompleter,
} from './catalogue.js'
import {
  classifyProduct, isPanel, isBattery, isReseauInverter, isHybridInverter,
} from '../ventes/solar.js'
import { Sun, Zap, Cpu, Droplets, ClipboardList } from 'lucide-react'

const CAT = {
  panneaux: { nom: 'Panneaux photovoltaïques', ordre: 10 },
  reseau: { nom: 'Onduleurs réseau', ordre: 20 },
  hybrides: { nom: 'Onduleurs hybrides', ordre: 30 },
  variateurs: { nom: 'Variateurs', ordre: 90 },
  pompes: { nom: 'Pompes', ordre: 80 },
  services: { nom: 'Services & prestations', ordre: 100 },
}

const FIXTURE = [
  { id: 1, nom: 'Panneau Canadien Solar 710W', marque: 'Canadien Solar', prix_vente: '1272.73', tva: '10.00', categorie: CAT.panneaux },
  { id: 2, nom: 'Panneau Jinko 710W', marque: 'Jinko', prix_vente: '1272.73', tva: '10.00', categorie: CAT.panneaux },
  { id: 3, nom: 'Onduleur réseau Huawei 10kW Triphasé', marque: 'Huawei', prix_vente: '16666.67', tva: '20.00', categorie: CAT.reseau },
  { id: 4, nom: 'Onduleur hybride Deye 5kW Monophasé', marque: 'Deye', prix_vente: '14166.67', tva: '20.00', categorie: CAT.hybrides },
  { id: 5, nom: 'VARIATEUR VEICHI SI23 7.5KW 380V', marque: 'VEICHI', prix_vente: '3333.33', tva: '20.00', pompe_kw: '7.5', tension_v: 380, categorie: CAT.variateurs },
  { id: 6, nom: 'Pompe immergée OSP 30/8 — 10 CV / 7.5 kW (3", 380V)', marque: 'OSP', prix_vente: '0.00', tva: '20.00', pompe_cv: '10', hmt_m: '91', courbe_pompe: { debits_m3h: [0, 12], hmt_m: [91, 85] }, categorie: CAT.pompes },
  { id: 7, nom: 'Installation', marque: '', prix_vente: '4000', tva: '20.00', categorie: CAT.services },
  { id: 8, nom: 'Transport', marque: '', prix_vente: '833.33', tva: '20.00', categorie: CAT.services },
]

test('groupement : catégories dans l\'ordre délibéré, hybrides ≠ réseau', () => {
  const g = groupCatalogue(FIXTURE)
  const noms = g.map(c => c.nom)
  assert.deepEqual(noms, [
    'Panneaux photovoltaïques', 'Onduleurs réseau', 'Onduleurs hybrides',
    'Pompes', 'Variateurs', 'Services & prestations',
  ])
  // marques sous chaque catégorie ; sans-marque → Génériques en dernier
  const services = g.find(c => c.nom === 'Services & prestations')
  assert.equal(services.brands.length, 1)
  assert.equal(services.brands[0].marque, MARQUE_GENERIQUE)
  assert.equal(services.brands[0].items.length, 2)
})

test('recherche transverse : trouve par nom, marque, catégorie et spec', () => {
  assert.equal(searchCatalogue(FIXTURE, 'veichi').length, 1)
  assert.equal(searchCatalogue(FIXTURE, 'hybride').length, 1)
  assert.equal(searchCatalogue(FIXTURE, 'panneaux photo').length, 2) // catégorie
  assert.equal(searchCatalogue(FIXTURE, '710')[0].id, 1)            // nom
  assert.ok(searchCatalogue(FIXTURE, '7.5 kW').some(p => p.id === 5)) // spec
  assert.equal(searchCatalogue(FIXTURE, '').length, FIXTURE.length)
})

// STKCAT15 — accents, jetons ET (ordre indifférent), jeton numérique nu sur
// une spec. Catalogue étendu LOCAL (jamais le FIXTURE partagé, pour ne pas
// perturber le comptage de catégories du test « groupement » ci-dessus).
test('STKCAT15 — recherche insensible aux accents, jetons ET, jeton numérique sur spec', () => {
  const CATALOGUE_ETENDU = [
    ...FIXTURE,
    {
      id: 9, nom: 'Câble solaire 6mm² — rouge (au mètre)', marque: 'Nexans',
      prix_vente: '15.00', tva: '20.00', categorie: { nom: 'Câbles', ordre: 70 },
    },
    {
      id: 10, nom: 'Module PV 550 W', marque: 'Jinko',
      prix_vente: '900.00', tva: '10.00', categorie: CAT.panneaux,
    },
  ]
  // accent-insensible : « cable » (sans accent) trouve « Câble … »
  assert.ok(searchCatalogue(CATALOGUE_ETENDU, 'cable').some(p => p.id === 9))
  // jetons ET, ordre indifférent : « hybride deye » == « deye hybride »
  assert.ok(searchCatalogue(CATALOGUE_ETENDU, 'hybride deye').some(p => p.id === 4))
  assert.ok(searchCatalogue(CATALOGUE_ETENDU, 'deye hybride').some(p => p.id === 4))
  // jeton numérique nu trouve une spec (nom contient 550)
  assert.ok(searchCatalogue(CATALOGUE_ETENDU, '550').some(p => p.id === 10))
  // superset : tout ce que l'ancienne recherche trouvait, la nouvelle le
  // trouve toujours (jamais un champ caché par rapport à avant).
  assert.equal(searchCatalogue(CATALOGUE_ETENDU, 'veichi').length, 1)
  assert.equal(searchCatalogue(CATALOGUE_ETENDU, 'panneaux photo').length, 3) // +Module PV 550W
})

test('spec clé par catégorie : Wc, kW+tension, CV/HMT/courbe', () => {
  assert.equal(keySpec(FIXTURE[0]), '710 Wc')
  assert.equal(keySpec(FIXTURE[4]), '7.5 kW · 380 V')
  assert.ok(keySpec(FIXTURE[5]).includes('10 CV'))
  assert.ok(keySpec(FIXTURE[5]).includes('courbe constructeur'))
  assert.equal(keySpec(FIXTURE[6]), null) // service : pas de spec inventée
})

test('prix vide : signalé, jamais sélectionnable comme produit chiffrable', () => {
  assert.equal(sansPrix(FIXTURE[5]), true)   // OSP à prix vide
  assert.equal(sansPrix(FIXTURE[0]), false)
})

// ── 762 — cohérence des familles : affichage catalogue ↔ classification PDF/
// auto-fill. Le moteur PDF (quote_engine/builder.py) et l'auto-fill (solar.js)
// partagent les MÊMES mots-clés de désignation (réseau/injection, hybride,
// batterie, panneau) — vérifié par ailleurs côté ventes. Ici on garantit que la
// taxonomie catalogue (catégorie réelle + keySpec) classe ces familles de la
// même manière que solar.js, pour qu'un article affiché sous « Panneaux » soit
// bien traité comme un panneau par le PDF, etc.
// Mots-clés canoniques de builder.py (_is_panel/_is_battery/_is_reseau_inverter/
// _is_hybrid_inverter), repris à l'identique par solar.js.
const FAMILLES = [
  {
    cat: 'Panneaux photovoltaïques', nom: 'Panneau Jinko 710W',
    classe: 'panneau', predicat: isPanel,
  },
  {
    cat: 'Onduleurs réseau', nom: 'Onduleur réseau Huawei 10kW Triphasé',
    classe: 'onduleur_reseau', predicat: isReseauInverter,
  },
  {
    cat: 'Onduleurs hybrides', nom: 'Onduleur hybride Deye 5kW Monophasé',
    classe: 'onduleur_hybride', predicat: isHybridInverter,
  },
  {
    cat: 'Batteries', nom: 'Batterie Pylontech 5kWh',
    classe: 'batterie', predicat: isBattery,
  },
]

test('762 — familles catalogue alignées sur la classification solar.js/builder.py', () => {
  for (const f of FAMILLES) {
    // solar.js classe la désignation dans la bonne famille…
    assert.equal(classifyProduct(f.nom), f.classe, `classifyProduct(${f.nom})`)
    // …et le prédicat de désignation (mêmes mots-clés que builder.py) répond oui.
    assert.equal(f.predicat(f.nom), true, `predicat ${f.classe}(${f.nom})`)
    // La taxonomie catalogue produit bien une spec pour ces familles (l'article
    // est reconnu, pas relégué dans « Autres » sans spec).
    const p = { nom: f.nom, categorie: { nom: f.cat, ordre: 10 } }
    assert.notEqual(keySpec(p), null, `keySpec famille ${f.classe}`)
  }
})

test('762 — exclusivité : un onduleur réseau n\'est ni hybride ni batterie', () => {
  const reseau = 'Onduleur réseau Huawei 10kW Triphasé'
  assert.equal(isReseauInverter(reseau), true)
  assert.equal(isHybridInverter(reseau), false)
  assert.equal(isBattery(reseau), false)
  assert.equal(isPanel(reseau), false)
})

test('typeOfProduit : type d\'un produit via categorie_type ou categorie.type_equipement', () => {
  // Avec categorie_type plat
  const withFlat = { categorie_type: 'onduleur_reseau', categorie: { type_equipement: 'onduleur' } }
  assert.equal(typeOfProduit(withFlat), 'onduleur_reseau')

  // Repli sur categorie.type_equipement
  const withNested = { categorie: { type_equipement: 'panneau' } }
  assert.equal(typeOfProduit(withNested), 'panneau')

  // Aucun type
  const noType = { categorie: {} }
  assert.equal(typeOfProduit(noType), null)

  // Produit null/undefined
  assert.equal(typeOfProduit(null), null)
  assert.equal(typeOfProduit(undefined), null)
})

test('familleAttendue : mappe les rôles aux familles de produits', () => {
  // Structure — trois rôles
  assert.equal(familleAttendue('structure'), 'structure')
  assert.equal(familleAttendue('structure_acier'), 'structure')
  assert.equal(familleAttendue('structure_alu'), 'structure')

  // Panneau
  assert.equal(familleAttendue('panneau'), 'panneau')

  // Batterie
  assert.equal(familleAttendue('batterie'), 'batterie')

  // Onduleurs — tous retournent null
  assert.equal(familleAttendue('onduleur_reseau'), null)
  assert.equal(familleAttendue('onduleur_hybride'), null)
  assert.equal(familleAttendue('onduleur_offgrid'), null)

  // Câbles — tous retournent null
  assert.equal(familleAttendue('cable_dc'), null)
  assert.equal(familleAttendue('cable_terre'), null)

  // Rôle inconnu
  assert.equal(familleAttendue('role_inconnu'), null)

  // null/undefined
  assert.equal(familleAttendue(null), null)
  assert.equal(familleAttendue(undefined), null)
})

// STKCAT16 — icônes et keySpec pilotées par typeOfProduit, repli par nom.
test('STKCAT16 — rendu byte-identique sur le catalogue semé (aucun type renseigné)', () => {
  // FIXTURE ne porte ni categorie_type ni categorie.type_equipement : le
  // repli par NOM doit produire EXACTEMENT les mêmes icônes/spécs qu'avant
  // STKCAT16 (valeurs capturées sur l'implémentation pré-changement).
  assert.equal(categorieIcone(FIXTURE[0]), Sun)           // Panneaux photovoltaïques
  assert.equal(categorieIcone(FIXTURE[2]), Zap)           // Onduleurs réseau
  assert.equal(categorieIcone(FIXTURE[3]), Zap)           // Onduleurs hybrides
  assert.equal(categorieIcone(FIXTURE[4]), Cpu)           // Variateurs
  assert.equal(categorieIcone(FIXTURE[5]), Droplets)      // Pompes
  assert.equal(categorieIcone(FIXTURE[6]), ClipboardList) // Services & prestations

  assert.equal(keySpec(FIXTURE[0]), '710 Wc')
  assert.equal(keySpec(FIXTURE[4]), '7.5 kW · 380 V')
  assert.ok(keySpec(FIXTURE[5]).includes('10 CV'))
  assert.ok(keySpec(FIXTURE[5]).includes('courbe constructeur'))
  assert.equal(keySpec(FIXTURE[6]), null)
})

test('STKCAT16 — une catégorie « PV Modules » typée panneau obtient Sun + spec Wc', () => {
  // "PV Modules" ne matche PAS /panneau/i par NOM : seul le type fait passer.
  const p = { nom: 'Module PV 550 W', categorie: { nom: 'PV Modules', ordre: 5, type_equipement: 'panneau' } }
  assert.equal(categorieIcone(p), Sun)
  assert.equal(keySpec(p), '550 Wc')
})

test('STKCAT16 — structure/protection/service : keySpec renvoie explicitement null', () => {
  assert.equal(keySpec({ nom: 'Rail alu 3m', categorie_type: 'structure' }), null)
  assert.equal(keySpec({ nom: 'Disjoncteur différentiel 32A', categorie_type: 'protection' }), null)
  assert.equal(keySpec({ nom: 'Installation', categorie_type: 'service' }), null)
})

// ASTK254 (D-ACI-4=a) — les prestations C&I sont tarifées dans Paramètres ›
// Devis › Prestations C&I (le moteur ne lit que ces forfaits) : la fiche Stock
// ne dit plus « prix à renseigner » et le filtre « C&I à compléter » les
// ignore. Les articles matériels C&I sans prix gardent « prix à renseigner ».
const _ci = (role, extra = {}, etat = {}) => ({
  id: 900, nom: role, prix_vente: '0.00', tva: '20.00', role_ci: role,
  etat_ci: {
    role_ci: role, libelle: role, classement: 'declare', prix_connu: false,
    eligible_ci: true, motif_exclusion: null, ...etat,
  },
  ...extra,
})

test('ASTK254/CCAT3 — les 8 rôles de prestation C&I (liste figée, sans om_ci)', () => {
  assert.deepEqual([...ROLES_CI_PRESTATION], [
    'etudes_ingenierie', 'pose_structure', 'pose_modules', 'raccordement_ac',
    'mise_en_service', 'dossier_raccordement', 'levage_acces',
    'transport_ci',
  ])
})

test('CCAT3 — om_ci sans prix : « a_renseigner » (tarifé sur son article Stock) et à compléter', () => {
  const om = _ci('om_ci')
  assert.equal(etatPrixCi(om), 'a_renseigner')
  assert.equal(produitCiACompleter(om), true)
  assert.equal(raisonCiACompleter(om), 'prix à renseigner')
})

test('CCAT3 — coffret sans prix de vente mais prix connu par barème : « bareme »', () => {
  for (const role of ['coffret_dc', 'coffret_ac']) {
    const coffret = _ci(role, {}, { prix_connu: true })
    assert.equal(etatPrixCi(coffret), 'bareme', role)
    assert.equal(produitCiACompleter(coffret), false, role)
  }
  // Prix de vente saisi : « ok » ; prix inconnu : « a_renseigner ».
  assert.equal(etatPrixCi(_ci('coffret_dc', { prix_vente: '900.00' }, { prix_connu: true })), 'ok')
  assert.equal(etatPrixCi(_ci('coffret_dc')), 'a_renseigner')
  // Une prestation garde « parametres » en premier.
  assert.equal(etatPrixCi(_ci('pose_modules', {}, { prix_connu: true })), 'parametres')
})

test('ASTK254 — prestation C&I sans prix : état « parametres », pas « a_renseigner »', () => {
  for (const role of ROLES_CI_PRESTATION) {
    assert.equal(etatPrixCi(_ci(role)), 'parametres', role)
  }
})

test('ASTK254 — matériel C&I sans prix : « a_renseigner » ; avec prix : « ok »', () => {
  for (const role of ['onduleur_string_tri', 'compteur_injection', 'cable_ac', 'batterie_ci']) {
    assert.equal(etatPrixCi(_ci(role)), 'a_renseigner', role)
    assert.equal(etatPrixCi(_ci(role, { prix_vente: '1500.00' }, { prix_connu: true })), 'ok', role)
  }
  // Article sans rôle C&I (panneau, etc.) : règle historique sansPrix.
  assert.equal(etatPrixCi({ nom: 'Panneau', prix_vente: '0' }), 'a_renseigner')
  assert.equal(etatPrixCi({ nom: 'Panneau', prix_vente: '1272.73' }), 'ok')
})

test('ASTK254 — le filtre « C&I à compléter » exclut les prestations, garde le matériel', () => {
  for (const role of ROLES_CI_PRESTATION) {
    assert.equal(produitCiACompleter(_ci(role)), false, role)
    assert.equal(raisonCiACompleter(_ci(role)), '', role)
  }
  const materiel = _ci('compteur_injection')
  assert.equal(produitCiACompleter(materiel), true)
  assert.equal(raisonCiACompleter(materiel), 'prix à renseigner')
})

test('ASTK254 — une prestation exclue pour un autre motif reste à compléter', () => {
  const exclue = _ci('om_ci', {}, { eligible_ci: false, motif_exclusion: 'fiche incomplète' })
  assert.equal(produitCiACompleter(exclue), true)
  assert.equal(raisonCiACompleter(exclue), 'fiche incomplète')
})

test('ASTK254 — le rôle se lit aussi sur role_ci quand etat_ci manque', () => {
  assert.equal(etatPrixCi({ nom: 'Pose', prix_vente: '0', role_ci: 'pose_modules' }), 'parametres')
})
