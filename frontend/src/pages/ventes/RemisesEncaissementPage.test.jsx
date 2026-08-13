import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* PACT46 — remises d'encaissement terrain. Zéro écran = aucun contrôle sur
   l'argent liquide collecté. Le test verrouille les deux garanties de la
   tâche : l'écart n'est JAMAIS masqué (affiché sur la ligne ET alerté à la
   clôture) et le bordereau PDF se télécharge. */

vi.mock('../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))
vi.mock('../../utils/pdfBlob', () => ({ openPdfBlob: vi.fn() }))
vi.mock('../../ui/confirm', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
  useConfirmDialog: () => ({
    confirm: () => Promise.resolve(true),
    confirmDelete: () => Promise.resolve(true),
  }),
}))

import api from '../../api/axios'
import { openPdfBlob } from '../../utils/pdfBlob'
import RemisesEncaissementPage from './RemisesEncaissementPage'

const OUVERTE = {
  id: 3, reference: 'REM-2026-0003', technicien_nom: 'youssef',
  date_collecte: '2026-08-10', montant_declare: '5000.00',
  montant_lignes: '4850.00', ecart: '150.00', statut: 'ouverte',
  statut_display: 'Ouverte', lignes: [],
}
const CLOTUREE = { ...OUVERTE, statut: 'cloturee', statut_display: 'Clôturée' }

const getFor = (rows) => (url) => {
  if (url === '/ventes/remises-encaissement/') {
    return Promise.resolve({ data: rows })
  }
  if (url === '/ventes/paiements/') {
    return Promise.resolve({
      data: [{ id: 11, montant: '4850.00', mode: 'especes', mode_display: 'Espèces', facture_reference: 'FAC-001' }],
    })
  }
  return Promise.resolve({ data: new Blob(['%PDF']) })
}

beforeEach(() => { api.get.mockImplementation(getFor([OUVERTE])) })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('RemisesEncaissementPage (PACT46)', () => {
  it('affiche l\'écart de chaque remise sans jamais le masquer', async () => {
    render(<RemisesEncaissementPage />)
    await waitFor(() => expect(api.get)
      .toHaveBeenCalledWith('/ventes/remises-encaissement/'))
    expect(await screen.findByText('REM-2026-0003')).toBeInTheDocument()
    expect(screen.getByText('youssef')).toBeInTheDocument()
    // 150,00 MAD d'écart, rendu tel quel sur la ligne.
    expect(screen.getByText(/150/)).toBeInTheDocument()
  })

  it('alerte explicitement quand la clôture révèle un écart non nul', async () => {
    const user = userEvent.setup()
    api.post.mockResolvedValue({
      data: { ...CLOTUREE, ecart_non_nul: true },
    })
    render(<RemisesEncaissementPage />)
    await screen.findByText('REM-2026-0003')

    api.get.mockImplementation(getFor([CLOTUREE]))
    await user.click(screen.getByRole('button', { name: 'Clôturer' }))

    await waitFor(() => expect(api.post)
      .toHaveBeenCalledWith('/ventes/remises-encaissement/3/cloturer/'))
    const alerte = await screen.findByRole('alert')
    expect(alerte).toHaveTextContent(/Écart constaté à la clôture/)
  })

  it('télécharge le bordereau PDF d\'une remise clôturée', async () => {
    const user = userEvent.setup()
    api.get.mockImplementation(getFor([CLOTUREE]))
    render(<RemisesEncaissementPage />)
    await screen.findByText('REM-2026-0003')

    await user.click(screen.getByRole('button', { name: /Bordereau PDF/ }))

    await waitFor(() => expect(api.get).toHaveBeenCalledWith(
      '/ventes/remises-encaissement/3/pdf/', { responseType: 'blob' }))
    await waitFor(() => expect(openPdfBlob).toHaveBeenCalled())
  })

  it('déclare une remise avec les encaissements terrain rattachés', async () => {
    const user = userEvent.setup()
    api.post.mockResolvedValue({ data: { id: 4 } })
    render(<RemisesEncaissementPage />)
    await screen.findByText('REM-2026-0003')

    await user.click(screen.getByRole('button', { name: /Déclarer une remise/ }))
    await user.type(await screen.findByLabelText('Montant déclaré (MAD)'), '5000')
    await user.click(screen.getByRole('checkbox', { name: /Rattacher le paiement 11/ }))
    await user.click(screen.getByRole('button', { name: 'Déclarer' }))

    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/ventes/remises-encaissement/',
      expect.objectContaining({
        montant_declare: '5000',
        lignes: [{ paiement: 11 }],
      })))
    // `company` n'est JAMAIS envoyée depuis le client (imposée serveur).
    expect(api.post.mock.calls[0][1]).not.toHaveProperty('company')
  })
})
