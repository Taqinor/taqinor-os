import { useState } from 'react'
import { describe, it, expect, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import PhoneInput from './PhoneInput'

/* NTI18N24 — numéros internationaux au-delà du format marocain. Vérifie :
   (1) le comportement marocain historique reste un passe-plat direct
   (aucune frappe rejetée/tronquée), (2) un indicatif explicitement tapé
   (« +33… ») n'est jamais rejeté ni tronqué comme un numéro marocain,
   (3) le sélecteur de pays préfixe un indicatif sur un champ local, (4) le
   formatage E.164 n'intervient qu'au blur, sur un numéro déjà international. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}

      unobserve() {}

      disconnect() {}
    }
  }
  if (typeof window.matchMedia === 'undefined') {
    window.matchMedia = () => ({
      matches: false,
      addListener() {},
      removeListener() {},
      addEventListener() {},
      removeEventListener() {},
    })
  }
})

function Harness({ initial = '', packPays } = {}) {
  const [value, setValue] = useState(initial)
  return (
    <PhoneInput
      value={value}
      onChange={setValue}
      packPays={packPays}
      aria-label="Téléphone"
    />
  )
}

describe('PhoneInput (NTI18N24)', () => {
  it('mode marocain par défaut : passe-plat direct, aucune troncature (comportement historique)', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    const champ = screen.getByRole('textbox', { name: 'Téléphone' })
    await user.type(champ, '0612345678')
    expect(champ).toHaveValue('0612345678')
  })

  it("un indicatif +33 explicitement tapé n'est jamais rejeté ni tronqué comme un numéro marocain", async () => {
    const user = userEvent.setup()
    render(<Harness />)
    const champ = screen.getByRole('textbox', { name: 'Téléphone' })
    await user.type(champ, '+33612345678')
    // Le numéro complet (indicatif + 9 chiffres) est conservé intégralement —
    // jamais tronqué à 10 chiffres comme un local marocain, jamais rejeté.
    expect(champ).toHaveValue('+33612345678')
    // Le sélecteur détecte et affiche l'indicatif français.
    expect(screen.getByRole('combobox', { name: 'Indicatif pays' })).toHaveTextContent('+33')
  })

  it('choisir un pays au sélecteur préfixe son indicatif sur un champ encore local', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    await user.click(screen.getByRole('combobox', { name: 'Indicatif pays' }))
    await user.click(await screen.findByRole('option', { name: /France/ }))
    const champ = screen.getByRole('textbox', { name: 'Téléphone' })
    expect(champ).toHaveValue('+33')
    await user.type(champ, '612345678')
    expect(champ).toHaveValue('+33612345678')
  })

  it('formate en E.164 canonique au blur un numéro déjà international (jamais en direct)', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    const champ = screen.getByRole('textbox', { name: 'Téléphone' })
    await user.type(champ, '+33 6 12 34 56 78')
    expect(champ).toHaveValue('+33 6 12 34 56 78') // aucun reformatage pendant la frappe
    await user.tab() // blur
    await waitFor(() => expect(champ).toHaveValue('+33612345678'))
  })

  it("ne reformate rien au blur pour un numéro marocain historique (aucun nouveau comportement)", async () => {
    const user = userEvent.setup()
    render(<Harness />)
    const champ = screen.getByRole('textbox', { name: 'Téléphone' })
    await user.type(champ, '0612345678')
    await user.tab()
    expect(champ).toHaveValue('0612345678')
  })

  it('packPays≠MA affiche directement le sélecteur sur ce pays par défaut', () => {
    render(<Harness packPays="SN" />)
    expect(screen.getByRole('combobox', { name: 'Indicatif pays' })).toHaveTextContent('+221')
  })
})
