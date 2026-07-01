import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import {
  ModuleDashboard, ListShell, EcheanceCenter, statusPill,
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
