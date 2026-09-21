/* CAL236 — le panneau « Production » du module calepinage.

   Ce qui est prouvé ici : les valeurs affichées sont EXACTEMENT celles du
   contrat `apps/calepinage/contract_samples/calepinage_resultat.json`
   (PACT10/13 — `reponseContrat`, jamais une charge utile écrite à la main),
   une grandeur `null` s'affiche « non calculée » (jamais `0`), et un pan sans
   module affiche un vrai `0` distinct de « non calculée ». */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, within, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat, reponseContrat } from '../../../test/fixtures/contractSamples'

/* CALX64 — le panneau monte désormais `TapisHoraire`, qui relit la série par
   la porte d'export (CAL144/CALX6) : la doublure doit porter `exportCsv`,
   sinon le panneau tomberait sur une méthode absente. Elle rend une réponse
   VIDE : le tapis affiche alors son état « Lancer la simulation », ce que ce
   fichier n'a pas à juger (il a son propre test). */
vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: { resultat: vi.fn(), exportCsv: vi.fn(), simuler: vi.fn() },
    moteur: { resultat: vi.fn() },
  },
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

/* CALX48 — le refus « production non calculée » devient ACTIONNABLE : un
   bouton « Lancer la simulation » (`POST simuler/`), le suivi du job
   (`moteur/resultat/<job_id>/`, même patron que `RemplissageProuve` CAL79) et
   la liste NOMMÉE des manques publiée par le serveur (`avertissements`). */
describe('PanneauProduction — refus actionnable (CALX48)', () => {
  // `exemple_vide` (pertes vides) DOIT désactiver le bouton (Done) ; les
  // scénarios de clic ont donc besoin de postes de pertes déjà saisis — repris
  // TELS QUELS de `exemple` (même contrat), jamais inventés.
  const nonSimuleAvecPostes = () => ({
    ...exempleContrat('calepinage', 'calepinage_resultat', 'exemple_vide'),
    pertes: exempleContrat('calepinage', 'calepinage_resultat', 'exemple').pertes,
  })

  it('sans poste de perte : le bouton est inactif et les manques pointent vers l’onglet Pertes', async () => {
    servir('exemple_vide')
    rendre()

    await screen.findByTestId('cal236-panneau')
    expect(screen.getByTestId('calx48-lancer-bouton')).toBeDisabled()

    const manques = screen.getByTestId('calx48-manques')
    expect(within(manques).getByText(
      'Calepinage non simulé : la pose est connue, la production ne l\'est pas.',
    )).toBeInTheDocument()
    expect(within(manques).getByTestId('calx48-lien-pertes'))
      .toHaveAttribute('href', '/calepinage/1?onglet=pertes')
  })

  it('des postes saisis activent le bouton ; le job en cours publie son avancement', async () => {
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: nonSimuleAvecPostes() })
    calepinageApi.calepinages.simuler.mockResolvedValue({
      data: { job_id: 77, statut: 'PENDING', progress_pct: null },
    })
    calepinageApi.moteur.resultat.mockResolvedValue({
      data: { job_id: 77, statut: 'PENDING', progress_pct: 30 },
    })
    rendre()

    await screen.findByTestId('cal236-panneau')
    const bouton = screen.getByTestId('calx48-lancer-bouton')
    expect(bouton).not.toBeDisabled()

    fireEvent.click(bouton)

    expect(await screen.findByTestId('calx48-avancement')).toHaveTextContent(
      'Calcul de fond n°77 — 30 %',
    )
  })

  it('simulation terminée : le panneau se rafraîchit tout seul, sans rechargement complet', async () => {
    calepinageApi.calepinages.resultat
      .mockResolvedValueOnce({ data: nonSimuleAvecPostes() })
      .mockResolvedValueOnce(reponseContrat('calepinage', 'calepinage_resultat', 'exemple'))
    calepinageApi.calepinages.simuler.mockResolvedValue({
      data: { job_id: 78, statut: 'PENDING', progress_pct: null },
    })
    calepinageApi.moteur.resultat.mockResolvedValue({
      data: { job_id: 78, statut: 'SUCCESS', resultat: { ok: true } },
    })
    rendre()

    await screen.findByTestId('cal236-panneau')
    fireEvent.click(screen.getByTestId('calx48-lancer-bouton'))

    await waitFor(() => {
      expect(calepinageApi.calepinages.resultat).toHaveBeenCalledTimes(2)
    })
    expect(await screen.findByText('13 000 kWh')).toBeInTheDocument()
  })

  it('refus 400 sur un réglage de simulation : motif du serveur + lien vers les réglages', async () => {
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: nonSimuleAvecPostes() })
    calepinageApi.calepinages.simuler.mockRejectedValue({
      response: {
        data: {
          'parametres.simulation.mode_meteo': ['Aucun mode météo choisi pour ce document.'],
        },
      },
    })
    rendre()

    await screen.findByTestId('cal236-panneau')
    fireEvent.click(screen.getByTestId('calx48-lancer-bouton'))

    const refus = await screen.findByTestId('calx48-refus')
    expect(refus).toHaveTextContent('Aucun mode météo choisi pour ce document.')
    expect(within(refus).getByTestId('calx48-lien-reglages'))
      .toHaveAttribute('href', '/calepinage/reglages')
  })

  it('simulation périmée (CALX70) : le bandeau de péremption remplace celui « jamais simulé »', async () => {
    servir('exemple_perime')
    rendre()

    await screen.findByTestId('cal236-panneau')
    expect(screen.getByTestId('calx48-perime')).toHaveTextContent(
      'simulation périmée : le document a changé depuis le calcul du 19/09/2026',
    )
    expect(screen.queryByTestId('cal236-non-simule')).toBeNull()
  })
})
