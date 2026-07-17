// NTUX11 — RecentEntitiesWidget : autonome (rien si liste vide), liste les
// récents avec horodatage relatif, clic navigue via ROUTE (même table que
// la palette ⌘K, aucune route dupliquée).
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const navigateMock = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useNavigate: () => navigateMock }
})

const readRecentEntitiesMock = vi.fn()
vi.mock('../../providers/commandActions', () => ({
  readRecentEntities: () => readRecentEntitiesMock(),
}))

import RecentEntitiesWidget from './RecentEntitiesWidget'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderWidget() {
  return render(<RecentEntitiesWidget />, { wrapper: MemoryRouter })
}

describe('RecentEntitiesWidget (NTUX11)', () => {
  it('ne rend rien sans entité récente (autonome)', () => {
    readRecentEntitiesMock.mockReturnValue([])
    const { container } = renderWidget()
    expect(container.firstChild).toBeNull()
  })

  it('liste les récents avec leur libellé', () => {
    readRecentEntitiesMock.mockReturnValue([
      { type: 'client', id: 7, label: 'Alaoui Solaire', ts: Date.now() },
      { type: 'devis', id: 3, label: 'DV-003', ts: Date.now() - 60000 },
    ])
    renderWidget()
    expect(screen.getByTestId('recent-entities-widget')).toBeInTheDocument()
    expect(screen.getByText('Alaoui Solaire')).toBeInTheDocument()
    expect(screen.getByText('DV-003')).toBeInTheDocument()
  })

  it('cliquer une entrée navigue via ROUTE[type](id)', () => {
    readRecentEntitiesMock.mockReturnValue([{ type: 'client', id: 7, label: 'Alaoui Solaire', ts: Date.now() }])
    renderWidget()
    fireEvent.click(screen.getByText('Alaoui Solaire'))
    expect(navigateMock).toHaveBeenCalledWith('/crm?id=7')
  })

  it('un horodatage absent (entrée pré-NTUX11) ne fait pas planter le rendu', () => {
    readRecentEntitiesMock.mockReturnValue([{ type: 'client', id: 7, label: 'Alaoui Solaire' }])
    expect(() => renderWidget()).not.toThrow()
    expect(screen.getByText('Alaoui Solaire')).toBeInTheDocument()
  })
})
