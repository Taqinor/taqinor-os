// SPL40 — HARNAIS DU GOLDEN DU GÉNÉRATEUR (capture seule).
//
// Monte l'écran RÉEL (`DevisGenerator.jsx`) sur des API mockées et fige ce
// qu'il rend (DOM) et ce qu'il enregistre (appels API), pour que chaque
// déplacement du groupe SPL (SPL43-SPL55) prouve qu'il laisse l'écran
// identique. Aucun `vi.mock` ici : ils restent dans chaque fichier de test
// (hissés par vitest) ; ce module ne porte que les fixtures, le magasin
// Redux, la normalisation et le sérialiseur des appels.
//
// `normalise()` ne réécrit QUE les jetons `useId` de React (`:r0:`, `«r0»`, `_r_0_` en React 19) :
// tout ce qui irait plus loin masquerait une vraie dérive.
import { configureStore } from '@reduxjs/toolkit'

import authReducer from '../../features/auth/store/authSlice'
import ventesReducer from '../../features/ventes/store/ventesSlice'
import { estimerMois } from '../../features/ventes/solar'

//: La date figée de toutes les captures (Date.now / new Date de l'écran).
export const DATE_FIGEE = new Date('2026-10-08T09:00:00Z')

//: Les API dont les appels sont figés après « Enregistrer ».
export const API_ENREGISTREMENT = [
  'replaceLignesDevis', 'createDevisAtomic', 'patchEtudeParams', 'poserOverrides', 'regenererOverride',
]

export function makeStore(role = 'normal') {
  return configureStore({
    reducer: { auth: authReducer, ventes: ventesReducer },
    preloadedState: {
      auth: {
        user: { id: 1 }, role,
        role_nom: role === 'admin' ? 'Directeur' : 'Commercial',
        permissions: [], isAuthenticated: true, loading: false,
      },
    },
  })
}

// ── Catalogue (les quatre marchés) ──────────────────────────────────────────
const P = (id, nom, prix_vente, tva, extra = {}) => ({
  id, nom, prix_vente, tva, is_archived: false, prix_achat: Math.round(prix_vente * 0.7), ...extra,
})
export const CATALOGUE = [
  P(101, 'Panneau Canadien Solar 715W', 1200, 10, { puissance_wc: 715 }),
  P(102, 'Onduleur réseau 5kW Monophasé', 9000, 20),
  P(103, 'Onduleur hybride Deye 6kW', 14000, 20),
  P(104, 'Batterie lithium 5kWh', 16000, 20),
  P(105, 'Structures acier', 375, 20),
  P(106, 'Smart Meter', 1200, 20),
  P(107, 'Onduleur réseau 50kW Triphasé', 52000, 20),
  P(201, 'Pompe immergée OSP 30/8 — 10 CV / 7.5 kW (3", 380V)', 12500, 20, {
    pompe_cv: '10', pompe_kw: '7.5', tension_v: 380,
    courbe_pompe: { debits_m3h: [0, 12, 24, 30, 36, 39], hmt_m: [91, 85, 70, 60, 43, 34] },
  }),
  P(202, 'VARIATEUR VEICHI SI23 7.5KW 380V', 3333.33, 20, { pompe_kw: '7.5', tension_v: 380 }),
  P(203, 'AFFICHEUR VARIATEUR SI22', 350, 20),
]

export const LEAD = {
  id: 77, nom: 'Khalid', prenom: 'Golden', societe: '', telephone: '0600000000',
  facture_hiver: '3000', ete_differente: false, facture_ete: null, ville: 'Mohammedia',
}
export const CLIENT = { id: 9, nom: 'Client Golden', email: 'golden@example.ma' }

const ligne = (id, produit, quantite, pu, taux, extra = {}) => ({
  id, produit: produit.id, designation: produit.nom, quantite: String(quantite),
  prix_unitaire: pu.toFixed(2), taux_tva: taux.toFixed(2), remise: '0.00', ordre: id - 1,
  type_ligne: 'produit', optionnelle: false, variante: '', ...extra,
})
const [PANNEAU, OND_RESEAU, OND_HYBRIDE, BATTERIE, STRUCTURE, SMART, OND_50, POMPE, VARIATEUR, AFFICHEUR] = CATALOGUE

