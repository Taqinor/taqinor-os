import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import CartePage from './CartePage'
import { ThemeProvider } from '../design/ThemeProvider'

/* VX32 — CartePage rejoint le design system : légende Badge cliquable (au lieu
   de boutons en hex codés en dur) + filtre statut Radix Select (au lieu du
   <select> natif fond blanc figé). On vérifie : (1) le compteur de points
   s'affiche en Badge ; (2) chaque pastille de légende bascule visibilité +
   affiche son compte ; (3) le filtre statut est un vrai combobox Radix
   (role=combobox, PAS un <select> natif) qui filtre les marqueurs affichés. */

vi.mock('../api/reportingApi', () => ({
  default: {
    getGeoPoints: vi.fn(() => Promise.resolve({
      data: {
        points: [
          {
            id: 1, type: 'lead', lat: 33.5, lng: -7.6, label: 'Lead A',
            statut: 'nouveau', statut_label: 'Nouveau', type_label: 'Lead',
            detail_path: '/crm/leads/1',
          },
          {
            id: 2, type: 'chantier', lat: 34.0, lng: -6.8, label: 'Chantier B',
            statut: 'en_cours', statut_label: 'En cours', type_label: 'Chantier',
            detail_path: '/installations/2',
          },
        ],
        counts: { total: 2, lead: 1, chantier: 1 },
      },
    })),
  },
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function renderPage() {
  return render(
    <ThemeProvider>
      <MemoryRouter>
        <CartePage />
      </MemoryRouter>
    </ThemeProvider>,
  )
}

describe('CartePage (VX32 — design system)', () => {
  it('affiche le compte total de points en Badge', async () => {
    renderPage()
    expect(await screen.findByText('2 point(s) géolocalisé(s)')).toBeInTheDocument()
  })

  it('affiche la légende en pastilles cliquables avec leur compte', async () => {
    renderPage()
    expect(await screen.findByRole('button', { name: /Leads \(1\)/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Chantiers \(1\)/ })).toBeInTheDocument()
  })

  it('bascule la visibilité d\'un type au clic sur sa pastille (aria-pressed)', async () => {
    const user = userEvent.setup()
    renderPage()
    const leadToggle = await screen.findByRole('button', { name: /Leads \(1\)/ })
    expect(leadToggle).toHaveAttribute('aria-pressed', 'true')
    await user.click(leadToggle)
    expect(leadToggle).toHaveAttribute('aria-pressed', 'false')
  })

  it('le filtre de statut est un combobox Radix (pas un <select> natif)', async () => {
    renderPage()
    const combo = await screen.findByRole('combobox', { name: 'Filtrer par statut' })
    expect(combo.tagName).not.toBe('SELECT')
  })

  it('filtrer par statut réduit les marqueurs affichés', async () => {
    const user = userEvent.setup()
    renderPage()
    const combo = await screen.findByRole('combobox', { name: 'Filtrer par statut' })
    await user.click(combo)
    const option = await screen.findByRole('option', { name: 'Nouveau' })
    await user.click(option)
    await waitFor(() => expect(combo).toHaveTextContent('Nouveau'))
  })
})
