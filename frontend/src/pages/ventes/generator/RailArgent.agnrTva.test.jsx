// AGNR28 (C-AGNR-021) — le Rail d'argent ne propose plus de champ « TVA % »
// qui ne changeait aucun total (chaque ligne porte son taux) : il dit « TVA :
// par ligne (voir la table) ». Le total final reste celui des taux de ligne.
//
// Rendu RÉEL de `RailArgent`, totaux du vrai `optionTotalsTTC` (taux de ligne).
// Run : npx vitest run src/pages/ventes/generator/RailArgent.agnrTva.test.jsx
import { useState } from 'react'
import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

import RailArgent from './RailArgent'
import { formatMoney } from '../../../features/ventes/solar'
import { lignesRemiseesParPanier, optionTotalsTTC } from '../../../features/ventes/calc/totaux.js'

const L = (designation, quantite, ttc, taux = '20') => ({
  designation, quantite: String(quantite), prix_unit_ttc: String(ttc), taux_tva: taux,
})
const KIT = [
  L('Panneau Canadien Solar 710W', 8, 1320, '10'),
  L('Onduleur réseau Huawei 5kW', 1, 10800),
]

describe('AGNR28 — TVA par ligne, aucun champ d’en-tête au rail', () => {
  it('aucun champ « TVA % » saisissable ; l’indication « par ligne » est présente ; total inchangé', () => {
    const totals = optionTotalsTTC(KIT, 5)
    const { container } = render(
      <RailArgent
        showSans showAvec={false} sansRec={false} avecRec={false} totals={totals}
        discountPct="5" setDiscountPct={() => {}} remiseMax=""
        pkwc={null} prixCible="" setPrixCible={() => {}} applyPrixCible={() => {}} kwp={0}
        marge={null} kpiTotal={totals.totalSans} remiseParPanier={lignesRemiseesParPanier(KIT, 5)}
      />,
    )
    expect(screen.getByTestId('rail-tva-par-ligne').textContent).toContain('TVA : par ligne (voir la table)')
    // Les seuls champs nombre du rail : remise et prix cible — plus de TVA.
    const champs = [...container.querySelectorAll('input[inputmode="decimal"]')]
    expect(champs).toHaveLength(2)
    expect(container.querySelectorAll('input[type="number"]')).toHaveLength(0)
    expect(screen.getByText('Total final SANS batterie')).toBeInTheDocument()
    expect(container.textContent).toContain(formatMoney(totals.totalSans))
  })
})

// R1-09 (recette 22/11, décision Q1) — « 12,5 » dans la remise d'un Chrome en
// anglais devenait 125 (total à 200 MAD sans un mot). Le champ lit la virgule.
describe('R1-09 — remise tapée à la française', () => {
  function RailVivant() {
    const [remise, setRemise] = useState('')
    const totals = optionTotalsTTC(KIT, parseFloat(remise) || 0)
    return (
      <RailArgent
        showSans showAvec={false} sansRec={false} avecRec={false} totals={totals}
        discountPct={remise} setDiscountPct={setRemise} remiseMax=""
        pkwc={null} prixCible="" setPrixCible={() => {}} applyPrixCible={() => {}} kwp={0}
        marge={null} kpiTotal={totals.totalSans}
      />
    )
  }

  it('« 12,5 » → remise de 12,5 % (jamais 125 %), texte tapé laissé tel quel', () => {
    const { container } = render(<RailVivant />)
    const remise = container.querySelector('input.gen-discount-input')
    fireEvent.change(remise, { target: { value: '12,5' } })
    expect(remise.value).toBe('12,5')
    expect(container.textContent).toContain(formatMoney(optionTotalsTTC(KIT, 12.5).totalSans))
    expect(container.textContent).not.toContain(formatMoney(optionTotalsTTC(KIT, 125).totalSans))
  })
})
