import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, fireEvent, within } from '@testing-library/react'
import { useState } from 'react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* CIQ225 — Paramètres › Devis : l'échéancier de chaque marché est une LISTE
   de jalons (ajout, retrait, ordre), somme affichée, refus serveur sous la
   liste. Les jalons du profil (`payment_terms_effectifs`) sont la seule source. */

vi.mock('../../api/ventesApi', () => ({
  default: {
    getVarianteConfig: vi.fn(() => Promise.resolve({ data: { variante_pct: '20.00' } })),
    setVarianteConfig: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

import DevisSection from './DevisSection'
import { formDevisBase } from '../../test/fixtures/devisSectionForm'
import { payloadTermes } from './peConstants'

afterEach(() => cleanup())

const store = configureStore({
  reducer: { auth: (s = { role: 'admin', role_nom: null }) => s },
})

const INDUSTRIEL = [
  { jalon: 'commande', pct: 30 }, { jalon: 'livraison_materiel', pct: 40 },
  { jalon: 'mise_en_service', pct: 20 }, { jalon: 'reception_definitive', pct: 10 },
]

function rendre(termes, profileError = null) {
  const etats = []
  function Harnais() {
    const [form, setFormEtat] = useState(formDevisBase({ payment_terms: termes }))
    const setForm = (fn) => setFormEtat((p) => {
      const suivant = typeof fn === 'function' ? fn(p) : fn
      etats.push(suivant)
      return suivant
    })
    return (
      <DevisSection form={form} set={vi.fn()} setForm={setForm}
                    setPrefix={vi.fn()} setNumbering={vi.fn()}
                    numberingPreview={() => 'DEV-1'} canManageSensitive
                    profileError={profileError} />
    )
  }
  render(<Provider store={store}><Harnais /></Provider>)
  return etats
}

describe('CIQ225 — échéancier société à N jalons', () => {
  it('affiche les 4 jalons industriels et leur somme', () => {
    rendre({ industriel: INDUSTRIEL })
    const bloc = screen.getByTestId('echeancier-industriel')
    expect(within(bloc).getByLabelText('Pourcentage 1 — Industriel')).toHaveValue(30)
    expect(within(bloc).getByLabelText('Pourcentage 4 — Industriel')).toHaveValue(10)
    expect(within(bloc).getByLabelText('Pourcentage 1 — Industriel')).toHaveAttribute('step', 'any')
    expect(screen.getByTestId('echeancier-industriel-somme')).toHaveTextContent('Total : 100 %')
    expect(within(bloc).queryByRole('alert')).toBeNull()
  })

  it('ancienne forme {acompte, materiel, solde} toujours lue', () => {
    rendre({ residentiel: { acompte: 30, materiel: 60, solde: 10 } })
    expect(screen.getByLabelText('Pourcentage 2 — Résidentiel')).toHaveValue(60)
  })

  it('ajouter, retirer, réordonner ; somme ≠ 100 ⇒ message sous la liste', () => {
    const etats = rendre({ industriel: INDUSTRIEL })
    fireEvent.click(screen.getByRole('button', { name: 'Retirer le jalon 4 — Industriel' }))
    const bloc = screen.getByTestId('echeancier-industriel')
    expect(screen.getByTestId('echeancier-industriel-somme')).toHaveTextContent('Total : 90 %')
    expect(within(bloc).getByRole('alert')).toHaveTextContent('100 %')
    fireEvent.click(within(bloc).getByRole('button', { name: 'Ajouter un jalon' }))
    fireEvent.change(screen.getByLabelText('Pourcentage 4 — Industriel'), { target: { value: '10' } })
    expect(within(bloc).queryByRole('alert')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Monter le jalon 4 — Industriel' }))
    const dernier = etats.at(-1).payment_terms.industriel
    expect(dernier.map(j => j.jalon)).toEqual(
      ['commande', 'livraison_materiel', 'mise_en_service', 'mise_en_service'])
    expect(payloadTermes(dernier).map(j => j.pct)).toEqual([30, 40, 10, 20])
  })

  it('refus du serveur affiché sous la liste', () => {
    rendre({ industriel: INDUSTRIEL },
      { payment_terms: ["L'échéancier du mode « industriel » doit totaliser 100 %."] })
    expect(screen.getByTestId('echeancier-erreur-serveur')).toHaveTextContent('doit totaliser 100 %')
  })

  it('charge utile : liste → [{jalon, pct nombre}], ancienne forme intacte', () => {
    expect(payloadTermes(INDUSTRIEL.map(j => ({ ...j, pct: String(j.pct) }))))
      .toEqual(INDUSTRIEL)
    expect(payloadTermes({ acompte: '30', materiel: 60, solde: 10 }))
      .toEqual({ acompte: 30, materiel: 60, solde: 10 })
  })
})
