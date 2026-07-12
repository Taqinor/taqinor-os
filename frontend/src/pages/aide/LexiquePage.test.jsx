import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import LexiquePage from './LexiquePage'

/* VX247(d) — glossaire métier statique : ≥15 termes (DoD), recherche simple,
   aucun appel réseau. */

function renderPage() {
  return render(<MemoryRouter><LexiquePage /></MemoryRouter>)
}

describe('LexiquePage (VX247)', () => {
  it('affiche au moins 15 termes du lexique', () => {
    const { container } = renderPage()
    // `<dt>` par terme (liste de définitions) — pas de dépendance à la
    // résolution de rôle ARIA (variable selon les moteurs de test).
    expect(container.querySelectorAll('dt').length).toBeGreaterThanOrEqual(15)
  })

  it('un terme connu (kWc) porte sa définition', () => {
    renderPage()
    expect(screen.getByText(/kWc \(kilowatt-crête\)/)).toBeInTheDocument()
    expect(screen.getByText(/puissance nominale maximale/i)).toBeInTheDocument()
  })

  it('la recherche filtre la liste (aucun appel réseau, purement local)', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.type(screen.getByLabelText('Rechercher un terme du lexique'), 'FEC')
    expect(screen.getByText(/FEC \(fichier des écritures comptables\)/)).toBeInTheDocument()
    expect(screen.queryByText(/^kWc/)).not.toBeInTheDocument()
  })

  it('une recherche sans résultat affiche un message clair (jamais une liste vide silencieuse)', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.type(screen.getByLabelText('Rechercher un terme du lexique'), 'zzz-inexistant')
    expect(screen.getByText(/Aucun terme ne correspond/)).toBeInTheDocument()
  })
})
