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
import { exempleContrat, reponseContrat } from '../../../test/fixtures/contractSamples'

vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: { resultat: vi.fn(), simuler: vi.fn() },
    moteur: { resultat: vi.fn() },
  },
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

/* CALX48 — `exemple` porte DÉSORMAIS aussi une `cascade` (CALX141), que le
   panneau affiche en PRIORITÉ (Done) : la liste plate reste testée ici avec
   son propre repli, `cascade` retirée — jamais une charge inventée, la même
   `exemple` du contrat, juste amputée de la clé que ces deux tests ne
   couvrent pas. */
const servirSansCascade = (variante = 'exemple') => {
  const donnees = exempleContrat('calepinage', 'calepinage_resultat', variante)
  delete donnees.cascade
  calepinageApi.calepinages.resultat.mockResolvedValue({ data: donnees })
}

const rendre = () => render(
  <MemoryRouter><DiagrammePertes calepinageId={1} /></MemoryRouter>,
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('DiagrammePertes (CAL143)', () => {
  it('affiche chaque poste du contrat, avec sa source', async () => {
    servirSansCascade()
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
    servirSansCascade()
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

/* CALX48 — `resultat['cascade'].etapes` (CALX141) prime sur la liste plate
   quand elle existe ; la liste plate reste le repli, en DISANT laquelle des
   deux est affichée. Le contrat `calepinage_pertes_cascade.json` (CALX141),
   PAS seulement `calepinage_resultat.json`, est importé ici pour la forme
   détaillée (rang, énergie avant/après, étape omise, gain). */
describe('DiagrammePertes — cascade séquentielle (CALX48)', () => {
  const donneesAvecCascadeDetaillee = () => ({
    ...exempleContrat('calepinage', 'calepinage_resultat', 'exemple'),
    cascade: exempleContrat('calepinage', 'calepinage_pertes_cascade', 'exemple').cascade,
  })

  it('cascade servie : rang, énergie avant/après, étape omise NOMMÉE avec son motif et une perte VIDE', async () => {
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: donneesAvecCascadeDetaillee() })
    rendre()

    const cascade = await screen.findByTestId('calx48-cascade-detaillee')
    const table = within(cascade).getByRole('table')

    // L'étape omise (spectral, D-CALX 16) reste NOMMÉE, jamais masquée.
    const ligneSpectrale = within(table).getByText('Correction spectrale').closest('tr')
    expect(within(ligneSpectrale).getByText(
      'D-CALX 16 — le spectral figure dans la cascade et reste TOUJOURS omis avec '
      + 'son motif, jamais forfaitisé.',
    )).toBeInTheDocument()
    // « perte_pct vide » (Done CALX48) : jamais un 0 % qui prétendrait que
    // l'étape omise n'a rien coûté. NB : `toHaveTextContent('')` serait
    // TOUJOURS vrai (chaîne vide incluse dans tout texte) — on lit le
    // `textContent` normalisé directement.
    expect(ligneSpectrale.querySelector('td[data-label="Perte"]').textContent.trim()).toBe('')

    // Une étape calculée porte sa vraie énergie avant/après et sa perte.
    // `getByText` (pas `toHaveTextContent`) : son normaliseur ramène l'espace
    // fine insécable (U+202F) des milliers de `formatNumber` à une espace
    // normale AVANT comparaison — `toHaveTextContent` ne normalise que le DOM,
    // jamais la chaîne attendue (piège catalogué dans `LANE_RULES_CALX.md` §2).
    const ligneThermique = within(table).getByText(
      'Échauffement de la cellule au-dessus du STC',
    ).closest('tr')
    expect(within(ligneThermique).getByText('16 800 kWh')).toBeInTheDocument()
    expect(within(ligneThermique).getByText('15 456 kWh')).toBeInTheDocument()

    // Le gain bifacial reste visible (parité PVsyst : un gain se lit dans la
    // même cascade qu'une perte, jamais dans un tableau à part).
    expect(within(table).getByText('Gain bifacial en face arrière')).toBeInTheDocument()

    expect(screen.getByTestId('calx48-mention-source'))
      .toHaveTextContent('Chaîne de pertes séquentielle calculée')
  })

  it('cascade absente : la liste plate (D-CALX 11) est affichée, avec la mention « postes saisis, non calculés »', async () => {
    servirSansCascade()
    rendre()

    await screen.findByTestId('cal143-cascade')
    expect(screen.queryByTestId('calx48-cascade-detaillee')).toBeNull()
    expect(screen.getByTestId('calx48-mention-source')).toHaveTextContent(
      'Postes saisis, non calculés',
    )
  })

  it('simulation périmée (CALX70) : le bandeau de péremption remplace un chiffre trompeur', async () => {
    servir('exemple_perime')
    rendre()

    await screen.findByTestId('cal143-panneau')
    expect(screen.getByTestId('calx48-perime')).toHaveTextContent(
      'simulation périmée : le document a changé depuis le calcul du 19/09/2026',
    )
  })
})
