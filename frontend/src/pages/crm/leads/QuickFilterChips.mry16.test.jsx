// MRY16 — deux nouvelles chips du moteur de relances : « Touche due »
// (prochaine_touche_at posé) et « ≥ 7 tentatives » (nb_tentatives), lues
// directement sur les champs déjà présents sur le lead (MRY5/MRY20) — AUCUN
// appel réseau supplémentaire (invariant D6-I7).
import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import QuickFilterChips from './QuickFilterChips'
import { EMPTY_FILTERS } from '../../../features/crm/stages'

afterEach(() => cleanup())

const LEADS = [
  { id: 1, nom: 'A', prochaine_touche_at: '2026-09-06T09:33:00Z', nb_tentatives: 2 },
  { id: 2, nom: 'B', prochaine_touche_at: null, nb_tentatives: 7 },
  { id: 3, nom: 'C', prochaine_touche_at: '2026-09-07T09:00:00Z', nb_tentatives: 8 },
]

describe('MRY16 QuickFilterChips — touche due / tentatives', () => {
  it('affiche « Touche due » avec le bon compte', () => {
    render(
      <QuickFilterChips leads={LEADS} filters={EMPTY_FILTERS} setFilters={vi.fn()} myUsername="meryem" />,
    )
    const chip = screen.getByRole('button', { name: /Touche due/ })
    expect(chip).toBeInTheDocument()
    expect(chip).toHaveTextContent('2') // leads 1 et 3
  })

  it('affiche « ≥ 7 tentatives » avec le bon compte', () => {
    render(
      <QuickFilterChips leads={LEADS} filters={EMPTY_FILTERS} setFilters={vi.fn()} myUsername="meryem" />,
    )
    const chip = screen.getByRole('button', { name: /≥ 7 tentatives/ })
    expect(chip).toBeInTheDocument()
    expect(chip).toHaveTextContent('2') // leads 2 et 3
  })

  it('clic sur « Touche due » bascule filters.touche', () => {
    const setFilters = vi.fn()
    render(
      <QuickFilterChips leads={LEADS} filters={EMPTY_FILTERS} setFilters={setFilters} myUsername="meryem" />,
    )
    fireEvent.click(screen.getByRole('button', { name: /Touche due/ }))
    const updater = setFilters.mock.calls[0][0]
    expect(updater(EMPTY_FILTERS)).toMatchObject({ touche: 'due' })
    // Un second clic désactive (toggle) — jamais un état bloqué.
    expect(updater({ ...EMPTY_FILTERS, touche: 'due' })).toMatchObject({ touche: '' })
  })

  it('clic sur « ≥ 7 tentatives » bascule filters.tentatives', () => {
    const setFilters = vi.fn()
    render(
      <QuickFilterChips leads={LEADS} filters={EMPTY_FILTERS} setFilters={setFilters} myUsername="meryem" />,
    )
    fireEvent.click(screen.getByRole('button', { name: /≥ 7 tentatives/ }))
    const updater = setFilters.mock.calls[0][0]
    expect(updater(EMPTY_FILTERS)).toMatchObject({ tentatives: '7plus' })
  })

  it('« Touche due » pressée (aria-pressed) quand le filtre est actif', () => {
    render(
      <QuickFilterChips
        leads={LEADS} filters={{ ...EMPTY_FILTERS, touche: 'due' }}
        setFilters={vi.fn()} myUsername="meryem"
      />,
    )
    expect(screen.getByRole('button', { name: /Touche due/ })).toHaveAttribute('aria-pressed', 'true')
  })
})
