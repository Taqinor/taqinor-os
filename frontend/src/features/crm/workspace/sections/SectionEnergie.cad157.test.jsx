// CAD157 — la fiche DIT ce que le chiffre ne compte pas : la tranche ONEE
// (texte libre qu'aucun calcul ne lit) et l'équipement déclaré sans sa
// puissance (il ne compose aucune couche). Aucun champ n'est ouvert au
// calcul : seules des mentions s'affichent.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { initState } from '../draftCore'
import SectionEnergie, { SectionEquipements } from './SectionEnergie'
import { NON_COMPTE_PLAQUE, NON_COMPTE_TRANCHE_ONEE } from '../../relances/appelGuidance'

afterEach(() => { cleanup(); vi.clearAllMocks() })

const etat = (lead) => initState({ lead: { id: 1, ...lead }, mode: 'edit' })

describe('CAD157 — la fiche dit ce qui n’est pas compté', () => {
  it('la tranche ONEE porte sa mention, sous son champ', () => {
    const setField = vi.fn()
    render(<SectionEnergie state={etat({ tranche_onee: 'Tranche 3' })} setField={setField} errors={{}} />)
    // Sous SON champ : l'indice du FormField de la tranche (id `<champ>-hint`).
    expect(document.getElementById('lf-tranche-onee-hint')).toHaveTextContent(NON_COMPTE_TRANCHE_ONEE)
    expect(setField).not.toHaveBeenCalled()
  })

  it('piscine déclarée sans puissance de pompe : « photo de la plaque » ; puissance saisie : plus rien', () => {
    const { unmount } = render(
      <SectionEquipements state={etat({ equip_piscine: true })} setField={vi.fn()} errors={{}} />)
    expect(screen.getByText(NON_COMPTE_PLAQUE)).toBeInTheDocument()
    unmount()
    render(
      <SectionEquipements
        state={etat({ equip_piscine: true, equip_piscine_pompe_kw: 1.1 })}
        setField={vi.fn()} errors={{}}
      />)
    expect(screen.queryByText(NON_COMPTE_PLAQUE)).not.toBeInTheDocument()
  })

  it('clim déclarée : le NOMBRE DE PIÈCES suffit à la compter (règle du serveur), sans lui la mention s’affiche', () => {
    const { unmount } = render(
      <SectionEquipements state={etat({ equip_clim: true })} setField={vi.fn()} errors={{}} />)
    expect(screen.getByText(NON_COMPTE_PLAQUE)).toBeInTheDocument()
    unmount()
    render(
      <SectionEquipements
        state={etat({ equip_clim: true, equip_clim_pieces: 2 })} setField={vi.fn()} errors={{}}
      />)
    expect(screen.queryByText(NON_COMPTE_PLAQUE)).not.toBeInTheDocument()
  })

  it('chauffe-eau électrique déclaré sans puissance : la mention s’affiche', () => {
    render(
      <SectionEquipements
        state={etat({ equip_chauffe_eau_electrique: true })} setField={vi.fn()} errors={{}}
      />)
    expect(screen.getByText(NON_COMPTE_PLAQUE)).toBeInTheDocument()
  })
})
