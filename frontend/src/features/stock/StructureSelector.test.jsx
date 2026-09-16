/* STKCAT10 — LE SÉLECTEUR DE STRUCTURES (décision fondateur 16/09/2026).
   Ce que ce fichier verrouille, et pourquoi :
     · les TROIS gardes d'éligibilité (archivé / sans prix / catégorie non
       typée) — c'est la définition MÊME de « structure du catalogue » ;
     · le REPLI : zéro structure typée ⇒ le bouton acier/aluminium d'hier est
       rendu tel quel, donc le sélecteur ne peut JAMAIS naître vide ;
     · le groupement par catégorie et l'ordre (`categorie.ordre` puis nom) ;
     · « Aucune structure » comme première option, et l'id RENDU au parent. */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import StructureSelector from './StructureSelector'
import { structuresEligibles, groupesStructures, estStructureEligible } from './structures'

// Le composant ne va au réseau QUE si `produits` n'est pas fourni ; tous les
// cas ci-dessous le fournissent, mais on neutralise l'API par sécurité pour
// qu'aucun test ne dépende d'un aller-retour.
vi.mock('../../api/stockApi', () => ({
  default: { getProduits: () => Promise.resolve({ data: { results: [], count: 0 } }) },
}))

const S = (id, nom, extra = {}) => ({
  id, nom, prix_vente: '1000.00', is_archived: false,
  categorie_type: 'structure',
  categorie: { nom: 'Structures', ordre: 7, type_equipement: 'structure' },
  ...extra,
})

const PERGOLA = S(71, 'Pergola bioclimatique 4x3', {
  categorie: { nom: 'Pergolas', ordre: 3, type_equipement: 'structure' },
})
const ACIER = S(72, 'Structures acier')
const ALU = S(73, 'Structures aluminium')

const REPLI = <button type="button">Acier galvanisé / Aluminium</button>

describe('STKCAT10 — éligibilité (les trois gardes)', () => {
  it('retient une structure non archivée, chiffrée, de catégorie TYPÉE', () => {
    expect(estStructureEligible(ACIER)).toBe(true)
  })

  it('écarte l’archivée, la non chiffrée et la catégorie non typée', () => {
    expect(estStructureEligible(S(1, 'Archivée', { is_archived: true }))).toBe(false)
    expect(estStructureEligible(S(2, 'Sans prix', { prix_vente: '0' }))).toBe(false)
    expect(estStructureEligible(S(3, 'Sans prix', { prix_vente: null }))).toBe(false)
    expect(estStructureEligible({
      id: 4, nom: 'Structures acier', prix_vente: '500', categorie_type: null,
      categorie: { nom: 'Divers', ordre: 1, type_equipement: null },
    })).toBe(false)
    expect(estStructureEligible(null)).toBe(false)
  })

  it('lit aussi le type par la catégorie imbriquée (API sans champ plat)', () => {
    const sansChampPlat = {
      id: 5, nom: 'Carport', prix_vente: '9000', is_archived: false,
      categorie: { nom: 'Carports', ordre: 4, type_equipement: 'structure' },
    }
    expect(estStructureEligible(sansChampPlat)).toBe(true)
  })

  it('ordonne par categorie.ordre, puis nom de catégorie, puis nom du produit', () => {
    const ordre = structuresEligibles([ALU, ACIER, PERGOLA]).map((p) => p.nom)
    // Pergolas (ordre 3) avant Structures (ordre 7) ; à l’intérieur, alpha.
    expect(ordre).toEqual([
      'Pergola bioclimatique 4x3', 'Structures acier', 'Structures aluminium',
    ])
    // Une entrée non tableau ne lève jamais.
    expect(structuresEligibles(null)).toEqual([])
    expect(groupesStructures(undefined)).toEqual([])
  })

  it('groupe par catégorie, dans le même ordre', () => {
    const groupes = groupesStructures([ALU, ACIER, PERGOLA])
    expect(groupes.map((g) => g.categorie)).toEqual(['Pergolas', 'Structures'])
    expect(groupes[1].items.map((p) => p.id)).toEqual([72, 73])
  })
})

describe('STKCAT10 — rendu du sélecteur', () => {
  it('rend un select groupé par catégorie, « Aucune structure » en tête', () => {
    render(
      <StructureSelector
        id="sel-structure" label="Type de Structure"
        produits={[ALU, ACIER, PERGOLA]} value="" onChange={() => {}}
        fallback={REPLI}
      />,
    )
    const select = screen.getByLabelText('Type de Structure')
    expect(select.tagName).toBe('SELECT')
    const options = [...select.querySelectorAll('option')].map((o) => o.textContent)
    expect(options).toEqual([
      'Aucune structure',
      'Pergola bioclimatique 4x3', 'Structures acier', 'Structures aluminium',
    ])
    const groupes = [...select.querySelectorAll('optgroup')].map((g) => g.label)
    expect(groupes).toEqual(['Pergolas', 'Structures'])
    // …et le repli n’est PAS rendu quand le catalogue répond.
    expect(screen.queryByRole('button', { name: /Acier galvanisé/ })).toBeNull()
  })

  it('rend l’ID choisi au parent (chaîne), et affiche la valeur courante', () => {
    const onChange = vi.fn()
    render(
      <StructureSelector
        id="sel-structure" label="Type de Structure"
        produits={[ACIER, PERGOLA]} value={71} onChange={onChange}
        fallback={REPLI}
      />,
    )
    const select = screen.getByLabelText('Type de Structure')
    expect(select.value).toBe('71')
    fireEvent.change(select, { target: { value: '72' } })
    expect(onChange).toHaveBeenCalledWith('72')
    fireEvent.change(select, { target: { value: '' } })
    expect(onChange).toHaveBeenLastCalledWith('')
  })

  it('REPLI — aucune structure typée ⇒ le bouton acier/aluminium d’hier, tel quel', () => {
    const { rerender } = render(
      <StructureSelector produits={[]} value="" onChange={() => {}} fallback={REPLI} />,
    )
    expect(screen.getByRole('button', { name: /Acier galvanisé/ })).toBeInTheDocument()
    expect(screen.queryByRole('combobox')).toBeNull()
    // Même repli quand le catalogue n’a que des structures INÉLIGIBLES.
    rerender(
      <StructureSelector
        produits={[S(9, 'Structures acier', { is_archived: true }),
                   S(10, 'Structures aluminium', { prix_vente: '0' })]}
        value="" onChange={() => {}} fallback={REPLI}
      />,
    )
    expect(screen.getByRole('button', { name: /Acier galvanisé/ })).toBeInTheDocument()
    expect(screen.queryByRole('combobox')).toBeNull()
  })

  it('sans repli fourni, ne rend RIEN plutôt qu’un sélecteur vide', () => {
    const { container } = render(
      <StructureSelector produits={[]} value="" onChange={() => {}} />,
    )
    expect(container).toBeEmptyDOMElement()
  })
})
