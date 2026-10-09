// ACHT71 — l'op hors-ligne `chantier.cocher_checklist` porte la série saisie
// (forme du contrat ACHT40) ; une erreur de chargement n'est pas une liste
// vide. Le test IMPORTE le contrat partagé et relit l'op dans la VRAIE file
// `fieldOutbox` (aucun mock de la file).
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { documentContrat } from '../../test/fixtures/contractSamples'

const { installationsApiMock } = vi.hoisted(() => ({
  installationsApiMock: { getChecklist: vi.fn(), cocherChecklist: vi.fn() },
}))
vi.mock('../../api/installationsApi', () => ({ default: installationsApiMock }))
vi.mock('../../api/recordsApi', () => ({ default: { uploadAttachment: vi.fn() } }))
vi.mock('../preferences/prefs', () => ({
  compressPhotoForUpload: vi.fn((f) => Promise.resolve(f)),
}))
vi.mock('../../features/pwa/CameraCapture', () => ({ default: () => null }))
vi.mock('../../components/ProduitPicker', () => ({
  default: ({ onChange }) => (
    <button type="button" onClick={() => onChange(87)}>Choisir le produit</button>
  ),
}))
const toasts = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }))
vi.mock('../../ui', async (importActual) => {
  const actual = await importActual()
  return { ...actual, toast: toasts }
})

import ChantierChecklist from './ChantierChecklist'
import { fieldOutbox } from '../../features/installations/offline/fieldOutbox'

const CONTRAT = documentContrat('installations', 'field_sync_cocher_checklist')
const [OP_SERIE, OP_SANS_SERIE] = CONTRAT.requete.ops

const item = (cle, libelle, capture_serie) => ({
  id: 1, cle, libelle, ordre: 1, capture_serie, photo_obligatoire: false,
  fait: false, fait_par_nom: null, fait_le: null, photos_count: 0,
})

const rendre = () => render(
  <MemoryRouter><ChantierChecklist installationId={88} produits={[]} /></MemoryRouter>,
)

beforeEach(async () => {
  vi.clearAllMocks()
  await fieldOutbox.clear()
  // Coupure réseau : pas de `response` sur l'erreur.
  installationsApiMock.cocherChecklist.mockRejectedValue(new Error('Network Error'))
})
afterEach(() => cleanup())

describe('ChantierChecklist — ACHT71', () => {
  it('hors-ligne, l’op filée porte la série saisie (forme du contrat)', async () => {
    installationsApiMock.getChecklist.mockResolvedValue({
      data: { items: [item('pose_onduleur', 'Pose onduleur', true)], completion: 0 },
    })
    const user = userEvent.setup()
    rendre()
    await screen.findByText('Pose onduleur')
    await user.click(screen.getByRole('button', { name: 'Choisir le produit' }))
    await user.type(screen.getByPlaceholderText(/N° de série/),
      OP_SERIE.payload.equipements[0].numero_serie)
    await user.click(screen.getByRole('checkbox'))

    await waitFor(async () => expect(await fieldOutbox.pending()).toHaveLength(1))
    const [op] = await fieldOutbox.pending()
    expect(op.op_type).toBe(OP_SERIE.op_type)
    expect(op.payload).toEqual(OP_SERIE.payload)
    expect(toasts.success).toHaveBeenCalledWith(
      'Hors ligne — coché, série enregistrée à la synchro.')
  })

  it('hors-ligne sans série : equipements vide (forme du contrat)', async () => {
    installationsApi_item('pose_panneaux', 'Pose panneaux')
    const user = userEvent.setup()
    rendre()
    await screen.findByText('Pose panneaux')
    await user.click(screen.getByRole('checkbox'))
    await waitFor(async () => expect(await fieldOutbox.pending()).toHaveLength(1))
    const [op] = await fieldOutbox.pending()
    expect(op.payload).toEqual(OP_SANS_SERIE.payload)
  })

  it('un échec de chargement n’affiche pas « Aucune étape modèle »', async () => {
    installationsApiMock.getChecklist.mockRejectedValueOnce(new Error('boom'))
    rendre()
    expect(await screen.findByText(/Checklist indisponible/)).toBeInTheDocument()
    expect(screen.queryByText(/Aucune étape modèle/)).toBeNull()
    expect(screen.getByRole('button', { name: 'réessayer' })).toBeInTheDocument()
  })
})

function installationsApi_item(cle, libelle) {
  installationsApiMock.getChecklist.mockResolvedValue({
    data: { items: [item(cle, libelle, false)], completion: 0 },
  })
}
