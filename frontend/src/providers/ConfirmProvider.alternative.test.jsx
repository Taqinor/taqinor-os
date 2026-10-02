// QJR570 — la confirmation de recomposition offre « garder » ET « prendre N
// (recalculé) » : le provider rend true / 'alternative' / false.
// Run : npx vitest run src/providers/ConfirmProvider.alternative.test.jsx
import { useEffect } from 'react'
import { describe, it, expect } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import ConfirmProvider from './ConfirmProvider'
import { useConfirm } from './confirm-context'

const sonde = { demander: null }
function Sonde() {
  const confirm = useConfirm()
  useEffect(() => { sonde.demander = confirm }, [confirm])
  return null
}
const demander = (options) => sonde.demander(options)

const OPTIONS = {
  title: 'Garder vos saisies ?',
  confirmLabel: 'Recomposer en les gardant',
  alternativeLabel: 'Prendre N (recalculé)',
}

function monter() {
  render(<ConfirmProvider><Sonde /></ConfirmProvider>)
}

describe('QJR570 — confirmation à trois issues', () => {
  it('« Recomposer en les gardant » → true', async () => {
    monter()
    let p
    await act(async () => { p = demander(OPTIONS) })
    expect(screen.getByRole('button', { name: 'Prendre N (recalculé)' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Recomposer en les gardant' }))
    expect(await p).toBe(true)
  })

  it('« Prendre N (recalculé) » → "alternative"', async () => {
    monter()
    let p
    await act(async () => { p = demander(OPTIONS) })
    await userEvent.click(screen.getByRole('button', { name: 'Prendre N (recalculé)' }))
    expect(await p).toBe('alternative')
  })

  it('« Annuler » → false ; sans alternativeLabel, pas de troisième bouton', async () => {
    monter()
    let p
    await act(async () => { p = demander(OPTIONS) })
    await userEvent.click(screen.getByRole('button', { name: 'Annuler' }))
    expect(await p).toBe(false)
    await act(async () => { p = demander({ title: 'Simple' }) })
    expect(screen.queryByRole('button', { name: /Prendre N/ })).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Annuler' }))
    expect(await p).toBe(false)
  })
})
