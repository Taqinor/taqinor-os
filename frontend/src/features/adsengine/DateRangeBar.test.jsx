import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import DateRangeBar from './DateRangeBar'

/* PUB40 — barre de sélection de période (composant CONTRÔLÉ, aucun state
   local hormis ce que le parent lui passe via `value`/`onChange`). */

describe('DateRangeBar', () => {
  it('un clic sur un preset résout ses dates et les remonte au parent', () => {
    const onChange = vi.fn()
    render(<DateRangeBar value={{ preset: '30j', debut: '', fin: '' }} onChange={onChange} />)
    fireEvent.click(screen.getByTestId('ae-daterange-preset-hier'))
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ preset: 'hier' }))
    const call = onChange.mock.calls[0][0]
    expect(call.debut).toBe(call.fin) // « hier » = un seul jour
  })

  it('« Personnalisé » affiche deux champs de date, sans résolution auto', () => {
    const onChange = vi.fn()
    render(<DateRangeBar value={{ preset: '30j', debut: '', fin: '' }} onChange={onChange} />)
    fireEvent.click(screen.getByTestId('ae-daterange-preset-personnalise'))
    expect(onChange).toHaveBeenCalledWith({
      preset: 'personnalise', debut: '', fin: '', compare: false,
    })
  })

  it('saisie des dates personnalisées remonte les valeurs au parent', () => {
    const onChange = vi.fn()
    render(<DateRangeBar value={{ preset: 'personnalise', debut: '', fin: '' }} onChange={onChange} />)
    fireEvent.change(screen.getByTestId('ae-daterange-debut'), { target: { value: '2026-07-01' } })
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ preset: 'personnalise', debut: '2026-07-01' }))
    fireEvent.change(screen.getByTestId('ae-daterange-fin'), { target: { value: '2026-07-05' } })
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ preset: 'personnalise', fin: '2026-07-05' }))
  })

  it('case « comparer » désactivée tant qu’aucune période n’est résolue', () => {
    render(<DateRangeBar value={{ preset: 'personnalise', debut: '', fin: '' }} onChange={() => {}} />)
    expect(screen.getByTestId('ae-daterange-compare')).toBeDisabled()
  })

  it('case « comparer » activable une fois debut/fin résolus, remonte le flag', () => {
    const onChange = vi.fn()
    render(<DateRangeBar value={{ preset: '7j', debut: '2026-07-13', fin: '2026-07-19' }} onChange={onChange} />)
    const checkbox = screen.getByTestId('ae-daterange-compare')
    expect(checkbox).not.toBeDisabled()
    fireEvent.click(checkbox)
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ compare: true }))
  })

  it('affiche un résumé de la période résolue', () => {
    render(<DateRangeBar value={{ preset: '7j', debut: '2026-07-13', fin: '2026-07-19' }} onChange={() => {}} />)
    expect(screen.getByTestId('ae-daterange-summary')).toHaveTextContent('2026-07-13 → 2026-07-19')
  })

  it('un jour unique résume une seule date (pas de flèche)', () => {
    render(<DateRangeBar value={{ preset: 'hier', debut: '2026-07-18', fin: '2026-07-18' }} onChange={() => {}} />)
    expect(screen.getByTestId('ae-daterange-summary')).toHaveTextContent('2026-07-18')
    expect(screen.getByTestId('ae-daterange-summary')).not.toHaveTextContent('→')
  })

  it('valeur par défaut absente -> ne casse pas (repli 30j)', () => {
    render(<DateRangeBar onChange={() => {}} />)
    expect(screen.getByTestId('ae-daterange-preset-30j')).toHaveAttribute('aria-pressed', 'true')
  })

  // ── FIXPUB2 — preset « Tout » (aucune borne) ────────────────────────────
  it('« Tout » résout des bornes VIDES (jamais une erreur, jamais null déréférencé)', () => {
    const onChange = vi.fn()
    render(<DateRangeBar value={{ preset: '30j', debut: '', fin: '' }} onChange={onChange} />)
    fireEvent.click(screen.getByTestId('ae-daterange-preset-tout'))
    expect(onChange).toHaveBeenCalledWith({ preset: 'tout', debut: '', fin: '', compare: false })
  })

  it('« Tout » sélectionné -> pas de résumé de période, comparaison désactivée', () => {
    render(<DateRangeBar value={{ preset: 'tout', debut: '', fin: '' }} onChange={() => {}} />)
    expect(screen.queryByTestId('ae-daterange-summary')).toBeNull()
    expect(screen.getByTestId('ae-daterange-compare')).toBeDisabled()
  })
})
