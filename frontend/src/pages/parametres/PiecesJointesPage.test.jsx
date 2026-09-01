import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* WIR270/FG10 — centre de pièces jointes société. `getAllAttachments` était un
   export MORT : l'endpoint transverse `records/attachments/all/` n'avait aucun
   appelant. Couvre : chargement paginé (50/page), les 5 filtres
   (mime/mime_like/phase/model/since), la page suivante, et le fait que la
   société n'est JAMAIS passée depuis le client (le serveur la scope seul). */

const api = vi.hoisted(() => ({ getAllAttachments: vi.fn() }))
vi.mock('../../api/recordsApi', () => ({ default: api }))

import PiecesJointesPage from './PiecesJointesPage'
import config from '../../features/parametres/module.config.jsx'

const PJ = {
  id: 3, filename: 'devis.pdf', size: 2048, mime: 'application/pdf',
  phase: 'avant', uploaded_by_nom: 'reda', created_at: '2026-08-20T10:00:00Z',
  url: '/api/django/records/attachments/3/download/',
}

beforeEach(() => {
  api.getAllAttachments.mockResolvedValue({
    data: { count: 1, results: [PJ] },
  })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('PiecesJointesPage — WIR270', () => {
  it('est routé sous /parametres ET présent dans la nav', () => {
    const route = config.routes.find((r) => r.path === '/parametres/pieces-jointes')
    expect(route).toBeTruthy()
    expect(route.roles).toEqual(['responsable', 'admin'])
    const nav = config.nav.items.find((i) => i.to === '/parametres/pieces-jointes')
    expect(nav).toBeTruthy()
    expect(nav.icon).toBeTruthy()
  })

  it('charge la première page et rend une ligne par fichier', async () => {
    render(<PiecesJointesPage />)
    await waitFor(() => expect(api.getAllAttachments).toHaveBeenCalledWith({ page: 1 }))
    const table = within(await screen.findByTestId('pieces-jointes-table'))
    expect(table.getByText('devis.pdf')).toBeInTheDocument()
    expect(table.getByText('application/pdf')).toBeInTheDocument()
    expect(table.getByText('2 Ko')).toBeInTheDocument()
    // Le lien pointe sur le proxy Django même-origine servi par le serializer.
    expect(table.getByRole('link', { name: 'devis.pdf' }))
      .toHaveAttribute('href', PJ.url)
  })

  it('applique les 5 filtres et ne passe JAMAIS de société', async () => {
    const user = userEvent.setup()
    render(<PiecesJointesPage />)
    await waitFor(() => expect(api.getAllAttachments).toHaveBeenCalled())

    await user.type(screen.getByLabelText('Type MIME exact'), 'application/pdf')
    await user.type(screen.getByLabelText('Type contient'), 'pdf')
    await user.selectOptions(screen.getByLabelText('Phase'), 'avant')
    await user.type(screen.getByLabelText('Objet lié'), 'crm.lead')
    await user.type(screen.getByLabelText('Depuis le'), '2026-08-01')
    await user.click(screen.getByRole('button', { name: 'Filtrer' }))

    await waitFor(() => expect(api.getAllAttachments).toHaveBeenLastCalledWith({
      page: 1,
      mime: 'application/pdf',
      mime_like: 'pdf',
      phase: 'avant',
      model: 'crm.lead',
      since: '2026-08-01',
    }))
    for (const appel of api.getAllAttachments.mock.calls) {
      expect(appel[0]).not.toHaveProperty('company')
    }
  })

  it('« Sans phase » envoie bien phase="" (filtre serveur valide)', async () => {
    const user = userEvent.setup()
    render(<PiecesJointesPage />)
    await waitFor(() => expect(api.getAllAttachments).toHaveBeenCalled())
    await user.selectOptions(screen.getByLabelText('Phase'), '__sans__')
    await user.click(screen.getByRole('button', { name: 'Filtrer' }))
    await waitFor(() => expect(api.getAllAttachments)
      .toHaveBeenLastCalledWith({ page: 1, phase: '' }))
  })

  it('pagine à 50 par page et charge la page suivante', async () => {
    api.getAllAttachments.mockResolvedValue({
      data: { count: 120, results: [PJ] },
    })
    const user = userEvent.setup()
    render(<PiecesJointesPage />)
    expect(await screen.findByTestId('pieces-jointes-pagination'))
      .toHaveTextContent('Page 1 / 3')

    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    await waitFor(() => expect(api.getAllAttachments)
      .toHaveBeenLastCalledWith({ page: 2 }))
  })

  it('dégrade proprement quand l’endpoint échoue', async () => {
    api.getAllAttachments.mockRejectedValue(new Error('boom'))
    render(<PiecesJointesPage />)
    expect(await screen.findByText('Pièces jointes indisponibles')).toBeInTheDocument()
  })
})
