/* ACAL888 — l'onglet « Livré et prévu » (étape Résultats, niveau expert).

   Tout est affirmé sur l'échantillon COMMITTÉ `calepinage_production_mesuree.json` (ACAL886) :
   1. douze mesures (onze saisies + un mois vide) postent `{annee, mesures}` et rendent douze lignes
      d'écart ; l'écart annuel servi est lu avec sa phrase ;
   2. un mois vide s'écrit « — » (jamais 0) et n'est pas envoyé ;
   3. une colonne collée remplit les mois à partir du champ visé ;
   4. un refus nommant `mesures[2].kwh_mesure` s'affiche sous le champ du mois envoyé en position 2. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { documentContrat, exempleContrat, reponseContrat } from '../../../test/fixtures/contractSamples'

const mocks = vi.hoisted(() => ({ hasPermission: vi.fn(() => true) }))
vi.mock('../../../hooks/useHasPermission', () => ({
  useHasPermission: (code) => mocks.hasPermission(code),
}))
vi.mock('../commun/Pourquoi', () => ({ default: ({ cle }) => <span data-testid="pourquoi" data-cle={cle} /> }))
vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: { productionMesuree: vi.fn(), enregistrerProductionMesuree: vi.fn() } },
}))

import calepinageApi from '../../../api/calepinageApi'
import ProductionMesuree from './ProductionMesuree'

const NOM = 'calepinage_production_mesuree'
const contrat = () => documentContrat('calepinage', NOM)
const rendre = () => render(<MemoryRouter><ProductionMesuree calepinageId={1} /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.hasPermission.mockReturnValue(true)
  calepinageApi.calepinages.productionMesuree.mockResolvedValue(reponseContrat('calepinage', NOM))
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('ProductionMesuree (ACAL888)', () => {
  it('l’exemple du contrat rend douze écarts lisibles, l’écart annuel et sa phrase', async () => {
    rendre()

    expect(await screen.findByTestId('acal888-tableau')).toBeTruthy()
    const servi = contrat().exemple
    servi.ecarts.forEach((ligne) => expect(screen.getByTestId(`acal888-ligne-${ligne.mois}`)).toBeTruthy())
    expect(screen.getAllByTestId(/^acal888-ligne-/)).toHaveLength(12)
    expect(screen.getByTestId('acal888-ecart-1')).toHaveTextContent('-3,4 %')
    expect(screen.getByTestId('acal888-ecart-3')).toHaveTextContent('+2,7 %')
    expect(screen.getByTestId('acal888-annuel')).toHaveTextContent('Le réel est 1,4 % en dessous de la prévision.')
    expect(screen.getByTestId('acal888-motif')).toHaveTextContent(servi.motif)
    expect(screen.getByTestId('pourquoi')).toHaveAttribute('data-cle', 'mesure.ecart')
    // Les champs sont relus du serveur.
    expect(screen.getByTestId('acal888-annee').value).toBe('2026')
    expect(screen.getByTestId('acal888-champ-1').value).toBe('850')
  })

  it('un mois vide s’écrit « — » (jamais 0) et n’est pas envoyé à l’enregistrement', async () => {
    rendre()
    await screen.findByTestId('acal888-tableau')
    expect(screen.getByTestId('acal888-mesure-12').textContent).toBe('—')
    expect(screen.getByTestId('acal888-ecart-12').textContent).toBe('—')
    calepinageApi.calepinages.enregistrerProductionMesuree.mockResolvedValue(reponseContrat('calepinage', NOM))

    fireEvent.click(screen.getByTestId('acal888-enregistrer'))

    await waitFor(() => expect(calepinageApi.calepinages.enregistrerProductionMesuree).toHaveBeenCalledTimes(1))
    const [id, corps] = calepinageApi.calepinages.enregistrerProductionMesuree.mock.calls[0]
    expect(id).toBe(1)
    expect(corps).toEqual(exempleContrat('calepinage', NOM, 'exemple_corps'))
    expect(corps.mesures).toHaveLength(11)
  })

  it('une colonne collée remplit les mois à partir du champ visé', async () => {
    calepinageApi.calepinages.productionMesuree.mockResolvedValue(reponseContrat('calepinage', NOM, 'exemple_vide'))
    rendre()
    await screen.findByTestId('acal888-motif')

    fireEvent.paste(screen.getByTestId('acal888-champ-3'), {
      clipboardData: { getData: () => '100\n200,5\n300' },
    })

    expect(screen.getByTestId('acal888-champ-2').value).toBe('')
    expect(screen.getByTestId('acal888-champ-3').value).toBe('100')
    expect(screen.getByTestId('acal888-champ-4').value).toBe('200,5')
    expect(screen.getByTestId('acal888-champ-5').value).toBe('300')
    expect(screen.queryByTestId('acal888-tableau')).toBeNull()
  })

  it('un refus mesures[2].kwh_mesure s’affiche sous le champ du mois envoyé en position 2', async () => {
    calepinageApi.calepinages.productionMesuree.mockResolvedValue(reponseContrat('calepinage', NOM, 'exemple_vide'))
    rendre()
    await screen.findByTestId('acal888-motif')
    fireEvent.change(screen.getByTestId('acal888-annee'), { target: { value: '2026' } })
    fireEvent.change(screen.getByTestId('acal888-champ-1'), { target: { value: '850' } })
    fireEvent.change(screen.getByTestId('acal888-champ-4'), { target: { value: '12x' } })
    fireEvent.change(screen.getByTestId('acal888-champ-9'), { target: { value: '-4' } })
    calepinageApi.calepinages.enregistrerProductionMesuree.mockRejectedValue({
      response: { data: { 'mesures[2].kwh_mesure': ['La production mesurée est un nombre positif.'] } },
    })

    fireEvent.click(screen.getByTestId('acal888-enregistrer'))

    expect(await screen.findByTestId('acal888-erreur-9')).toHaveTextContent('La production mesurée est un nombre positif.')
    expect(screen.queryByTestId('acal888-erreur-4')).toBeNull()
  })

  it('sans le droit d’écrire : pas de bouton d’enregistrement', async () => {
    mocks.hasPermission.mockReturnValue(false)
    rendre()
    await screen.findByTestId('acal888-tableau')

    expect(screen.queryByTestId('acal888-enregistrer')).toBeNull()
    expect(screen.getByTestId('acal888-sans-droit')).toBeTruthy()
  })
})
