import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* AUDV24 (DRAFT165-5, AOF140) — planches d'implantation : `PlancheAO`/
   `services.generer_indice_planche` existaient déjà (testés côté backend)
   mais aucun écran ne pouvait verser une révision. Preuves : (1) l'écran
   affiche les planches RÉELLES de l'affaire avec leur indice/statut ;
   (2) verser un fichier appelle `aoApi.planches.upload` avec le bon
   `appel_offre`/`code_document`, jamais un indice choisi côté client. */

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  upload: vi.fn(),
}))

vi.mock('../../../api/aoApi', () => ({
  default: {
    planches: { list: mocks.list, upload: mocks.upload },
  },
}))

import PlanchesPanel from './PlanchesPanel'

const PLANCHE_ACTIVE = {
  id: 2, appel_offre: 7, code_document: '05', indice: 'B',
  reference_complete: '05B', statut: 'active', motif_revision: 'Obstacle écarté',
}
const PLANCHE_ARCHIVEE = {
  id: 1, appel_offre: 7, code_document: '05', indice: 'A',
  reference_complete: '05A', statut: 'archivee', motif_revision: '',
}

const renderPanel = (props) => render(<PlanchesPanel affaireId={7} {...props} />)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: [PLANCHE_ARCHIVEE, PLANCHE_ACTIVE] })
  mocks.upload.mockResolvedValue({
    data: { id: 3, reference_complete: '06A', indice: 'A', statut: 'active' },
  })
})

describe('PlanchesPanel (AUDV24)', () => {
  it('affiche les planches RÉELLES de l’affaire avec leur indice et leur statut', async () => {
    renderPanel()
    await waitFor(() => expect(mocks.list).toHaveBeenCalledWith({ appel_offre: 7 }))
    expect(await screen.findByText('05A')).toBeInTheDocument()
    expect(screen.getByText('05B')).toBeInTheDocument()
    expect(screen.getByText('Archivée')).toBeInTheDocument()
    expect(screen.getByText('Active')).toBeInTheDocument()
    expect(screen.getByText('Obstacle écarté')).toBeInTheDocument()
  })

  it('verser une planche appelle aoApi.planches.upload avec le code document saisi', async () => {
    const user = userEvent.setup()
    renderPanel()
    await screen.findByText('05A')

    await user.type(screen.getByLabelText('Code document'), '06')
    const fichier = new File(['contenu'], 'planche-06.pdf', { type: 'application/pdf' })
    await user.upload(screen.getByLabelText('Fichier'), fichier)
    await user.click(screen.getByRole('button', { name: 'Verser la planche' }))

    await waitFor(() => expect(mocks.upload).toHaveBeenCalledWith(
      expect.objectContaining({ appel_offre: 7, code_document: '06', fichier }),
    ))
    // La liste est rechargée après un versement réussi.
    expect(mocks.list).toHaveBeenCalledTimes(2)
  })

  it('le bouton de versement reste désactivé sans code document ni fichier', async () => {
    renderPanel()
    await screen.findByText('05A')
    expect(screen.getByRole('button', { name: 'Verser la planche' })).toBeDisabled()
  })

  it('sans affaire sélectionnée, affiche un état vide motivé sans appeler la liste', () => {
    render(<PlanchesPanel affaireId={null} />)
    expect(screen.getByText('Planches indisponibles')).toBeInTheDocument()
    expect(mocks.list).not.toHaveBeenCalled()
  })
})
