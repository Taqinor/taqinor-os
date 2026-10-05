import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* AGR108 — Paramètres › Devis : les trois réglages pompage d'AGR107 se
   saisissent SANS valeur par défaut. Un champ vide reste vide à l'écran et
   part `null` au serveur ; l'indication sourcée est affichée À CÔTÉ du champ,
   jamais pré-remplie ; « heures de repli » remplace « heures par défaut ». */

vi.mock('../../api/ventesApi', () => ({
  default: {
    getVarianteConfig: vi.fn(() => Promise.resolve({ data: { variante_pct: '20.00' } })),
    setVarianteConfig: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

import DevisSection from './DevisSection'
import { formDevisBase } from '../../test/fixtures/devisSectionForm'
import {
  REGLAGES_POMPAGE, formReglagesPompage, payloadReglagesPompage, nombreOuNull,
} from './peConstants'

afterEach(() => cleanup())

function withStore(ui) {
  const store = configureStore({
    reducer: { auth: (s = { role: 'admin', role_nom: null }) => s },
  })
  return <Provider store={store}>{ui}</Provider>
}

const baseForm = formDevisBase()

function rendre(form = baseForm, set = vi.fn()) {
  render(withStore(
    <DevisSection form={form} set={set} setForm={vi.fn()} setPT={vi.fn()}
                  setPrefix={vi.fn()} setNumbering={vi.fn()}
                  numberingPreview={() => 'DEV-1'} canManageSensitive />,
  ))
  return set
}

describe('AGR108 — réglages pompage sans défaut', () => {
  it('les trois champs sont vides, step="any", avec leur indication à côté', () => {
    rendre()
    for (const { champ, libelle, indication } of REGLAGES_POMPAGE) {
      const input = screen.getByLabelText(libelle)
      expect(input).toHaveAttribute('name', champ)
      expect(input).toHaveAttribute('step', 'any')
      expect(input).toHaveValue(null)
      expect(screen.getByText(indication)).toBeInTheDocument()
    }
    expect(screen.getByLabelText(/Heures de repli/)).toBeInTheDocument()
  })

  it('vider un champ remonte une valeur vide (jamais un chiffre de repli)', () => {
    const form = { ...baseForm, agricole_part_debit_forage_pct: '85' }
    const set = rendre(form)
    const input = screen.getByLabelText(REGLAGES_POMPAGE[0].libelle)
    expect(input).toHaveValue(85)
    fireEvent.change(input, { target: { value: '' } })
    expect(set).toHaveBeenCalled()
    const evt = set.mock.calls.at(-1)[0]
    expect(evt.target.name).toBe('agricole_part_debit_forage_pct')
  })

  it('un champ vidé est envoyé null ; une valeur tapée part telle quelle', () => {
    const corps = payloadReglagesPompage({
      agricole_part_debit_forage_pct: '',
      agricole_marge_cable_descente_m: '2,5',
      agricole_salissure_supp_pct: '7.25',
    })
    expect(corps).toEqual({
      agricole_part_debit_forage_pct: null,
      agricole_marge_cable_descente_m: '2.5',
      agricole_salissure_supp_pct: '7.25',
    })
    expect(nombreOuNull(null)).toBeNull()
    expect(nombreOuNull('   ')).toBeNull()
  })

  it('enregistrer → rouvrir = mêmes valeurs', () => {
    // Profil tel que le serveur le renvoie après le PATCH (null = vide).
    const serveur = {
      agricole_part_debit_forage_pct: '85.50',
      agricole_marge_cable_descente_m: null,
      agricole_salissure_supp_pct: '5.00',
    }
    const rouvert = formReglagesPompage(serveur)
    expect(rouvert).toEqual({
      agricole_part_debit_forage_pct: '85.50',
      agricole_marge_cable_descente_m: '',
      agricole_salissure_supp_pct: '5.00',
    })
    expect(payloadReglagesPompage(rouvert)).toEqual(serveur)
  })
})
