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

/* NTI18N6 — en contexte RTL (arabe), un montant reste lisible de GAUCHE à
   DROITE (convention universelle des chiffres) : le champ natif porte
   `dir="ltr"` EXPLICITE, indépendamment de la direction ambiante posée sur
   un ancêtre (`<html dir="rtl">` en pratique, simulé ici par un conteneur
   `dir="rtl"`). L'alignement VISUEL (`text-right`, le conteneur) reste lui
   physique — les deux ne se contredisent pas : un champ peut se lire de
   gauche à droite tout en étant aligné à droite dans son conteneur. */
describe('NTI18N6 — chiffres LTR même en contexte RTL', () => {
  it('CurrencyInput affiche un montant lisible de gauche à droite, aligné à droite', () => {
    render(
      <div dir="rtl">
        <CurrencyInput aria-label="montant" defaultValue="1 234,50" onChange={() => {}} />
      </div>,
    )
    const input = screen.getByLabelText('montant')
    // Lecture gauche→droite du contenu du champ, quelle que soit la
    // direction ambiante RTL du conteneur englobant.
    expect(input).toHaveAttribute('dir', 'ltr')
    expect(input).toHaveValue('1 234,50')
    // Alignement visuel du conteneur : toujours à droite (convention
    // numérique universelle, cf. NTI18N1 — jamais inversé en RTL).
    expect(input.className).toContain('text-right')
  })

  it('NumberInput et PercentInput portent aussi dir="ltr"', () => {
    render(
      <div dir="rtl">
        <NumberInput aria-label="nombre" value="" onChange={() => {}} />
        <PercentInput aria-label="pourcentage" value="" onChange={() => {}} />
      </div>,
    )
    expect(screen.getByLabelText('nombre')).toHaveAttribute('dir', 'ltr')
    expect(screen.getByLabelText('pourcentage')).toHaveAttribute('dir', 'ltr')
  })
})
