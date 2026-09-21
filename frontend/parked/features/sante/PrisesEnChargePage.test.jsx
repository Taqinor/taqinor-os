import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import PrisesEnChargePage from './PrisesEnChargePage'

/* WIR53(b) — destination réelle du lien de notification
   `sante.alertes_prise_en_charge_expirant` (`/sante/prises-en-charge?id=`),
   jusque-là non enregistrée (404 systématique). Vérifie que la route rend un
   écran réel : la liste complète ET la fiche détaillée quand `?id=` est
   présent dans l'URL. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

vi.mock('../../api/santeApi', () => ({
  default: {
    prisesEnCharge: {
      list: () => Promise.resolve({
        data: [
          {
            id: 7, patient: 5, convention: 2, statut: 'accordee',
            statut_display: 'Accordée', date_demande: '2026-07-01',
            date_expiration: '2026-08-01', montant_accorde: '300.00',
          },
        ],
      }),
    },
    patients: {
      list: () => Promise.resolve({ data: [{ id: 5, nom: 'Zahra', prenom: 'Fatima' }] }),
    },
    conventions: {
      list: () => Promise.resolve({ data: [{ id: 2, nom: 'CNOPS' }] }),
    },
  },
}))

function renderPage(search = '') {
  return render(
    <MemoryRouter initialEntries={[`/sante/prises-en-charge${search}`]}>
      <ThemeProvider>
        <PrisesEnChargePage />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('PrisesEnChargePage', () => {
  it('affiche la liste des prises en charge (jamais un 404)', async () => {
    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('pec-row-7')).toBeInTheDocument()
    })
    expect(screen.getByText('CNOPS')).toBeInTheDocument()
  })

  it('affiche la fiche détaillée quand ?id= pointe vers une PEC réelle', async () => {
    renderPage('?id=7')

    await waitFor(() => {
      expect(screen.getByTestId('pec-fiche')).toBeInTheDocument()
    })
    expect(screen.getByText(/Fiche — Zahra Fatima/)).toBeInTheDocument()
  })
})
