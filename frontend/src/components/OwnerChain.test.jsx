// VX216(c) — OwnerChain : chaîne de responsabilité cliquable, Lead · Devis ·
// Chantier · SAV, deep-links réels (patron VX79). Un maillon sans donnée
// n'apparaît jamais comme un lien mort.
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import OwnerChain from './OwnerChain'

function wrap(ui) {
  return <MemoryRouter>{ui}</MemoryRouter>
}

describe('OwnerChain (VX216c)', () => {
  it('rend un maillon par entité fournie, dans l\'ordre Lead · Devis · Chantier · SAV', () => {
    render(wrap(
      <OwnerChain
        lead={{ id: 1, nom: 'Amine K.' }}
        devis={{ id: 2, nom: 'DEV-2026-07-0002' }}
        chantier={{ id: 3, nom: 'CH-2026-07-0003' }}
        sav={{ id: 4, nom: 'SAV-2026-07-0004' }}
      />,
    ))
    const links = screen.getAllByRole('link')
    expect(links).toHaveLength(4)
    expect(links[0]).toHaveAttribute('href', '/crm/leads?lead=1')
    expect(links[1]).toHaveAttribute('href', '/ventes/devis?devis=2')
    expect(links[2]).toHaveAttribute('href', '/chantiers?id=3')
    expect(links[3]).toHaveAttribute('href', '/sav?id=4')
  })

  it('omet les maillons sans donnée (jamais un lien mort)', () => {
    render(wrap(<OwnerChain devis={{ id: 2, nom: 'DEV-2026-07-0002' }} />))
    const links = screen.getAllByRole('link')
    expect(links).toHaveLength(1)
    expect(links[0]).toHaveAttribute('href', '/ventes/devis?devis=2')
  })

  it('ne rend rien du tout sans aucune entité', () => {
    const { container } = render(wrap(<OwnerChain />))
    expect(container).toBeEmptyDOMElement()
  })
})
