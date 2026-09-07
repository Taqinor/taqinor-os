// QJRREM (fondateur 07/09/2026) — « la remise de 5 % est gardée partout et
// s'applique aussi à chaque poste de la liste des composants, de
// l'installation, de tout ». Jusqu'ici l'écran de CRÉATION
// (`/ventes/devis/nouveau`, `DevisGenerator.jsx` → `LigneTable.jsx` →
// `DevisLineRow.jsx`) n'affichait la remise globale que dans le rail
// (`RailArgent`) : impossible de dire au client ce que CETTE ligne coûte
// après remise. Ce fichier verrouille l'affichage par ligne, à l'image de
// `DevisForm.jsx` (l'écran d'édition HT, déjà livré) — MÊME harnais que
// `DevisLineRow.test.jsx` (rendu isolé, ProduitPicker mocké).
//
// Le CALCUL (répartition du miroir, alignement, invariants) est verrouillé
// séparément dans `DevisGeneratorRemiseParLigne.test.jsx` : ce fichier-ci ne
// teste QUE l'AFFICHAGE d'un `totalTtcRemise` déjà calculé, reçu en prop.
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import DevisLineRow from './DevisLineRow'

vi.mock('../../components/ProduitPicker', () => ({
  default: (props) => <div data-testid="produit-picker-mock">{props.value ?? 'aucun'}</div>,
}))

function wrap(ui) {
  return <ThemeProvider>{ui}</ThemeProvider>
}

// Mêmes valeurs que DevisLineRow.test.jsx (baseLine) : quantite=4,
// prix_unit_ttc=1500 ⇒ lineTtc = 6 000. `totalTtcRemise=5700` simule une
// remise globale de 5 % déjà répartie par le miroir (6000 × 0,95 = 5700,
// sans reste à distribuer sur cette fixture — la répartition réelle est
// testée ailleurs, voir DevisGeneratorRemiseParLigne.test.jsx).
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

function renderRow(overrides = {}) {
  render(
    <table><tbody>{wrap(<DevisLineRow {...baseProps(overrides)} />)}</tbody></table>,
  )
  return screen.getByDisplayValue('Panneau solaire 450W').closest('tr')
}

describe('QJRREM — DevisLineRow : remise globale affichée par ligne (écran de création)', () => {
  it('montrerRemise + totalTtcRemise fournis : le total remisé devient le montant PRINCIPAL, le catalogue passe en secondaire BARRÉ, et le P.U. après remise apparaît', () => {
    const row = renderRow({ montrerRemise: true, totalTtcRemise: 5700 })

    const totalCell = row.querySelector('td[data-label="Total TTC"]')
    // Montant principal = le total remisé (5 700), plus le catalogue (6 000)
    // barré en secondaire — jamais un remplacement silencieux.
    expect(totalCell).toHaveTextContent('5 700 MAD')
    const struck = totalCell.querySelector('s')
    expect(struck).not.toBeNull()
    expect(struck).toHaveTextContent('6 000 MAD')
    // U4 — la ligne « HT : … » reste INCHANGÉE (quantite=4 × HT unitaire
    // 1250 = 5 000, dérivé du catalogue, jamais de la remise).
    expect(totalCell).toHaveTextContent('HT : 5 000 MAD')

    // P.U. après remise, lecture seule, sous l'input catalogue : puRemise(5700, 4) = 1425.
    const prixCell = row.querySelector('td[data-label="Prix unit. TTC"]')
    expect(prixCell).toHaveTextContent('après remise : 1 425 MAD')
    // Toujours un seul input éditable (le P.U. catalogue) — aucun nouveau champ.
    expect(prixCell.querySelectorAll('input').length).toBe(1)
  })

  it('montrerRemise=false : aucun texte de remise, DOM identique au cas sans remise (remise nulle ⇒ écran inchangé)', () => {
    const row = renderRow({ montrerRemise: false, totalTtcRemise: 5700 })

    const totalCell = row.querySelector('td[data-label="Total TTC"]')
    expect(totalCell).toHaveTextContent('6 000 MAD')
    expect(totalCell).toHaveTextContent('HT : 5 000 MAD')
    expect(totalCell.querySelector('s')).toBeNull()
    expect(totalCell).not.toHaveTextContent('5 700')

    const prixCell = row.querySelector('td[data-label="Prix unit. TTC"]')
    expect(prixCell).not.toHaveTextContent('après remise')
    expect(prixCell.querySelectorAll('input').length).toBe(1)
  })

  it('totalTtcRemise=null (ligne hors totaux — optionnelle ou section/note) : aucun texte de remise même si montrerRemise=true', () => {
    const row = renderRow({ montrerRemise: true, totalTtcRemise: null })

    const totalCell = row.querySelector('td[data-label="Total TTC"]')
    expect(totalCell).toHaveTextContent('6 000 MAD')
    expect(totalCell.querySelector('s')).toBeNull()

    const prixCell = row.querySelector('td[data-label="Prix unit. TTC"]')
    expect(prixCell).not.toHaveTextContent('après remise')
  })

  it('props par défaut (aucune remise passée par le parent) : DOM byte-identique au comportement d’avant QJRREM', () => {
    const row = renderRow()
    const totalCell = row.querySelector('td[data-label="Total TTC"]')
    expect(totalCell).toHaveTextContent('6 000 MAD')
    expect(totalCell).toHaveTextContent('HT : 5 000 MAD')
    expect(totalCell.querySelector('s')).toBeNull()
    const prixCell = row.querySelector('td[data-label="Prix unit. TTC"]')
    expect(prixCell).not.toHaveTextContent('après remise')
  })
})
