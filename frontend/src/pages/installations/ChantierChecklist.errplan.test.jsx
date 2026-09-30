// ERR117 — cocher une étape EN LIGNE ne doit ni vider la liste ni effacer le
// pourcentage : `withOfflineFallback` renvoie {queued:false, data:<réponse axios
// brute>} (donc les items sont sous `r.data.data`). Le wrapper est mocké ici
// avec sa VRAIE forme (contrairement à ChantierChecklist.ntmob11.test.jsx).
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

const { installationsApiMock } = vi.hoisted(() => ({
  installationsApiMock: { getChecklist: vi.fn(), cocherChecklist: vi.fn() },
}))
vi.mock('../../api/installationsApi', () => ({ default: installationsApiMock }))
vi.mock('../../api/recordsApi', () => ({ default: { uploadAttachment: vi.fn() } }))
vi.mock('../preferences/prefs', () => ({
  compressPhotoForUpload: vi.fn((f) => Promise.resolve(f)),
}))
vi.mock('../../features/installations/offline/fieldOutbox', () => ({
  // Forme réelle : { queued:false, data:<réponse axios BRUTE> }.
  withOfflineFallback: (fn) => fn().then((data) => ({ queued: false, data })),
  FIELD_OPS: { COCHER_CHECKLIST: 'cocher_checklist' },
}))
vi.mock('../../features/pwa/CameraCapture', () => ({ default: () => null }))

import ChantierChecklist from './ChantierChecklist'

const item = (fait) => ({
  id: 1, cle: 'pose', libelle: 'Pose des panneaux', ordre: 1,
  capture_serie: false, photo_obligatoire: false, fait,
  fait_par_nom: null, fait_le: null, photos_count: 0,
})

beforeEach(() => {
  vi.clearAllMocks()
  installationsApiMock.getChecklist.mockResolvedValue({
    data: { items: [item(false)], completion: 0 },
  })
  installationsApiMock.cocherChecklist.mockResolvedValue({
    data: { items: [item(true)], completion: 100 },
  })
})
afterEach(() => cleanup())

describe('ChantierChecklist — ERR117', () => {
  it('cocher une étape en ligne garde la liste et met à jour le pourcentage', async () => {
    const user = userEvent.setup()
    render(<ChantierChecklist installationId={42} produits={[]} />)
    await screen.findByText('Pose des panneaux')
    await user.click(screen.getByRole('checkbox'))
    await waitFor(() => expect(installationsApiMock.cocherChecklist).toHaveBeenCalled())
    expect(await screen.findByText('Pose des panneaux')).toBeInTheDocument()
    expect(screen.queryByText(/Aucune étape/)).not.toBeInTheDocument()
    expect(await screen.findByText(/100/)).toBeInTheDocument()
  })
})