const devisBase = (id, mode, etude, lignes, extra = {}) => ({
  id, reference: `DEV-202610-0${id}`, statut: 'brouillon', modifiable: true,
  raison_non_modifiable: '', revision_possible: false, is_active: true,
  lead: null, client: CLIENT.id, mode_installation: mode, taux_tva: '20.00',
  remise_globale: '0.00', date_validite: '2026-11-07', note: null, prix_cible_kwc: null,
  echeancier: [], etude_params: etude, lignes, ...extra,
})

//: (c) un devis ENVOYÉ résidentiel « Les deux » recommandé « Sans batterie ».
export const DEVIS_ENVOYE_LES_DEUX = devisBase(31, 'residentiel', {
  scenario: 'Les deux', recommended_option: 'Sans batterie',
  // Les factures du lead (3 000 MAD hiver = été) : aucune alerte d'écart.
  factures_mensuelles_reelles: estimerMois(3000, 3000),
}, [
  ligne(1, PANNEAU, 8, 1200, 10),
  ligne(2, OND_RESEAU, 1, 9000, 20, { variante: 'sans' }),
  ligne(3, OND_HYBRIDE, 1, 14000, 20, { variante: 'avec' }),
  ligne(4, BATTERIE, 1, 16000, 20, { variante: 'avec' }),
  ligne(5, STRUCTURE, 8, 375, 20),
], { statut: 'envoye', lead: LEAD.id, date_envoi: '2026-09-28T10:00:00Z' })

//: (d) industriel MT avec part diurne.
export const DEVIS_INDUSTRIEL_MT = devisBase(32, 'industriel', {
  scenario: 'Sans batterie', part_diurne_pct: 70,
  mode: 'industriel',
  site: { ville: 'Kénitra', lat: null, lon: null },
  tension: 'mt', phases: 'tri', puissance_souscrite_kva: 250,
  consommation: {
    kwh_mensuels: [9000, 8800, 9100, 9500, 9900, 10400, 11000, 11200, 10100, 9600, 9200, 9000],
    kwh_annuel: null, factures_mad: [], registres_mt: null,
  },
  rythme: {
    jours_ouverts: [true, true, true, true, true, true, false],
    plages: { ouvre: [[7, 19]] }, equipes: '1x8', debut_equipe_h: 7, fermetures: [],
    ramadan: null, talon: { kw: 12, part_pct: null, inconnu: false },
    categorie_commerciale: null, reponses_categorie: null,
  },
  courbe_mesuree: null,
  toit: {
    type_pose: 'bac_acier', surface_utile_m2: 1200, surface_type: 'declaree', pente_deg: null,
    azimut_deg: null, couverture: 'tôle', charge_admissible_kg_m2: null, charge_admissible_source: null,
  },
  contraintes: {
    revente_choisie: false, nb_points_raccordement: null, longueur_dc_m: null,
    longueur_ac_m: null, besoin_cellule_mt: null,
  },
  options: { batterie_souhaitee: null, om: null },
  taille_explicite_kwc: null,
}, [
  ligne(1, PANNEAU, 140, 1200, 10),
  ligne(2, OND_50, 2, 52000, 20),
  ligne(3, STRUCTURE, 140, 375, 20),
])

//: (e) commercial hôtel.
export const DEVIS_COMMERCIAL_HOTEL = devisBase(33, 'commercial', {
  scenario: 'Sans batterie', categorie_commerciale: 'hotel',
  mode: 'commercial',
  site: { ville: 'Marrakech', lat: null, lon: null },
  tension: 'bt', phases: 'tri', puissance_souscrite_kva: 60,
  consommation: { kwh_mensuels: null, kwh_annuel: 96000, factures_mad: [], registres_mt: null },
  rythme: {
    jours_ouverts: [true, true, true, true, true, true, true],
    plages: null, equipes: null, debut_equipe_h: null, fermetures: [], ramadan: null,
    talon: null, categorie_commerciale: 'hotel', reponses_categorie: null,
  },
  courbe_mesuree: null,
  toit: {
    type_pose: null, surface_utile_m2: null, surface_type: null, pente_deg: null,
    azimut_deg: null, couverture: null, charge_admissible_kg_m2: null, charge_admissible_source: null,
  },
  contraintes: {
    revente_choisie: false, nb_points_raccordement: null, longueur_dc_m: null,
    longueur_ac_m: null, besoin_cellule_mt: null,
  },
  options: { batterie_souhaitee: null, om: null },
  taille_explicite_kwc: null,
}, [
  ligne(1, PANNEAU, 40, 1200, 10),
  ligne(2, OND_50, 1, 52000, 20),
])

