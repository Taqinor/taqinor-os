// R1-09 / R1-10 (recette 22/11/2026) — les trois champs de dimensionnement de
// la carte « Paramètres Techniques » lisent la VIRGULE française : « 5,5 » kWc
// vaut 5,5 (un champ natif « number » d'un Chrome en anglais en faisait 55).
// Aucun module de test n'existait pour cette carte (SPL55 l'a extraite sans
// test dédié) : celui-ci la rend avec des props minimales.
// Run : npx vitest run src/pages/ventes/generator/CarteParametresTechniques.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

import CarteParametresTechniques from './CarteParametresTechniques'

function rendre(surcharge = {}) {
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
    const p = rendre()
    fireEvent.change(screen.getByTestId('gen-kwc-cible'), { target: { value: '5,5' } })
    expect(p.onKwcCibleChange).toHaveBeenLastCalledWith('5.5')
  })

  it('« 12,0 » dans le nombre de panneaux ⇒ 12 (la virgule est lue, jamais avalée)', () => {
    const p = rendre()
    fireEvent.change(document.getElementById('gen-nbpanneaux'), { target: { value: '12,0' } })
    expect(p.onNbPanneauxChange).toHaveBeenLastCalledWith('12')
  })

  it('« 550,5 » dans la puissance du panneau ⇒ 550.5 envoyé au reducer', () => {
    const p = rendre()
    fireEvent.change(document.getElementById('gen-panelw'), { target: { value: '550,5' } })
    expect(p.dispatchSizing).toHaveBeenLastCalledWith({ type: 'SAISI', champ: 'panelW', valeur: '550.5' })
  })

  it('les trois champs sont du texte à clavier décimal, sans borne ni pas', () => {
    rendre()
    for (const id of ['gen-kwc-cible', 'gen-nbpanneaux', 'gen-panelw']) {
      const el = document.getElementById(id)
      expect(el.getAttribute('type')).toBe('text')
      expect(el.getAttribute('inputmode')).toBe('decimal')
      expect(el.hasAttribute('min')).toBe(false)
      expect(el.hasAttribute('max')).toBe(false)
    }
  })
})
