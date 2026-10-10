// AGNR7 — l'aller-retour d'écran C&I ne renvoie que les feuilles que l'écran
// ÉDITE : ouvrir puis enregistrer sans toucher un devis C&I créé par le
// SERVEUR (devis auto, relevé de visite, API) laisse `site`, `toit`,
// `contraintes`, `options`, `rythme` identiques, feuille à feuille.
import test from 'node:test'
import assert from 'node:assert/strict'

import { devisVersEtat, etatVersEcritures } from './etatDevis.js'
import { poserProfilCi } from './profilCi.js'

// Étude telle que le PRODUCTEUR serveur l'écrit (`domain/etude_ci.py`) :
// feuilles posées par le devis auto / un relevé de visite, que l'écran
// n'expose pas.
const stockeServeur = (mode) => ({
  mode,
  site: { ville: 'Kénitra', lat: 34.26, lon: -6.58 },
  tension: 'mt', phases: 'tri', puissance_souscrite_kva: 250,
  consommation: {
    kwh_mensuels: [9000, 8800, 9100, 9500, 9900, 10400, 11000, 11200, 10100, 9600, 9200, 9000],
    kwh_annuel: null, factures_mad: [], registres_mt: null,
  },
  rythme: {
    jours_ouverts: [true, true, true, true, true, true, false],
    plages: { ouvre: [[7, 12], [13, 18]], samedi: [[8, 12]] },
    equipes: '1x8', debut_equipe_h: 7,
    fermetures: [{ du: '2026-08-01', au: '2026-08-15', motif: 'congés' }],
    ramadan: { actif: true, plages: [[9, 15]] },
    talon: { kw: 12, part_pct: 18, inconnu: false },
    categorie_commerciale: null, reponses_categorie: null,
  },
  courbe_mesuree: null,
  toit: {
    type_pose: 'bac_acier', surface_utile_m2: 1200, surface_type: 'mesuree',
    pente_deg: 15, azimut_deg: 180, couverture: 'tôle',
    charge_admissible_kg_m2: 25, charge_admissible_source: 'mesure_visite',
  },
  contraintes: {
    revente_choisie: false, nb_points_raccordement: 2, longueur_dc_m: 60,
    longueur_ac_m: 40, besoin_cellule_mt: true,
  },
  options: { batterie_souhaitee: false, om: true },
  taille_explicite_kwc: null,
})

const devis = (mode) => ({
  id: 42, reference: 'DEV-202610-042', statut: 'envoye', lead: 77, client: 9,
  mode_installation: mode, taux_tva: '20.00', remise_globale: '0.00',
  date_validite: '2026-10-30', note: null, prix_cible_kwc: null, echeancier: [],
  etude_params: stockeServeur(mode),
  lignes: [{
    id: 1, produit: 3, designation: 'Panneau', quantite: '100', prix_unitaire: '1000.00',
    remise: '0.00', taux_tva: '20.00', optionnelle: false, variante: '', type_ligne: 'produit',
  }],
})

// Le contexte EXACT que l'écran transmet (`DevisGenerator.jsx`, ctxProfilCi) :
// `villeCalculLead` vide ⇒ ville vide.
const ctxEcran = (mode) => ({ mode, lead: 77, devis: 42, ville: null, categorie: null, reponses: null })

const CLES = ['site', 'toit', 'contraintes', 'options', 'rythme']

const comparerFeuilles = (obtenu, attendu, chemin) => {
  if (attendu && typeof attendu === 'object' && !Array.isArray(attendu)) {
    for (const [k, v] of Object.entries(attendu)) comparerFeuilles(obtenu?.[k], v, `${chemin}.${k}`)
    return
  }
  assert.deepEqual(obtenu, attendu, chemin)
}

for (const mode of ['industriel', 'commercial']) {
  test(`AGNR7 — ${mode} : rouvrir → enregistrer sans toucher garde chaque feuille stockée`, () => {
    const d = devis(mode)
    const etat = devisVersEtat(d)
    const { etude } = etatVersEcritures({ ...etat, ctxCi: ctxEcran(mode) })
    for (const cle of CLES) comparerFeuilles(etude?.[cle], d.etude_params[cle], cle)
  })

  test(`AGNR7 — ${mode} : une feuille éditée part avec sa nouvelle valeur, les autres intactes`, () => {
    const d = devis(mode)
    const etat = devisVersEtat(d)
    const profilCi = poserProfilCi(etat.profilCi, 'surfaceUtile', '900')
    const { etude } = etatVersEcritures({ ...etat, profilCi, ctxCi: ctxEcran(mode) })
    assert.equal(etude.toit.surface_utile_m2, 900)
    assert.equal(etude.toit.surface_type, 'declaree', 'une surface retapée est déclarée')
    assert.equal(etude.toit.pente_deg, 15)
    assert.equal(etude.toit.azimut_deg, 180)
    assert.equal(etude.toit.charge_admissible_kg_m2, 25)
    comparerFeuilles(etude.contraintes, d.etude_params.contraintes, 'contraintes')
    comparerFeuilles(etude.site, d.etude_params.site, 'site')
  })
}

test('AGNR7 — la ville du lead, quand elle existe, remplace la ville stockée', () => {
  const d = devis('industriel')
  const etat = devisVersEtat(d)
  const { etude } = etatVersEcritures({ ...etat, ctxCi: { ...ctxEcran('industriel'), ville: 'Rabat' } })
  assert.equal(etude.site.ville, 'Rabat')
  assert.equal(etude.site.lat, 34.26)
})
