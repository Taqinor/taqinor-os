import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import rhApi from '../../api/rhApi'
import FermeturesCollectives from './FermeturesCollectives.jsx'

/* PACT92 — Fermetures collectives. Ré-appliquer une fermeture déjà appliquée
   ne doit afficher aucun doublon : le compte de demandes créées vient TEL
   QUEL de la réponse serveur (idempotence visible côté écran). */

vi.mock('../../api/rhApi', () => {
  const empty = () => Promise.resolve({ data: [] })
  return {
    default: {
      getPeriodesFermeture: vi.fn(() => Promise.resolve({
        data: [{ id: 6, libelle: 'Fermeture annuelle', date_debut: '2026-08-01', date_fin: '2026-08-15', type_absence: 2, type_absence_code: 'CP', appliquee: false, departements: [] }],
      })),
      getTypesAbsence: vi.fn(empty),
      getDepartements: vi.fn(empty),
      createPeriodeFermeture: vi.fn(),
      appliquerPeriodeFermeture: vi.fn(),
    },
  }
})

function renderScreen() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <FermeturesCollectives />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('FermeturesCollectives (PACT92)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('rend le module et liste les fermetures', async () => {
    renderScreen()
    expect((await screen.findAllByText('Fermetures collectives')).length).toBeGreaterThan(0)
    expect((await screen.findAllByText('Fermeture annuelle')).length).toBeGreaterThan(0)
  })

  it('crée une fermeture via rhApi.createPeriodeFermeture', async () => {
    rhApi.createPeriodeFermeture.mockResolvedValueOnce({ data: { id: 1 } })
    rhApi.getTypesAbsence.mockResolvedValue({ data: [{ id: 2, code: 'CP', libelle: 'Congé payé' }] })
    renderScreen()
    await screen.findAllByText('Fermetures collectives')

    fireEvent.click((await screen.findAllByRole('button', { name: /Nouvelle fermeture/ }))[0])
    fireEvent.change(screen.getByLabelText('Libellé'), { target: { value: 'Pont Aïd' } })
    fireEvent.change(screen.getByLabelText('Du'), { target: { value: '2026-09-01' } })
    fireEvent.change(screen.getByLabelText('Au'), { target: { value: '2026-09-03' } })
    fireEvent.change(screen.getByLabelText('Type d’absence'), { target: { value: '2' } })
    fireEvent.click(screen.getAllByRole('button', { name: 'Créer' })[0])

    await waitFor(() => expect(rhApi.createPeriodeFermeture).toHaveBeenCalledWith(
      expect.objectContaining({ libelle: 'Pont Aïd', type_absence: '2' }),
    ))
  })
})
