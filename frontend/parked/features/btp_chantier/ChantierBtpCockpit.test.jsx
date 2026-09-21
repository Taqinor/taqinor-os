import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* NTCON21 — tableau de bord BTP : SIX blocs alimentés uniquement par des
   endpoints déjà construits. Le bloc « déboursé vs facturé » est une donnée
   INTERNE : un 403 serveur le masque proprement (jamais un coût affiché à qui
   n'y a pas droit). */

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
  planningLots: vi.fn(),
  reservesList: vi.fn(),
  rfiList: vi.fn(),
  visasList: vi.fn(),
  journalList: vi.fn(),
  debourse: vi.fn(),
}))

vi.mock('../../api/btpChantierApi', () => ({
  default: {
    planningLots: (...a) => api.planningLots(...a),
    reserves: { list: (...a) => api.reservesList(...a) },
    rfi: { list: (...a) => api.rfiList(...a) },
    visas: { list: (...a) => api.visasList(...a) },
    journal: { list: (...a) => api.journalList(...a) },
    debourseVsFacture: (...a) => api.debourse(...a),
  },
}))

vi.mock('../../api/installationsApi', () => ({
  default: {
    getInstallations: () => Promise.resolve({
      data: [{ id: 5, client_nom: 'Villa Zenith', site_ville: 'Agadir' }],
    }),
  },
}))

import ChantierBtpCockpit from './ChantierBtpCockpit'

beforeEach(() => {
  vi.clearAllMocks()
  api.planningLots.mockResolvedValue({
    data: [
      { id: 1, nom: 'Gros-œuvre', couleur: '#2563EB', avancement_pct: 75, en_retard: true, taches: [] },
      { id: 2, nom: 'Électricité', couleur: '#16A34A', avancement_pct: 0, en_retard: false, taches: [] },
    ],
  })
  api.reservesList.mockResolvedValue({
    data: [
      { id: 11, statut: 'ouverte' },
      { id: 12, statut: 'en_cours' },
      { id: 13, statut: 'levee' },
    ],
  })
  api.rfiList.mockResolvedValue({
    data: [{ id: 21, numero: 3, question: 'Section de câble ?', en_retard: true }],
  })
  api.visasList.mockResolvedValue({
    data: [
      { id: 31, reference: 'VIS-1', statut: 'soumis' },
      { id: 32, reference: 'VIS-2', statut: 'approuve_sans_reserve' },
    ],
  })
  api.journalList.mockResolvedValue({
    data: [{ id: 41, date: '2026-02-02', evenements: 'Coulage dalle' }],
  })
  api.debourse.mockResolvedValue({
    data: {
      debourse_sec_total: '10500.00', facture_total: '14000.00',
      marge: '3500.00',
    },
  })
})

function withProviders(ui, route = '/btp-chantier/cockpit') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

async function choisirChantier(user) {
  const select = await screen.findByLabelText('Chantier du tableau de bord')
  await user.selectOptions(
    select, within(select).getByRole('option', { name: /Villa Zenith/ }),
  )
}

describe('ChantierBtpCockpit (NTCON21)', () => {
  it('affiche les six blocs avec les données réelles', async () => {
    const user = userEvent.setup()
    withProviders(<ChantierBtpCockpit />)
    await choisirChantier(user)

    await screen.findByTestId('btp-cockpit')
    expect(screen.getByLabelText('Lots et avancement')).toBeTruthy()
    expect(screen.getByLabelText('Réserves')).toBeTruthy()
    expect(screen.getByLabelText('RFI en attente')).toBeTruthy()
    expect(screen.getByLabelText('Visas en cours')).toBeTruthy()
    expect(screen.getByLabelText('Déboursé vs facturé')).toBeTruthy()
    expect(screen.getByLabelText('Dernier journal de chantier')).toBeTruthy()
  })

  it('compte les réserves ouvertes et levées', async () => {
    const user = userEvent.setup()
    withProviders(<ChantierBtpCockpit />)
    await choisirChantier(user)

    const bloc = await screen.findByTestId('btp-cockpit-reserves')
    expect(bloc.textContent).toContain('2 ouverte(s)')
    expect(bloc.textContent).toContain('1 levée(s)')
  })

  it('ne garde que les visas en cours (soumis / en revue)', async () => {
    const user = userEvent.setup()
    withProviders(<ChantierBtpCockpit />)
    await choisirChantier(user)

    const bloc = await screen.findByTestId('btp-cockpit-visas')
    expect(bloc.textContent).toContain('1 visa(s) en cours')
    const section = screen.getByLabelText('Visas en cours')
    expect(within(section).queryByText('VIS-2')).toBeNull()
  })

  it('affiche le déboursé vs facturé quand le serveur l’autorise', async () => {
    const user = userEvent.setup()
    withProviders(<ChantierBtpCockpit />)
    await choisirChantier(user)

    const bloc = await screen.findByTestId('btp-cockpit-debourse')
    expect(bloc.textContent).toContain('Déboursé')
    expect(bloc.textContent).toContain('Marge')
  })

  it('masque le déboursé sur un 403 serveur (donnée interne)', async () => {
    api.debourse.mockRejectedValue({ response: { status: 403 } })
    const user = userEvent.setup()
    withProviders(<ChantierBtpCockpit />)
    await choisirChantier(user)

    await screen.findByTestId('btp-cockpit')
    expect(screen.queryByTestId('btp-cockpit-debourse')).toBeNull()
    expect(
      screen.getByText('Réservé aux responsables (donnée interne).'),
    ).toBeTruthy()
  })

  it('charge directement le chantier de l’URL (lien profond)', async () => {
    render(
      <MemoryRouter initialEntries={['/btp-chantier/cockpit/5']}>
        <ThemeProvider>
          <Routes>
            <Route
              path="/btp-chantier/cockpit/:chantierId"
              element={<ChantierBtpCockpit />}
            />
          </Routes>
        </ThemeProvider>
      </MemoryRouter>,
    )
    // Sans sélection manuelle : le paramètre de route suffit.
    await waitFor(() => expect(api.planningLots).toHaveBeenCalledWith('5'))
  })

  it('affiche le dernier journal de chantier', async () => {
    const user = userEvent.setup()
    withProviders(<ChantierBtpCockpit />)
    await choisirChantier(user)

    const bloc = await screen.findByTestId('btp-cockpit-journal')
    expect(bloc.textContent).toContain('Coulage dalle')
  })
})
