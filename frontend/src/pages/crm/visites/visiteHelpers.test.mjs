// VT10 — tests des helpers PURS de la visite technique. Les objets utilisés
// ici copient EXACTEMENT la forme du contrat committé
// `apps/crm/contract_samples/visite_terrain.json` (PACT10, garde
// check_api_shapes.py) : mêmes clés, mêmes natures.
//   node --test src/pages/crm/visites/visiteHelpers.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  trierCategories, progressionPhotos, manquantsMesures, manquantsPhotos,
  whatsappUrl, mapsUrl,
} from './visiteHelpers.js'

const CHECKLIST = [
  {
    categorie: 'general', libelle: 'Général',
    slots: [{ code: 'general_facade', libelle: 'Façade', guide: '', requis: true, min_photos: 1, etat: 'manquant', photos: [] }],
  },
  {
    categorie: 'toiture', libelle: 'Toiture',
    slots: [
      { code: 'toiture_vue_generale', libelle: 'Vue générale', guide: '', requis: true, min_photos: 2, etat: 'ok', photos: [{ id: 1 }] },
      {
        code: 'toiture_obstacles', libelle: 'Obstacles', guide: '', requis: true, min_photos: 1, etat: 'a_refaire',
        photos: [{ id: 2, a_refaire: true, motif_refaire: 'Photo floue — reprendre.' }],
      },
    ],
  },
  {
    categorie: 'cheminement', libelle: 'Cheminement',
    slots: [{ code: 'cheminement_parcours', libelle: 'Parcours', guide: '', requis: false, min_photos: 1, etat: 'manquant', photos: [] }],
  },
]

const COMPLETUDE = {
  complet: false,
  manquants: [
    { type: 'photo', categorie: 'tableau', code: 'tableau_ouvert', libelle: 'Tableau ouvert' },
    { type: 'photo_a_refaire', categorie: 'toiture', code: 'toiture_obstacles', libelle: 'Obstacles et ombrages' },
    { type: 'mesure', categorie: 'local_onduleur', code: 'largeur_mur_cm', libelle: 'Largeur du mur libre (cm)' },
  ],
}

test('trierCategories — remet toiture -> tableau -> local_onduleur -> cheminement -> general dans l’ordre du wizard', () => {
  const ordre = trierCategories(CHECKLIST).map((c) => c.categorie)
  assert.deepEqual(ordre, ['toiture', 'cheminement', 'general'])
})

test('trierCategories — garde une catégorie inconnue du serveur À LA FIN plutôt que de la perdre', () => {
  const avecInconnue = [...CHECKLIST, { categorie: 'exotique', libelle: 'Exotique', slots: [] }]
  const ordre = trierCategories(avecInconnue).map((c) => c.categorie)
  assert.equal(ordre[ordre.length - 1], 'exotique')
})

test('trierCategories — rend un tableau vide sans planter sur une entrée absente/invalide', () => {
  assert.deepEqual(trierCategories(null), [])
  assert.deepEqual(trierCategories(undefined), [])
})

test('progressionPhotos — compte les slots requis en état ok sur le total des slots requis (jamais les optionnels)', () => {
  // requis : general_facade (manquant), toiture_vue_generale (ok), toiture_obstacles (a_refaire) = 3
  // cheminement_parcours est optionnel -> exclu du total
  assert.deepEqual(progressionPhotos(CHECKLIST), { done: 1, total: 3 })
})

test('manquantsMesures — ne garde que type=mesure, lecture directe (jamais recalculé)', () => {
  assert.deepEqual(manquantsMesures(COMPLETUDE), [
    { type: 'mesure', categorie: 'local_onduleur', code: 'largeur_mur_cm', libelle: 'Largeur du mur libre (cm)' },
  ])
})

test('manquantsPhotos — garde photo ET photo_a_refaire', () => {
  assert.deepEqual(manquantsPhotos(COMPLETUDE).map((m) => m.type), ['photo', 'photo_a_refaire'])
})

test('manquants* — rendent un tableau vide sans completude', () => {
  assert.deepEqual(manquantsMesures(null), [])
  assert.deepEqual(manquantsPhotos(undefined), [])
})

test('whatsappUrl — construit un lien wa.me depuis un numéro E164', () => {
  assert.equal(whatsappUrl('+212600000000'), 'https://wa.me/212600000000')
})

test('whatsappUrl — renvoie null sans numéro exploitable', () => {
  assert.equal(whatsappUrl(''), null)
  assert.equal(whatsappUrl(null), null)
})

test('mapsUrl — construit un lien Maps depuis lat/lng', () => {
  assert.equal(mapsUrl(33.4589, -7.6528), 'https://www.google.com/maps/search/?api=1&query=33.4589,-7.6528')
})

test('mapsUrl — renvoie null sans coordonnées', () => {
  assert.equal(mapsUrl(null, null), null)
})
