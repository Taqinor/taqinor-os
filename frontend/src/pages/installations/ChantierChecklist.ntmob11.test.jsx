// NTMOB11 — capture multi-photos horodatées géotaguées par étape de
// checklist. CameraCapture lui-même est déjà couvert (mode `multiple` +
// géoloc) par CameraCapture.test.jsx ; ce test couvre UNIQUEMENT le câblage
// propre à ChantierChecklist : ouverture du panneau par étape, upload
// générique (galerie du chantier) + pose des métadonnées, mise à jour locale
// du compteur de photos.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

const { installationsApiMock, recordsApiMock } = vi.hoisted(() => ({
  installationsApiMock: {
    getChecklist: vi.fn(),
    cocherChecklist: vi.fn(),
    ajouterChecklistPhotoMeta: vi.fn(),
  },
  recordsApiMock: { uploadAttachment: vi.fn() },
}))
vi.mock('../../api/installationsApi', () => ({ default: installationsApiMock }))
vi.mock('../../api/recordsApi', () => ({ default: recordsApiMock }))
// Compression réelle dépend du décodage d'image (Image/canvas) — hors
// périmètre de ce test (déjà passthrough-safe en environnement sans decode,
// cf. ui/file-utils.js), on la neutralise en identité pour rester focalisé
// sur le câblage upload → métadonnées.
vi.mock('../../ui/file-utils', () => ({ compressImage: vi.fn((f) => Promise.resolve(f)) }))
// N91 — le repli hors-ligne n'est pas le sujet ici (couvert ailleurs) :
// exécute toujours l'appel réseau directement.
vi.mock('../../features/installations/offline/fieldOutbox', () => ({
  withOfflineFallback: (fn) => fn().then((data) => ({ queued: false, data: data.data })),
  FIELD_OPS: { COCHER_CHECKLIST: 'cocher_checklist' },
}))
// CameraCapture réel est testé séparément (CameraCapture.test.jsx) — stub
// minimal ici qui expose un bouton déclenchant onCapture(fakeFile, fakeGeo).
vi.mock('../../features/pwa/CameraCapture', () => ({
  default: ({ onCapture, onClose }) => (
    <div>
      <button type="button" onClick={() => onCapture(
        new File(['x'], 'photo.jpg', { type: 'image/jpeg' }),
        { latitude: 33.5, longitude: -7.6, precision_m: 10 },
      )}>
        Simuler capture
      </button>
      <button type="button" onClick={onClose}>Fermer capture</button>
    </div>
  ),
}))

import ChantierChecklist from './ChantierChecklist'

const ITEMS = [
  { id: 1, cle: 'pose', libelle: 'Pose des panneaux', ordre: 1,
    capture_serie: false, photo_obligatoire: false, fait: false,
    fait_par_nom: null, fait_le: null, photos_count: 0 },
]

beforeEach(() => {
  vi.clearAllMocks()
  installationsApiMock.getChecklist.mockResolvedValue({
    data: { items: ITEMS, completion: 0 },
  })
  recordsApiMock.uploadAttachment.mockResolvedValue({ data: { id: 77 } })
  installationsApiMock.ajouterChecklistPhotoMeta.mockResolvedValue({
    data: { id: 1, attachment: 77, checklist_item: 1 },
  })
})
afterEach(() => cleanup())

describe('ChantierChecklist — NTMOB11 (câblage capture photo par étape)', () => {
  it('capturer une photo l’envoie via recordsApi puis pose les métadonnées (étape + géoloc)', async () => {
    const user = userEvent.setup()
    render(<ChantierChecklist installationId={42} produits={[]} />)

    await screen.findByText('Pose des panneaux')
    await user.click(screen.getByLabelText('Photos — Pose des panneaux'))
    await user.click(await screen.findByRole('button', { name: 'Simuler capture' }))

    await waitFor(() => expect(recordsApiMock.uploadAttachment).toHaveBeenCalledTimes(1))
    expect(recordsApiMock.uploadAttachment).toHaveBeenCalledWith(
      'installations.installation', 42, expect.any(File), 'pendant')

    await waitFor(() =>
      expect(installationsApiMock.ajouterChecklistPhotoMeta).toHaveBeenCalledTimes(1))
    expect(installationsApiMock.ajouterChecklistPhotoMeta).toHaveBeenCalledWith(42, {
      attachment: 77, cle: 'pose',
      latitude: 33.5, longitude: -7.6, precision_m: 10,
    })

    // Compteur local mis à jour sans re-fetch.
    expect(await screen.findByLabelText('Photos — Pose des panneaux'))
      .toHaveTextContent('1')
  })

  it('un échec réseau affiche une erreur sans casser la session de capture', async () => {
    recordsApiMock.uploadAttachment.mockRejectedValueOnce(new Error('network'))
    const user = userEvent.setup()
    render(<ChantierChecklist installationId={42} produits={[]} />)

    await screen.findByText('Pose des panneaux')
    await user.click(screen.getByLabelText('Photos — Pose des panneaux'))
    await user.click(await screen.findByRole('button', { name: 'Simuler capture' }))

    await waitFor(() => expect(recordsApiMock.uploadAttachment).toHaveBeenCalledTimes(1))
    expect(installationsApiMock.ajouterChecklistPhotoMeta).not.toHaveBeenCalled()
    // Le panneau de capture reste ouvert (pas de fermeture forcée sur échec).
    expect(screen.getByRole('button', { name: 'Simuler capture' })).toBeInTheDocument()
  })

  it('le panneau se ferme et n’affiche qu’une étape à la fois', async () => {
    const user = userEvent.setup()
    render(<ChantierChecklist installationId={42} produits={[]} />)
    await screen.findByText('Pose des panneaux')

    await user.click(screen.getByLabelText('Photos — Pose des panneaux'))
    expect(screen.getByRole('button', { name: 'Simuler capture' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Fermer capture' }))
    expect(screen.queryByRole('button', { name: 'Simuler capture' })).not.toBeInTheDocument()
  })
})
