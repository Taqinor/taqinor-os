/* CAL236 — le panneau « Production » du module calepinage.

   Ce qui est prouvé ici : les valeurs affichées sont EXACTEMENT celles du
   contrat `apps/calepinage/contract_samples/calepinage_resultat.json`
   (PACT10/13 — `reponseContrat`, jamais une charge utile écrite à la main),
   une grandeur `null` s'affiche « non calculée » (jamais `0`), et un pan sans
   module affiche un vrai `0` distinct de « non calculée ». */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, within, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { exempleContrat, fichierContrat, reponseContrat } from '../../../test/fixtures/contractSamples'
import { NON_PUBLIEE, chiffresSansGrandeur, remplirPhrase } from '../commun/useExplications'

/* CALX64 — le panneau monte désormais `TapisHoraire`, qui relit la série par
   la porte d'export (CAL144/CALX6) : la doublure doit porter `exportCsv`,
   sinon le panneau tomberait sur une méthode absente. Elle rend une réponse
   VIDE : le tapis affiche alors son état « Lancer la simulation », ce que ce
   fichier n'a pas à juger (il a son propre test). */
vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      resultat: vi.fn(), exportCsv: vi.fn(), simuler: vi.fn(), diagrammeEnergie: vi.fn(),
      explications: vi.fn(), // ACAL880 — le registre (geste de chaque poste)
    },
    moteur: { resultat: vi.fn() },
    // ACAL986 — la page d'arrivée des liens (Réglages) est rendue pour lire ses champs montés.
    parametres: { get: vi.fn(), update: vi.fn(), profilDepart: vi.fn() },
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
import PiedResultats from './PiedResultats'
import { NoteValeursPubliees } from './LigneValeursPubliees'
import ReglagesSimulation from '../reglages/ReglagesSimulation'
import sourceBibliotheque from '../Bibliotheque.jsx?raw'
import { BandeauBorneHaute, EcartPvgis } from './BandeauProvenanceProduction'
import { suivreSimulationDuServeur, viderSimulationsAuto } from './simulationAuto'
import { OPTIONS_TELECHARGEMENT } from '../documents/telechargement'
import { libelleSource } from './DiagrammePertes.helpers'

const servir = (variante) => {
  calepinageApi.calepinages.resultat
    .mockResolvedValue(reponseContrat('calepinage', 'calepinage_resultat', variante))
}

