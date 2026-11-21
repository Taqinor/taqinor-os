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
import { lancerSimulationAuto, viderSimulationsAuto } from './simulationAuto'

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
    // ACAL443 : un seul état, aucune tuile (le conteneur des chiffres n'existe pas).
    expect(screen.queryByTestId('cal236-total')).toBeNull()
    const etat = screen.getByTestId('acal443-non-calcule')
    expect(within(etat).queryByText(/^0 kWh$/)).toBeNull()
    expect(etat).toHaveTextContent('Production non calculée')
  })

  it('ACAL443 — héros : P50 en grand, trois secondaires, détails repliés ; non simulé ou périmé : un seul état, zéro tuile', async () => {
    servir('exemple')
    const { unmount } = rendre()
    const total = await screen.findByTestId('cal236-total')
    const serveur = exempleContrat('calepinage', 'calepinage_resultat', 'exemple').production.total
    expect(within(screen.getByTestId('acal443-heros')).getByText('Production annuelle (P50)')).toBeInTheDocument()
    expect(within(screen.getByTestId('acal443-heros')).getByText('13 000 kWh')).toBeInTheDocument()
    for (const libelle of ['Puissance installée', 'Productible', 'Pertes totales']) {
      expect(within(total).getByText(libelle)).toBeInTheDocument()
    }
    const details = screen.getByTestId('acal443-details')
    expect(details.tagName).toBe('DETAILS')
    expect(details).not.toHaveAttribute('open')
    expect(within(details).getByText('P75 (annuel)')).toBeInTheDocument()
    expect(within(details).getByText('79,9 %')).toBeInTheDocument()
    expect(serveur.p50_kwh).toBe(13000)
    unmount()

    servir('exemple_perime')
    rendre()
    await screen.findByTestId('cal236-panneau')
    expect(screen.queryByTestId('cal236-total')).toBeNull()
    expect(screen.getByTestId('acal443-non-calcule')).toHaveTextContent('Production non calculée')
  })

  it('ACAL453 — le graphique mensuel se trace depuis par_mois ; mois null sans valeur ; bloc absent = motif nommé', async () => {
    // Clone du contrat, modifié en place : aucun littéral de réponse écrit à la main.
    const servi = structuredClone(exempleContrat('calepinage', 'calepinage_resultat', 'exemple'))
    const mars = servi.autoconsommation.par_mois.find((m) => m.mois === 3)
    mars.consommation_kwh = null
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: servi })
    const { unmount } = rendre()
    const graphique = await screen.findByTestId('acal453-graphique')
    // Valeurs servies telles quelles (mois 1 : 975 kWh produits, 720 consommés).
    expect(within(graphique).getByText('975 kWh')).toBeInTheDocument()
    expect(within(graphique).getByText('720 kWh')).toBeInTheDocument()
    // Mois 3 : consommation null ⇒ « non calculée », jamais 0 kWh.
    expect(within(graphique).getByText('non calculée')).toBeInTheDocument()
    expect(within(within(graphique).getByText('non calculée').closest('tr')).getByText('Mar')).toBeInTheDocument()
    // Le tableau P50 reste à côté, inchangé.
    expect(screen.getByTestId('cal236-mensuel')).toBeInTheDocument()
    unmount()

    servi.autoconsommation.par_mois = null
    servi.autoconsommation.motif_absence = 'Aucune courbe de charge saisie.'
    rendre()
    expect(await screen.findByTestId('acal453-vide')).toHaveTextContent('Aucune courbe de charge saisie.')
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
    // ACAL397 : sans `parcours.manque`, les avertissements restent du texte.
    expect(within(manques).queryByTestId('calx48-manque-ligne')).toBeNull()
  })

  /* ACAL397 — « Ce qui manque » = liste d'actions issue de `parcours.manque`
     (contrat `calepinage_parcours_guide.json`, jamais écrit à la main). */
  describe('liste des manques (ACAL397)', () => {
    const manque = () => exempleContrat('calepinage', 'calepinage_parcours_guide', 'exemple').manque
    const rendreAvec = (liste) => render(
      <MemoryRouter><PanneauProduction calepinageId={1} parcours={{ etats: {}, manque: liste }} /></MemoryRouter>,
    )

    it('une entrée `nombre` > 1 ⇒ une ligne « × n », une ligne par entrée', async () => {
      servir('exemple_vide')
      const liste = manque()
      rendreAvec(liste)
      const lignes = await screen.findAllByTestId('calx48-manque-ligne')
      expect(lignes).toHaveLength(liste.length)
      const multiple = liste.find((m) => m.nombre > 1)
      expect(screen.getByText(`× ${multiple.nombre}`)).toBeInTheDocument()
    })

    it('trie bloquant avant info', async () => {
      servir('exemple_vide')
      const [bloquant, info] = [manque()[0], manque()[1]]
      rendreAvec([info, bloquant])
      const lignes = await screen.findAllByTestId('calx48-manque-ligne')
      expect(lignes[0]).toHaveTextContent(bloquant.message)
      expect(lignes[1]).toHaveTextContent(info.message)
    })

    it('le lien porte onglet et champ ; `reglages` mène à /calepinage/reglages', async () => {
      servir('exemple_vide')
      rendreAvec([
        { code: 'x', message: 'Norme', etape: 'electrique', gravite: 'a_regler', nombre: 1,
          cible: { onglet: 'electrique', champ: 'norme' } },
        { code: 'y', message: 'Réglage', etape: 'resultats', gravite: 'bloquant', nombre: 1,
          cible: { onglet: 'reglages', champ: '' } },
      ])
      const lignes = await screen.findAllByTestId('calx48-manque-ligne')
      expect(lignes[0]).toHaveAttribute('href', '/calepinage/reglages')
      expect(lignes[1]).toHaveAttribute('href', '/calepinage/1?onglet=electrique&champ=norme')
    })
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

  it("une géométrie posée ET simulée : la porte d'export est ouverte une fois", async () => {
    servir('exemple')
    calepinageApi.calepinages.exportCsv.mockRejectedValue({ response: { status: 400, data: {} } })
    rendre()

    await screen.findByTestId('cal236-panneau')
    await screen.findByTestId('cal-tapis-vide')
    expect(calepinageApi.calepinages.exportCsv).toHaveBeenCalledTimes(1)
  })

  /* Acceptation ACAL490 (oracle 2 : GET export-csv/?quoi=horaire en erreur pendant
     « calcul en cours ») — jamais simulé : aucune série, aucune requête ; la
     simulation terminée (relecture), la série est lue UNE fois. */
  it("jamais simulé : pas d'export ; simulé ensuite : un seul export", async () => {
    servir('exemple_vide')
    calepinageApi.calepinages.exportCsv.mockRejectedValue({ response: { status: 400, data: {} } })
    const { rerender } = rendre()
    await screen.findByTestId('cal-tapis-vide')
    expect(calepinageApi.calepinages.exportCsv).not.toHaveBeenCalled()

    servir('exemple')
    rerender(<MemoryRouter><PanneauProduction calepinageId={1} key="relu" /></MemoryRouter>)
    await waitFor(() => expect(calepinageApi.calepinages.exportCsv).toHaveBeenCalledTimes(1))
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

  /* ACAL398 — la simulation partie à l'enregistrement : l'onglet reprend son job. */
  it('ACAL398 — job automatique en cours ⇒ « Simulation en cours… » puis relecture', async () => {
    viderSimulationsAuto()
    servir('exemple')
    calepinageApi.calepinages.simuler.mockResolvedValue({ data: { job_id: 'j-9' } })
    calepinageApi.moteur.resultat
      .mockResolvedValueOnce({ data: { job_id: 'j-9', statut: 'running' } })
      .mockResolvedValue({ data: { job_id: 'j-9', statut: 'done' } })
    await lancerSimulationAuto(1)
    render(<MemoryRouter><PanneauProduction calepinageId={1} intervalleMs={300} /></MemoryRouter>)

    expect(await screen.findByText('Simulation en cours…')).toBeInTheDocument()
    await waitFor(() => expect(calepinageApi.moteur.resultat).toHaveBeenCalledWith('j-9'))
    await waitFor(() => expect(calepinageApi.calepinages.resultat.mock.calls.length).toBeGreaterThan(1))
  })

  it('ACAL398 — refus nommé du serveur ⇒ phrase affichée dans l’onglet', async () => {
    viderSimulationsAuto()
    servir('exemple')
    calepinageApi.calepinages.simuler.mockRejectedValue(
      { response: { status: 409, data: { 'parametres.mode_meteo': ['Mode météo non choisi.'] } } })
    await lancerSimulationAuto(1)
    rendre()

    const refus = await screen.findByTestId('calx48-refus')
    expect(refus).toHaveTextContent('La simulation automatique n’a pas démarré : Mode météo non choisi.')
    expect(screen.getByTestId('calx48-lien-reglages')).toBeInTheDocument()
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

/* ACAL696 — la carte « Du soleil au réseau » (niveau expert). Le mode expert
   est mémorisé par ACAL394 : on le pose dans le stockage du navigateur. */
const CLE_EXPERT = 'calepinage.mode_expert.anonyme'

describe('PanneauProduction — carte Du soleil au réseau (ACAL696)', () => {
  const servirAvecPostes = (postes, motifAbsence = '') => {
    const reponse = reponseContrat('calepinage', 'calepinage_resultat', 'exemple')
    reponse.data.cascade.postes_lisibles = {
      depart_kwh: 16800, arrivee_kwh: 13400, arrivee_pct: 79.9, total_pct: 20.1,
      postes, motif_absence: motifAbsence,
    }
    calepinageApi.calepinages.resultat.mockResolvedValue(reponse)
    return reponse.data.cascade
  }
  const POSTES = [
    { poste: 'ombres_proches', libelle: 'Ombres proches', perte_kwh: 300, perte_pct: 1.8, statut: 'compte', etapes: [] },
    { poste: 'poussiere', libelle: 'Poussière', perte_kwh: null, perte_pct: null, statut: 'non_compte', etapes: [{ etape: 'salissure', libelle: 'Salissure', motif_omission: 'Aucune salissure saisie pour cette société.' }] },
    { poste: 'chaleur', libelle: 'Chaleur', perte_kwh: 900, perte_pct: 5.4, statut: 'compte', etapes: [] },
    { poste: 'cables_et_onduleur', libelle: 'Câbles et onduleur', perte_kwh: 700, perte_pct: 4.2, statut: 'compte', etapes: [] },
    { poste: 'autres', libelle: 'Autres pertes', perte_kwh: 500, perte_pct: 3, statut: 'partiel', etapes: [{ etape: 'spectral', libelle: 'Correction spectrale', motif_omission: 'toujours omis' }] },
  ]
  afterEach(() => { try { localStorage.removeItem(CLE_EXPERT) } catch { /* sans stockage */ } })

  it('expert : cinq postes, poste non compté nommé avec son motif, clic déplie les N étapes', async () => {
    localStorage.setItem(CLE_EXPERT, '1')
    const cascade = servirAvecPostes(POSTES)
    rendre()
    const carte = await screen.findByTestId('acal696-carte')
    expect(within(carte).getByText('Soleil reçu par les panneaux')).toBeInTheDocument()
    expect(within(carte).getByText('Électricité produite')).toBeInTheDocument()
    expect(carte.querySelectorAll('[data-testid^="acal696-poste-"]')).toHaveLength(5)
    expect(screen.getByTestId('acal696-barre-chaleur')).toHaveStyle({ width: '5.4%' })
    const poussiere = screen.getByTestId('acal696-poste-poussiere')
    expect(poussiere).toHaveTextContent('non compté')
    expect(screen.getByTestId('acal696-motif-poussiere')).toHaveTextContent('Aucune salissure saisie')
    expect(screen.queryByTestId('acal696-barre-poussiere')).toBeNull() // jamais une barre à zéro
    expect(screen.getByTestId('acal696-partiel-autres')).toHaveTextContent('+ 1 étape non comptée')
    expect(screen.queryByTestId('acal696-etapes')).toBeNull()
    const bouton = screen.getByTestId('acal696-voir-etapes')
    expect(bouton).toHaveTextContent(`Voir les ${cascade.etapes.length} étapes`)
    fireEvent.click(bouton)
    expect(within(screen.getByTestId('acal696-etapes')).getByTestId('acal444-lignes')).toBeInTheDocument()
  })

  it('guidé : la carte est absente ; postes vides : le motif servi', async () => {
    servirAvecPostes(POSTES)
    rendre()
    await screen.findByTestId('cal236-panneau')
    expect(screen.queryByTestId('acal696-carte')).toBeNull()
    cleanup()
    localStorage.setItem(CLE_EXPERT, '1')
    servirAvecPostes([], 'Aucune cascade de pertes publiée.')
    rendre()
    expect(await screen.findByTestId('acal696-absente')).toHaveTextContent('Aucune cascade de pertes publiée.')
  })
})

/* ACAL698 — la ligne « n réglages utilisent des valeurs publiées ». */
describe('PanneauProduction — valeurs publiées (ACAL698)', () => {
  const PREFIXE = 'Profil de départ — '
  const servirAvecReglages = (reglages) => {
    const reponse = reponseContrat('calepinage', 'calepinage_resultat', 'exemple')
    reponse.data.simulation = {
      ...reponse.data.simulation, reglages_utilises: reglages,
    }
    calepinageApi.calepinages.resultat.mockResolvedValue(reponse)
  }
  const publie = (valeur) => ({ valeur, source: 'texte', reference: `${PREFIXE}PVsyst` })
  const saisi = (valeur) => ({ valeur, source: 'societe', reference: 'mesuré sur site' })
  afterEach(() => { try { localStorage.removeItem(CLE_EXPERT) } catch { /* sans stockage */ } })

  it('expert : compte et noms des seuls réglages publiés ; « Voir les sources » ouvre Réglages utilisés', async () => {
    localStorage.setItem(CLE_EXPERT, '1')
    servirAvecReglages({
      salissure_mensuelle_pct: publie(2), lid_par_techno: publie(1.5), mismatch_fabricant_pct: publie(1),
      mode_meteo: saisi('tmy'), tolerance_validation_pct: saisi(3),
    })
    rendre()
    const texte = await screen.findByTestId('acal698-texte')
    expect(texte).toHaveTextContent('3 réglages utilisent des valeurs publiées, non mesurées sur ce chantier')
    expect(texte).toHaveTextContent('salissure_mensuelle_pct, lid_par_techno, mismatch_fabricant_pct') // clé brute : registre absent
    expect(screen.getByTestId('acal52-reglages-utilises')).not.toHaveAttribute('open')
    fireEvent.click(screen.getByTestId('acal698-voir-sources'))
    expect(screen.getByTestId('acal52-reglages-utilises')).toHaveAttribute('open')
  })

  it('aucun réglage publié (ou mode guidé) : la ligne est absente, jamais « 0 réglage »', async () => {
    localStorage.setItem(CLE_EXPERT, '1')
    servirAvecReglages({ mode_meteo: saisi('tmy') })
    rendre()
    await screen.findByTestId('cal236-panneau')
    expect(screen.queryByTestId('acal698-ligne')).toBeNull()
    cleanup()
    localStorage.removeItem(CLE_EXPERT)
    servirAvecReglages({ salissure_mensuelle_pct: publie(2) })
    rendre()
    await screen.findByTestId('cal236-panneau')
    expect(screen.queryByTestId('acal698-ligne')).toBeNull()
  })

  it('l’exemple du contrat (profil de départ appliqué) annonce son réglage publié', async () => {
    localStorage.setItem(CLE_EXPERT, '1')
    const reponse = reponseContrat('calepinage', 'calepinage_resultat', 'exemple')
    reponse.data.simulation = exempleContrat('calepinage', 'calepinage_simulation', 'exemple_profil_publie').simulation
    calepinageApi.calepinages.resultat.mockResolvedValue(reponse)
    rendre()
    expect(await screen.findByTestId('acal698-texte')).toHaveTextContent('1 réglage utilise des valeurs publiées')
  })
})

/* ACAL700 — l'état « résultat incomplet » de la maquette. */
describe('PanneauProduction — résultat incomplet (ACAL700)', () => {
  const borneHaute = exempleContrat('calepinage', 'calepinage_simulation', 'exemple_borne_haute')
  const incomplet = () => {
    const base = exempleContrat('calepinage', 'calepinage_resultat', 'exemple')
    // postes lisibles : « Ombres proches » compté, pour « Ce qui est déjà sûr ».
    const postes = JSON.parse(JSON.stringify(borneHaute.cascade.postes_lisibles))
    postes.postes[0] = { ...postes.postes[0], statut: 'compte', perte_pct: 1.8, perte_kwh: 300 }
    return {
      ...base,
      production: borneHaute.production,
      simulation: borneHaute.simulation,
      cascade: { ...borneHaute.cascade, postes_lisibles: postes },
    }
  }
  const rendreAvecParcours = (parcours) => render(
    <MemoryRouter><PanneauProduction calepinageId={1} parcours={parcours} /></MemoryRouter>,
  )

  it('incomplet : plafond, n étapes sur N, lignes Renseigner, démarrage rapide, ce qui est sûr', async () => {
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: incomplet() })
    rendreAvecParcours({ etapes: [{ cle: 'electrique', etat: 'fait' }], manque: [] })
    const bloc = await screen.findByTestId('acal700-incomplet')
    const a = borneHaute.cascade.a_renseigner
    expect(within(bloc).getByTestId('acal700-etiquette')).toHaveTextContent('Production la première année · au plus')
    expect(within(bloc).getByTestId('acal700-plafond')).toHaveTextContent(
      `C'est un plafond : ${a.lignes.length} pertes ne sont pas encore comptées. Le chiffre réel sera plus bas.`)
    expect(within(bloc).getByTestId('acal700-jauge')).toHaveTextContent(
      `${a.etapes_comptees} étapes sur ${a.etapes_a_compter}`)
    const lignes = within(bloc).getAllByTestId('acal700-ligne')
    expect(lignes).toHaveLength(a.lignes.length)
    expect(lignes[0]).toHaveTextContent('Aucune valeur pour votre société')
    const renseigner = within(lignes[0]).getByTestId('acal700-renseigner')
    expect(renseigner).toHaveAttribute('href', '/calepinage/reglages#salissure_mensuelle_pct')
    expect(within(bloc).getByTestId('acal700-lien-reglages')).toHaveAttribute('href', '/calepinage/reglages')
    const sur = within(bloc).getByTestId('acal700-sur')
    for (const t of ['Panneaux', 'Puissance', 'Raccordement', 'Conforme', 'Ombres proches']) {
      expect(within(sur).getByText(t)).toBeInTheDocument()
    }
    expect(bloc).toHaveTextContent("Les années basses et l'indice de performance s'affichent dès que le résultat est complet")
    expect(screen.queryByTestId('acal52-borne-haute')).toBeNull() // remplacé
  })

  it('Raccordement « Conforme » seulement si l’étape électrique est faite', async () => {
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: incomplet() })
    rendreAvecParcours({ etapes: [{ cle: 'electrique', etat: 'a_faire' }], manque: [] })
    const sur = await screen.findByTestId('acal700-sur')
    expect(within(sur).queryByText('Raccordement')).toBeNull()
  })

  it('complet : aucun de ces blocs', async () => {
    servir('exemple')
    rendre()
    await screen.findByTestId('cal236-panneau')
    expect(screen.queryByTestId('acal700-incomplet')).toBeNull()
  })
})

/* ACAL703 — la phrase sous « Pertes totales » (niveau expert). */
describe('PanneauProduction — plage habituelle (ACAL703)', () => {
  const servirAvecTotal = (total) => {
    const reponse = reponseContrat('calepinage', 'calepinage_resultat', 'exemple')
    reponse.data.cascade.plages = {
      etapes: {}, total, motif_absence: total ? '' : 'aucune bande sourcée',
    }
    calepinageApi.calepinages.resultat.mockResolvedValue(reponse)
  }
  afterEach(() => { try { localStorage.removeItem(CLE_EXPERT) } catch { /* sans stockage */ } })

  it('expert + bande totale servie : « Dans la plage habituelle » / « Hors de la plage habituelle »', async () => {
    localStorage.setItem(CLE_EXPERT, '1')
    servirAvecTotal({ statut: 'dans_la_plage', min: 10, max: 25, unite: '%', url: 'https://exemple.test' })
    rendre()
    expect(await screen.findByTestId('acal703-total-plage')).toHaveTextContent('Dans la plage habituelle')
    cleanup()
    servirAvecTotal({ statut: 'inhabituel', min: 10, max: 15, unite: '%', url: 'https://exemple.test' })
    rendre()
    expect(await screen.findByTestId('acal703-total-plage')).toHaveTextContent('Hors de la plage habituelle')
  })

  it('sans bande totale servie, ou en guidé : aucune phrase', async () => {
    localStorage.setItem(CLE_EXPERT, '1')
    servirAvecTotal(null)
    rendre()
    await screen.findByTestId('cal236-panneau')
    expect(screen.queryByTestId('acal703-total-plage')).toBeNull()
    cleanup()
    localStorage.removeItem(CLE_EXPERT)
    servirAvecTotal({ statut: 'dans_la_plage', min: 10, max: 25, unite: '%', url: 'https://exemple.test' })
    rendre()
    await screen.findByTestId('cal236-panneau')
    expect(screen.queryByTestId('acal703-total-plage')).toBeNull()
  })
})

/* ACAL707 — le tableau mensuel complet (mode expert). */
describe('PanneauProduction — tableau mensuel complet (ACAL707)', () => {
  afterEach(() => { try { localStorage.removeItem(CLE_EXPERT) } catch { /* sans stockage */ } })
  const servirModifie = (modifier) => {
    const reponse = reponseContrat('calepinage', 'calepinage_resultat', 'exemple')
    modifier?.(reponse.data.production)
    calepinageApi.calepinages.resultat.mockResolvedValue(reponse)
    return reponse.data.production
  }

  it('expert : douze lignes à cinq colonnes, null = « non calculée » (jamais 0) ; guidé : Mois / P50', async () => {
    localStorage.setItem(CLE_EXPERT, '1')
    const production = servirModifie((p) => { p.bilan_mensuel[0].pr = null })
    rendre()
    const table = await screen.findByTestId('acal707-mensuel')
    expect(within(table).getAllByRole('row')).toHaveLength(13)
    for (const t of ['Mois', 'Irradiation horizontale', 'Irradiation du plan', 'Température', 'Production', 'PR']) {
      expect(within(table).getByText(t)).toBeInTheDocument()
    }
    expect(screen.getByTestId('acal707-horizontale-1')).toHaveTextContent('68,7 kWh/m²')
    expect(screen.getByTestId('acal707-plan-1')).toHaveTextContent('79,0 kWh/m²')
    expect(screen.getByTestId('acal707-temperature-1')).toHaveTextContent('non calculée') // null servi
    expect(screen.getByTestId('acal707-pr-1')).toHaveTextContent('non calculée')
    expect(screen.getByTestId('acal707-production-1')).toHaveTextContent('880 kWh')
    expect(production.bilan_mensuel[0].temperature_ambiante_c).toBeNull()
    expect(screen.queryByTestId('cal236-mensuel')).toBeNull()
    cleanup()
    localStorage.removeItem(CLE_EXPERT)
    servirModifie()
    rendre()
    await screen.findByTestId('cal236-mensuel')
    expect(screen.queryByTestId('acal707-mensuel')).toBeNull()
  })

  it('un bloc entier absent : sa colonne n’apparaît pas', async () => {
    localStorage.setItem(CLE_EXPERT, '1')
    servirModifie((p) => { delete p.bilan_mensuel; p.gain_inclinaison = null })
    rendre()
    const table = await screen.findByTestId('acal707-mensuel')
    expect(within(table).queryByText('Température')).toBeNull()
    expect(within(table).queryByText('PR')).toBeNull()
    expect(within(table).queryByText('Irradiation horizontale')).toBeNull()
    expect(within(table).getByText('Irradiation du plan')).toBeInTheDocument()
    expect(within(table).getByText('Production')).toBeInTheDocument()
  })
})

/* ACAL709 — la tuile « De la consommation » (niveau expert). */
describe('PanneauProduction — tuile couverture (ACAL709)', () => {
  afterEach(() => { try { localStorage.removeItem(CLE_EXPERT) } catch { /* sans stockage */ } })
  const servirAutoconso = (modifier) => {
    const reponse = reponseContrat('calepinage', 'calepinage_resultat', 'exemple')
    modifier?.(reponse.data)
    calepinageApi.calepinages.resultat.mockResolvedValue(reponse)
  }

  it('expert : 71 % (batterie comprise) ; en guidé : aucune tuile', async () => {
    localStorage.setItem(CLE_EXPERT, '1')
    servirAutoconso()
    rendre()
    const tuile = await screen.findByTestId('acal709-couverture')
    expect(tuile).toHaveTextContent('De la consommation')
    expect(tuile).toHaveTextContent('71 %')
    expect(tuile).toHaveTextContent('Part de la consommation couverte par le solaire')
    expect(tuile).toHaveTextContent('(batterie comprise)')
    expect(tuile).not.toHaveTextContent('62 %') // jamais le taux d'autoconsommation
    cleanup()
    localStorage.removeItem(CLE_EXPERT)
    servirAutoconso()
    rendre()
    await screen.findByTestId('cal236-panneau')
    expect(screen.queryByTestId('acal709-couverture')).toBeNull()
  })

  it('taux null : « non calculée » et le motif servi ; bloc absent : repli', async () => {
    localStorage.setItem(CLE_EXPERT, '1')
    servirAutoconso((d) => {
      d.autoconsommation.taux_couverture = null
      d.autoconsommation.motif_absence = 'Aucune courbe de charge saisie.'
    })
    rendre()
    const tuile = await screen.findByTestId('acal709-couverture')
    expect(tuile).toHaveTextContent('non calculée')
    expect(tuile).toHaveTextContent('Aucune courbe de charge saisie.')
    expect(tuile).not.toHaveTextContent('0 %')
    cleanup()
    servirAutoconso((d) => { d.autoconsommation = null })
    rendre()
    expect(await screen.findByTestId('acal709-couverture')).toHaveTextContent('Aucune consommation connue.')
  })
})

/* ACAL710 — la ligne « sur la durée » (niveau expert). */
describe('PanneauProduction — sur la durée (ACAL710)', () => {
  afterEach(() => { try { localStorage.removeItem(CLE_EXPERT) } catch { /* sans stockage */ } })
  const servirDuree = (modifier) => {
    const reponse = reponseContrat('calepinage', 'calepinage_resultat', 'exemple')
    modifier?.(reponse.data.production)
    calepinageApi.calepinages.resultat.mockResolvedValue(reponse)
  }
  const projectionSur = (n) => Array.from({ length: n }, (_, i) => ({
    annee: i + 1, facteur: i ? 0.99 : null, p50_kwh: 13000 - i * 100, source: 'x',
  }))

  it('N lu dans la dernière année (2, 20, 25), garantie seulement à 10 ou 25 ans', async () => {
    localStorage.setItem(CLE_EXPERT, '1')
    servirDuree()
    rendre()
    expect(await screen.findByTestId('acal710-basse')).toHaveTextContent('Année basse (9 fois sur 10 au-dessus) : 11 900 kWh')
    expect(screen.getByTestId('acal710-derniere')).toHaveTextContent('Dans 2 ans : 12 929 kWh')
    expect(screen.getByTestId('acal710-derniere')).not.toHaveTextContent('garantie fabricant')
    cleanup()
    servirDuree((p) => { p.projection = projectionSur(20) })
    rendre()
    expect(await screen.findByTestId('acal710-derniere')).toHaveTextContent('Dans 20 ans : 11 100 kWh')
    expect(screen.getByTestId('acal710-derniere')).not.toHaveTextContent('garantie fabricant')
    expect(screen.getByTestId('acal710-annee-10')).toHaveTextContent('90 %')
    cleanup()
    servirDuree((p) => { p.projection = projectionSur(25) })
    rendre()
    expect(await screen.findByTestId('acal710-derniere')).toHaveTextContent('(garantie fabricant : 80 %)')
    expect(screen.getByTestId('acal710-tableau').tagName).toBe('DETAILS')
    expect(screen.getByTestId('acal710-tableau')).toHaveTextContent('Sur 25 ans')
    expect(screen.getByTestId('acal710-annee-25')).toHaveTextContent('80 %')
    expect(screen.getByTestId('acal710-annee-1')).toHaveTextContent('non calculée')
  })

  it('omission : le motif servi remplace le tableau ; guidé : rien', async () => {
    localStorage.setItem(CLE_EXPERT, '1')
    servirDuree((p) => { p.duree_de_vie.motif_omission = 'Dégradation absente de la fiche produit.'; p.projection = projectionSur(1) })
    rendre()
    expect(await screen.findByTestId('acal710-motif')).toHaveTextContent('Dégradation absente de la fiche produit.')
    expect(screen.queryByTestId('acal710-tableau')).toBeNull()
    expect(screen.queryByTestId('acal710-derniere')).toBeNull()
    cleanup()
    localStorage.removeItem(CLE_EXPERT)
    servirDuree()
    rendre()
    await screen.findByTestId('cal236-panneau')
    expect(screen.queryByTestId('acal710-ligne')).toBeNull()
  })
})
