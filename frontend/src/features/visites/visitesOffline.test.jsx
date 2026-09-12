/* VTA10 — tests du BRANCHEMENT offline de l'app Visites, PAS du moteur.
   Le moteur (Outbox/BinaryOutbox, idempotence, rejeu, quotas) a déjà ses
   propres tests dans `lib/`/`features/installations/offline/` : on ne les
   redouble pas. Ce qu'on vérifie ici, et seulement cela :
     1. un envoi qui PASSE ne met rien en file ;
     2. une panne RÉSEAU (erreur sans `response`) met l'op dans LA file de la
        plateforme — la file de module `visites` pour les mesures, l'unique
        file binaire pour les photos ;
     3. un refus APPLICATIF (4xx) est RELANCÉ, jamais enterré dans la file.
*/
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../../api/visitesApi', () => ({
  default: {
    patchVisiteMesures: vi.fn(),
    uploadVisitePhoto: vi.fn(),
  },
}))
// compressImage est inopérant hors navigateur (pas de canvas) : on le neutralise
// pour que le test porte sur le BRANCHEMENT, pas sur la recette de compression.
vi.mock('../../ui/file-utils', () => ({ compressImage: vi.fn(async (f) => f) }))

import visitesApi from '../../api/visitesApi'
import { compressImage } from '../../ui/file-utils'
import {
  MODULE_VISITES, VISITE_OPS, enregistrerMesures, envoyerPhotoVisite,
} from './visitesOffline'
import { OFFLINE_MODULES, getModuleOutbox, purgeModuleOutboxes } from '../../lib/offlineOutbox'
import { binaryOutbox, BINARY_OPS } from '../installations/offline/fieldOutbox'

const erreurReseau = () => Object.assign(new Error('Network Error'), { response: undefined })
const erreur400 = () => Object.assign(new Error('Bad Request'), {
  response: { status: 400, data: { erreurs: { largeur_mur_cm: 'Obligatoire.' } } },
})

const fichier = () => ({
  name: 'toit.jpg',
  type: 'image/jpeg',
  arrayBuffer: async () => new ArrayBuffer(8),
})

describe('VTA10 — branchement de l’app Visites sur la primitive offline', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    await purgeModuleOutboxes()
    await binaryOutbox.clear()
  })

  it('déclare le module `visites` dans LA liste de la plateforme (jamais un 2e outbox)', () => {
    expect(OFFLINE_MODULES).toContain(MODULE_VISITES)
  })

  it('mesures — en ligne : appel direct, rien en file', async () => {
    visitesApi.patchVisiteMesures.mockResolvedValue({ data: { id: 7 } })
    const res = await enregistrerMesures(7, 'local_onduleur', { largeur_mur_cm: 120 })
    expect(res.queued).toBe(false)
    expect(visitesApi.patchVisiteMesures).toHaveBeenCalledWith(
      7, 'local_onduleur', { largeur_mur_cm: 120 })
    expect(await getModuleOutbox(MODULE_VISITES).pending()).toHaveLength(0)
  })

  it('mesures — panne réseau : l’op part dans la file de module `visites`', async () => {
    visitesApi.patchVisiteMesures.mockRejectedValue(erreurReseau())
    const res = await enregistrerMesures(7, 'local_onduleur', { largeur_mur_cm: 120 })
    expect(res.queued).toBe(true)
    const ops = await getModuleOutbox(MODULE_VISITES).pending()
    expect(ops).toHaveLength(1)
    expect(ops[0].op_type).toBe(VISITE_OPS.MESURES)
    expect(ops[0].payload).toMatchObject({ visite: 7, categorie: 'local_onduleur' })
    expect(ops[0].target).toBe(7)
  })

  it('mesures — refus applicatif 400 : relancé, jamais mis en file', async () => {
    visitesApi.patchVisiteMesures.mockRejectedValue(erreur400())
    await expect(enregistrerMesures(7, 'local_onduleur', {})).rejects.toBeTruthy()
    expect(await getModuleOutbox(MODULE_VISITES).pending()).toHaveLength(0)
  })

  it('photo — en ligne : compressée puis envoyée, rien en file', async () => {
    visitesApi.uploadVisitePhoto.mockResolvedValue({ data: { id: 7 } })
    const res = await envoyerPhotoVisite(7, { slotCode: 'toiture_vue_generale', fichier: fichier() })
    expect(res.queued).toBe(false)
    expect(compressImage).toHaveBeenCalled()
    expect(await binaryOutbox.count()).toBe(0)
  })

  it('photo — panne réseau : la photo rejoint L’UNIQUE file binaire', async () => {
    visitesApi.uploadVisitePhoto.mockRejectedValue(erreurReseau())
    const res = await envoyerPhotoVisite(7, {
      slotCode: 'toiture_vue_generale', fichier: fichier(), gpsLat: 33.4, gpsLng: -7.6,
    })
    expect(res.queued).toBe(true)
    const ops = await binaryOutbox.pending()
    expect(ops).toHaveLength(1)
    expect(ops[0].op_type).toBe(BINARY_OPS.PHOTO_VISITE)
    expect(ops[0].meta).toMatchObject({ visite: 7, slot_code: 'toiture_vue_generale' })
  })

  it('photo — refus applicatif : relancé, jamais mis en file', async () => {
    visitesApi.uploadVisitePhoto.mockRejectedValue(erreur400())
    await expect(envoyerPhotoVisite(7, {
      slotCode: 'toiture_vue_generale', fichier: fichier(),
    })).rejects.toBeTruthy()
    expect(await binaryOutbox.count()).toBe(0)
  })
})
