/* CALX65 — le bandeau de provenance des deux productions dans l'atelier.

   Ce qui est prouvé ici (Done, PLAN2.md) : sans simulation, UNE SEULE
   mention (celle de l'estimation rapide, avec le mot « forfaitaires ») ;
   avec simulation, les DEUX valeurs et leurs DEUX provenances sont visibles
   côte à côte — les chiffres viennent tels quels du contrat
   `apps/calepinage/contract_samples/calepinage_resultat.json` (PACT10/13 —
   `reponseContrat`, jamais une charge utile écrite à la main). */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { reponseContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: { resultat: vi.fn() } },
}))

import calepinageApi from '../../../api/calepinageApi'
import BandeauProvenanceProduction from './BandeauProvenanceProduction'

const servir = (variante) => {
  calepinageApi.calepinages.resultat
    .mockResolvedValue(reponseContrat('calepinage', 'calepinage_resultat', variante))
}

const rendre = () => render(
  <MemoryRouter><BandeauProvenanceProduction calepinageId={1} /></MemoryRouter>,
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('BandeauProvenanceProduction (CALX65)', () => {
  it('sans simulation : une seule mention, avec le mot « forfaitaires »', async () => {
    servir('exemple_vide')
    rendre()

    const bandeau = await screen.findByTestId('calx65-bandeau')
    expect(within(bandeau).getByTestId('calx65-rapide')).toHaveTextContent('forfaitaires')
    expect(within(bandeau).getByTestId('calx65-rapide')).toHaveTextContent(
      'Estimation rapide (PVGIS PVcalc, pertes forfaitaires 20 %)',
    )
    // UNE SEULE mention (Done) : la moitié « Simulation » n'existe pas.
    expect(within(bandeau).queryByTestId('calx65-simulation')).toBeNull()
  })

  it('simulation périmée (CALX70, `production` publiée null) : une seule mention aussi', async () => {
    servir('exemple_perime')
    rendre()

    await screen.findByTestId('calx65-bandeau')
    expect(screen.queryByTestId('calx65-simulation')).toBeNull()
  })

  it('avec simulation : les deux valeurs et leurs deux provenances, côte à côte', async () => {
    servir('exemple')
    rendre()

    const bandeau = await screen.findByTestId('calx65-bandeau')
    // Les DEUX mentions sont visibles ENSEMBLE (le même bandeau), jamais l'une
    // à la place de l'autre.
    expect(within(bandeau).getByTestId('calx65-rapide')).toHaveTextContent('forfaitaires')
    const simulation = within(bandeau).getByTestId('calx65-simulation')
    expect(simulation).toHaveTextContent('P50')
    // `formatNumber` insère une espace fine insécable dans « 13 000 » :
    // `getByText` normalise cette espace en comparant, `toHaveTextContent`
    // sur la chaîne attendue ne le ferait pas (piège banqué en lane).
    expect(within(simulation).getByText(/13.000 kWh\/an/)).toBeInTheDocument()
    expect(simulation).toHaveTextContent('chaîne de pertes du')
    // `calcule_le` de l'exemple : 2026-09-19T11:30:00Z → 19/09/2026 (formatDate).
    expect(simulation).toHaveTextContent('19/09/2026')

    const lien = within(simulation).getByTestId('calx65-lien-production')
    expect(lien).toHaveAttribute('href', '/calepinage/1?onglet=production')
  })
})
