/* CAL236 — le panneau « Production » du module calepinage.

   Ce qui est prouvé ici : les valeurs affichées sont EXACTEMENT celles du
   contrat `apps/calepinage/contract_samples/calepinage_resultat.json`
   (PACT10/13 — `reponseContrat`, jamais une charge utile écrite à la main),
   une grandeur `null` s'affiche « non calculée » (jamais `0`), et un pan sans
   module affiche un vrai `0` distinct de « non calculée ». */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { reponseContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: { resultat: vi.fn() } },
}))

import calepinageApi from '../../../api/calepinageApi'
import PanneauProduction from './PanneauProduction'

const servir = (variante) => {
  calepinageApi.calepinages.resultat
    .mockResolvedValue(reponseContrat('calepinage', 'calepinage_resultat', variante))
}

const rendre = () => render(
  <MemoryRouter><PanneauProduction calepinageId={1} /></MemoryRouter>,
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('PanneauProduction (CAL236)', () => {
  it('affiche les grandeurs de production EXACTEMENT telles que le contrat les sert', async () => {
    servir('exemple')
    rendre()

    const panneau = await screen.findByTestId('cal236-panneau')
    expect(within(panneau).getByText('13 000 kWh')).toBeInTheDocument() // P50
    expect(within(panneau).getByText('11 900 kWh')).toBeInTheDocument() // P90
    expect(within(panneau).getByText('79,9 %')).toBeInTheDocument() // PR
    expect(within(panneau).getByText('1 504,6 kWh/kWc')).toBeInTheDocument()
    expect(screen.queryByTestId('cal236-non-simule')).toBeNull()
  })

  it('production mensuelle et par pan viennent du serveur, aucune ne recalcule', async () => {
    servir('exemple')
    rendre()

    await screen.findByTestId('cal236-panneau')
    const mensuel = screen.getByTestId('cal236-mensuel')
    expect(within(mensuel).getByText('Janvier')).toBeInTheDocument()
    expect(within(mensuel).getByText('880 kWh')).toBeInTheDocument()

    const parPan = screen.getByTestId('cal236-par-pan')
    expect(within(parPan).getByText('PAN-A')).toBeInTheDocument()
    expect(within(parPan).getByText('8 900 kWh')).toBeInTheDocument()
    expect(within(parPan).getByText('PAN-B')).toBeInTheDocument()
  })

  it('non simulé : chaque grandeur « non calculée », jamais 0, et le motif du serveur affiché', async () => {
    servir('exemple_vide')
    rendre()

    await screen.findByTestId('cal236-panneau')
    expect(screen.getByTestId('cal236-non-simule')).toHaveTextContent(
      'Calepinage non simulé : la pose est connue, la production ne l\'est pas.',
    )
    const total = screen.getByTestId('cal236-total')
    // Aucune occurrence de « 0 kWh » : la production non lancée n'est jamais un zéro.
    expect(within(total).queryByText(/^0 kWh$/)).toBeNull()
    expect(within(total).getAllByText('non calculée').length).toBeGreaterThan(0)
  })

  it('un pan sans module affiche un vrai 0 modules, distinct de « non calculée »', async () => {
    servir('exemple_vide')
    rendre()

    await screen.findByTestId('cal236-panneau')
    const parPan = screen.getByTestId('cal236-par-pan')
    // exemple_vide : PAN-A porte 12 modules (un vrai nombre) et une production null.
    const ligne = within(parPan).getByText('PAN-A').closest('tr')
    expect(within(ligne).getByText('12')).toBeInTheDocument()
    expect(within(ligne).getAllByText('non calculée').length).toBeGreaterThan(0)
  })

  it('erreur réseau : message français, aucune valeur inventée', async () => {
    calepinageApi.calepinages.resultat.mockRejectedValue(new Error('boom'))
    rendre()

    expect(await screen.findByTestId('cal236-erreur')).toHaveTextContent(
      'Production indisponible.',
    )
  })
})
