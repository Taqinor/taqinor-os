import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ContratStatutPill } from './ContratsMaintenance.jsx'

/* J144 — refonte SAV : les contrats de maintenance affichent leur statut via
   StatusPill. `ContratStatutPill` encode le mapping (inactif > visite due >
   à jour) ; la couleur n'est jamais le seul signal — le libellé FR reste. */

const DOT_CLASS = {
  neutral: 'bg-muted-foreground', success: 'bg-success', danger: 'bg-destructive',
}

describe('ContratStatutPill (J144 — statut contrat → ton + libellé FR)', () => {
  it('contrat inactif → point neutre, libellé « Inactif »', () => {
    const { container } = render(<ContratStatutPill contrat={{ actif: false }} />)
    expect(screen.getByText('Inactif')).toBeInTheDocument()
    expect(container.querySelector(`.${DOT_CLASS.neutral}`)).toBeTruthy()
  })

  it('contrat actif avec visite due → point danger, libellé « Visite due »', () => {
    const { container } = render(<ContratStatutPill contrat={{ actif: true, due: true }} />)
    expect(screen.getByText('Visite due')).toBeInTheDocument()
    expect(container.querySelector(`.${DOT_CLASS.danger}`)).toBeTruthy()
  })

  it('contrat actif à jour → point succès, libellé « À jour »', () => {
    const { container } = render(<ContratStatutPill contrat={{ actif: true, due: false }} />)
    expect(screen.getByText('À jour')).toBeInTheDocument()
    expect(container.querySelector(`.${DOT_CLASS.success}`)).toBeTruthy()
  })

  it('inactif l’emporte même si une visite est due', () => {
    render(<ContratStatutPill contrat={{ actif: false, due: true }} />)
    expect(screen.getByText('Inactif')).toBeInTheDocument()
  })
})
