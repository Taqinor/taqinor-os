import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { initState } from '../draftCore'
import SectionEnergie, { SectionEquipements } from './SectionEnergie'

/* RÈGLE FONDATEUR 08/09/2026 — « all the errors should point at the field
   creating this error and even say what is exactly the error so it is easy
   to solve ». Incident déclencheur : `equip_clim_kw` refusait « plus de 3
   chiffres avant la virgule » sans jamais dire QUEL champ — ce test prouve
   que le message serveur atterrit désormais SOUS le bon champ, en rouge, et
   que le contrôle porte bien aria-invalid. Patron d'assertion
   (`getByRole('alert')` + `toHaveTextContent`) repris de `ui/Form.test.jsx`
   (G127), pas un `getByText` exact — le paragraphe d'erreur du FormField
   porte AUSSI un préfixe sr-only (« Format invalide : »), un match exact sur
   le seul texte serveur échouerait. */
describe('SectionEquipements — erreur serveur nommée sous le champ fautif', () => {
  it('equip_clim_kw : le message serveur apparaît sous « Puissance totale climatisation (kW) », le champ est invalide', () => {
    const state = initState({ lead: { id: 1, equip_clim: true }, mode: 'edit' })
    render(
      <SectionEquipements
        state={state}
        setField={vi.fn()}
        errors={{ equip_clim_kw: "Assurez-vous qu'il n'y a pas plus de 3 chiffres avant la virgule." }}
        mode="edit"
        refData={{}}
      />,
    )
    const input = document.querySelector('#lf-equip-clim-kw')
    expect(input).toBeInTheDocument()
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByRole('alert')).toHaveTextContent(
      "Assurez-vous qu'il n'y a pas plus de 3 chiffres avant la virgule.",
    )
  })

  it('sans erreur, le champ reste valide et aucune alerte ne se rend', () => {
    const state = initState({ lead: { id: 1, equip_clim: true }, mode: 'edit' })
    render(
      <SectionEquipements state={state} setField={vi.fn()} errors={{}} mode="edit" refData={{}} />,
    )
    expect(document.querySelector('#lf-equip-clim-kw')).not.toHaveAttribute('aria-invalid')
    expect(screen.queryByRole('alert')).toBeNull()
  })

  // Un native <select> (pas de prop `invalid` — TriStateSelect) porte lui
  // aussi la classe/aria-invalid quand son propre champ est en erreur.
  it('equip_clim (TriStateSelect natif) : aria-invalid + classe is-invalid quand errors.equip_clim est posé', () => {
    const state = initState({ lead: { id: 1 }, mode: 'edit' })
    render(
      <SectionEquipements
        state={state} setField={vi.fn()}
        errors={{ equip_clim: 'Valeur invalide.' }} mode="edit" refData={{}}
      />,
    )
    const select = document.querySelector('#lf-equip-clim')
    expect(select).toHaveAttribute('aria-invalid', 'true')
    expect(select.className).toContain('is-invalid')
  })

  it('raccordement (SectionEnergie, select natif) : même traitement', () => {
    const state = initState({ lead: { id: 1 }, mode: 'edit' })
    render(
      <SectionEnergie
        state={state} setField={vi.fn()}
        errors={{ raccordement: 'Choix invalide.' }}
      />,
    )
    const select = document.querySelector('#lf-raccordement')
    expect(select).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByRole('alert')).toHaveTextContent('Choix invalide.')
  })
})