//: (f) agricole avec pompe à courbe.
export const DEVIS_AGRICOLE_POMPE = devisBase(34, 'agricole', {
  scenario: 'Sans batterie',
}, [
  ligne(1, PANNEAU, 16, 1200, 10),
  ligne(2, POMPE, 1, 12500, 20),
  ligne(3, VARIATEUR, 1, 3333.33, 20),
  ligne(4, AFFICHEUR, 1, 350, 20),
])

//: (g) multi-villas.
export const DEVIS_MULTI_VILLAS = devisBase(35, 'residentiel', {
  scenario: 'Sans batterie',
}, [
  ligne(1, SMART, 1, 1200, 20, { groupe_index: 0, groupe_label: 'Équipement commun' }),
  ligne(2, PANNEAU, 8, 1200, 10, { groupe_index: 1, groupe_label: 'Villa A' }),
  ligne(3, OND_RESEAU, 1, 9000, 20, { groupe_index: 1, groupe_label: 'Villa A' }),
  ligne(4, PANNEAU, 10, 1200, 10, { groupe_index: 2, groupe_label: 'Villa B' }),
  ligne(5, OND_RESEAU, 1, 9000, 20, { groupe_index: 2, groupe_label: 'Villa B' }),
])

//: (h) résidentiel rouvert par un administrateur, registre non vide.
export const DEVIS_REGISTRE = devisBase(36, 'residentiel', {
  scenario: 'Sans batterie',
}, [
  ligne(1, PANNEAU, 8, 1200, 10),
  ligne(2, OND_RESEAU, 1, 9000, 20),
])
export const REGISTRE_NON_VIDE = {
  overrides: { scenario: 'Sans batterie' },
  effectif: {
    scenario: { auto: 'Les deux', manuel: 'Sans batterie', effectif: 'Sans batterie', source: 'manuel' },
  },
  lignes: {},
}

//: (i) résidentiel rouvert, aperçu d'étude horaire servi par le serveur.
export const DEVIS_ETUDE_HORAIRE = devisBase(37, 'residentiel', {
  scenario: 'Sans batterie',
}, [
  ligne(1, PANNEAU, 8, 1200, 10),
  ligne(2, OND_RESEAU, 1, 9000, 20),
])

// ── Normalisation et sérialisation ──────────────────────────────────────────
/** Le HTML rendu, jetons `useId` de React remplacés par un ordinal stable. */
export function normalise(html) {
  const vus = new Map()
  return String(html).replace(/(?::r[0-9a-z]+:|«r[0-9a-z]+»|_r_[0-9a-z]+_)/g, (jeton) => {
    if (!vus.has(jeton)) vus.set(jeton, `:id${vus.size}:`)
    return vus.get(jeton)
  })
}

/** Le JSON des `mock.calls` des API d'enregistrement, ordre fixe. */
export function serialiseAppels(api, noms = API_ENREGISTREMENT) {
  const out = {}
  for (const nom of noms) out[nom] = api[nom]?.mock?.calls ?? []
  return `${sansCr(JSON.stringify(out, null, 2)).replace(/\\r\\n/g, '\\n')}\n`
}

// `\r\n` → `\n` : une source extraite en CRLF (Windows, autocrlf) porte des
// CR dans ses `className` multilignes, absents sur la CI (LF) — jamais figés.
const sansCr = (texte) => String(texte).replace(/\r\n/g, '\n')

/** Le golden d'un DOM : useId normalisés, une balise par ligne (lisible en diff). */
export function formaterGolden(html) {
  return `${sansCr(normalise(html)).replace(/></g, '>\n<')}\n`
}

/** Attend que le DOM ne bouge plus pendant 1,5 s (> le plus long debounce de
 *  l’écran : brouillon 800 ms, aperçus serveur 500 ms), promesses résolues. */
export async function attendreStable(container, act, { pas = 100, stables = 15, max = 15000 } = {}) {
  let precedent = null
  let egal = 0
  // `Date` est figée : le temps écoulé se mesure au nombre de pas.
  for (let i = 0; i * pas < max; i += 1) {
    await act(async () => { await new Promise((r) => setTimeout(r, pas)) })
    const html = container.innerHTML
    if (html === precedent) {
      egal += 1
      if (egal >= stables) return html
    } else {
      egal = 0
      precedent = html
    }
  }
  return container.innerHTML
}
