// VX188 — DevisLineRow extrait en React.memo : une ligne dont les props
// n'ont pas changé ne doit PAS se re-rendre quand le parent re-rend pour une
// raison sans rapport (ex. la frappe dans « Note »). Test isolé du composant
// (pas de montage complet de DevisGenerator) — ProduitPicker est mocké pour
// compter ses rendus sans tirer ses dépendances redux/permissions internes.
import { useState } from 'react'
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { wrap, baseLine, baseProps } from './devisLineRow.testHelpers.jsx'
import DevisLineRow from './DevisLineRow'

const produitPickerRenderSpy = vi.fn()
// STKCAT24 — le spy capture aussi `typeFilter` (en plus de `value`, préservé
// pour les tests VX188 existants) pour vérifier lequel de `l.role_devis` /
// `classifyProduct(l.designation)` le composant transmet au picker.
vi.mock('../../components/ProduitPicker', () => ({
  default: (props) => {
    produitPickerRenderSpy(props.value, props.typeFilter)
    return <div data-testid="produit-picker-mock">{props.value ?? 'aucun'}</div>
  },
}))

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

  it('U4 — affiche le HT unitaire dérivé (lecture seule) sous le prix TTC et le total HT sous le total TTC', () => {
    render(
      <table><tbody>{wrap(<DevisLineRow {...baseProps()} />)}</tbody></table>,
    )
    const row = screen.getByDisplayValue('Panneau solaire 450W').closest('tr')
    // prix_unit_ttc=1500, taux_tva=20 → HT unitaire = 1500 / 1.2 = 1250.00
    const prixCell = row.querySelector('td[data-label="Prix unit. TTC"]')
    expect(prixCell).toHaveTextContent('HT : 1 250 MAD')
    // quantite=4 × HT unitaire 1250 = 5000 (total HT de la ligne)
    const totalCell = row.querySelector('td[data-label="Total TTC"]')
    expect(totalCell).toHaveTextContent('6 000 MAD') // total TTC = 4 × 1500
    expect(totalCell).toHaveTextContent('HT : 5 000 MAD')
    // L'input TTC reste la seule saisie — aucun nouveau champ éditable pour le HT.
    expect(prixCell.querySelectorAll('input').length).toBe(1)
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

// STKCAT24 — le picker reçoit le rôle STOCKÉ de la ligne (`l.role_devis`,
// posé à la création par STKCAT23) et ne retombe sur `classifyProduct` que
// s'il est vide (ligne libre, ou créée avant STKCAT23).
describe('DevisLineRow (STKCAT24) — typeFilter du picker : rôle stocké prioritaire', () => {
  it('l.role_devis présent (désignation sans mot-clé) : passé TEL QUEL au picker', () => {
    produitPickerRenderSpy.mockClear()
    render(
      <table><tbody>{wrap(
        <DevisLineRow {...baseProps({
          line: { ...baseLine, designation: 'Charpente sur mesure', role_devis: 'structure' },
        })} />,
      )}</tbody></table>,
    )
    expect(produitPickerRenderSpy).toHaveBeenCalledWith('10', 'structure')
  })

  it('l.role_devis vide/absent : repli sur classifyProduct(l.designation) — comportement historique', () => {
    produitPickerRenderSpy.mockClear()
    render(
      <table><tbody>{wrap(
        <DevisLineRow {...baseProps()} />,
      )}</tbody></table>,
    )
    // baseLine.designation = 'Panneau solaire 450W', aucun role_devis stocké
    expect(produitPickerRenderSpy).toHaveBeenCalledWith('10', 'panneau')
  })

  it('l.role_devis présent MAIS différent du mot-clé de la désignation : le rôle stocké gagne', () => {
    produitPickerRenderSpy.mockClear()
    render(
      <table><tbody>{wrap(
        <DevisLineRow {...baseProps({
          line: { ...baseLine, designation: 'Onduleur Hybride Deye 6kW', role_devis: 'onduleur_reseau' },
        })} />,
      )}</tbody></table>,
    )
    expect(produitPickerRenderSpy).toHaveBeenCalledWith('10', 'onduleur_reseau')
  })
})

describe('DevisLineRow — QJR529 : remise de ligne stockée visible (lecture seule)', () => {
  it('affiche « remise ligne 10 % » quand la ligne porte une remise > 0', () => {
    render(
      <table><tbody>{wrap(
        <DevisLineRow {...baseProps({ line: { ...baseLine, remise: '10' } })} />,
      )}</tbody></table>,
    )
    expect(screen.getByText(/remise ligne 10\s?%/)).toBeInTheDocument()
  })

  it('aucun badge sans remise (ou remise nulle)', () => {
    render(
      <table><tbody>{wrap(
        <DevisLineRow {...baseProps({ line: { ...baseLine, remise: '0' } })} />,
      )}</tbody></table>,
    )
    expect(screen.queryByText(/remise ligne/)).toBeNull()
  })
})

// QJR569 — le verrou de quantité (posé par une frappe) est VISIBLE sur la
// ligne et RÉVERSIBLE : « Libérer » rend la quantité au dimensionnement.
describe('DevisLineRow — QJR569 : badge « Qté figée » + « Libérer »', () => {
  it('rend le badge et « Libérer » appelle onSetField(key, quantiteManuelle, false)', () => {
    const onSetField = vi.fn()
    render(
      <table><tbody>{wrap(
        <DevisLineRow {...baseProps({ onSetField, line: { ...baseLine, quantiteManuelle: true } })} />,
      )}</tbody></table>,
    )
    expect(screen.getByText(/Qté figée/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Libérer/ }))
    expect(onSetField).toHaveBeenCalledWith('l1', 'quantiteManuelle', false)
  })

  it('aucun badge sans verrou', () => {
    render(
      <table><tbody>{wrap(<DevisLineRow {...baseProps()} />)}</tbody></table>,
    )
    expect(screen.queryByText(/Qté figée/)).toBeNull()
    expect(screen.queryByRole('button', { name: /Libérer/ })).toBeNull()
  })
})

// R1-09 / R1-10 / R1-11 (recette 22/11, décision Q1) — saisie française : un
// Chrome en anglais ou en arabe filtrait la virgule et l'espace d'un champ
// « number » (« 4 800,50 » → 480050). Le champ est un texte à clavier décimal
// qui lit la virgule ; le total de la ligne suit le nombre LU.
describe('R1-10 — saisie française des champs de ligne', () => {
  function LigneVivante({ initiale = baseLine }) {
    const [ligne, setLigne] = useState(initiale)
    const poser = (_k, champ, v) => setLigne(l => ({ ...l, [champ]: v }))
    return (
      <table><tbody>{wrap(
        <DevisLineRow {...baseProps({ line: ligne, onSetField: poser,
          onQuantiteChange: (k, v) => poser(k, 'quantite', v) })} />,
      )}</tbody></table>
    )
  }
  const champ = (label) => document.querySelector(`td[data-label="${label}"] input`)
  const totalLigne = () => document.querySelector('td[data-label="Total TTC"]').textContent.replace(/\s+/g, ' ')

  it('champs texte à clavier décimal, step="any", aucune borne', () => {
    render(<LigneVivante />)
    for (const label of ['Qté', 'Prix unit. TTC', 'TVA %']) {
      expect(champ(label)).toHaveAttribute('type', 'text')
      expect(champ(label)).toHaveAttribute('inputmode', 'decimal')
      expect(champ(label)).toHaveAttribute('step', 'any')
      expect(champ(label)).not.toHaveAttribute('min')
    }
  })

  it('« 4 800,50 » (espace normale ou insécable) → 4 800,5 × 4, jamais 480 050 ; le texte tapé reste affiché', () => {
    render(<LigneVivante />)
    for (const tape of ['4 800,50', '4 800,50', '4 800,50']) {
      fireEvent.change(champ('Prix unit. TTC'), { target: { value: tape } })
      expect(champ('Prix unit. TTC').value).toBe(tape)
      expect(totalLigne()).toContain('19 202 MAD')
      expect(totalLigne()).not.toMatch(/1 920 200/)
    }
  })

  it('quantité « 2,5 » → 2,5 × 1 500 = 3 750', () => {
    render(<LigneVivante />)
    fireEvent.change(champ('Qté'), { target: { value: '2,5' } })
    expect(totalLigne()).toContain('3 750 MAD')
  })

  it('une saisie illisible est DITE sous le champ et ne devient pas un autre nombre', () => {
    render(<LigneVivante />)
    fireEvent.change(champ('Prix unit. TTC'), { target: { value: '1,234.56' } })
    expect(champ('Prix unit. TTC').value).toBe('1,234.56')
    expect(champ('Prix unit. TTC')).toHaveAttribute('aria-invalid', 'true')
    const td = document.querySelector('td[data-label="Prix unit. TTC"]')
    expect(td.querySelector('[role="alert"]').textContent).toMatch(/n’est pas un nombre lisible.*le calcul garde 1500/)
    expect(totalLigne()).toContain('6 000 MAD') // 4 × 1 500, la dernière valeur lue
  })

  it('R1-11 — une quantité vidée est acceptée et dite « ligne à 0 MAD »', () => {
    render(<LigneVivante />)
    expect(screen.queryByTestId('ligne-quantite-vide')).toBeNull()
    fireEvent.change(champ('Qté'), { target: { value: '' } })
    expect(screen.getByTestId('ligne-quantite-vide').textContent).toBe('Quantité vide : ligne à 0 MAD')
  })

  it('une valeur relue du serveur s’affiche telle qu’avant (point décimal)', () => {
    render(<LigneVivante initiale={{ ...baseLine, prix_unit_ttc: '1234.56' }} />)
    expect(champ('Prix unit. TTC').value).toBe('1234.56')
  })
})
