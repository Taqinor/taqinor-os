// AGR134 — marge indicative PARTIELLE : une ligne chiffrée sans prix d'achat
// (pompe générique, prix d'achat 0) sort du coût ; le rail le DIT et masque le
// pourcentage. Tests EXÉCUTÉS : `computeBuyCostDetail` (vraie fonction du
// générateur) alimente le vrai `RailArgent`, comme dans DevisGenerator.
//
// Run : npx vitest run src/pages/ventes/generator/RailArgent.margePartielle.test.jsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'

import RailArgent from './RailArgent'
import { computeBuyCostDetail, computeBuyCost } from '../../../features/ventes/solar'

const PRODUITS = [
  { id: 1, nom: 'Panneau 710W', prix_achat: '800', prix_vente: '1000', taux_tva: 20 },
  { id: 2, nom: 'Pompe immergée OSP 30/8', prix_achat: '0', prix_vente: '9000', taux_tva: 20 },
]
const LIGNE_PANNEAU = { produit: '1', quantite: 10, prix_unit_ttc: 1200 }
const LIGNE_POMPE = { produit: '2', quantite: 1, prix_unit_ttc: 10800 }

function rendre(lines) {
  const kpiTotal = lines.reduce((t, l) => t + l.quantite * l.prix_unit_ttc, 0)
  const detail = computeBuyCostDetail(lines, PRODUITS)
  const marge = detail.cost != null ? Math.round(kpiTotal - detail.cost) : null
  const totals = { totalSansBrut: kpiTotal, totalAvecBrut: kpiTotal, totalSans: kpiTotal, totalAvec: kpiTotal }
  return render(
    <RailArgent
      showSans showAvec={false} sansRec={false} avecRec={false} totals={totals}
      discountPct="0" setDiscountPct={() => {}} remiseMax=""
      tauxTva="20" setTauxTva={() => {}}
      pkwc={null} prixCible="" setPrixCible={() => {}} applyPrixCible={() => {}} kwp={0}
      marge={marge} kpiTotal={kpiTotal} margeLignesSansAchat={detail.sansAchat}
    />,
  )
}

describe('AGR134 — marge partielle', () => {
  it('computeBuyCostDetail compte les lignes chiffrées sans prix d\'achat', () => {
    expect(computeBuyCostDetail([LIGNE_PANNEAU, LIGNE_POMPE], PRODUITS).sansAchat).toBe(1)
    expect(computeBuyCostDetail([LIGNE_PANNEAU], PRODUITS).sansAchat).toBe(0)
    // Une ligne à prix 0 (placeholder « prix à renseigner ») n'est pas « chiffrée ».
    expect(computeBuyCostDetail([LIGNE_PANNEAU, { produit: '', quantite: 1, prix_unit_ttc: 0 }],
      PRODUITS).sansAchat).toBe(0)
    // Appelants inchangés : computeBuyCost rend toujours le seul coût.
    expect(computeBuyCost([LIGNE_PANNEAU], PRODUITS)).toBe(Math.round(10 * 800 * 1.2))
  })

  it('devis avec une pompe sans prix d\'achat → « marge partielle : 1 ligne », pas de %', () => {
    rendre([LIGNE_PANNEAU, LIGNE_POMPE])
    expect(screen.getByTestId('marge-partielle').textContent)
      .toBe('marge partielle : 1 ligne sans prix d\'achat')
    expect(screen.getByText('Marge indicative (interne)').parentElement.textContent).not.toMatch(/%/)
  })

  it('devis complet → affichage inchangé (pourcentage, pas de réserve)', () => {
    rendre([LIGNE_PANNEAU])
    expect(screen.queryByTestId('marge-partielle')).toBeNull()
    expect(screen.getByText('Marge indicative (interne)').parentElement.textContent).toMatch(/\(\d+ %\)/)
  })
})