/* ACAL1987 — `GET resultat/` d'une variante du contrat, avec l'état `simulation_automatique` servi posé dessus. */
const servieAvecSimulationAuto = (variante, auto) => ({
  data: { ...exempleContrat('calepinage', 'calepinage_resultat', variante), simulation_automatique: auto },
})

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
    const { unmount: unmount2 } = rendre()
    // R3-08 — la production mensuelle servie est tracée ; le motif ne vaut que pour la consommation.
    const sansCharge = await screen.findByTestId('acal453-graphique')
    expect(screen.queryByTestId('acal453-vide')).toBeNull()
    expect(within(sansCharge).getByTestId('acal453-motif')).toHaveTextContent('Aucune courbe de charge saisie.')
    expect(within(sansCharge).getAllByText('Production (P50)').length).toBeGreaterThan(0)
    expect(within(sansCharge).queryByText('Consommation')).toBeNull()
    unmount2()

    // Ni charge ni production mensuelle : l'état vide d'origine.
    servi.production.mensuel = []
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
    // ACAL970 — « non calculée » passe en infobulle d'un « — ».
    expect(within(ligne).getAllByTitle('non calculée').length).toBeGreaterThan(0)
  })

  it('ACAL970 — avant simulation le tableau par pan écrit « — » et chaque cellule a un espacement', async () => {
    servir('exemple_vide')
    rendre()
    await screen.findByTestId('cal236-panneau')
    const parPan = screen.getByTestId('cal236-par-pan')
    for (const cellule of parPan.querySelectorAll('th, td')) expect(cellule).toHaveClass('px-3')
    const ligne = within(parPan).getByText('PAN-A').closest('tr')
    expect(within(ligne).queryByText('non calculée')).toBeNull()
    for (const absent of within(ligne).getAllByTitle('non calculée')) expect(absent).toHaveTextContent(/^—$/)
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

    // ACAL990 : l'avertissement servi est dit UNE fois (le bandeau) ; la liste ne le répète pas.
    expect(screen.getByTestId('cal236-non-simule')).toHaveTextContent(
      'Calepinage non simulé : la pose est connue, la production ne l\'est pas.',
    )
    expect(screen.queryByTestId('calx48-manques')).toBeNull()
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

    /* R5B-N5 (jumeau, revue du 26/11) — la ligne des ombres servie avec la cible `?onglet=production` menait à l'écran
       même où elle se lit : un lien mort dans le panneau Production. Même destination qu'aux Résultats : l'étape Panneaux,
       ouverte comme par le clic sur l'étape (`state.etapeChoisie`). */
    it('R5B-N5 — la ligne des ombres ouvre l’étape Panneaux ; aucune ligne ne mène à l’écran où elle se lit', async () => {
      const { Routes, Route, useLocation } = await import('react-router-dom')
      const Sonde = () => {
        const lieu = useLocation()
        return <p data-testid="sonde">{`${lieu.pathname}${lieu.search}|${lieu.state?.etapeChoisie === true}`}</p>
      }
      servir('exemple_vide')
      render(
        <MemoryRouter initialEntries={['/calepinage/1?onglet=production']}>
          <Routes>
            <Route path="/calepinage/:id" element={<>
              <PanneauProduction calepinageId={1} parcours={{ etats: {}, manque: [
                { code: 'acces_solaire_absent', message: 'L’ombre sur chaque panneau n’est pas encore calculée.',
                  etape: 'resultats', gravite: 'info', nombre: 1, cible: { onglet: 'production', champ: '' } },
              ] }} />
              <Sonde />
            </>} />
          </Routes>
        </MemoryRouter>,
      )
      const ligne = await screen.findByTestId('calx48-manque-ligne')
      expect(ligne).toHaveAttribute('href', '/calepinage/1?onglet=fiches')
      expect(ligne.getAttribute('href')).not.toContain('onglet=production')
      fireEvent.click(ligne)
      await waitFor(() => expect(screen.getByTestId('sonde')).toHaveTextContent('/calepinage/1?onglet=fiches|true'))
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
    // ACAL940 — le lien ouvre le CHAMP du réglage nommé (ancre calx69-<clé>).
    expect(within(refus).getByTestId('calx48-lien-reglages'))
      .toHaveAttribute('href', '/calepinage/reglages#calx69-mode_meteo')
  })

  it('T4-V1-012 — temps dépassé : la phrase du serveur, le lien vers la fenêtre météo et « Réessayer » qui relance', async () => {
    const motif = 'La simulation a dépassé le temps alloué (2 minutes) : relancez-la ; si cela se reproduit, réduisez la « Fenêtre d’années météo » dans les réglages de simulation du calepinage.'
    calepinageApi.calepinages.resultat.mockResolvedValue(vide())
    calepinageApi.calepinages.simuler.mockResolvedValue({ data: accuse })
    calepinageApi.moteur.resultat.mockResolvedValue({
      data: { ...refusServi, elements: [{ statut: 'failed', champ: 'parametres.simulation.fenetre_annees', motif }] },
    })
    rendre()
    await screen.findByTestId('cal236-panneau')
    fireEvent.click(screen.getByTestId('calx48-lancer-bouton'))
    const refus = await screen.findByTestId('calx48-refus')
    expect(refus).toHaveTextContent(motif)
    expect(within(refus).getByTestId('calx48-lien-reglages'))
      .toHaveAttribute('href', '/calepinage/reglages#calx69-fenetre_annees')
    fireEvent.click(within(refus).getByRole('button', { name: 'Réessayer' }))
    await waitFor(() => expect(calepinageApi.calepinages.simuler).toHaveBeenCalledTimes(2))
    expect(calepinageApi.calepinages.simuler).toHaveBeenLastCalledWith(1, { forcer: true })
  })

  it('T4-V1-012 — un nom d’exception brut n’atteint jamais l’écran (ancien job) : phrase française et « Réessayer »', async () => {
    calepinageApi.calepinages.resultat.mockResolvedValue(vide())
    calepinageApi.calepinages.simuler.mockResolvedValue({ data: accuse })
    calepinageApi.moteur.resultat.mockResolvedValue({
      data: { ...refusServi, elements: [{ statut: 'failed', champ: '', motif: 'SoftTimeLimitExceeded()' }] },
    })
    rendre()
    await screen.findByTestId('cal236-panneau')
    fireEvent.click(screen.getByTestId('calx48-lancer-bouton'))
    const refus = await screen.findByTestId('calx48-refus')
    expect(refus).not.toHaveTextContent('SoftTimeLimitExceeded')
    expect(refus).toHaveTextContent('La simulation a échoué')
    expect(within(refus).getByRole('button', { name: 'Réessayer' })).toBeInTheDocument()
  })

  it('ACAL940 — un seul 409 : 3 lignes, deux liens vers leur champ de réglage', async () => {
    const refusManquants = exempleContrat('calepinage', 'calepinage_simulation', 'exemple_refus_manquants')
    calepinageApi.calepinages.resultat.mockResolvedValue(vide())
    calepinageApi.calepinages.simuler.mockRejectedValue({ response: { data: refusManquants } })
    rendre()

    await screen.findByTestId('cal236-panneau')
    fireEvent.click(screen.getByTestId('calx48-lancer-bouton'))

    const lignes = await screen.findAllByTestId('acal940-manquant')
    expect(lignes).toHaveLength(3)
    refusManquants.manquants.forEach((m, i) => expect(lignes[i]).toHaveTextContent(m.motif))
    expect(screen.getAllByTestId('acal940-lien-reglage').map((a) => a.getAttribute('href'))).toEqual([
      '/calepinage/reglages#calx69-mode_meteo', '/calepinage/reglages#calx69-fenetre_annees',
    ])
  })

  // ACAL1639 — le serveur nomme l'étape où agir (`cible.etape`, contrat `exemple_refus_sans_pan_equipe`) : le refus y
  // mène (« Tracer le toit » / « Poser les panneaux ») ; cible nulle (modules posés) : l'onglet Matériel, comme avant.
  it.each([
    ['toit', 'Tracer le toit', '/calepinage/1?onglet=pente'],
    ['panneaux', 'Poser les panneaux', '/calepinage/1?onglet=fiches'],
    [null, 'Ouvrir le matériel électrique', '/calepinage/1?onglet=materiel-electrique'],
  ])('ACAL1639 — refus « sans module », cible servie %s : le lien suit la cible servie', async (etape, libelle, href) => {
    const sansPan = exempleContrat('calepinage', 'calepinage_simulation', 'exemple_refus_sans_pan_equipe')
    const servi = etape === 'toit' ? sansPan : { ...sansPan, manquants: sansPan.manquants.map((m) => ({
      ...m, cible: etape ? { ...m.cible, etape } : null })) }
    calepinageApi.calepinages.resultat.mockResolvedValue(vide())
    calepinageApi.calepinages.simuler.mockRejectedValue({ response: { data: servi } })
    rendre()
    await screen.findByTestId('cal236-panneau')
    fireEvent.click(screen.getByTestId('calx48-lancer-bouton'))
    const lien = within(await screen.findByTestId('calx48-refus')).getByTestId('acal774-lien')
    expect(lien).toHaveTextContent(libelle)
    expect(lien).toHaveAttribute('href', href)
  })

  it('ACAL774 — sans cible servie, « aucun module » ouvre l’onglet Matériel électrique ; l’épingle ouvre l’atelier', async () => {
    const contrat = exempleContrat('calepinage', 'calepinage_simulation', 'exemple_refus_sans_pan_equipe')
    // Serveur d'avant ACAL1639 (aucune `cible` sur la ligne) : la table par champ fait foi.
    const sansPan = { ...contrat, manquants: contrat.manquants.map((m) => ({ champ: m.champ, motif: m.motif })) }
    calepinageApi.calepinages.resultat.mockResolvedValue(vide())
    calepinageApi.calepinages.simuler.mockRejectedValue({ response: { data: sansPan } })
    rendre()

    await screen.findByTestId('cal236-panneau')
    fireEvent.click(screen.getByTestId('calx48-lancer-bouton'))
    expect(within(await screen.findByTestId('calx48-refus')).getByTestId('acal774-lien'))
      .toHaveAttribute('href', '/calepinage/1?onglet=materiel-electrique')

    // Liste d'ACAL940 : `site.pin` (cible nulle) mène à l'atelier ; un champ inconnu reste sans lien.
    const manquants = exempleContrat('calepinage', 'calepinage_simulation', 'exemple_refus_manquants')
    calepinageApi.calepinages.simuler.mockRejectedValue({ response: { data: {
      ...manquants, manquants: [...manquants.manquants, { champ: 'inconnu.x', motif: 'Autre manque.', cible: null }],
    } } })
    fireEvent.click(screen.getByTestId('calx48-lancer-bouton'))
    await waitFor(() => expect(screen.getAllByTestId('acal940-manquant')).toHaveLength(4))
    expect(screen.getAllByTestId('acal774-lien').map((a) => a.getAttribute('href'))).toEqual(['/calepinage/1'])
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

  it('périmé sans cause prouvée : « Relancer la simulation » (aucune cause nommée)', async () => {
    servir('exemple_perime')
    rendre()

    await screen.findByTestId('cal236-panneau')
    expect(screen.getByTestId('calx48-lancer-bouton')).toHaveTextContent('Relancer la simulation')
  })

  it('ACAL1647 — périmé par un réglage de la société : « Relancer (réglages modifiés) »', async () => {
    const servi = exempleContrat('calepinage', 'calepinage_resultat', 'exemple_perime')
    const perimeParUnReglage = () => ({
      ...servi,
      motif: 'simulation périmée : un réglage de la société a changé depuis le calcul du 19/09/2026',
    })
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: perimeParUnReglage() })
    rendre()

    await screen.findByTestId('cal236-panneau')
    expect(screen.getByTestId('calx48-lancer-bouton')).toHaveTextContent('Relancer (réglages modifiés)')
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
      'simulation périmée : le document ou un réglage de la société a changé depuis le calcul du 19/09/2026',
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
    // ACAL990 : le motif servi est dit UNE fois (le bandeau) ; le tapis dit sa propre phrase.
    expect(screen.getByTestId('calx48-perime')).toHaveTextContent(
      'simulation périmée : le document ou un réglage de la société a changé depuis le calcul du 19/09/2026',
    )
    expect(tapis).toHaveTextContent('relancez-la')
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
      .toHaveAttribute('href', '/calepinage/reglages#calx69-section-simulation')

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

  /* ACAL1987 — la simulation partie à l'enregistrement est lancée par le SERVEUR : l'onglet reprend SON job. */
  it('ACAL1987 — job du serveur en cours ⇒ « Simulation en cours… » puis relecture, sans POST simuler', async () => {
    viderSimulationsAuto()
    servir('exemple')
    calepinageApi.calepinages.resultat.mockResolvedValue(
      servieAvecSimulationAuto('exemple', { en_cours: true, job_id: 'j-9', manquants: [] }))
    calepinageApi.moteur.resultat
      .mockResolvedValueOnce({ data: { job_id: 'j-9', statut: 'running' } })
      .mockResolvedValue({ data: { job_id: 'j-9', statut: 'done' } })
    await suivreSimulationDuServeur(1)
    render(<MemoryRouter><PanneauProduction calepinageId={1} intervalleMs={300} /></MemoryRouter>)

    expect(await screen.findByText('Simulation en cours…')).toBeInTheDocument()
    await waitFor(() => expect(calepinageApi.moteur.resultat).toHaveBeenCalledWith('j-9'))
    await waitFor(() => expect(calepinageApi.calepinages.resultat.mock.calls.length).toBeGreaterThan(2))
    expect(calepinageApi.calepinages.simuler).not.toHaveBeenCalled()
  })

  it('ACAL1987 — pose incomplète (aucun job servi) ⇒ aucune reprise, aucun calcul, l’onglet ne dit pas « en cours »', async () => {
    viderSimulationsAuto()
    servir('exemple_vide')
    calepinageApi.calepinages.resultat.mockResolvedValue(servieAvecSimulationAuto(
      'exemple_vide', exempleContrat('calepinage', 'calepinage_resultat', 'acal1987_simulation_automatique')))
    await suivreSimulationDuServeur(1)
    rendre()

    await screen.findByTestId('cal236-panneau')
    expect(screen.queryByText('Simulation en cours…')).toBeNull()
    expect(calepinageApi.calepinages.simuler).not.toHaveBeenCalled()
    expect(calepinageApi.moteur.resultat).not.toHaveBeenCalled()
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
describe("PanneauProduction — Où va l'énergie (ACAL762)", () => {
  afterEach(() => { try { localStorage.removeItem(CLE_EXPERT) } catch { /* sans stockage */ } })
  const ouvrir = async () => {
    fireEvent.click(await screen.findByTestId('acal762-bascule'))
  }

  it("expert : repliée d'office, dépliée elle appelle le schéma et liste les flux servis", async () => {
    localStorage.setItem(CLE_EXPERT, '1')
    calepinageApi.calepinages.diagrammeEnergie.mockResolvedValue({ data: new Blob(['<svg/>']) })
    servir('exemple')
    rendre()
    const bascule = await screen.findByTestId('acal762-bascule')
    expect(calepinageApi.calepinages.diagrammeEnergie).not.toHaveBeenCalled()
    fireEvent.click(bascule)
    expect(calepinageApi.calepinages.diagrammeEnergie).toHaveBeenCalledWith(1, undefined, OPTIONS_TELECHARGEMENT)
    const energie = reponseContrat('calepinage', 'calepinage_resultat', 'exemple').data.autoconsommation.energie
    for (const [code, cle] of [['production_brute', 'production_brute_kwh'], ['sur_place', 'autoconsomme_kwh'],
      ['injectee', 'export_reseau_kwh'], ['importee', 'import_reseau_kwh'], ['consommation', 'consommation_kwh']]) {
      expect(screen.getByTestId(`acal762-flux-${code}`).textContent)
        .toContain(String(Math.trunc(energie[cle])).slice(0, 1))
    }
    expect(screen.getByTestId('acal762-flux-batterie')).toBeInTheDocument()
  })

  it('un flux non calculé dit « non calculé » et son motif, jamais 0 ; exemple_vide aussi', async () => {
    localStorage.setItem(CLE_EXPERT, '1')
    calepinageApi.calepinages.diagrammeEnergie.mockResolvedValue({ data: new Blob(['<svg/>']) })
    const vide = reponseContrat('calepinage', 'calepinage_resultat', 'exemple_vide')
    vide.data.autoconsommation = { energie: null, motif_absence: 'Aucune simulation lancée.' }
    calepinageApi.calepinages.resultat.mockResolvedValue(vide)
    rendre()
    await ouvrir()
    const flux = screen.getByTestId('acal762-flux-production_brute')
    expect(flux).toHaveTextContent('non calculé')
    expect(flux.textContent).not.toContain(' 0 kWh')
    expect(flux).toHaveTextContent('Aucune simulation lancée')
  })

  it('un refus 409 du schéma montre son motif et garde la liste', async () => {
    localStorage.setItem(CLE_EXPERT, '1')
    calepinageApi.calepinages.diagrammeEnergie.mockRejectedValue({
      response: { data: { text: () => Promise.resolve(JSON.stringify({ cascade: ['Aucune cascade regroupée.'] })) } },
    })
    servir('exemple')
    rendre()
    await ouvrir()
    expect(await screen.findByTestId('acal762-refus')).toHaveTextContent('Aucune cascade regroupée.')
    expect(screen.getByTestId('acal762-flux-soleil')).toBeInTheDocument()
  })

  it('un schéma trop long à produire dit le délai en français (R3)', async () => {
    localStorage.setItem(CLE_EXPERT, '1')
    calepinageApi.calepinages.diagrammeEnergie.mockRejectedValue({ code: 'ECONNABORTED' })
    servir('exemple')
    rendre()
    await ouvrir()
    expect(await screen.findByTestId('acal762-refus')).toHaveTextContent("Le serveur n'a pas fini de préparer ce document en 2 minutes.")
  })

  it('guidé : aucune carte', async () => {
    servir('exemple')
    rendre()
    await screen.findByTestId('cal236-panneau')
    expect(screen.queryByTestId('acal762-carte')).toBeNull()
  })
})

describe('PanneauProduction — charges ajoutées (ACAL781)', () => {
  const avecCharges = (adapter) => {
    const reponse = reponseContrat('calepinage', 'calepinage_resultat', 'exemple')
    const sim = reponseContrat('calepinage', 'calepinage_simulation', 'exemple').data
    reponse.data.consommation = JSON.parse(JSON.stringify(sim.consommation))
    adapter?.(reponse.data.consommation)
    calepinageApi.calepinages.resultat.mockResolvedValue(reponse)
    return reponse.data.consommation
  }

  it('ligne et détail lus du contrat : total servi, libellé, méthode, prévue, plafonnée', async () => {
    const conso = avecCharges((c) => {
      c.charges[0].planifie = true
      c.charges[0].plafonnee = true
    })
    rendre()
    const ligne = await screen.findByTestId('calx-charges-ajoutees')
    expect(ligne.textContent.replace(/\s/g, ' ')).toContain('Charges ajoutées : 1 800 kWh/an')
    const detail = within(ligne).getByTestId(`calx-charge-${conso.charges[0].code}`)
    expect(detail).toHaveTextContent(conso.charges[0].libelle)
    expect(detail).toHaveTextContent('km par jour')
    expect(detail).toHaveTextContent('prévue')
    expect(detail).toHaveTextContent('plafonnée par la borne')
  })

  it('ACAL1646 — une charge ignorée par le serveur est nommée en mots : « Voiture électrique : ignorée — <motif> », sans le code', async () => {
    avecCharges((c) => {
      c.avertissements = [
        'La charge n°2 (vehicule) est déjà comprise dans les factures : elle est ignorée pour ne pas être comptée deux '
        + "fois (décochez la case pour l'ajouter).",
        '« Piscine » est seulement PRÉVU : sa consommation est comptée et le devis le dit.',
      ]
    })
    rendre()
    const ligne = await screen.findByTestId('calx-charges-ajoutees')
    const ignoree = within(ligne).getByTestId('calx-charge-ignoree-vehicule')
    expect(ignoree).toHaveTextContent(/^Voiture électrique : ignorée — déjà comprise dans les factures/)
    expect(ignoree).toHaveTextContent('pour ne pas être comptée deux fois')
    expect(ignoree).not.toHaveTextContent('vehicule')
    expect(ligne).not.toHaveTextContent('n°2')
    // La charge comptée garde sa ligne ; l'avertissement « prévu » n'est pas une charge ignorée.
    expect(within(ligne).getAllByTestId(/^calx-charge-ignoree-/)).toHaveLength(1)
  })

  it('ACAL1646 — toutes les charges ignorées : la ligne « Charges ajoutées » ne ment pas, l’ignorée reste dite', async () => {
    avecCharges((c) => {
      c.charges = []
      c.total_charges_kwh = 0
      c.avertissements = ['La charge n°1 (pac) est déjà comprise dans les factures : elle est ignorée pour ne pas être comptée deux fois (décochez la case pour l\'ajouter).']
    })
    rendre()
    const ligne = await screen.findByTestId('calx-charges-ajoutees')
    expect(ligne).toHaveTextContent('Pompe à chaleur : ignorée — déjà comprise dans les factures')
    expect(ligne).not.toHaveTextContent('Charges ajoutées')
  })

  it('ACAL1608 — l’écran dit la source de la courbe de base : « facture du lead » quand `courbe_origine` le dit', async () => {
    avecCharges((c) => { c.courbe_origine = 'facture_lead' })
    rendre()
    expect(await screen.findByTestId('calx-courbe-origine')).toHaveTextContent('Courbe de base : facture du lead')
    cleanup()
    avecCharges((c) => { c.courbe_origine = 'profil_mensuel' })
    rendre()
    expect(await screen.findByTestId('calx-courbe-origine')).toHaveTextContent('Courbe de base : douze mois saisis')
  })

  it('sans charge déclarée : aucune ligne', async () => {
    avecCharges((c) => { c.charges = []; c.total_charges_kwh = 0 })
    rendre()
    await screen.findByTestId('cal236-panneau')
    expect(screen.queryByTestId('calx-charges-ajoutees')).toBeNull()
  })
})

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
    // Item 15 — registre absent : le nom du profil de départ, jamais la clé brute.
    expect(texte).toHaveTextContent('Poussière sur les panneaux, Perte des premières heures de soleil, Écarts entre panneaux')
    expect(texte).not.toHaveTextContent('salissure_mensuelle_pct')
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

  /* Item 15 (T4-U2-013, T4-U4-009) — la simulation sert les clés PRÉFIXÉES (`electrique_societe.…`) ; les libellés
     sont tenus SANS préfixe : trois clés brutes s'imprimaient. Un seul résolveur, avec et sans préfixe ; une clé sans
     libellé ne s'imprime jamais brute. */
  it('Item 15 / ACAL1632 — clés préfixées : leurs noms en clair ; les « electrique_societe.… » ne sont pas des pertes (ni nommées ni comptées) ; une clé sans libellé : « autre réglage (réglage de la société) »', async () => {
    render(<MemoryRouter><NoteValeursPubliees onVoirSources={vi.fn()} simulation={{ reglages_utilises: {
      'pertes.salissure_mensuelle_pct': publie(2),
      'pertes.reglage_sans_libelle_x': publie(1),
      'electrique_societe.seuil_bas_dc_ac': publie(0.8),
      'electrique_societe.tolerance_polystring_bloquante_pct': publie(10),
      'electrique_societe.tolerance_polystring_acceptable_pct': publie(5),
    } }} /></MemoryRouter>)
    const note = await screen.findByTestId('acal698-texte-note')
    expect(note).toHaveTextContent('2 réglages utilisent des valeurs publiées')
    expect(note).toHaveTextContent('poussière sur les panneaux, autre réglage (réglage de la société)')
    expect(note).not.toHaveTextContent('electrique_societe')
    expect(note).not.toHaveTextContent(/onduleur|entre chaînes/)
    expect(note).not.toHaveTextContent('_')
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
    expect(within(bloc).getByTestId('acal700-plafond')).toHaveAttribute('title', 'Toutes sont à renseigner ici.')
    expect(within(bloc).queryByTestId('acal700-jauge')).toBeNull() // R3-06 : plus de troisième compte
    const lignes = within(bloc).getAllByTestId('acal700-ligne')
    expect(lignes).toHaveLength(a.lignes.length)
    expect(lignes[0]).toHaveTextContent('Aucune valeur pour votre société')
    const renseigner = within(lignes[0]).getByTestId('acal700-renseigner')
    expect(renseigner).toHaveAttribute('href', '/calepinage/reglages#calx69-salissure_mensuelle_pct')
    expect(within(bloc).getByTestId('acal700-lien-reglages')).toHaveAttribute('href', expect.stringContaining('/calepinage/reglages/demarrage-rapide?reglages=')) // T4-B4-003
    const sur = within(bloc).getByTestId('acal700-sur')
    for (const t of ['Panneaux', 'Puissance', 'Raccordement', 'Conforme', 'Ombres proches']) {
      expect(within(sur).getByText(t)).toBeInTheDocument()
    }
    // ACAL1833 — la phrase de la note est portée par les deux blocs ABSENTS de la maquette v2 (jamais de valeur inventée).
    expect(within(bloc).getByTestId('acal1833-absent-annees')).toHaveTextContent("9 fois sur 10 au-dessus. S'affiche dès que le résultat est complet.")
    expect(within(bloc).getByTestId('acal1833-absent-indice')).toHaveTextContent("Indice de performance")
    // Maquette ResultatsIncomplet : la barre « N étapes sur M » du serveur, les lignes numérotées, la carte « au plus » à gauche.
    expect(within(bloc).getByTestId('acal700-progression')).toHaveTextContent(`${a.etapes_comptees} ${a.etapes_comptees > 1 ? 'étapes' : 'étape'} sur ${a.etapes_a_compter}`)
    expect(within(bloc).getByTestId('acal700-valeur')).toHaveTextContent('kWh')
    expect(lignes[0]).toHaveTextContent('1')
    expect(within(bloc).getByTestId('acal700-lien-reglages')).toHaveTextContent('Voir les valeurs')
    expect(screen.queryByTestId('acal52-borne-haute')).toBeNull() // remplacé
  })

  it('démarrage rapide qui ne peut rien remplir : pas de bouton or « Voir les valeurs », un lien discret vers les réglages', async () => {
    const servi = incomplet()
    servi.cascade = { ...servi.cascade, a_renseigner: { ...servi.cascade.a_renseigner,
      lignes: servi.cascade.a_renseigner.lignes.map((l) => ({ ...l, cle: 'sigma_modele_pct' })) } }
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: servi })
    rendreAvecParcours({ etapes: [], manque: [] })
    const lien = await screen.findByTestId('acal700-lien-reglages')
    expect(lien).toHaveAttribute('href', '/calepinage/reglages')
    expect(lien).toHaveTextContent('Saisir mes mesures')
    expect(lien).not.toHaveClass('cal-res-cta')
    expect(screen.getByTestId('acal700-demarrage-texte')).toHaveTextContent('Aucune valeur publiée n’existe')
  })

  it('R3-06 — un seul compte : 17 pertes pas encore comptées (3 à renseigner ici), sur UNE ligne de 14 px', async () => {
    const servi = incomplet()
    servi.cascade = { ...servi.cascade, a_renseigner: { ...servi.cascade.a_renseigner, etapes_comptees: 4, etapes_a_compter: 21 } }
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: servi })
    rendreAvecParcours({ etapes: [], manque: [] })
    const bloc = await screen.findByTestId('acal700-incomplet')
    expect(within(bloc).getByTestId('acal700-plafond')).toHaveTextContent(
      "C'est un plafond : 17 pertes ne sont pas encore comptées. Le chiffre réel sera plus bas.")
    expect(within(bloc).getByTestId('acal700-plafond')).toHaveAttribute('title', '3 à renseigner ici.')
    // Le compte de la barre est celui du serveur (4 sur 21), le même que « 17 pertes non renseignées » (21 − 4).
    expect(within(bloc).getByTestId('acal700-progression')).toHaveTextContent('4 étapes sur 21')
  })

  it('Raccordement « Conforme » seulement si l’étape électrique est faite', async () => {
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: incomplet() })
    rendreAvecParcours({ etapes: [{ cle: 'electrique', etat: 'a_faire' }], manque: [] })
    const sur = await screen.findByTestId('acal700-sur')
    expect(within(sur).queryByText('Raccordement')).toBeNull()
  })

  it('ACAL1833 — tuile « Ombres proches » non servie ⇒ « à renseigner » ; chiffre avec séparateur insécable visible', async () => {
    const servi = incomplet()
    servi.cascade.postes_lisibles.postes[0] = { ...servi.cascade.postes_lisibles.postes[0], statut: 'non_compte', perte_pct: null, perte_kwh: null }
    servi.production = { ...servi.production, total: { ...servi.production.total, p50_kwh: 12950 } }
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: servi })
    rendreAvecParcours({ etapes: [], manque: [] })
    const sur = await screen.findByTestId('acal700-sur')
    const ombres = [...sur.querySelectorAll('.cal-resinc-tuile')].find((t) => t.textContent.startsWith('Ombres proches'))
    expect(ombres).toBeTruthy()
    expect(ombres).toHaveTextContent('à renseigner')
    expect(ombres).not.toHaveTextContent('%')
    // Le chiffre principal : l'espace insécable des milliers est gardée dans le texte ET dessinée (largeur propre).
    const valeur = screen.getByTestId('acal700-valeur')
    expect(valeur.textContent).toBe('12\u202f950 kWh')
    const sep = valeur.querySelector('.cal-gros-sep')
    expect(sep).toBeTruthy()
    const { readFileSync } = await import('node:fs')
    const style = document.createElement('style')
    style.textContent = readFileSync(`${globalThis.process.cwd()}/src/styles/calepinage/54-etape-resultats.css`, 'utf8')
    document.head.appendChild(style)
    try {
      expect(getComputedStyle(sep).display).toBe('inline-block')
      expect(parseFloat(getComputedStyle(sep).width)).toBeGreaterThan(0)
      expect(parseFloat(getComputedStyle(sep).fontSize || '16')).toBeGreaterThan(0) // un em de 0 px aurait une largeur nulle
    } finally {
      style.remove()
    }
  })

  it('ACAL1833 — deux colonnes ; « Étapes du calcul » en N segments servis ; pertes qui manquent en pastilles ; deux blocs absents', async () => {
    calepinageApi.calepinages.resultat.mockResolvedValue({ data: incomplet() })
    rendreAvecParcours({ etapes: [], manque: [] })
    const bloc = await screen.findByTestId('acal700-incomplet')
    const a = borneHaute.cascade.a_renseigner
    expect(bloc.querySelectorAll('.cal-resinc-haut > .cal-resinc-colonne')).toHaveLength(2)
    const segments = [...within(bloc).getByTestId('acal700-progression').querySelectorAll('.cal-resinc-segments > span')]
    expect(segments).toHaveLength(a.etapes_a_compter)
    expect(segments.filter((x) => x.dataset.fait === 'oui')).toHaveLength(a.etapes_comptees)
    expect([...within(bloc).getByTestId('acal1833-manques').children].map((n) => n.textContent)).toEqual(
      ['Poussière sur les panneaux', 'Écarts entre panneaux', 'Vieillissement de la première année'])
    expect(within(bloc).getByTestId('acal1833-absent-indice')).toHaveTextContent('À renseigner')
    expect(within(bloc).getByTestId('acal1833-absent-annees')).toHaveTextContent('À renseigner')
    expect(within(bloc).getByTestId('acal1833-compteur')).toHaveTextContent('réglage')
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

  it('ACAL1657 — « Année basse » nomme ce qu’elle compte : météo seule, puis chaque composante servie', async () => {
    localStorage.setItem(CLE_EXPERT, '1')
    const servirIncertitude = (composantes) => {
      const reponse = reponseContrat('calepinage', 'calepinage_resultat', 'exemple')
      if (composantes) reponse.data.incertitude = { ...reponse.data.incertitude, composantes }
      calepinageApi.calepinages.resultat.mockResolvedValue(reponse)
    }
    servirIncertitude(null)
    rendre()
    expect(await screen.findByTestId('acal710-basse'))
      .toHaveTextContent('Année basse (variabilité météo seule, 9 années sur 10 au-dessus) : 11 900 kWh')
    expect(screen.getByTestId('acal710-basse')).not.toHaveTextContent('9 fois sur 10')
    cleanup()
    servirIncertitude([
      { nom: 'variabilite_interannuelle', sigma_relatif: 0.0195, source: 'pvgis' },
      { nom: 'modele_simulation', sigma_relatif: 0.03, source: 'texte' },
      { nom: 'biais_long_terme', sigma_relatif: 0.02, source: 'texte' },
    ])
    rendre()
    expect(await screen.findByTestId('acal710-basse')).toHaveTextContent(
      'Année basse (variabilité météo, modèle de simulation et biais à long terme, 9 années sur 10 au-dessus) : 11 900 kWh')
  })

  it('ACAL1657 — le pied de l’étape Résultats dit la même chose', () => {
    const complet = exempleContrat('calepinage', 'calepinage_resultat')
    render(<MemoryRouter><PiedResultats production={complet.production} incertitude={complet.incertitude} /></MemoryRouter>)
    expect(screen.getByTestId('cal-resultats-pied'))
      .toHaveTextContent('Année basse (variabilité météo seule, 9 années sur 10 au-dessus) : 11 900 kWh')
  })

  it('N lu dans la dernière année (2, 20, 25), garantie seulement à 10 ou 25 ans', async () => {
    localStorage.setItem(CLE_EXPERT, '1')
    servirDuree()
    rendre()
    expect(await screen.findByTestId('acal710-basse')).toHaveTextContent('Année basse (variabilité météo seule, 9 années sur 10 au-dessus) : 11 900 kWh')
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

  // ACAL1634 — la fiche du module ne porte pas sa dégradation : la ligne de durée le dit, avec le lien vers la fiche.
  it('ACAL1634 — sans dégradation : le motif servi suit « Année basse » avec le lien vers la fiche du module', async () => {
    localStorage.setItem(CLE_EXPERT, '1')
    servirDuree((p) => {
      p.duree_de_vie.motif_omission = 'La fiche du module ne porte pas sa dégradation : le tableau pluriannuel est OMIS.'
      p.projection = projectionSur(1)
    })
    render(<MemoryRouter initialEntries={['/calepinage/7']}><Routes>
      <Route path="/calepinage/:id" element={<PanneauProduction calepinageId={7} />} />
    </Routes></MemoryRouter>)
    const ligne = await screen.findByTestId('acal710-ligne')
    const basse = within(ligne).getByTestId('acal710-basse')
    const motif = within(ligne).getByTestId('acal710-motif')
    expect(basse.compareDocumentPosition(motif) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(motif).toHaveTextContent('La fiche du module ne porte pas sa dégradation')
    const lien = within(motif).getByRole('link', { name: 'Voir la fiche du module' })
    expect(lien).toHaveAttribute('href', '/calepinage/7?onglet=fiches')
    cleanup()
    // avec dégradation servie : « Dans N ans », aucun motif ni lien
    servirDuree((p) => { p.projection = projectionSur(25) })
    rendre()
    expect(await screen.findByTestId('acal710-derniere')).toHaveTextContent('Dans 25 ans')
    expect(screen.queryByRole('link', { name: 'Voir la fiche du module' })).toBeNull()
  })
})

/* ACAL873 — le « ? » de la famille PRODUCTION : chaque tuile, chaque mois et
   l'écart PVGIS portent leur grandeur ; la phrase du registre insère la valeur
   servie, jamais un chiffre écrit. */
describe('PanneauProduction — « ? » de la famille production (ACAL873)', () => {
  const REGISTRE = JSON.parse(readFileSync(
    join(fichierContrat('calepinage', 'x'), '..', '..', 'data', 'explications.json'), 'utf8')).entrees
  const entree = (cle) => REGISTRE.find((e) => e.cle === cle)
  const TUILES = ['production.p50_kwh', 'production.kwc', 'production.productible', 'production.pertes_totales',
    'production.p75_kwh', 'production.p90_kwh', 'production.p95_kwh', 'production.variabilite',
    'production.performance_ratio']

  it('chaque tuile a son « ? » et sa phrase avec la valeur servie', async () => {
    servir('exemple')
    rendre()
    const tuiles = await screen.findByTestId('cal236-total')
    const grandeurs = [...tuiles.querySelectorAll('[data-grandeur]')].map((b) => b.getAttribute('data-grandeur'))
    expect(grandeurs).toEqual(TUILES)
    expect(chiffresSansGrandeur(tuiles)).toEqual([])
    const data = exempleContrat('calepinage', 'calepinage_resultat', 'exemple')
    const p90 = remplirPhrase(entree('production.p90_kwh'), data).replace(/\s/g, ' ')
    expect(p90).toContain('neuf années sur dix')
    expect(p90).toContain('11 900 kWh')
    expect(entree('production.p90_kwh').source).toContain('DEPASSEMENTS')
    expect(screen.getByTestId('cal236-mensuel').querySelectorAll('[data-grandeur="production.mensuel"]'))
      .toHaveLength(data.production.mensuel.length)
    expect(screen.getByTestId('acal854-ecart-pvgis').querySelector('[data-grandeur="production.ecart_pvgis"]'))
      .not.toBeNull()
  })

  it('valeur absente ⇒ « valeur non publiée », jamais 0', () => {
    const phrase = remplirPhrase(entree('production.p90_kwh'), { production: { total: { p90_kwh: null } } })
    expect(phrase).toContain(NON_PUBLIEE)
    expect(phrase).not.toMatch(/\b0 kWh/)
  })
})

/* ACAL880 — « Pourquoi ce chiffre ? » : les trois plus gros postes CALCULÉS de
   la cascade servie (`calepinage_pertes_cascade.json`), avec le geste du
   registre ; niveau expert. Mutant : classer par rang ⇒ ordre faux, échec. */
describe('PanneauProduction — Pourquoi ce chiffre ? (ACAL880)', () => {
  const REGISTRE = JSON.parse(readFileSync(
    join(fichierContrat('calepinage', 'x'), '..', '..', 'data', 'explications.json'), 'utf8')).entrees
  const CASCADE = exempleContrat('calepinage', 'calepinage_pertes_cascade').cascade
  const servirAvecCascade = (variante = 'exemple') => {
    const reponse = reponseContrat('calepinage', 'calepinage_resultat', variante)
    if (reponse.data.cascade) reponse.data.cascade = CASCADE
    calepinageApi.calepinages.resultat.mockResolvedValue(reponse)
  }
  beforeEach(() => {
    calepinageApi.calepinages.explications.mockResolvedValue({ data: { entrees: REGISTRE } })
    localStorage.setItem(CLE_EXPERT, '1')
  })
  afterEach(() => { try { localStorage.removeItem(CLE_EXPERT) } catch { /* sans stockage */ } })

  it('trois plus gros postes calculés, triés par perte, avec leur geste', async () => {
    servirAvecCascade()
    rendre()
    fireEvent.click(await screen.findByTestId('acal880-bouton'))
    const postes = within(screen.getByTestId('acal880-postes')).getAllByRole('listitem')
    expect(postes.map((li) => li.getAttribute('data-testid')))
      .toEqual(['acal880-poste-thermique', 'acal880-poste-ohmique_dc', 'acal880-poste-irradiation_plan'])
    const thermique = CASCADE.etapes.find((e) => e.etape === 'thermique')
    expect(postes[0]).toHaveTextContent(thermique.libelle)
    expect(postes[0].textContent.replace(/\s/g, ' ')).toContain('8,0 %')
    // ACAL1654 — la source se lit par la table de l'écran (« Fiche technique »), jamais le code brut.
    expect(postes[0]).toHaveTextContent(libelleSource(thermique.source))
    expect(libelleSource(thermique.source)).not.toBe(thermique.source)
    const geste = REGISTRE.find((e) => e.cle === 'pertes.etape').geste
    expect(await within(postes[0]).findByText(geste)).toBeInTheDocument()
  })

  it('étape omise et étape de gain exclues', async () => {
    servirAvecCascade()
    rendre()
    fireEvent.click(await screen.findByTestId('acal880-bouton'))
    for (const etape of ['bifacial', 'spectral', 'indisponibilite']) {
      expect(screen.queryByTestId(`acal880-poste-${etape}`)).toBeNull()
    }
  })

  it('non simulé ⇒ pas de bouton', async () => {
    servirAvecCascade('exemple_vide')
    rendre()
    await screen.findByTestId('cal236-panneau')
    expect(screen.queryByTestId('acal880-bouton')).toBeNull()
  })
})

/* ACAL848 — « Existant / Ajouté / Total » (niveau expert, seulement avec `production.parties`). */
describe('PanneauProduction — existant et ajouté (ACAL848)', () => {
  afterEach(() => { try { localStorage.removeItem(CLE_EXPERT) } catch { /* sans stockage */ } })
  // `exemple_avec_existant` est un fragment `{production: {parties}}` : posé sur le résultat simulé.
  const servirParties = (avec) => {
    const reponse = reponseContrat('calepinage', 'calepinage_resultat', 'exemple')
    const parties = exempleContrat('calepinage', 'calepinage_resultat', 'exemple_avec_existant').production.parties
    if (avec) reponse.data.production.parties = parties
    calepinageApi.calepinages.resultat.mockResolvedValue(reponse)
    return parties
  }

  it('exemple_avec_existant : trois lignes, P50 avec l’âge, neuf en petit, mention servie', async () => {
    localStorage.setItem(CLE_EXPERT, '1')
    const parties = servirParties(true)
    rendre()
    expect(await screen.findByTestId('acal848-parties')).toBeInTheDocument()
    expect(screen.getByTestId('acal848-existant')).toHaveTextContent('Existant')
    expect(screen.getByTestId('acal848-existant')).toHaveTextContent('3 888 kWh')
    expect(screen.getByTestId('acal848-existant')).toHaveTextContent('neuf : 4 000 kWh')
    expect(screen.getByTestId('acal848-ajoute')).toHaveTextContent('Ajouté')
    expect(screen.getByTestId('acal848-total')).toHaveTextContent('5,00 kWc')
    expect(screen.getByTestId('acal848-mention')).toHaveTextContent(parties.mention)
  })

  it('sans `parties` (ou en guidé) : rien ne change', async () => {
    localStorage.setItem(CLE_EXPERT, '1')
    servirParties(false)
    rendre()
    await screen.findByTestId('cal236-panneau')
    expect(screen.queryByTestId('acal848-parties')).toBeNull()
    cleanup()
    localStorage.removeItem(CLE_EXPERT)
    servirParties(true)
    rendre()
    await screen.findByTestId('cal236-panneau')
    expect(screen.queryByTestId('acal848-parties')).toBeNull()
  })
})

/* ACAL986 (garde K-IMPASSE) — un message qui demande une saisie mène à un champ MONTÉ de la page
   d'arrivée. Le registre est CALCULÉ au rendu des Réglages (contrat `parametres_calepinage.json`),
   jamais écrit ici ; les cibles viennent des refus servis et des contrats. */
describe('ACAL986 — chaque lien « aller aux réglages » vise un champ monté', () => {
  const idsMontesDesReglages = async () => {
    calepinageApi.parametres.get.mockResolvedValue(reponseContrat('calepinage', 'parametres_calepinage'))
    const { container, unmount } = render(<ReglagesSimulation />)
    await screen.findByTestId('acal572-lestage')
    await screen.findByTestId('acal397-norme')
    const ids = new Set([...container.querySelectorAll('[id]')].map((n) => n.id))
    unmount()
    return ids
  }
  const exiger = (ids, cible, message, ecran) => {
    expect(ids.has(cible), `« ${message} » (${ecran}) vise #${cible}, aucun champ monté aux Réglages`).toBe(true)
  }

  it('les lignes de « ce qui manque » d’un refus de simulation ouvrent leur champ', async () => {
    const ids = await idsMontesDesReglages()
    const refus = exempleContrat('calepinage', 'calepinage_simulation', 'exemple_refus_manquants')
    calepinageApi.calepinages.resultat.mockResolvedValue(
      { data: exempleContrat('calepinage', 'calepinage_resultat', 'exemple_vide') })
    calepinageApi.calepinages.simuler.mockRejectedValue({ response: { data: refus } })
    rendre()
    await screen.findByTestId('cal236-panneau')
    fireEvent.click(screen.getByTestId('calx48-lancer-bouton'))
    await screen.findAllByTestId('acal940-manquant')

    const liens = screen.getAllByTestId('acal940-lien-reglage')
    const attendus = refus.manquants.filter((m) => m.cible?.onglet === 'reglages')
    expect(attendus.length).toBeGreaterThan(0)
    expect(liens).toHaveLength(attendus.length)
    liens.forEach((lien, i) => {
      const [chemin, ancre] = lien.getAttribute('href').split('#')
      expect(chemin).toBe('/calepinage/reglages')
      exiger(ids, ancre, attendus[i].motif, 'Production')
    })
  })

  it('les lignes « Renseigner » du résultat incomplet (ACAL700) ouvrent leur champ monté', async () => {
    const ids = await idsMontesDesReglages()
    const borneHaute = exempleContrat('calepinage', 'calepinage_simulation', 'exemple_borne_haute')
    const donnees = reponseContrat('calepinage', 'calepinage_resultat', 'exemple')
    donnees.data.production = borneHaute.production
    donnees.data.simulation = borneHaute.simulation
    donnees.data.cascade = borneHaute.cascade
    calepinageApi.calepinages.resultat.mockResolvedValue(donnees)
    render(<MemoryRouter><PanneauProduction calepinageId={1} parcours={{ etapes: [], manque: [] }} /></MemoryRouter>)
    const bloc = await screen.findByTestId('acal700-incomplet')
    const lignes = borneHaute.cascade.a_renseigner.lignes.filter((l) => l.cible?.onglet === 'reglages')
    const liens = within(bloc).getAllByTestId('acal700-renseigner')
    expect(lignes.length).toBeGreaterThan(0)
    expect(liens).toHaveLength(borneHaute.cascade.a_renseigner.lignes.length)
    liens.forEach((lien, i) => {
      const [chemin, ancre] = lien.getAttribute('href').split('#')
      if (!chemin.endsWith('/calepinage/reglages')) return
      exiger(ids, ancre, borneHaute.cascade.a_renseigner.lignes[i].libelle, 'Résultat incomplet')
    })
  })

  it('norme électrique et lestage : la cible servie existe sur la page d’arrivée', async () => {
    const ids = await idsMontesDesReglages()
    exiger(ids, 'norme', 'Choisir la norme', 'Provenance')
    exiger(ids, 'lestage', 'Saisir le lestage', 'Provenance')
    const lestage = exempleContrat('calepinage', 'calepinage_masse_lestage', 'exemple_vide').lestage
    expect(lestage.manquants.length).toBeGreaterThan(0)
    for (const cle of lestage.manquants) exiger(ids, `lestage-${cle}`, 'Masse et lestage', 'Atelier')
  })

  it('tolérance PVGIS, borne haute et lien de la Bibliothèque : ancre montée aux Réglages', async () => {
    const ids = await idsMontesDesReglages()
    const borneHaute = exempleContrat('calepinage', 'calepinage_simulation', 'exemple_borne_haute')
    const { unmount } = render(<MemoryRouter>
      <EcartPvgis validation={{ ecart_pct: -2, tolerance_pct: null, verdict: null }} />
      <BandeauBorneHaute total={borneHaute.production.total} />
    </MemoryRouter>)
    const cibles = [
      ['acal854-lien-tolerance', 'Régler la tolérance', 'Provenance'],
      ['acal52-lien-reglages', 'Pertes non renseignées', 'Production'],
    ]
    for (const [testid, message, ecran] of cibles) {
      const [chemin, ancre] = screen.getByTestId(testid).getAttribute('href').split('#')
      expect(chemin).toBe('/calepinage/reglages')
      exiger(ids, ancre, message, ecran)
    }
    unmount()
    // La Bibliothèque ne demande aucune saisie : lien d'entrée vers la page (sans ancre), route des Réglages.
    expect(sourceBibliotheque).toMatch(/href="\/calepinage\/reglages"[^>]*data-testid="cal-biblio-lien-reglages"/)
  })
})

/* ACAL990 — garde de la classe K-JARGON : ce qui est RENDU (jamais le source) ne porte ni clé, ni chemin,
   ni code interne, et un même avertissement ne s'affiche qu'une fois dans l'onglet. */
describe('PanneauProduction — texte rendu (ACAL990)', () => {
  const INTERDITS = [/::/, /\.py\b/, /\[\]/, /\?\./, /MODULES_PAR_CHAINE/, /degagements\./, /CAL\d+/, /\bmartin_ruiz\b/, /\btmy\b/]

  it.each(['exemple_vide', 'exemple_perime'])('%s : chaque avertissement une seule fois, aucun jargon', async (variante) => {
    servir(variante)
    const { container } = rendre()
    await screen.findByTestId('cal236-panneau')
    const phrases = [...container.querySelectorAll('*')]
      .filter((el) => el.children.length === 0).map((el) => el.textContent.trim()).filter(Boolean)
    const servis = reponseContrat('calepinage', 'calepinage_resultat', variante).data.avertissements
    for (const avertissement of servis) {
      expect(phrases.filter((p) => p === avertissement.trim()), `affiché plusieurs fois : ${avertissement}`).toHaveLength(1)
    }
    for (const motif of INTERDITS) {
      expect(phrases.filter((p) => motif.test(p)), `texte rendu portant ${motif}`).toEqual([])
    }
  })
})

/* ACAL1905 — une réponse lente n'est pas une connexion coupée : un délai dépassé de la lecture du résultat se dit
   « Calcul en cours… » (information, pas erreur) avec « Réessayer », qui relit ; un vrai refus garde son message. */
describe('ACAL1905 — lecture lente du résultat', () => {
  it('délai dépassé : « Calcul en cours… » + « Réessayer » ; le bouton relit et le panneau s’affiche', async () => {
    calepinageApi.calepinages.resultat.mockRejectedValueOnce({ code: 'ECONNABORTED', message: 'timeout of 60000ms exceeded' })
    servir('exemple_vide')
    rendre()
    const lent = await screen.findByTestId('cal-calcul-lent')
    expect(lent).toHaveTextContent('Calcul en cours…')
    expect(screen.queryByText(/connexion a expiré/i)).toBeNull()
    expect(screen.queryByTestId('cal236-erreur')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Réessayer' }))
    await screen.findByTestId('cal236-panneau')
    expect(calepinageApi.calepinages.resultat).toHaveBeenCalledTimes(2)
  })

  it('un refus du serveur garde son message d’erreur (et le bouton « Réessayer »)', async () => {
    calepinageApi.calepinages.resultat.mockRejectedValue({ response: { status: 500, data: {} } })
    rendre()
    expect(await screen.findByTestId('cal236-erreur')).toHaveTextContent('Production indisponible.')
    expect(screen.queryByTestId('cal-calcul-lent')).toBeNull()
    expect(screen.getByRole('button', { name: 'Réessayer' })).toBeInTheDocument()
  })
})

/* ACAL1958 (T3-VAGUEC2, point 12) — le bouton de pied de l'étape Résultats : 340 × 52 comme les autres étapes quand il est
   SEUL (résultat incomplet ou avant simulation : aucune phrase de durée) ; la maquette Resultats.dc.html garde son
   330 × 104 à côté de la phrase quand le résultat est complet. Le CSS réel du module est posé dans le DOM de test. */
describe('ACAL1958 — gabarit du bouton de pied de l’étape Résultats', () => {
  const mesures = (production) => {
    render(<MemoryRouter><PiedResultats production={production} /></MemoryRouter>)
    const style = document.createElement('style')
    style.textContent = readFileSync(`${globalThis.process.cwd()}/src/styles/calepinage/54-etape-resultats.css`, 'utf8')
    document.head.appendChild(style)
    try {
      const bouton = screen.getByRole('button', { name: /Préparer les documents/ })
      const calcule = getComputedStyle(bouton)
      return { phrase: screen.getByTestId('cal-resultats-pied').querySelector('.cal-res-pied-ligne').textContent, largeur: calcule.width, hauteur: calcule.minHeight }
    } finally {
      style.remove()
    }
  }

  it('sans phrase de durée (incomplet, avant simulation) : 340 × 52, le gabarit des autres étapes', () => {
    expect(mesures(null)).toEqual({ phrase: '', largeur: '340px', hauteur: '52px' })
  })

  it('résultat complet, phrase de durée servie : la maquette Resultats garde son 330 × 104', () => {
    const complet = exempleContrat('calepinage', 'calepinage_resultat').production
    const m = mesures(complet)
    expect(m.phrase).toMatch(/^Année basse|^Dans \d+ ans/)
    expect([m.largeur, m.hauteur]).toEqual(['330px', '104px'])
  })
})
