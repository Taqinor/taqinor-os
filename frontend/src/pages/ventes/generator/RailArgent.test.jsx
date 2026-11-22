// ATOT25 — le rail DIT l'« Arrondi commercial » : Σ des lignes remisées
// (au centime, comme le PDF) + arrondi = « Total final ». Le vrai
// `lignesRemiseesParPanier` (solar.js) alimente le vrai `RailArgent`, comme
// dans DevisGenerator — aucun mock.
//
// Run : npx vitest run src/pages/ventes/generator/RailArgent.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

import RailArgent from './RailArgent'
import CarteParametresTechniques from './CarteParametresTechniques'
import { formatMoney } from '../../../features/ventes/solar'
import { lignesRemiseesParPanier, optionTotalsTTC } from '../../../features/ventes/calc/totaux.js'

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

describe('AGV10 — rail agricole sans mot batterie', () => {
  it('prop agricole : Total TTC, aucun libellé batterie', () => {
    const totals = optionTotalsTTC(KIT, 7)
    const { container } = render(
      <RailArgent
        agricole showSans showAvec={false} sansRec={false} avecRec={false} totals={totals}
        discountPct="7" setDiscountPct={() => {}} remiseMax=""
        pkwc={null} prixCible="" setPrixCible={() => {}} applyPrixCible={() => {}} kwp={0}
        marge={null} kpiTotal={totals.totalSans} remiseParPanier={lignesRemiseesParPanier(KIT, 7)}
      />,
    )
    expect(container.textContent).toContain('Total TTC')
    expect(container.textContent).toContain('Total final TTC')
    expect(container.textContent).not.toMatch(/batterie/i)
  })

  it('prop agricole avec showAvec : aucun libellé AVEC batterie', () => {
    const totals = optionTotalsTTC(KIT, 7)
    const { container } = render(
      <RailArgent
        agricole showSans showAvec avecRec={false} sansRec={false} totals={totals}
        discountPct="7" setDiscountPct={() => {}} remiseMax=""
        pkwc={null} prixCible="" setPrixCible={() => {}} applyPrixCible={() => {}} kwp={0}
        marge={null} kpiTotal={totals.totalSans} remiseParPanier={lignesRemiseesParPanier(KIT, 7)}
      />,
    )
    expect(container.textContent).not.toMatch(/batterie/i)
  })
})

// R1-09 / R1-10 (recette 22/11/2026) — les trois champs de dimensionnement de la carte
// « Paramètres Techniques » lisent la VIRGULE française, comme les champs du rail : « 5,5 » kWc
// vaut 5,5 (un champ natif « number » d'un Chrome en anglais en faisait 55).
function rendreCarte(surcharge = {}) {
  const props = {
    kwcCible: '', onKwcCibleChange: vi.fn(), nbPanneaux: '', onNbPanneauxChange: vi.fn(),
    panelW: '710', dispatchSizing: vi.fn(), kwp: 0, panneauxLignes: 0, produits: [],
    structureProduitId: '', structureType: 'acier', sizingInfo: null,
    modeInstallation: 'residentiel', showSans: true, deuxValeursDim: {}, showAvec: false,
    sizingServeurMessage: '', dayUsage: 60, errors: {}, pompageManquants: [],
    autoFillLoading: false, marcheCi: false, fHiver: '', recalculerDimensionnement: vi.fn(),
    avecQuantitesFigees: vi.fn(), handleAutoFill: vi.fn(), compositionErreur: '',
    editDevis: null, leadValeursModifiees: [], setLeadValeursModifiees: vi.fn(),
    clear: vi.fn(), setRechargeEdit: vi.fn(), onduleursIncomplets: [],
    pompageAutoFilled: false, apercuPompage: null,
    ...surcharge,
  }
  render(<CarteParametresTechniques {...props} />)
  return props
}

describe('R1-09 — CarteParametresTechniques : virgule française', () => {
  it('« 5,5 » dans la puissance cible ⇒ 5,5 kWc (jamais 55)', () => {
    const p = rendreCarte()
    fireEvent.change(screen.getByTestId('gen-kwc-cible'), { target: { value: '5,5' } })
    expect(p.onKwcCibleChange).toHaveBeenLastCalledWith('5.5')
  })

  it('« 12,0 » dans le nombre de panneaux ⇒ 12 (la virgule est lue, jamais avalée)', () => {
    const p = rendreCarte()
    fireEvent.change(document.getElementById('gen-nbpanneaux'), { target: { value: '12,0' } })
    expect(p.onNbPanneauxChange).toHaveBeenLastCalledWith('12')
  })

  it('« 550,5 » dans la puissance du panneau ⇒ 550.5 envoyé au reducer', () => {
    const p = rendreCarte()
    fireEvent.change(document.getElementById('gen-panelw'), { target: { value: '550,5' } })
    expect(p.dispatchSizing).toHaveBeenLastCalledWith({ type: 'SAISI', champ: 'panelW', valeur: '550.5' })
  })

  it('les trois champs sont du texte à clavier décimal, sans borne ni pas', () => {
    rendreCarte()
    for (const id of ['gen-kwc-cible', 'gen-nbpanneaux', 'gen-panelw']) {
      const el = document.getElementById(id)
      expect(el.getAttribute('type')).toBe('text')
      expect(el.getAttribute('inputmode')).toBe('decimal')
      expect(el.hasAttribute('min')).toBe(false)
      expect(el.hasAttribute('max')).toBe(false)
    }
  })
})
