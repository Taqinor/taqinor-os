import { describe, it, expect, beforeAll } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

// La sparkline VX15 mesure sa taille : jsdom n'a pas ResizeObserver.
beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}

      unobserve() {}

      disconnect() {}
    }
  }
})
import {
  ModuleDashboard, ModuleHero, ListShell, EcheanceCenter, statusPill,
} from './index.js'

/* Tests de RENDU (smoke) du kit module ERP (UX1). On vérifie le comportement
   visible (libellés, tableau, tri des échéances, repli de libellé), pas
   l'implémentation. Tout ce qui utilise <Link>/DataTable est enveloppé dans un
   <MemoryRouter> + <ThemeProvider> (DataTable lit la densité via useDensity). */

function withRouter(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('ModuleDashboard', () => {
  it('rend les libellés de KPI', () => {
    withRouter(
      <ModuleDashboard
        stats={[
          { label: 'Contrats actifs', value: '42' },
          { label: 'À renouveler', value: '7', to: '/contrats?statut=expire' },
        ]}
      />,
    )
    expect(screen.getByText('Contrats actifs')).toBeInTheDocument()
    expect(screen.getByText('À renouveler')).toBeInTheDocument()
  })

  it('VX15 — rend une sparkline quand `trend` est fourni, rien sinon', () => {
    const { container } = withRouter(
      <ModuleDashboard
        stats={[
          { label: 'Production kWc', value: '120', trend: [1, 2, 3, 4] },
          { label: 'Sans tendance', value: '5' },
        ]}
      />,
    )
    // KpiSpark rend un conteneur ResponsiveContainer (recharts) — un seul
    // KPI porte `trend`, donc un seul graphique doit apparaître.
    expect(container.querySelectorAll('.recharts-responsive-container').length).toBe(1)
  })

  it('VX15 — `accent` pose une pastille de couleur, rien sans accent', () => {
    withRouter(
      <ModuleDashboard
        stats={[{ label: 'Casiers actifs', value: '10' }]}
        accent="var(--info)"
      />,
    )
    expect(screen.getByText('Casiers actifs')).toBeInTheDocument()
  })
})

describe('ModuleHero', () => {
  it('rend le titre en heading + sous-titre', () => {
    withRouter(<ModuleHero title="Tableau de bord" subtitle="Vue d'ensemble" />)
    expect(screen.getByRole('heading', { name: 'Tableau de bord' })).toBeInTheDocument()
    expect(screen.getByText("Vue d'ensemble")).toBeInTheDocument()
  })

  it('headingAs="h2" rend un <h2> (contrat e2e Dashboard préservé)', () => {
    withRouter(<ModuleHero title="Tableau de bord" headingAs="h2" />)
    const heading = screen.getByRole('heading', { name: 'Tableau de bord' })
    expect(heading.tagName).toBe('H2')
  })

  it('sans headingAs, rend un <h1> par défaut', () => {
    withRouter(<ModuleHero title="Contrats" />)
    const heading = screen.getByRole('heading', { name: 'Contrats' })
    expect(heading.tagName).toBe('H1')
  })
})

describe('ListShell', () => {
  it('rend le titre et un tableau', () => {
    const columns = [
      { id: 'nom', header: 'Nom', accessor: (r) => r.nom },
      { id: 'ville', header: 'Ville', accessor: (r) => r.ville },
    ]
    const rows = [
      { id: 1, nom: 'Reda Kasri', ville: 'Rabat' },
      { id: 2, nom: 'Meryem B', ville: 'Casablanca' },
    ]
    withRouter(<ListShell title="Contrats" columns={columns} rows={rows} />)
    expect(screen.getByRole('heading', { name: 'Contrats' })).toBeInTheDocument()
    expect(screen.getByRole('grid')).toBeInTheDocument()
    expect(screen.getAllByText('Reda Kasri').length).toBeGreaterThan(0)
  })
})

describe('EcheanceCenter', () => {
  it('trie une échéance en retard avant une échéance future', () => {
    withRouter(
      <EcheanceCenter
        items={[
          { id: 'futur', label: 'Contrat futur', daysLeft: 20 },
          { id: 'retard', label: 'Contrat en retard', daysLeft: -3 },
        ]}
      />,
    )
    const labels = screen.getAllByText(/Contrat (futur|en retard)/)
    expect(labels[0]).toHaveTextContent('Contrat en retard')
    expect(labels[1]).toHaveTextContent('Contrat futur')
  })

  it('affiche le texte vide quand items=[]', () => {
    withRouter(<EcheanceCenter items={[]} emptyText="Aucune échéance à venir." />)
    expect(screen.getByText('Aucune échéance à venir.')).toBeInTheDocument()
  })
})

describe('statusPill', () => {
  it('retombe sur le statut brut quand la valeur est inconnue', () => {
    const Pill = statusPill({ actif: { label: 'Actif', tone: 'success' } })
    render(<Pill status="inconnu" />)
    expect(screen.getByText('inconnu')).toBeInTheDocument()
  })

  it('utilise le libellé du map quand le statut est connu', () => {
    const Pill = statusPill({ actif: { label: 'Actif', tone: 'success' } })
    render(<Pill status="actif" />)
    expect(screen.getByText('Actif')).toBeInTheDocument()
    expect(Pill.toneOf('actif')).toBe('success')
    expect(Pill.options).toEqual([{ value: 'actif', label: 'Actif' }])
  })
})
