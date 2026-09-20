/* CAL143 — le diagramme de pertes (cascade) du module calepinage.

   Ce qui est prouvé ici : chaque poste vient EXACTEMENT du contrat
   `apps/calepinage/contract_samples/calepinage_resultat.json`
   (`production.pertes`, PACT10/13 — `reponseContrat`), un poste non sourcé
   (`source: null`) reste NOMMÉ (jamais masqué) et sa colonne Source affiche
   « — », et l'absence de pertes (non simulé) dit pourquoi plutôt que
   d'afficher un graphe vide silencieux. */
import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { reponseContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: { resultat: vi.fn() } },
}))

import calepinageApi from '../../../api/calepinageApi'
import DiagrammePertes from './DiagrammePertes'

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const servir = (variante) => {
  calepinageApi.calepinages.resultat
    .mockResolvedValue(reponseContrat('calepinage', 'calepinage_resultat', variante))
}

const rendre = () => render(
  <MemoryRouter><DiagrammePertes calepinageId={1} /></MemoryRouter>,
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('DiagrammePertes (CAL143)', () => {
  it('affiche chaque poste du contrat, avec sa source', async () => {
    servir('exemple')
    rendre()

    const cascade = await screen.findByTestId('cal143-cascade')
    const table = within(cascade).getByRole('table')
    // Postes exacts du contrat (`production.pertes`).
    expect(within(table).getByText('Horizon et ombrage proche')).toBeInTheDocument()
    expect(within(table).getByText('Échauffement cellule au-dessus du STC')).toBeInTheDocument()
    expect(within(table).getByText('Salissure et poussière')).toBeInTheDocument()
    expect(within(table).getByText('Rendement de conversion onduleur')).toBeInTheDocument()
    // Sources françaises lisibles, jamais le code brut.
    expect(within(table).getAllByText('Mesure').length).toBeGreaterThan(0)
    expect(within(table).getAllByText('Hypothèse').length).toBeGreaterThan(0)
  })

  it('poste non sourcé : nommé, jamais masqué, source affichée « — »', async () => {
    servir('exemple')
    rendre()

    const cascade = await screen.findByTestId('cal143-cascade')
    const table = within(cascade).getByRole('table')
    // `availability` porte `source: null` dans l'exemple.
    expect(within(table).getByText('Indisponibilité réseau et maintenance')).toBeInTheDocument()
    const ligne = within(table).getByText('Indisponibilité réseau et maintenance').closest('tr')
    expect(within(ligne).getByText('—')).toBeInTheDocument()
  })

  it('non simulé (pertes vides) : dit pourquoi, jamais un graphe vide silencieux', async () => {
    servir('exemple_vide')
    rendre()

    await screen.findByTestId('cal143-panneau')
    expect(screen.getByText('Pertes non calculées')).toBeInTheDocument()
    expect(screen.getByText(
      'Calepinage non simulé : la pose est connue, la production ne l\'est pas.',
    )).toBeInTheDocument()
    expect(screen.queryByTestId('cal143-cascade')).toBeNull()
  })

  it('erreur réseau : message français, aucune valeur inventée', async () => {
    calepinageApi.calepinages.resultat.mockRejectedValue(new Error('boom'))
    rendre()

    expect(await screen.findByTestId('cal143-erreur')).toHaveTextContent(
      'Diagramme de pertes indisponible.',
    )
  })
})
