// ATOT25 — le rail DIT l'« Arrondi commercial » : Σ des lignes remisées
// (au centime, comme le PDF) + arrondi = « Total final ». Le vrai
// `lignesRemiseesParPanier` (solar.js) alimente le vrai `RailArgent`, comme
// dans DevisGenerator — aucun mock.
//
// Run : npx vitest run src/pages/ventes/generator/RailArgent.test.jsx
import { useState } from 'react'
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

import RailArgent from './RailArgent'
import CarteParametresTechniques from './CarteParametresTechniques'
import ChampDecimal from './ChampDecimal'
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

// V3-02 (rejeu du 22/11/2026) — la cible kWc se re-remplit depuis les panneaux dès qu'elle est
// vide : le champ vidé PENDANT la frappe reste vide (« 5,5 » tapé ensuite devenait « 3.555,5 »).
function CibleQuiSeReremplit({ surValeur }) {
  const [valeur, setValeur] = useState('3.55')
  return (
    <ChampDecimal data-testid="cible" value={valeur}
      onValeur={(v) => { surValeur(v); setValeur(v === '' ? '3.55' : v) }} />
  )
}

describe('V3-02 — ChampDecimal : un champ vidé pendant la frappe n’est pas réécrit', () => {
  it('vider puis taper « 5,5 » donne 5,5 ; la valeur recalculée revient à la sortie d’un champ laissé vide', () => {
    const surValeur = vi.fn()
    render(<CibleQuiSeReremplit surValeur={surValeur} />)
    const champ = screen.getByTestId('cible')
    fireEvent.focus(champ)
    fireEvent.change(champ, { target: { value: '' } })
    expect(champ.value).toBe('')
    fireEvent.change(champ, { target: { value: '5,5' } })
    expect(champ.value).toBe('5,5')
    expect(surValeur).toHaveBeenLastCalledWith('5.5')
    fireEvent.change(champ, { target: { value: '' } })
    fireEvent.blur(champ)
    expect(champ.value).toBe('3.55')
  })
})

