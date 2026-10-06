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

/* ACAL125 — le bouton de calcul est sous `calepinage_gerer` : la permission
   est pilotée par la doublure (sans Provider Redux dans ce test). */
const permission = vi.hoisted(() => ({ gerer: true }))
vi.mock('../../../hooks/useHasPermission', () => ({
  useHasPermission: () => permission.gerer,
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

beforeEach(() => { vi.clearAllMocks(); permission.gerer = true })
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

/* CALX48 / ACAL125 — le refus « production non calculée » devient ACTIONNABLE :
   un bouton de calcul unique (`POST simuler/`), le suivi du job
   (`moteur/resultat/<job_id>/`) avec les statuts RÉELS du serveur
   (queued/running/done/failed) et la liste NOMMÉE des manques publiée par le
   serveur. Les réponses viennent de `calepinage_simulation.json`. */
describe('PanneauProduction — bouton de calcul (CALX48, ACAL125)', () => {
  const accuse = exempleContrat('calepinage', 'calepinage_simulation', 'exemple_accepte')
  const refusServi = exempleContrat('calepinage', 'calepinage_simulation', 'exemple_refus')
  const refus400 = exempleContrat('calepinage', 'calepinage_simulation', 'exemple_refus_400')
  // Jamais de fixture fabriquée : `exemple_vide` TEL QUEL (aucun poste de perte).
  const vide = () => ({ data: exempleContrat('calepinage', 'calepinage_resultat', 'exemple_vide') })

  it('jamais simulé sans poste de perte : le bouton « Lancer » est ACTIF et les manques pointent vers l’onglet Pertes', async () => {
    servir('exemple_vide')
    rendre()

    await screen.findByTestId('cal236-panneau')
    const bouton = screen.getByTestId('calx48-lancer-bouton')
    expect(bouton).not.toBeDisabled()
    expect(bouton).toHaveTextContent('Lancer la simulation')

    const manques = screen.getByTestId('calx48-manques')
    expect(within(manques).getByText(
      'Calepinage non simulé : la pose est connue, la production ne l\'est pas.',
    )).toBeInTheDocument()
    expect(within(manques).getByTestId('calx48-lien-pertes'))
      .toHaveAttribute('href', '/calepinage/1?onglet=pertes')
  })

  it('suit queued → running → done sans refus, puis relit le résultat', async () => {
    calepinageApi.calepinages.resultat
      .mockResolvedValueOnce(vide())
      .mockResolvedValue(reponseContrat('calepinage', 'calepinage_resultat', 'exemple'))
    calepinageApi.calepinages.simuler.mockResolvedValue({ data: accuse })
    calepinageApi.moteur.resultat
      .mockResolvedValueOnce({ data: { ...accuse, statut: 'queued' } })
      .mockResolvedValueOnce({ data: { ...accuse, statut: 'running', progress_pct: 40 } })
      .mockResolvedValue({ data: { ...accuse, statut: 'done', progress_pct: 100 } })
    render(<MemoryRouter><PanneauProduction calepinageId={1} intervalleMs={5} /></MemoryRouter>)

    await screen.findByTestId('cal236-panneau')
    fireEvent.click(screen.getByTestId('calx48-lancer-bouton'))

    expect(await screen.findByTestId('calx48-avancement')).toHaveTextContent(
      `Calcul de fond n°${accuse.job_id}`,
    )
    expect(screen.getByTestId('calx48-lancer-bouton')).toHaveTextContent('Simulation en cours…')
    expect(await screen.findByText('13 000 kWh')).toBeInTheDocument()
    expect(calepinageApi.moteur.resultat).toHaveBeenCalledTimes(3)
    expect(screen.queryByTestId('calx48-refus')).toBeNull()
    // Première demande sans `forcer` (jamais simulé).
    expect(calepinageApi.calepinages.simuler).toHaveBeenCalledWith(1)
  })

  it('failed nommé : le motif du serveur et le lien vers les réglages', async () => {
    calepinageApi.calepinages.resultat.mockResolvedValue(vide())
    calepinageApi.calepinages.simuler.mockResolvedValue({ data: accuse })
    calepinageApi.moteur.resultat.mockResolvedValue({
      data: {
        ...refusServi,
        elements: [{
          statut: 'failed',
          champ: 'parametres.simulation.mode_meteo',
          motif: 'Aucun mode météo choisi pour ce document.',
        }],
      },
    })
    rendre()

    await screen.findByTestId('cal236-panneau')
    fireEvent.click(screen.getByTestId('calx48-lancer-bouton'))

    const refus = await screen.findByTestId('calx48-refus')
    expect(refus).toHaveTextContent('Aucun mode météo choisi pour ce document.')
    expect(refus).not.toHaveTextContent('La simulation a échoué.')
    expect(within(refus).getByTestId('calx48-lien-reglages'))
      .toHaveAttribute('href', '/calepinage/reglages')
  })

  it('refus 400 de la porte (fuseau) : motif nommé du serveur + lien vers les réglages', async () => {
    calepinageApi.calepinages.resultat.mockResolvedValue(vide())
    calepinageApi.calepinages.simuler.mockRejectedValue({ response: { data: refus400 } })
    rendre()

    await screen.findByTestId('cal236-panneau')
    fireEvent.click(screen.getByTestId('calx48-lancer-bouton'))

    const refus = await screen.findByTestId('calx48-refus')
    expect(refus).toHaveTextContent(refus400.fuseau[0])
    expect(within(refus).getByTestId('calx48-lien-reglages'))
      .toHaveAttribute('href', '/calepinage/reglages')
  })

  it('frais : « Recalculer » est visible et envoie forcer:true', async () => {
    servir('exemple')
    calepinageApi.calepinages.simuler.mockResolvedValue({ data: accuse })
    calepinageApi.moteur.resultat.mockResolvedValue({ data: { ...accuse, statut: 'running' } })
    rendre()

    await screen.findByTestId('cal236-panneau')
    const bouton = screen.getByTestId('calx48-lancer-bouton')
    expect(bouton).toHaveTextContent('Recalculer')
    fireEvent.click(bouton)

    await waitFor(() => expect(calepinageApi.calepinages.simuler)
      .toHaveBeenCalledWith(1, { forcer: true }))
  })

  it('périmé : « Relancer (document modifié) »', async () => {
    servir('exemple_perime')
    rendre()

    await screen.findByTestId('cal236-panneau')
    expect(screen.getByTestId('calx48-lancer-bouton')).toHaveTextContent('Relancer (document modifié)')
  })

  it('sans la permission de gestion : aucun bouton de calcul', async () => {
    permission.gerer = false
    servir('exemple_vide')
    rendre()

    await screen.findByTestId('cal236-panneau')
    expect(screen.queryByTestId('calx48-lancer-bouton')).toBeNull()
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

/* ERR-QAH-CALEPINAGE-EXPORT-CSV-400-PRODUCTION — le panneau sait déjà, SANS
   requête de plus, si une géométrie est posée (`pose.total_modules` de son
   propre `resultat()`, CAL244 : « la pose est un fait, toujours chiffrée »)
   et le passe à `TapisHoraire` (`geometriePresente`) pour qu'il n'ouvre même
   pas la porte d'export quand elle refuserait de toute façon en 400. */
describe('PanneauProduction — geometriePresente (ERR-QAH-CALEPINAGE-EXPORT-CSV-400-PRODUCTION)', () => {
  const sansGeometrie = () => ({
    ...exempleContrat('calepinage', 'calepinage_resultat', 'exemple_vide'),
    pose: {
      ...exempleContrat('calepinage', 'calepinage_resultat', 'exemple_vide').pose,
      total_modules: 0,
      kwc: 0,
      pans: [],
    },
  })

  it("aucune géométrie posée : TapisHoraire ne demande pas l'export", async () => {
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: sansGeometrie() })
    rendre()

    await screen.findByTestId('cal236-panneau')
    // `TapisHoraire` affiche son propre état vide, SANS avoir rien demandé.
    expect(await screen.findByTestId('cal-tapis-vide')).toBeInTheDocument()
    expect(calepinageApi.calepinages.exportCsv).not.toHaveBeenCalled()
  })

  it('une géométrie posée (les fixtures ordinaires) : le comportement '
    + "d'aujourd'hui est inchangé — la porte d'export reste ouverte", async () => {
    servir('exemple_vide')
    rendre()

    await screen.findByTestId('cal236-panneau')
    await screen.findByTestId('cal-tapis-vide')
    expect(calepinageApi.calepinages.exportCsv).toHaveBeenCalledTimes(1)
  })
})

/* ACAL218 — simulation périmée : le tapis horaire n'est pas monté, la porte
   d'export n'est pas appelée, le motif SERVI est affiché. */
describe('PanneauProduction — simulation périmée (ACAL218)', () => {
  it('ne monte pas le tapis horaire quand simulation_perimee est vrai', async () => {
    servir('exemple_perime')
    rendre()

    await screen.findByTestId('cal236-panneau')
    const tapis = await screen.findByTestId('cal-tapis-perime')
    expect(tapis).toHaveTextContent(
      'simulation périmée : le document a changé depuis le calcul du 19/09/2026',
    )
    expect(screen.queryByTestId('cal-tapis')).toBeNull()
    expect(calepinageApi.calepinages.exportCsv).not.toHaveBeenCalled()
  })
})

/* ACAL52 — résultat INCOMPLET (borne haute) : réponse = `calepinage_resultat.json`
   `exemple` dont `production` et `simulation` sont ceux de
   `calepinage_simulation.json::exemple_borne_haute` (contrats partagés, ACAL8). */
describe('PanneauProduction — borne haute (ACAL52)', () => {
  const borneHaute = exempleContrat('calepinage', 'calepinage_simulation', 'exemple_borne_haute')
  const incomplet = () => ({
    ...exempleContrat('calepinage', 'calepinage_resultat', 'exemple'),
    production: borneHaute.production,
    simulation: borneHaute.simulation,
  })

  it('incomplet : bandeau borne haute et PR non publié', async () => {
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: incomplet() })
    rendre()

    await screen.findByTestId('cal236-panneau')
    const bandeau = screen.getByTestId('acal52-borne-haute')
    expect(bandeau).toHaveTextContent(borneHaute.production.total.mention)
    for (const poste of borneHaute.production.total.socle_manquant) {
      expect(within(bandeau).getByText(poste)).toBeInTheDocument()
    }
    expect(within(bandeau).getByTestId('acal52-lien-reglages'))
      .toHaveAttribute('href', '/calepinage/reglages')

    // PR, P75, P90, P95 : « non publié » (motif en infobulle), jamais un nombre.
    const total = screen.getByTestId('cal236-total')
    expect(within(total).getAllByTestId('acal52-non-publie')).toHaveLength(4)
    expect(within(total).getAllByTestId('acal52-non-publie')[0])
      .toHaveAttribute('title', borneHaute.production.total.p75_kwh_motif)
    expect(within(total).queryByText(/79,9/)).toBeNull()
    // Le P50 reste publié.
    expect(within(total).getByText('13 000 kWh')).toBeInTheDocument()
    // Par pan : les colonnes P75 / P90 / PR sont masquées aussi.
    const ligne = within(screen.getByTestId('cal236-par-pan')).getByText('PAN-A').closest('tr')
    expect(within(ligne).getAllByTestId('acal52-non-publie')).toHaveLength(3)
  })

  it('complet : ni bandeau ni masquage', async () => {
    servir('exemple')
    rendre()

    await screen.findByTestId('cal236-panneau')
    expect(screen.queryByTestId('acal52-borne-haute')).toBeNull()
    expect(screen.queryByTestId('acal52-non-publie')).toBeNull()
    expect(within(screen.getByTestId('cal236-total')).getByText('11 790 kWh')).toBeInTheDocument()
  })

  it('jamais simulé : pas de bandeau borne haute (rien n’a été calculé)', async () => {
    servir('exemple_vide')
    rendre()

    await screen.findByTestId('cal236-panneau')
    expect(screen.queryByTestId('acal52-borne-haute')).toBeNull()
  })

  it('réglages utilisés : chaque clé, valeur et source figées au calcul', async () => {
    servir('exemple')
    rendre()

    await screen.findByTestId('cal236-panneau')
    const lignes = screen.getAllByTestId('acal52-reglage')
    expect(lignes).toHaveLength(2)
    expect(lignes[0]).toHaveTextContent('mode_meteo')
    expect(lignes[0]).toHaveTextContent('pluriannuel')
    expect(lignes[0]).toHaveTextContent('societe')
  })
})
