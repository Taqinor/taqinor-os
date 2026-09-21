import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* NTCON24 — assistant de clôture : la liste PRÉCISE des pré-requis manquants
   est affichée telle que le serveur la renvoie ; le succès enchaîne DGD +
   notification + mise à disposition du dossier consolidé. */

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
  prerequis: vi.fn(),
  cloturer: vi.fn(),
  exportDossier: vi.fn(() => Promise.resolve({ data: new Blob(['zip']) })),
}))

vi.mock('../../api/btpChantierApi', () => ({
  default: {
    cloture: {
      prerequis: (...a) => api.prerequis(...a),
      cloturer: (...a) => api.cloturer(...a),
    },
    exportDossierBtp: (...a) => api.exportDossier(...a),
  },
}))

vi.mock('../../api/installationsApi', () => ({
  default: {
    getInstallations: () => Promise.resolve({
      data: [{ id: 5, client_nom: 'Villa Zenith', site_ville: 'Agadir' }],
    }),
  },
}))

import ClotureChantierBtpWizard from './ClotureChantierBtpWizard'

beforeEach(() => {
  vi.clearAllMocks()
  api.prerequis.mockResolvedValue({ data: { pret: true, blocages: [] } })
  api.cloturer.mockResolvedValue({
    data: {
      dgd: { id: 3, reference: 'DGD-202602-0001', statut: 'notifie' },
      prerequis: { pret: true, blocages: [] },
      export_dossier_url:
        '/api/django/btp-chantier/chantiers/5/export-dossier-btp/',
    },
  })
})

function afficher() {
  return render(
    <MemoryRouter>
      <ThemeProvider><ClotureChantierBtpWizard /></ThemeProvider>
    </MemoryRouter>,
  )
}

async function choisirChantier(user) {
  const select = await screen.findByLabelText('Chantier à clôturer')
  await user.selectOptions(
    select, within(select).getByRole('option', { name: /Villa Zenith/ }))
}

describe('ClotureChantierBtpWizard (NTCON24)', () => {
  it('affiche la liste précise des pré-requis manquants et bloque', async () => {
    api.prerequis.mockResolvedValue({
      data: {
        pret: false,
        blocages: [
          '2 réserve(s) bloquante(s) encore ouverte(s) — à lever avant la clôture.',
          'Visa(s) encore en attente de décision : VIS-1.',
        ],
      },
    })
    const user = userEvent.setup()
    afficher()
    await choisirChantier(user)

    const bloc = await screen.findByTestId('btp-cloture-prerequis')
    expect(within(bloc).getByText(/2 réserve\(s\) bloquante/)).toBeTruthy()
    expect(within(bloc).getByText(/VIS-1/)).toBeTruthy()
    expect(
      screen.getByRole('button', { name: 'Suivant' }).disabled,
    ).toBe(true)
  })

  it('enchaîne DGD puis propose le dossier consolidé', async () => {
    const user = userEvent.setup()
    afficher()
    await choisirChantier(user)

    await waitFor(() => expect(api.prerequis).toHaveBeenCalledWith('5'))
    await user.click(screen.getByRole('button', { name: 'Suivant' }))

    await user.type(
      screen.getByLabelText('Montant du marché initial HT'), '250000')
    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    await user.click(
      screen.getByRole('button', { name: 'Clôturer le chantier' }))

    await waitFor(() => expect(api.cloturer).toHaveBeenCalledWith('5', {
      montant_marche_initial_ht: '250000',
    }))
    const resultat = await screen.findByTestId('btp-cloture-resultat')
    expect(within(resultat).getByText(/DGD-202602-0001/)).toBeTruthy()

    await user.click(
      screen.getByRole('button', { name: 'Télécharger le dossier de chantier' }))
    await waitFor(() => expect(api.exportDossier).toHaveBeenCalledWith('5'))
  })

  it('réaffiche les blocages renvoyés par un refus serveur', async () => {
    api.cloturer.mockRejectedValue({
      response: {
        status: 400,
        data: {
          detail: 'Clôture impossible — PPSPS non signé par : ELEC SARL.',
          blocages: ['PPSPS non signé par : ELEC SARL.'],
        },
      },
    })
    const user = userEvent.setup()
    afficher()
    await choisirChantier(user)
    await waitFor(() => expect(api.prerequis).toHaveBeenCalled())

    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    await user.click(
      screen.getByRole('button', { name: 'Clôturer le chantier' }))

    const bloc = await screen.findByTestId('btp-cloture-prerequis')
    expect(within(bloc).getByText(/ELEC SARL/)).toBeTruthy()
  })
})
