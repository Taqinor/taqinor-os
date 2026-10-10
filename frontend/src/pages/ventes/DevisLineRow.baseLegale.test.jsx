// AGR218 (contrat AGR200) — une ligne du générateur à 0 % de TVA porte sa
// BASE LÉGALE : champ obligatoire, jamais pré-rempli ; l'alerte « taux
// attendu » se tait quand la base est saisie ; le refus 400 du serveur
// s'affiche sous le champ de SA ligne. Formes tirées du contrat partagé
// `devis_replace_lines_entete.json` (check_api_shapes).
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, within } from '@testing-library/react'

import DevisLineRow from './DevisLineRow'
import {
  lignesServeurVersEcran, erreursBaseLegaleServeur,
} from '../../features/ventes/quote/lignesEcran'
import { documentContrat, exempleContrat } from '../../test/fixtures/contractSamples'

vi.mock('../../components/ProduitPicker', () => ({
  default: () => <span data-testid="produit-picker" />,
}))

afterEach(() => { cleanup(); vi.clearAllMocks() })

const CORPS = documentContrat('ventes', 'devis_replace_lines_entete').corps_agricole
const REFUS = exempleContrat('ventes', 'devis_replace_lines_entete', 'exemple_400_tva_base_legale')

const lignesEcran = () => lignesServeurVersEcran(CORPS.lignes, '20.00')
  .map((l, i) => ({ ...l, _key: `k${i}` }))

function monter(ligne, props = {}) {
  const onSetField = vi.fn()
  render(
    <table><tbody>
      <DevisLineRow
        line={ligne} produits={[]} multiMode="" villaGroups={[]}
        canRenameLine tarifBadge={null} tvaPanneaux={10} tvaStandard={20}
        onSetField={onSetField} onDesignationBlur={vi.fn()}
        onProduitChange={vi.fn()} onProduitCreated={vi.fn()}
        onQuantiteChange={vi.fn()} onSetGroupe={vi.fn()} onRemove={vi.fn()}
        totalTtcRemise={null} montrerRemise={false}
        canMoveUp={false} canMoveDown={false} onMoveUp={vi.fn()} onMoveDown={vi.fn()}
        {...props}
      />
    </tbody></table>,
  )
  return { onSetField }
}

describe('AGR218 — base légale d’une ligne à 0 %', () => {
  it('ligne à 0 % sans base ⇒ champ visible + erreur sous le champ', () => {
    const [pompe] = lignesEcran()
    monter({ ...pompe, tvaBaseLegale: '' })
    const bloc = screen.getByTestId('ligne-base-legale')
    expect(within(bloc).getByLabelText('Base légale de l’exonération').value).toBe('')
    expect(within(bloc).getByRole('alert').textContent)
      .toContain('Base légale obligatoire')
  })

  it('jamais pré-rempli : le champ vide ne propose aucun article', () => {
    const [pompe] = lignesEcran()
    monter({ ...pompe, tvaBaseLegale: '' })
    const champ = screen.getByLabelText('Base légale de l’exonération')
    expect(champ.value).toBe('')
    expect(champ.getAttribute('placeholder') || '').not.toMatch(/art\.|CGI|\d/)
  })

  it('ligne à 0 % avec base ⇒ pas d’erreur, et l’alerte « attendu » se tait', () => {
    const [pompe] = lignesEcran()
    monter(pompe)
    expect(screen.getByLabelText('Base légale de l’exonération').value)
      .toBe(CORPS.lignes[0].tva_base_legale)
    expect(screen.queryByRole('alert')).toBeNull()
    // ATOT20 — l'alerte dit le taux appliqué (« TVA appliquée : N % (catalogue : M %) »).
    expect(screen.queryByText(/TVA appliquée/)).toBeNull()
  })

  it('ligne à 0 % sans base ⇒ l’alerte d’incohérence reste', () => {
    const [pompe] = lignesEcran()
    monter({ ...pompe, tvaBaseLegale: '' })
    expect(screen.getByText(/TVA appliquée : 0 % \(catalogue : \d+ %\)/)).toBeTruthy()
  })

  it('ligne à 20 % ⇒ aucun champ de base légale', () => {
    const [, variateur] = lignesEcran()
    monter(variateur)
    expect(screen.queryByTestId('ligne-base-legale')).toBeNull()
  })

  it('saisir la base remonte par onSetField(tvaBaseLegale) — taux jamais touché', () => {
    const [pompe] = lignesEcran()
    const { onSetField } = monter({ ...pompe, tvaBaseLegale: '' })
    fireEvent.change(screen.getByLabelText('Base légale de l’exonération'),
      { target: { value: 'Texte saisi' } })
    expect(onSetField).toHaveBeenCalledWith('k0', 'tvaBaseLegale', 'Texte saisi')
    expect(onSetField.mock.calls.some(([, champ]) => champ === 'taux_tva')).toBe(false)
  })

  it('le 400 serveur s’affiche sous le champ de SA ligne', () => {
    const lignes = lignesEcran().map((l) => ({ ...l, tvaBaseLegale: '' }))
    const parLigne = erreursBaseLegaleServeur(REFUS, lignes)
    expect(Object.keys(parLigne)).toEqual(['k0'])
    monter({ ...lignes[0], _erreurBaseLegale: parLigne.k0 })
    expect(screen.getByRole('alert').textContent).toBe(REFUS.detail)
  })
})
