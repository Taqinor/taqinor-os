import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import {
  StatutContrat, CONTRAT_STATUS, CONTRAT_STATUS_ORDER,
  StatutRetenue, StatutPiece,
} from './status'
import StateMachine from './StateMachine'

/* Tests du module Contrats (UX34–UX37) : cohérence des maps statut→ton +
   rendu smoke de la machine d'états. On enveloppe dans MemoryRouter +
   ThemeProvider comme le kit UX1. */

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('CONTRAT_STATUS map', () => {
  it('mappe chaque statut backend vers le bon ton', () => {
    expect(StatutContrat.toneOf('brouillon')).toBe('neutral')
    expect(StatutContrat.toneOf('en_approbation')).toBe('info')
    expect(StatutContrat.toneOf('signe')).toBe('info')
    expect(StatutContrat.toneOf('actif')).toBe('success')
    expect(StatutContrat.toneOf('suspendu')).toBe('warning')
    expect(StatutContrat.toneOf('resilie')).toBe('danger')
    expect(StatutContrat.toneOf('expire')).toBe('warning')
  })

  it('couvre exactement les 7 statuts canoniques dans l’ordre du cycle de vie', () => {
    expect(CONTRAT_STATUS_ORDER).toEqual([
      'brouillon', 'en_approbation', 'signe', 'actif', 'suspendu', 'resilie', 'expire',
    ])
    // Chaque clé de l'ordre existe dans la map (pas de statut inventé/oublié).
    for (const key of CONTRAT_STATUS_ORDER) {
      expect(CONTRAT_STATUS[key]).toBeTruthy()
    }
    expect(Object.keys(CONTRAT_STATUS)).toHaveLength(CONTRAT_STATUS_ORDER.length)
  })

  it('mappe les statuts financiers (retenue, pièce)', () => {
    expect(StatutRetenue.toneOf('liberee')).toBe('success')
    expect(StatutPiece.toneOf('manquante')).toBe('danger')
    expect(StatutPiece.toneOf('validee')).toBe('success')
  })
})

describe('StatutContrat pill', () => {
  it('affiche le libellé français du statut', () => {
    withProviders(<StatutContrat status="actif" />)
    expect(screen.getByText('Actif')).toBeInTheDocument()
  })
})

describe('StateMachine', () => {
  it('rend tous les états du cycle de vie et met en avant le courant', () => {
    withProviders(<StateMachine statut="actif" />)
    // Le libellé de l'état courant apparaît (via la pastille).
    expect(screen.getByText('Actif')).toBeInTheDocument()
    // Un état non-courant apparaît en libellé texte simple.
    expect(screen.getByText('Brouillon')).toBeInTheDocument()
    expect(screen.getByText('Expiré')).toBeInTheDocument()
  })
})
