/* ACAL153 — l'onglet « Saisies électriques ».

   Les réponses viennent de l'exemple COMMITTÉ `calepinage_entree_electrique.json` ; seule la
   façade `calepinageApi` est mockée, le composant ne l'est pas. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: { entreeElectrique: vi.fn(), enregistrerEntreeElectrique: vi.fn() },
  },
}))

import calepinageApi from '../../../api/calepinageApi'
import SaisiesElectriques, { corpsDeSaisie, depuisEntree } from './SaisiesElectriques'

const EXEMPLE = exempleContrat('calepinage', 'calepinage_entree_electrique')
const VIDE = exempleContrat('calepinage', 'calepinage_entree_electrique', 'exemple_vide')
// L'entrée de l'exemple, avec les trois longueurs de liaison portées par `cheminement`.
const ENTREE = {
  ...EXEMPLE.entree,
  cheminement: { descente_m: 4, coffret_vers_onduleur_m: 6, onduleur_vers_tgbt_m: 12 },
}

const servir = (entree) => calepinageApi.calepinages.entreeElectrique
  .mockResolvedValue({ data: { ...EXEMPLE, entree } })
const rendre = () => render(
  <MemoryRouter><SaisiesElectriques calepinageId={5} /></MemoryRouter>,
)
const champ = (cle) => document.getElementById(`acal153-champ-${cle}`)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('SaisiesElectriques (ACAL153)', () => {
  it('préremplit depuis GET puis un enregistrement sans retouche renvoie un corps équivalent à l’entrée stockée', async () => {
    servir(ENTREE)
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue({ data: {} })

    rendre()
    await screen.findByTestId('acal153-formulaire')
    expect(champ('dc_m')).toHaveValue(ENTREE.dc_m)
    expect(champ('descente_m')).toHaveValue(4)
    expect(champ('regime')).toHaveValue('TT')
    expect(champ('transformateur-declare')).toHaveValue('oui')

    await userEvent.click(screen.getByTestId('acal153-enregistrer'))

    await waitFor(() => expect(calepinageApi.calepinages.enregistrerEntreeElectrique).toHaveBeenCalledTimes(1))
    const [, corps] = calepinageApi.calepinages.enregistrerEntreeElectrique.mock.calls[0]
    expect(Object.keys(corps).length).toBeGreaterThan(8)
    for (const [cle, valeur] of Object.entries(corps)) {
      expect({ cle, valeur }).toEqual({ cle, valeur: ENTREE[cle] })
    }
    // `zone_keraunique` est servi « faible » (texte) : illisible pour le formulaire, jamais écrasé.
    expect('zone_keraunique' in corps).toBe(false)
  })

  it('refus 400 affiché sous le champ nommé', async () => {
    servir(VIDE.entree)
    const refus = exempleContrat('calepinage', 'calepinage_entree_electrique', 'exemple_refus_400')
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockRejectedValue({ response: { status: 400, data: refus } })

    rendre()
    await screen.findByTestId('acal153-formulaire')
    await userEvent.type(champ('temperature_min_c'), '-80')
    await userEvent.click(screen.getByTestId('acal153-enregistrer'))

    expect(await screen.findByTestId('acal153-erreur-temperature_min_c'))
      .toHaveTextContent(refus.temperature_min_c)
    expect(champ('temperature_min_c')).toHaveAttribute('aria-invalid', 'true')
  })

  it('transformateur sans source refusé sous sa grandeur', async () => {
    servir(VIDE.entree)
    const message = '« perte_a_vide_kw » est saisi sans sa source.'
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockRejectedValue({
      response: { status: 400, data: { 'transformateur.perte_a_vide_kw.source': message } },
    })

    rendre()
    await screen.findByTestId('acal153-formulaire')
    await userEvent.selectOptions(champ('transformateur-declare'), 'oui')
    await userEvent.type(champ('perte_a_vide_kw-valeur'), '0.8')
    await userEvent.click(screen.getByTestId('acal153-enregistrer'))

    await waitFor(() => expect(calepinageApi.calepinages.enregistrerEntreeElectrique).toHaveBeenCalled())
    const [, corps] = calepinageApi.calepinages.enregistrerEntreeElectrique.mock.calls[0]
    expect(corps.transformateur).toMatchObject({ declare: true, perte_a_vide_kw: { valeur: 0.8, source: null } })
    expect(await screen.findByTestId('acal153-erreur-perte_a_vide_kw')).toHaveTextContent(message)
    expect(screen.queryByTestId('acal153-bandeau')).toBeNull()
  })

  it('champ vidé = null, jamais 0', async () => {
    servir(ENTREE)
    calepinageApi.calepinages.enregistrerEntreeElectrique.mockResolvedValue({ data: {} })

    rendre()
    await screen.findByTestId('acal153-formulaire')
    await userEvent.clear(champ('dc_m'))
    await userEvent.clear(champ('descente_m'))
    await userEvent.click(screen.getByTestId('acal153-enregistrer'))

    await waitFor(() => expect(calepinageApi.calepinages.enregistrerEntreeElectrique).toHaveBeenCalled())
    const [, corps] = calepinageApi.calepinages.enregistrerEntreeElectrique.mock.calls[0]
    expect(corps.dc_m).toBeNull()
    expect(corps.cheminement.descente_m).toBeNull()
    // Les autres clés du cheminement sont conservées telles quelles.
    expect(corps.cheminement.coffret_vers_onduleur_m).toBe(6)
  })

  it('une saisie jamais touchée et absente du stock n’est pas inventée', () => {
    const corps = corpsDeSaisie(depuisEntree({}), {})
    expect(corps).toEqual({})
  })

  it('une lecture en panne le DIT', async () => {
    calepinageApi.calepinages.entreeElectrique.mockRejectedValue(new Error('boum'))

    rendre()

    expect(await screen.findByTestId('acal153-erreur')).toBeInTheDocument()
  })
})
