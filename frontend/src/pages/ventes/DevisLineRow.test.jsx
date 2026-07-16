// VX188 — DevisLineRow extrait en React.memo : une ligne dont les props
// n'ont pas changé ne doit PAS se re-rendre quand le parent re-rend pour une
// raison sans rapport (ex. la frappe dans « Note »). Test isolé du composant
// (pas de montage complet de DevisGenerator) — ProduitPicker est mocké pour
// compter ses rendus sans tirer ses dépendances redux/permissions internes.
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import DevisLineRow from './DevisLineRow'

const produitPickerRenderSpy = vi.fn()
vi.mock('../../components/ProduitPicker', () => ({
  default: (props) => {
    produitPickerRenderSpy(props.value)
    return <div data-testid="produit-picker-mock">{props.value ?? 'aucun'}</div>
  },
}))

function wrap(ui) {
  return <ThemeProvider>{ui}</ThemeProvider>
}

const baseLine = {
  _key: 'l1', designation: 'Panneau solaire 450W', produit: '10',
  quantite: '4', prix_unit_ttc: '1500', taux_tva: '20',
}

const noop = () => {}
function baseProps(overrides = {}) {
  return {
    line: baseLine,
    produits: [{ id: 10, nom: 'Panneau solaire 450W' }],
    multiMode: 'none',
    villaGroups: [],
    canRenameLine: true,
    tarifBadge: undefined,
    tvaPanneaux: 10,
    tvaStandard: 20,
    onSetField: noop,
    onDesignationBlur: noop,
    onProduitChange: noop,
    onProduitCreated: noop,
    onQuantiteChange: noop,
    onSetGroupe: noop,
    onRemove: noop,
    ...overrides,
  }
}

describe('DevisLineRow (VX188) — mémoïsation', () => {
  it('rend la ligne avec les mêmes contrats DOM (data-label, step="any", noValidate côté champs)', () => {
    render(
      <table><tbody>{wrap(<DevisLineRow {...baseProps()} />)}</tbody></table>,
    )
    const row = screen.getByDisplayValue('Panneau solaire 450W').closest('tr')
    const qte = row.querySelector('td[data-label="Qté"] input')
    const prix = row.querySelector('td[data-label="Prix unit. TTC"] input')
    const tva = row.querySelector('td[data-label="TVA %"] input')
    expect(qte).toHaveAttribute('step', 'any')
    expect(prix).toHaveAttribute('step', 'any')
    expect(tva).toHaveAttribute('step', 'any')
    expect(qte.value).toBe('4')
  })

  it('ne se re-rend PAS (ProduitPicker non ré-invoqué) quand un re-render parent passe des props IDENTIQUES par référence', () => {
    produitPickerRenderSpy.mockClear()
    const props = baseProps()
    const { rerender } = render(
      <table><tbody>{wrap(<DevisLineRow {...props} />)}</tbody></table>,
    )
    expect(produitPickerRenderSpy).toHaveBeenCalledTimes(1)
    // Simule un re-render du parent déclenché par un état SANS RAPPORT (ex.
    // « Note ») : mêmes props (mêmes références), un nouvel objet `table`
    // racine seulement — React.memo doit sauter le re-rendu de la ligne.
    rerender(
      <table><tbody>{wrap(<DevisLineRow {...props} />)}</tbody></table>,
    )
    expect(produitPickerRenderSpy).toHaveBeenCalledTimes(1)
  })

  it('SE re-rend quand `line` change réellement (nouvelle quantité)', () => {
    produitPickerRenderSpy.mockClear()
    const props = baseProps()
    const { rerender } = render(
      <table><tbody>{wrap(<DevisLineRow {...props} />)}</tbody></table>,
    )
    expect(produitPickerRenderSpy).toHaveBeenCalledTimes(1)
    rerender(
      <table><tbody>{wrap(
        <DevisLineRow {...props} line={{ ...baseLine, quantite: '5' }} />,
      )}</tbody></table>,
    )
    expect(produitPickerRenderSpy).toHaveBeenCalledTimes(2)
  })

  it('appelle onRemove(key) — jamais l\'identité de la fermeture (clé en argument)', async () => {
    const onRemove = vi.fn()
    render(
      <table><tbody>{wrap(
        <DevisLineRow {...baseProps({ onRemove })} />,
      )}</tbody></table>,
    )
    screen.getByRole('button', { name: 'Supprimer la ligne' }).click()
    expect(onRemove).toHaveBeenCalledWith('l1')
  })
})
