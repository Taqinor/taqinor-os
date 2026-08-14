import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* NTLOG34 — mini-wizard réserve/litige : la réserve ET le litige naissent
   d'une seule soumission (`POST /transport/reserves-reception/`, le litige
   étant créé côté serveur dans le MÊME appel — jamais un second POST vers un
   endpoint litige dédié). Les photos passent par `AttachmentsPanel` ciblant
   la réserve UNIQUEMENT (mocké ici pour rester hors réseau) — jamais une
   seconde cible litige. */

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('../../api/axios', () => ({ default: { get, post } }))

const { toastError, toastSuccess } = vi.hoisted(() => ({
  toastError: vi.fn(), toastSuccess: vi.fn(),
}))
vi.mock('../../ui/confirm', () => ({
  toast: { error: toastError, success: toastSuccess },
}))

const attachmentsPanelProps = vi.hoisted(() => ({ calls: [] }))
vi.mock('../../components/AttachmentsPanel', () => ({
  default: (props) => {
    attachmentsPanelProps.calls.push(props)
    return <div data-testid="attachments-panel">{props.model}:{props.id}</div>
  },
}))

import ReserveEtLitigeWizard from './ReserveEtLitigeWizard'

afterEach(() => { cleanup(); vi.clearAllMocks(); attachmentsPanelProps.calls = [] })

const ETAPE = { id: 7, type_etape: 'livraison' }
const ORDRE = { id: 1, installations_transporteur_id: 5 }

describe('ReserveEtLitigeWizard', () => {
  it('crée la réserve (et donc le litige) en UNE seule soumission', async () => {
    post.mockResolvedValueOnce({ data: { id: 99, litige: 42 } })
    get.mockResolvedValueOnce({ data: { id: 5, nom: 'Transporteur X' } })
    const user = userEvent.setup()

    render(<ReserveEtLitigeWizard etape={ETAPE} ordre={ORDRE} onClose={vi.fn()} onCreated={vi.fn()} />)

    await user.type(screen.getByLabelText('Nature du dommage'), 'Panneau fissuré')
    await user.click(screen.getByRole('button', { name: 'Suivant' }))

    await waitFor(() => expect(post).toHaveBeenCalledWith(
      '/transport/reserves-reception/',
      expect.objectContaining({ etape: 7, nature_reserve: 'Panneau fissuré' }),
    ))
    expect(post).toHaveBeenCalledTimes(1)

    // Étape photos : la cible est la RÉSERVE, jamais le litige.
    await screen.findByTestId('attachments-panel')
    expect(attachmentsPanelProps.calls[0]).toMatchObject({
      model: 'transport.reservereception', id: 99,
    })
  })

  it('affiche le transporteur pré-rempli à la confirmation', async () => {
    post.mockResolvedValueOnce({ data: { id: 99, litige: 42 } })
    get.mockResolvedValueOnce({ data: { id: 5, nom: 'Transporteur X' } })
    const user = userEvent.setup()

    render(<ReserveEtLitigeWizard etape={ETAPE} ordre={ORDRE} onClose={vi.fn()} onCreated={vi.fn()} />)
    await user.type(screen.getByLabelText('Nature du dommage'), 'Carton écrasé')
    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    await screen.findByTestId('attachments-panel')
    await user.click(screen.getByRole('button', { name: 'Suivant' }))

    await screen.findByText('Transporteur X')
    expect(screen.getByText(/Litige #42/)).toBeInTheDocument()
  })

  it('appelle onCreated puis onClose au clic sur Terminer', async () => {
    post.mockResolvedValueOnce({ data: { id: 99, litige: 42 } })
    get.mockResolvedValueOnce({ data: { id: 5, nom: 'Transporteur X' } })
    const onCreated = vi.fn()
    const onClose = vi.fn()
    const user = userEvent.setup()

    render(<ReserveEtLitigeWizard etape={ETAPE} ordre={ORDRE} onClose={onClose} onCreated={onCreated} />)
    await user.type(screen.getByLabelText('Nature du dommage'), 'x')
    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    await screen.findByTestId('attachments-panel')
    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    await screen.findByText('Transporteur X')
    await user.click(screen.getByRole('button', { name: 'Terminer' }))

    expect(onCreated).toHaveBeenCalled()
    expect(onClose).toHaveBeenCalled()
  })
})
