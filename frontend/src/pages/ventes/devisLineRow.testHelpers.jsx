/* Harnais partagé des tests DevisLineRow (ENF19) : enveloppe thème + props de base. */
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

export function wrap(ui) {
  return <ThemeProvider>{ui}</ThemeProvider>
}

// quantite=4, prix_unit_ttc=1500 ⇒ lineTtc = 6 000.
export const baseLine = {
  _key: 'l1', designation: 'Panneau solaire 450W', produit: '10',
  quantite: '4', prix_unit_ttc: '1500', taux_tva: '20',
}

const noop = () => {}
export function baseProps(overrides = {}) {
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
