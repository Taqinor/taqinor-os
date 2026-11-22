/* ACAL847 — l'onglet « Consommation mesurée » (étape Résultats, niveau expert).

   Tout est affirmé sur l'échantillon COMMITTÉ `calepinage_asbuilt_mesures.json` (ACAL846) :
   1. avec le droit `calepinage_approuver`, 12 saisies postent `{kwh}` et rendent 12 lignes
      simulé / mesuré / écart en % (mois vide = vide, jamais 0), la mention du serveur et l'eau ;
   2. sans le droit, l'onglet dit seulement que le droit manque et AUCUNE requête ne part ;
   3. un refus 409 nommant `kwh[2]` s'affiche sous le champ de mars. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { documentContrat, reponseContrat } from '../../../test/fixtures/contractSamples'

const mocks = vi.hoisted(() => ({ hasPermission: vi.fn(() => false) }))
vi.mock('../../../hooks/useHasPermission', () => ({
  useHasPermission: (code) => mocks.hasPermission(code),
}))
vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: { ecartMesures: vi.fn() } },
}))

import calepinageApi from '../../../api/calepinageApi'
import EcartMesures from './EcartMesures'

const contrat = () => documentContrat('calepinage', 'calepinage_asbuilt_mesures')
const rendre = () => render(<MemoryRouter><EcartMesures calepinageId={7} /></MemoryRouter>)

const saisirTout = (kwh) => {
  kwh.forEach((valeur, i) => {
    fireEvent.change(screen.getByTestId(`acal847-champ-${i + 1}`), {
      target: { value: valeur === null ? '' : String(valeur) },
    })
  })
}

beforeEach(() => { vi.clearAllMocks(); mocks.hasPermission.mockReturnValue(true) })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('EcartMesures (ACAL847)', () => {
  it('avec le droit : 12 saisies postent {kwh} et rendent 12 écarts, la mention et l’eau', async () => {
    calepinageApi.calepinages.ecartMesures.mockResolvedValue(reponseContrat('calepinage', 'calepinage_asbuilt_mesures'))
    rendre()
    saisirTout(contrat().corps.kwh)

    fireEvent.click(screen.getByTestId('acal847-comparer'))

    await waitFor(() => expect(calepinageApi.calepinages.ecartMesures).toHaveBeenCalledTimes(1))
    const [id, corps] = calepinageApi.calepinages.ecartMesures.mock.calls[0]
    expect(id).toBe(7)
    expect(corps).toEqual({ kwh: contrat().corps.kwh })
    const servi = contrat().exemple.consommation.lignes
    expect(await screen.findByTestId('acal847-ligne-1')).toBeTruthy()
    servi.forEach((ligne) => {
      expect(screen.getByTestId(`acal847-ligne-${ligne.mois}`)).toBeTruthy()
    })
    expect(screen.getByTestId('acal847-ecart-1')).toHaveTextContent('3,7')
    // Mois sans mesure : vide, jamais 0.
    expect(screen.getByTestId('acal847-mesure-12').textContent).toBe('—')
    expect(screen.getByTestId('acal847-ecart-12').textContent).toBe('—')
    expect(screen.getByTestId('acal847-mention')).toHaveTextContent(contrat().exemple.mention)
    expect(screen.getByTestId('acal847-eau')).toHaveTextContent('simulé : non enregistré')
  })

  it('sans le droit : la mention seule, aucune requête', () => {
    mocks.hasPermission.mockReturnValue(false)
    rendre()

    expect(screen.getByTestId('acal847-sans-droit'))
      .toHaveTextContent('Réservé aux porteurs du droit calepinage_approuver')
    expect(screen.queryByTestId('acal847-comparer')).toBeNull()
    expect(calepinageApi.calepinages.ecartMesures).not.toHaveBeenCalled()
  })

  it('un refus nommant kwh[2] s’affiche sous le champ de mars', async () => {
    calepinageApi.calepinages.ecartMesures.mockRejectedValue({ response: { data: contrat().refus_409_kwh } })
    rendre()
    saisirTout([850, 720, -5])

    fireEvent.click(screen.getByTestId('acal847-comparer'))

    expect(await screen.findByTestId('acal847-erreur-3')).toHaveTextContent(contrat().refus_409_kwh['kwh[2]'])
    expect(screen.queryByTestId('acal847-erreur-2')).toBeNull()
  })

  it('sans simulation : le motif du serveur, pas de tableau', async () => {
    calepinageApi.calepinages.ecartMesures.mockResolvedValue({
      data: { consommation: contrat().exemple_sans_simulation, eau: contrat().exemple.eau, mention: contrat().exemple.mention },
    })
    rendre()
    saisirTout([850])

    fireEvent.click(screen.getByTestId('acal847-comparer'))

    expect(await screen.findByTestId('acal847-motif')).toHaveTextContent('lancez la simulation')
    expect(screen.queryByTestId('acal847-ligne-1')).toBeNull()
  })
})
