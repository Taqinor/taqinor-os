// ATOT25 — le rail DIT l'« Arrondi commercial » : Σ des lignes remisées
// (au centime, comme le PDF) + arrondi = « Total final ». Le vrai
// `lignesRemiseesParPanier` (solar.js) alimente le vrai `RailArgent`, comme
// dans DevisGenerator — aucun mock.
//
// Run : npx vitest run src/pages/ventes/generator/RailArgent.test.jsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'

import RailArgent from './RailArgent'
import { lignesRemiseesParPanier, optionTotalsTTC, formatMoney } from '../../../features/ventes/solar'

const L = (designation, quantite, ttc, taux = '20') => ({
  designation, quantite: String(quantite), prix_unit_ttc: String(ttc), taux_tva: taux,
})
const KIT = [
  L('Panneau Canadien Solar 710W', 24, 1481, '10'),
  L('Onduleur réseau Huawei 10kW', 1, 13999),
  L('Structures acier', 1, 4351),
]

function rendre(remise) {
  const totals = optionTotalsTTC(KIT, remise)
  const parPanier = lignesRemiseesParPanier(KIT, remise)
  render(
    <RailArgent
      showSans showAvec={false} sansRec={false} avecRec={false} totals={totals}
      discountPct={String(remise)} setDiscountPct={() => {}} remiseMax=""
      tauxTva="20" setTauxTva={() => {}}
      pkwc={null} prixCible="" setPrixCible={() => {}} applyPrixCible={() => {}} kwp={0}
      marge={null} kpiTotal={totals.totalSans} remiseParPanier={parPanier}
    />,
  )
  return { totals, parPanier }
}

describe('ATOT25 — arrondi commercial au rail', () => {
  it('affiche l arrondi commercial', () => {
    const { parPanier } = rendre(7)
    const ligne = screen.getByTestId('arrondi-commercial-sans')
    expect(ligne.textContent).toContain('Arrondi commercial')
    expect(ligne.textContent).toContain(formatMoney(parPanier.sans.arrondi))
  })

  it('somme lignes + arrondi = total', () => {
    const { totals, parPanier } = rendre(7)
    const somme = parPanier.parLigne.reduce((s, v) => s + Math.round(v * 100), 0)
    expect(somme + Math.round(parPanier.sans.arrondi * 100)).toBe(Math.round(totals.totalSans * 100))
    expect(totals.totalSans).toBe(50100)
    expect(screen.getByText('Total final SANS batterie')).toBeInTheDocument()
  })

  it('aucun arrondi ⇒ aucune ligne d’arrondi', () => {
    render(
      <RailArgent
        showSans showAvec={false} sansRec={false} avecRec={false}
        totals={{ totalSansBrut: 100, totalAvecBrut: 100, totalSans: 100, totalAvec: 100 }}
        discountPct="0" setDiscountPct={() => {}} remiseMax=""
        tauxTva="20" setTauxTva={() => {}}
        pkwc={null} prixCible="" setPrixCible={() => {}} applyPrixCible={() => {}} kwp={0}
        marge={null} kpiTotal={100}
        remiseParPanier={{ sans: { arrondi: 0 }, avec: { arrondi: 0 } }}
      />,
    )
    expect(screen.queryByTestId('arrondi-commercial-sans')).toBeNull()
  })
})
