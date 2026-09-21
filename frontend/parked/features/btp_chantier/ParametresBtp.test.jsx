import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* NTCON25 — réglages BTP : les deux interrupteurs pilotent des guards réels ;
   une erreur serveur est rendue SOUS le champ fautif (jamais un message
   générique). */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const api = vi.hoisted(() => ({
  get: vi.fn(),
  enregistrer: vi.fn(),
}))

vi.mock('../../api/btpChantierApi', () => ({
  default: { parametres: { get: (...a) => api.get(...a), enregistrer: (...a) => api.enregistrer(...a) } },
}))

import ParametresBtp from './ParametresBtp'

const REGLAGES = {
  id: 1,
  delai_reponse_rfi_defaut_jours: 5,
  delai_revue_visa_defaut_jours: 10,
  guard_ppsps_bloquant: true,
  guard_checklist_lot_bloquant: true,
  lots_types_defaut: ['Gros-œuvre', 'Électricité'],
  taux_penalite_retard_defaut_pmil: null,
}

beforeEach(() => {
  vi.clearAllMocks()
  api.get.mockResolvedValue({ data: { ...REGLAGES } })
  api.enregistrer.mockImplementation((data) =>
    Promise.resolve({ data: { ...REGLAGES, ...data } }))
})

function afficher() {
  return render(
    <MemoryRouter>
      <ThemeProvider><ParametresBtp /></ThemeProvider>
    </MemoryRouter>,
  )
}

describe('ParametresBtp (NTCON25)', () => {
  it('affiche les réglages de la société', async () => {
    afficher()
    const ppsps = await screen.findByLabelText(
      'Bloquer le démarrage sans PPSPS signé')
    expect(ppsps.checked).toBe(true)
    expect(screen.getByLabelText('Délai de réponse RFI par défaut').value)
      .toBe('5')
    expect(screen.getByLabelText('Lots types suggérés').value)
      .toBe('Gros-œuvre\nÉlectricité')
  })

  it('désactive le guard PPSPS et enregistre', async () => {
    const user = userEvent.setup()
    afficher()
    const ppsps = await screen.findByLabelText(
      'Bloquer le démarrage sans PPSPS signé')
    await user.click(ppsps)
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(api.enregistrer).toHaveBeenCalledWith(
      expect.objectContaining({ guard_ppsps_bloquant: false })))
  })

  it('envoie les lots types ligne par ligne', async () => {
    const user = userEvent.setup()
    afficher()
    const zone = await screen.findByLabelText('Lots types suggérés')
    await user.clear(zone)
    await user.type(zone, 'Gros-œuvre{Enter}CVC')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(api.enregistrer).toHaveBeenCalledWith(
      expect.objectContaining({ lots_types_defaut: ['Gros-œuvre', 'CVC'] })))
  })

  it('affiche l’erreur serveur sous le champ fautif', async () => {
    api.enregistrer.mockRejectedValue({
      response: {
        status: 400,
        data: {
          taux_penalite_retard_defaut_pmil: [
            'Le taux de pénalité ne peut pas être négatif.',
          ],
        },
      },
    })
    const user = userEvent.setup()
    afficher()
    await screen.findByLabelText('Taux de pénalité de retard par défaut')
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))

    const alerte = await screen.findByRole('alert')
    expect(alerte.textContent).toContain('ne peut pas être négatif')
  })
})
