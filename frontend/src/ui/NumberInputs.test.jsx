import { describe, it, expect } from 'vitest'
import { useState } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { axe } from 'vitest-axe'
import { CurrencyInput, PercentInput, NumberInput } from './NumberInputs'

/* RÈGLE FONDATRICE (cf. CLAUDE.md / générateur de devis) : l'écran de devis est
   100 % TTC et ne doit JAMAIS « snap »/rejeter/reformater un nombre tapé. Ces
   primitifs s'appuient sur type="text" + inputMode="decimal" exprès. Ce test
   garde ce contrat côté composant (le pendant du garde-fou côté formulaire). */
function CtrlCurrency() {
  const [v, setV] = useState('')
  return <CurrencyInput aria-label="montant" value={v} onChange={(e) => setV(e.target.value)} />
}

function CtrlNumber() {
  const [v, setV] = useState('')
  return <NumberInput aria-label="montant" value={v} onChange={(e) => setV(e.target.value)} />
}

function CtrlPercent() {
  const [v, setV] = useState('')
  return <PercentInput aria-label="montant" value={v} onChange={(e) => setV(e.target.value)} />
}

describe('NumberInputs — saisie sans perte', () => {
  it('CurrencyInput conserve les décimales tapées telles quelles (aucun snapping)', async () => {
    render(<CtrlCurrency />)
    const input = screen.getByLabelText('montant')
    await userEvent.type(input, '1234.567')
    expect(input).toHaveValue('1234.567')
  })

  it('garde une décimale partielle comme « 12. » (pas de reformatage en cours de frappe)', async () => {
    render(<CtrlNumber />)
    const input = screen.getByLabelText('montant')
    await userEvent.type(input, '12.')
    expect(input).toHaveValue('12.')
  })

  it('utilise type=text + inputMode=decimal pour que le navigateur ne rejette rien', () => {
    render(<CtrlPercent />)
    const input = screen.getByLabelText('montant')
    expect(input).toHaveAttribute('type', 'text')
    expect(input).toHaveAttribute('inputmode', 'decimal')
  })

  it("n'a aucune violation d'accessibilité quand le champ est étiqueté", async () => {
    const { container } = render(
      <CurrencyInput aria-label="Montant TTC" defaultValue="1000" onChange={() => {}} />,
    )
    const results = await axe(container)
    expect(results.violations).toEqual([])
  })
})
