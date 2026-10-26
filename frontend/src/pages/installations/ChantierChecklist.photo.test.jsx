// Revue chantier 26/10/2026 — la checklist chantier ne cache plus les refus
// du serveur (409 « Photo requise ») et annonce l'étape à photo obligatoire
// avant même le clic (case désactivée, « Photo requise »).
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

const { installationsApiMock, toasts } = vi.hoisted(() => ({
  installationsApiMock: { getChecklist: vi.fn(), cocherChecklist: vi.fn() },
  toasts: { success: vi.fn(), error: vi.fn() },
}))
vi.mock('../../api/installationsApi', () => ({ default: installationsApiMock }))
vi.mock('../../api/recordsApi', () => ({ default: { uploadAttachment: vi.fn() } }))
vi.mock('../preferences/prefs', () => ({
  compressPhotoForUpload: vi.fn((f) => Promise.resolve(f)),
}))
vi.mock('../../features/installations/offline/fieldOutbox', () => ({
  // Forme réelle : une erreur applicative (avec `response`) est relancée.
  withOfflineFallback: (fn) => fn().then((data) => ({ queued: false, data })),
  FIELD_OPS: { COCHER_CHECKLIST: 'chantier.cocher_checklist' },
}))
vi.mock('../../features/pwa/CameraCapture', () => ({ default: () => null }))
vi.mock('../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { ...actual.toast, success: toasts.success, error: toasts.error } }
})

import ChantierChecklist from './ChantierChecklist'

const item = (over) => ({
  id: 1, cle: 'pose', libelle: 'Pose des panneaux', ordre: 1,
  capture_serie: false, photo_obligatoire: false, fait: false,
  fait_par_nom: null, fait_le: null, photos_count: 0, ...over,
})

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => cleanup())

describe('ChantierChecklist — erreurs serveur et photo requise', () => {
  it('un refus serveur est affiché (toast + sous l’étape), plus avalé', async () => {
    const user = userEvent.setup()
    installationsApiMock.getChecklist.mockResolvedValue({
      data: { items: [item({})], completion: 0 },
    })
    const detail = 'Photo requise pour l’étape « Pose des panneaux » : ajoutez une photo.'
    installationsApiMock.cocherChecklist.mockRejectedValue({
      response: { status: 409, data: { detail, cle: 'pose' } },
    })
    render(<ChantierChecklist installationId={42} produits={[]} />)
    await screen.findByText('Pose des panneaux')
    await user.click(screen.getByRole('checkbox'))
    await waitFor(() => expect(toasts.error).toHaveBeenCalledWith(detail))
    expect((await screen.findByRole('alert')).textContent).toBe(detail)
  })

  it('étape à photo obligatoire sans photo : case désactivée, « Photo requise »', async () => {
    installationsApiMock.getChecklist.mockResolvedValue({
      data: { items: [item({ photo_obligatoire: true })], completion: 0 },
    })
    render(<ChantierChecklist installationId={42} produits={[]} />)
    expect(await screen.findByText('Photo requise')).toBeInTheDocument()
    expect(screen.getByRole('checkbox')).toBeDisabled()
  })

  it('avec une photo, l’étape obligatoire redevient cochable', async () => {
    installationsApiMock.getChecklist.mockResolvedValue({
      data: { items: [item({ photo_obligatoire: true, photos_count: 1 })], completion: 0 },
    })
    render(<ChantierChecklist installationId={42} produits={[]} />)
    await screen.findByText('Pose des panneaux')
    expect(screen.queryByText('Photo requise')).not.toBeInTheDocument()
    expect(screen.getByRole('checkbox')).not.toBeDisabled()
  })
})
