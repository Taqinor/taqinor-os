import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { axe } from 'vitest-axe'
import { Table } from './Table.jsx'

/* J146 — Primitif de tableau partagé du reporting. */
describe('Table (primitif reporting J146)', () => {
  const columns = [
    { key: 'client', header: 'Client', cell: (r) => r.client },
    { key: 'total', header: 'Total', align: 'right', cell: (r) => `${r.total} DH` },
  ]
  const rows = [
    { client: 'ACME', total: 1000 },
    { client: 'Globex', total: 2000 },
  ]

  it('rend en-têtes et lignes', () => {
    render(<Table columns={columns} rows={rows} aria-label="Créances" />)
    expect(screen.getByRole('columnheader', { name: 'Client' })).toBeInTheDocument()
    expect(screen.getByText('ACME')).toBeInTheDocument()
    expect(screen.getByText('2000 DH')).toBeInTheDocument()
  })

  it('passe l\'index à cell()', () => {
    render(
      <Table
        columns={[{ key: 'n', header: 'N°', cell: (r, i) => `#${i}` }]}
        rows={rows}
        aria-label="Index"
      />,
    )
    expect(screen.getByText('#0')).toBeInTheDocument()
    expect(screen.getByText('#1')).toBeInTheDocument()
  })

  it('affiche l\'état vide quand rows est vide', () => {
    render(<Table columns={columns} rows={[]} empty={<span>Rien à afficher</span>} aria-label="Vide" />)
    expect(screen.getByText('Rien à afficher')).toBeInTheDocument()
  })

  it('enveloppe la table dans un conteneur scrollable (overflow-x-auto)', () => {
    const { container } = render(<Table columns={columns} rows={rows} aria-label="Scroll" />)
    expect(container.querySelector('.overflow-x-auto')).toBeTruthy()
  })

  it("n'a aucune violation d'accessibilité détectable", async () => {
    const { container } = render(
      <Table columns={columns} rows={rows} aria-label="Créances" caption="Table des créances" />,
    )
    const results = await axe(container)
    expect(results.violations).toEqual([])
  })
})
