/* NTESG20 — écran Paramètres > ESG.
 *
 * Ce que le test PROUVE :
 *   - les réglages EFFECTIFS sont chargés (la ligne est créée côté serveur,
 *     l'écran n'affiche jamais un formulaire vide qui ferait croire que rien
 *     n'est réglé) ;
 *   - la pondération doit sommer à 100 : le total est affiché en direct et
 *     l'enregistrement est bloqué sinon ;
 *   - après enregistrement, le badge de maturité est RELU — le critère
 *     d'acceptation « recalcule immédiatement le badge affiché » ;
 *   - une erreur serveur est AFFICHÉE (jamais avalée).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

const { getParametres, updateParametres, badgeMaturite } = vi.hoisted(() => ({
  getParametres: vi.fn(),
  updateParametres: vi.fn(),
  badgeMaturite: vi.fn(),
}))

vi.mock('../../api/esgApi', () => ({
  default: {
    parametres: { get: getParametres, update: updateParametres },
    catalogue: { badgeMaturite },
  },
}))

import ParametresEsgPage from './ParametresEsgPage'

const REGLAGES = {
  id: 3,
  seuil_alerte_derive_pct: 10,
  pilote_esg: null,
  pilote_esg_nom: '',
  frequence_reporting: 'annuelle',
  frequence_reporting_display: 'Annuelle',
  ponderation_badge_maturite: { couverture: 34, cibles: 33, trajectoire: 33 },
  updated_at: '2026-09-12T09:20:00Z',
}

function monter() {
  return render(
    <ThemeProvider>
      <MemoryRouter>
        <ParametresEsgPage />
      </MemoryRouter>
    </ThemeProvider>,
  )
}

describe('NTESG20 — Paramètres > ESG', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getParametres.mockResolvedValue({ data: { ...REGLAGES } })
    updateParametres.mockImplementation((data) => Promise.resolve({
      data: { ...REGLAGES, ...data },
    }))
    badgeMaturite.mockResolvedValue({ data: { score: 33.0 } })
  })

  it('charge les réglages effectifs', async () => {
    monter()
    await waitFor(() => {
      expect(screen.getByLabelText(/Seuil d’alerte de dérive/))
        .toHaveValue(10)
    })
    expect(screen.getByLabelText('Fréquence de reporting'))
      .toHaveValue('annuelle')
    expect(screen.getByTestId('esg-ponderation-total'))
      .toHaveTextContent('100')
  })

  it('bloque l’enregistrement si la pondération ne somme pas à 100', async () => {
    const user = userEvent.setup()
    monter()
    const champ = await screen.findByLabelText(
      /Poids — Couverture du catalogue/)
    await user.clear(champ)
    await user.type(champ, '50')

    expect(screen.getByTestId('esg-ponderation-total'))
      .toHaveTextContent('116')
    expect(screen.getByRole('button', { name: /Enregistrer/ })).toBeDisabled()
    expect(updateParametres).not.toHaveBeenCalled()
  })

  it('enregistre et RELIT le badge de maturité', async () => {
    const user = userEvent.setup()
    monter()
    const couverture = await screen.findByLabelText(
      /Poids — Couverture du catalogue/)
    const cibles = screen.getByLabelText(/Poids — Indicateurs atteignant/)
    const trajectoire = screen.getByLabelText(/Poids — Indicateurs dotés/)
    await user.clear(couverture)
    await user.type(couverture, '0')
    await user.clear(cibles)
    await user.type(cibles, '0')
    await user.clear(trajectoire)
    await user.type(trajectoire, '100')

    // Le badge renvoyé APRÈS enregistrement reflète la nouvelle pondération.
    badgeMaturite.mockResolvedValue({ data: { score: 100.0 } })
    await user.click(screen.getByRole('button', { name: /Enregistrer/ }))

    await waitFor(() => expect(updateParametres).toHaveBeenCalledTimes(1))
    expect(updateParametres.mock.calls[0][0].ponderation_badge_maturite)
      .toEqual({ couverture: 0, cibles: 0, trajectoire: 100 })
    // 2 appels : au montage + après enregistrement (recalcul immédiat).
    await waitFor(() => expect(badgeMaturite).toHaveBeenCalledTimes(2))
    await waitFor(() => {
      expect(screen.getByTestId('esg-badge-maturite'))
        .toHaveTextContent('100')
    })
  })

  it('affiche l’erreur du serveur', async () => {
    updateParametres.mockRejectedValue({
      response: {
        status: 400,
        data: { ponderation_badge_maturite: ['La pondération doit sommer à 100.'] },
      },
    })
    const user = userEvent.setup()
    monter()
    await screen.findByLabelText(/Poids — Couverture du catalogue/)
    await user.click(screen.getByRole('button', { name: /Enregistrer/ }))
    expect(await screen.findByTestId('esg-parametres-erreur'))
      .toBeInTheDocument()
  })

  it('reste utilisable si le badge est indisponible', async () => {
    badgeMaturite.mockRejectedValue(new Error('HS'))
    monter()
    await waitFor(() => {
      expect(screen.getByLabelText(/Seuil d’alerte de dérive/))
        .toBeInTheDocument()
    })
    expect(screen.queryByTestId('esg-badge-maturite')).toBeNull()
  })
})
