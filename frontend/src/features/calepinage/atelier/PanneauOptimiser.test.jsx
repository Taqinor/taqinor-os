/* ACAL469 — l'onglet « Optimiser » : lance le balayage, suit le job, affiche la
   grille (couleur = rendement spécifique), applique l'optimum à l'atelier.

   Les charges servies viennent du contrat `calepinage_balayage.json` (ACAL388,
   `exemple` = accusé 202, `exemple_resultat` = résultat du job) — jamais d'un
   objet écrit à la main. Mutant visé : ne pas épingler l'azimut ⇒ échec. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: { balayer: vi.fn() }, moteur: { resultat: vi.fn() } },
}))
vi.mock('../../../hooks/useHasPermission', () => ({ useHasPermission: () => true }))

import calepinageApi from '../../../api/calepinageApi'
import PanneauOptimiser from './PanneauOptimiser'

const accuse = () => exempleContrat('calepinage', 'calepinage_balayage', 'exemple')
const resultat = () => exempleContrat('calepinage', 'calepinage_balayage', 'exemple_resultat')

const servir = (res) => {
  calepinageApi.calepinages.balayer.mockResolvedValue({ data: accuse() })
  calepinageApi.moteur.resultat.mockResolvedValue({
    data: { ...accuse(), statut: 'done', progress_pct: 100, resultat: res },
  })
}

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

describe('PanneauOptimiser (ACAL469)', () => {
  it('Lancer poste le balayage, suit le job puis affiche la grille colorée et l’optimum', async () => {
    servir({ ...resultat(), grille: resultat().grille.map((l) => ({ inclinaison_deg: l.inclinaison_deg, p50_kwh: l.p50_kwh, rendement_specifique_kwh_kwc: l.rendement_specifique_kwh_kwc })) })
    render(<PanneauOptimiser calepinageId={7} />)
    fireEvent.click(screen.getByTestId('acal469-lancer'))
    await screen.findByTestId('acal469-grille')
    const [, corps] = calepinageApi.calepinages.balayer.mock.calls[0]
    expect(calepinageApi.calepinages.balayer.mock.calls[0][0]).toBe(7)
    expect(corps.pan).toBe(1)
    expect(corps.axes.map((a) => a.nom)).toEqual(['inclinaison_deg', 'azimut_deg'])
    const cases = screen.getAllByTestId('acal469-case')
    expect(cases).toHaveLength(2)
    expect(cases[0].style.background).not.toBe(cases[1].style.background)
    expect(screen.getByTestId('acal469-optimum')).toHaveTextContent('1 100,0 kWh/kWc')
    expect(screen.queryByTestId('acal469-incomplet')).toBeNull()
  })

  it('Appliquer l’optimum épingle inclinaison ET azimut par appliquerSection(choixConception)', async () => {
    servir({
      grille: [{ inclinaison_deg: 20, azimut_deg: 180, p50_kwh: 1100, rendement_specifique_kwh_kwc: 1100 }],
      optimum: { inclinaison_deg: 20, azimut_deg: 180, p50_kwh: 1100, rendement_specifique_kwh_kwc: 1100 },
      complete: true, socle_manquant: [],
    })
    const appliquerSection = vi.fn()
    render(<PanneauOptimiser calepinageId={7} builderApi={{ appliquerSection }} />)
    fireEvent.click(screen.getByTestId('acal469-lancer'))
    fireEvent.click(await screen.findByTestId('acal469-appliquer'))
    expect(appliquerSection).toHaveBeenCalledWith('choixConception', {
      tilt: 20, azimuth: 180, epingles: ['tilt', 'azimuth'],
    })
    expect(screen.getByTestId('acal469-message')).toHaveTextContent('enregistrez le calepinage')
  })

  it('un résultat incomplet est signalé avec le socle manquant', async () => {
    servir({ ...resultat(), complete: false, socle_manquant: ['pvgis'] })
    render(<PanneauOptimiser calepinageId={7} />)
    fireEvent.click(screen.getByTestId('acal469-lancer'))
    expect(await screen.findByTestId('acal469-incomplet')).toHaveTextContent('pvgis')
  })

  it('un refus 400 du serveur nomme le champ fautif', async () => {
    calepinageApi.calepinages.balayer.mockRejectedValue({ response: { data: { pan: ['Pan introuvable dans le document : 9.'] } } })
    render(<PanneauOptimiser calepinageId={7} />)
    fireEvent.click(screen.getByTestId('acal469-lancer'))
    await waitFor(() => expect(screen.getByTestId('acal469-refus')).toHaveTextContent('pan : Pan introuvable'))
  })
})