// T4-V2-018 — « Recommandé sans batterie : 6 panneaux · 3,30 kWc » (conseil du
// moteur) et, sur le même écran, la taille « Recommandé · Devis officiel ·
// 10 panneaux » (LE devis, définition fondateur des tailles) : deux choses
// différentes sous un même mot. Chacune son nom ; l'écran dit ce que le devis
// chiffre quand il diffère du conseil, et le geste qui chiffre le conseil.
describe('T4-V2-018 — CarteParametresTechniques : conseil du moteur et taille chiffrée', () => {
  const DIM = { sans: { nbPanneaux: 6, kwc: 3.3 }, avec: { nbPanneaux: 10, kwc: 5.5 } }
  const ligne = (designation, quantite, extra = {}) => ({ designation, quantite: String(quantite), ...extra })
  const carte = (lines) => rendreCarte({ panelW: '550', showAvec: true, deuxValeursDim: DIM, lines })

  it('les lignes communes chiffrent 10 panneaux dans les deux options : l’écart sans batterie est dit', () => {
    carte([ligne('Panneau mono 550W', 10), ligne('Onduleur réseau Huawei 3kW', 1, { variante: 'sans' }),
      ligne('Onduleur hybride Deye 5kW', 1, { variante: 'avec' }), ligne('Batterie lithium 5kWh', 1, { variante: 'avec' })])
    const bloc = screen.getByTestId('dimensionnement-deux-valeurs').textContent.replace(/\s/g, ' ')
    expect(bloc).toMatch(/Conseillé par le moteur, sans batterie : 6 panneaux · 3,30 kWc/)
    expect(bloc).toMatch(/Conseillé par le moteur, avec batterie : 10 panneaux · 5,50 kWc/)
    expect(screen.getByTestId('dimensionnement-ecart-sans').textContent.replace(/\s/g, ' '))
      .toMatch(/Ce devis chiffre 10 panneaux · 5,50 kWc dans l’option sans batterie .*« Recalculer le dimensionnement »/)
    expect(screen.queryByTestId('dimensionnement-ecart-avec')).toBeNull()
    expect(bloc).not.toMatch(/Recommandé/)
  })

  it('T4-X6-016 — un seul kWc par option : celui des LIGNES, jamais un wattage que le devis ne vend pas', () => {
    // Rejeu X6-r : le moteur conseille 4 (sans) et 7 (avec) panneaux sur SON wattage ;
    // le devis vend 4 × 550 W (sans) et 7 × 710 W (avec).
    rendreCarte({
      panelW: '710', kwp: 2.84, nbPanneaux: '4', showAvec: true,
      deuxValeursDim: { sans: { nbPanneaux: 4, kwc: 2.84 }, avec: { nbPanneaux: 7, kwc: 3.85 } },
      lines: [ligne('Panneau mono 550W', 4, { variante: 'sans' }),
        ligne('Panneau Canadien Solar 710W', 7, { variante: 'avec' })],
    })
    const bloc = screen.getByTestId('dimensionnement-deux-valeurs').textContent.replace(/\s/g, ' ')
    expect(bloc).toMatch(/sans batterie : 4 panneaux · 2,20 kWc/)
    expect(bloc).toMatch(/avec batterie : 7 panneaux · 4,97 kWc/)
    expect(bloc).not.toMatch(/2,84|3,85/)
    expect(document.querySelector('.gen-kwp').textContent).toBe('2,20 kWp')
  })

  it('R5A-N2 — compte saisi (6) ≠ conseil avec batterie (10) : l écran dit AVANT le geste ce qu Auto-remplir posera', () => {
    rendreCarte({ panelW: '550', nbPanneaux: '6', showAvec: true, deuxValeursDim: DIM, nbSaisiPourLesDeux: true })
    expect(screen.getByTestId('auto-remplir-avec-prevenu').textContent)
      .toMatch(/posera l'option avec batterie à 6 panneaux, pas aux 10 conseillés/)
  })

  it('R5A-N2 — rien de saisi, ou un seul compte : aucune phrase', () => {
    rendreCarte({ panelW: '550', nbPanneaux: '6', showAvec: true, deuxValeursDim: DIM })
    expect(screen.queryByTestId('auto-remplir-avec-prevenu')).toBeNull()
  })

  it('les lignes suivent le conseil : aucun écart affiché', () => {
    carte([ligne('Panneau mono 550W', 6), ligne('Panneau mono 550W', 4, { variante: 'avec' })])
    expect(screen.queryByTestId('dimensionnement-ecart-sans')).toBeNull()
    expect(screen.queryByTestId('dimensionnement-ecart-avec')).toBeNull()
  })
})

// T4-V1-003 — sous la table « TOTAL SANS BATTERIE 34 900 » (AVANT remise) et dans
// la carte de droite « Total sans batterie · TTC 33 900 » (après remise) : même nom,
// deux chiffres. Avec une remise, le brut s'appelle « … avant remise ».
describe('T4-V1-003 — rail : le total avant remise porte son nom', () => {
  const monter = (remise) => {
    const totals = optionTotalsTTC(KIT, remise)
    const { container } = render(
      <RailArgent
        showSans showAvec sansRec={false} avecRec={false} totals={totals}
        discountPct={String(remise)} setDiscountPct={() => {}} remiseMax=""
        pkwc={null} prixCible="" setPrixCible={() => {}} applyPrixCible={() => {}} kwp={0}
        marge={null} kpiTotal={totals.totalSans} remiseParPanier={lignesRemiseesParPanier(KIT, remise)}
      />,
    )
    return container
  }
  it('remise 3 % : « avant remise » sur le brut, « Total final » sur le remisé', () => {
    const c = monter(3)
    expect(screen.getByText('Total SANS batterie avant remise')).toBeInTheDocument()
    expect(screen.getByText('Total AVEC batterie avant remise')).toBeInTheDocument()
    expect(screen.getByText('Total final SANS batterie')).toBeInTheDocument()
    expect(c.textContent).not.toMatch(/Total SANS batterie(?! avant remise)\d/)
  })
  it('sans remise : un seul total, sans « avant remise »', () => {
    const c = monter(0)
    expect(c.textContent).not.toMatch(/avant remise/)
    expect(screen.getByText('Total SANS batterie')).toBeInTheDocument()
  })
})
