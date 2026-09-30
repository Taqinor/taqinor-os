import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  render, screen, cleanup, waitFor, fireEvent, within,
} from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* COCKPIT-CONTRÔLE F2 — la file du jour (« À faire aujourd'hui ») suit la cadence. Charge utile =
   les exemples COMMITTÉS de `relance_etape_v2.json` (PACT10) : la liste, son
   bloc `file` (maintenant / demain / semaine / traitées aujourd'hui) et la
   variante `exemple_generique` (qui porte une TÂCHE, `est_tache: true`). Aucun
   objet retapé à la main ; les autres situations du serveur ne changent que le
   champ qui les distingue. */
import { exempleContrat } from '../../test/fixtures/contractSamples'

const V2 = exempleContrat('crm', 'relance_etape_v2')
const GENERIQUE = exempleContrat('crm', 'relance_etape_v2', 'exemple_generique')
const APPEL = V2.results[0] // contact_appel, canal appel
const MESSAGE = V2.results[1] // suivi_message, canal whatsapp
const TACHE = GENERIQUE.results.find((e) => e.est_tache) // decider_suite, canal appel
const FILE = V2.file

vi.mock('../../api/crmApi', () => ({
  default: {
    getRelanceEtapesDues: vi.fn(),
    getCadencesEchues: vi.fn(() => Promise.resolve({ data: { count: 0, results: [] } })),
    // PIÈGE : cette méthode a quitté `crmApi.js` avec le sous-bloc « leads sans
    // cadence ». Si le widget la rappelait un jour, ce mock la verrait (et
    // servirait un lead sans cadence, que le test « a disparu » refuse).
    getKpiAdherence: vi.fn(() => Promise.resolve({ data: { leads_sans_touche: [{ lead_id: 1, nom: 'X' }] } })),
    marquerRelanceEtapeFait: vi.fn(),
    marquerRelanceEtapeSautee: vi.fn(),
    reporterRelanceEtape: vi.fn(),
    getRelanceEtapeMessage: vi.fn(),
    whatsappRelanceEtape: vi.fn(),
  },
}))

import crmApi from '../../api/crmApi'
import RelancesDuJourWidget from './RelancesDuJourWidget'

/** La réponse du serveur : la liste demandée + le bloc `file` du contrat. */
const reponse = (results, file = FILE) => ({
  data: { count: results.length, results, ...(file ? { file } : {}) },
})

beforeEach(() => {
  crmApi.getRelanceEtapesDues.mockResolvedValue(reponse([APPEL, MESSAGE, TACHE]))
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

function mount() {
  return render(
    <MemoryRouter>
      <RelancesDuJourWidget />
    </MemoryRouter>,
  )
}

async function attendreListe() {
  await waitFor(() => expect(screen.getAllByTestId('relance-etape-row').length).toBeGreaterThan(0))
}

const scopeRadio = (nom) => screen.getByRole('radio', { name: nom })
const filtreRadio = (nom) => within(screen.getByRole('radiogroup', { name: 'Filtrer par type' }))
  .getByRole('radio', { name: nom })

describe('« À faire aujourd\'hui » — sélecteur et compteurs du serveur', () => {
  it('le bloc porte le titre « À faire aujourd\'hui » (plus « Ma journée ») et garde son hook de test', async () => {
    mount()
    await attendreListe()
    const widget = screen.getByTestId('relances-du-jour-widget')
    expect(within(widget).getByRole('heading', { name: 'À faire aujourd\'hui' })).toBeInTheDocument()
    expect(screen.queryByText(/Ma journée/)).not.toBeInTheDocument()
  })

  it('« Maintenant (n) · Demain (n) · 7 jours (n) » : les compteurs viennent du bloc `file`', async () => {
    mount()
    await attendreListe()
    expect(scopeRadio(`Maintenant (${FILE.maintenant})`)).toHaveAttribute('aria-checked', 'true')
    expect(scopeRadio(`Demain (${FILE.demain})`)).toBeInTheDocument()
    expect(scopeRadio(`7 jours (${FILE.semaine})`)).toBeInTheDocument()
    expect(crmApi.getRelanceEtapesDues).toHaveBeenCalledWith({ scope: 'all' })
  })

  it('un serveur qui ne sert pas `file` : les libellés restent sans compteur, jamais un nombre inventé', async () => {
    crmApi.getRelanceEtapesDues.mockResolvedValue(reponse([APPEL], null))
    mount()
    await attendreListe()
    expect(scopeRadio('Maintenant')).toBeInTheDocument()
    expect(scopeRadio('Demain')).toBeInTheDocument()
    expect(scopeRadio('7 jours')).toBeInTheDocument()
    expect(screen.queryByTestId('file-progression')).not.toBeInTheDocument()
  })

  it('« Demain (n) » interroge scope=tomorrow, « 7 jours (n) » scope=week ; les compteurs survivent au changement', async () => {
    mount()
    await attendreListe()
    // La réponse suivante ne porte plus `file` : le dernier bloc reçu reste affiché.
    crmApi.getRelanceEtapesDues.mockResolvedValue(reponse([], null))
    fireEvent.click(scopeRadio(`Demain (${FILE.demain})`))
    await waitFor(() => expect(crmApi.getRelanceEtapesDues).toHaveBeenCalledWith({ scope: 'tomorrow' }))
    await screen.findByText('Rien de prévu pour demain.')
    expect(scopeRadio(`Demain (${FILE.demain})`)).toHaveAttribute('aria-checked', 'true')
    expect(scopeRadio(`7 jours (${FILE.semaine})`)).toBeInTheDocument()
    fireEvent.click(scopeRadio(`7 jours (${FILE.semaine})`))
    await waitFor(() => expect(crmApi.getRelanceEtapesDues).toHaveBeenCalledWith({ scope: 'week' }))
    await screen.findByText('Rien de prévu dans les 7 prochains jours.')
  })

  it('l\'aide dit ce que montre le segment choisi (plus « dues aujourd\'hui ou en retard » pour les trois)', async () => {
    mount()
    await attendreListe()
    expect(screen.getByText(/tâches à traiter dès maintenant/)).toBeInTheDocument()
    fireEvent.click(scopeRadio(`Demain (${FILE.demain})`))
    await screen.findByText('Relances prévues demain.')
    expect(screen.queryByText(/dues aujourd'hui ou en retard/)).not.toBeInTheDocument()
    fireEvent.click(scopeRadio(`7 jours (${FILE.semaine})`))
    await screen.findByText('Relances prévues dans les 7 prochains jours.')
    expect(screen.queryByText(/dues aujourd'hui ou en retard/)).not.toBeInTheDocument()
  })
})

describe('« À faire aujourd\'hui » — filtres Tout / Appels / Messages / Tâches', () => {
  it('chaque filtre porte son compteur, calculé sur la liste chargée', async () => {
    mount()
    await attendreListe()
    // APPEL (canal appel), MESSAGE (whatsapp), TACHE (`est_tache`, canal appel).
    expect(filtreRadio('Tout (3)')).toHaveAttribute('aria-checked', 'true')
    expect(filtreRadio('Appels (1)')).toBeInTheDocument()
    expect(filtreRadio('Messages (1)')).toBeInTheDocument()
    expect(filtreRadio('Tâches (1)')).toBeInTheDocument()
  })

  it('une TÂCHE est comptée comme tâche, jamais comme appel, même sur le canal appel', async () => {
    expect(TACHE.est_tache).toBe(true)
    expect(TACHE.canal).toBe('appel')
    mount()
    await attendreListe()
    fireEvent.click(filtreRadio('Appels (1)'))
    expect(screen.getAllByTestId('relance-etape-row')).toHaveLength(1)
    expect(screen.getByText(APPEL.lead_nom)).toBeInTheDocument()
    expect(screen.queryByText(TACHE.lead_nom)).not.toBeInTheDocument()
  })

  it('« Messages » ne montre que les touches par écrit, « Tâches » que les tâches', async () => {
    mount()
    await attendreListe()
    fireEvent.click(filtreRadio('Messages (1)'))
    expect(screen.getAllByTestId('relance-etape-row')).toHaveLength(1)
    expect(screen.getByText(MESSAGE.lead_nom)).toBeInTheDocument()
    fireEvent.click(filtreRadio('Tâches (1)'))
    expect(screen.getAllByTestId('relance-etape-row')).toHaveLength(1)
    expect(screen.getByText(TACHE.lead_nom)).toBeInTheDocument()
    fireEvent.click(filtreRadio('Tout (3)'))
    expect(screen.getAllByTestId('relance-etape-row')).toHaveLength(3)
  })

  it('un filtre sans correspondance le dit, sans vider la file', async () => {
    crmApi.getRelanceEtapesDues.mockResolvedValue(reponse([APPEL, MESSAGE]))
    mount()
    await attendreListe()
    fireEvent.click(filtreRadio('Tâches (0)'))
    expect(screen.getByTestId('file-filtre-vide')).toHaveTextContent('Aucune tâche dans cette liste.')
    expect(screen.queryByTestId('relance-etape-row')).not.toBeInTheDocument()
    fireEvent.click(filtreRadio('Tout (2)'))
    expect(screen.getAllByTestId('relance-etape-row')).toHaveLength(2)
  })

  it('le filtre suit la liste quand une touche est traitée (compteurs recalculés sur ce qui reste)', async () => {
    crmApi.getRelanceEtapesDues.mockResolvedValue(reponse([APPEL, MESSAGE]))
    crmApi.marquerRelanceEtapeSautee.mockResolvedValue({ data: { statut: 'sautee' } })
    mount()
    await attendreListe()
    const ligne = screen.getAllByTestId('relance-etape-row')[0]
    fireEvent.click(within(ligne).getByRole('button', { name: /Sauter/ }))
    fireEvent.click(within(ligne).getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(filtreRadio('Tout (1)')).toBeInTheDocument())
    expect(filtreRadio('Appels (0)')).toBeInTheDocument()
    expect(filtreRadio('Messages (1)')).toBeInTheDocument()
  })

  it('aucun filtre quand la file est vide', async () => {
    crmApi.getRelanceEtapesDues.mockResolvedValue(reponse([]))
    mount()
    await screen.findByTestId('file-vide')
    expect(screen.queryByRole('radiogroup', { name: 'Filtrer par type' })).not.toBeInTheDocument()
  })
})

describe('« À faire aujourd\'hui » — progression sobre', () => {
  it('« 8 traitées aujourd\'hui · 6 restantes » + une barre fine, depuis `file`', async () => {
    mount()
    await attendreListe()
    const progression = screen.getByTestId('file-progression')
    expect(progression).toHaveTextContent(
      `${FILE.traitees_aujourdhui} traitées aujourd'hui · ${FILE.maintenant} restantes`)
    const barre = within(progression).getByRole('progressbar', { name: 'Avancement de la journée' })
    const total = FILE.traitees_aujourdhui + FILE.maintenant
    expect(Number(barre.getAttribute('aria-valuenow')))
      .toBe(Math.round((FILE.traitees_aujourdhui / total) * 100))
  })

  it('accord au singulier (« 1 traitée · 1 restante »)', async () => {
    crmApi.getRelanceEtapesDues.mockResolvedValue(reponse(
      [APPEL], { ...FILE, traitees_aujourdhui: 1, maintenant: 1 }))
    mount()
    await attendreListe()
    expect(screen.getByTestId('file-progression'))
      .toHaveTextContent('1 traitée aujourd\'hui · 1 restante')
  })

  it('rien du tout quand les deux valent 0', async () => {
    crmApi.getRelanceEtapesDues.mockResolvedValue(reponse(
      [APPEL], { ...FILE, traitees_aujourdhui: 0, maintenant: 0 }))
    mount()
    await attendreListe()
    expect(screen.queryByTestId('file-progression')).not.toBeInTheDocument()
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
  })

  it('journée à zéro traitée : la ligne reste, la barre est vide', async () => {
    crmApi.getRelanceEtapesDues.mockResolvedValue(reponse(
      [APPEL], { ...FILE, traitees_aujourdhui: 0, maintenant: 5 }))
    mount()
    await attendreListe()
    const progression = screen.getByTestId('file-progression')
    expect(progression).toHaveTextContent('0 traitée aujourd\'hui · 5 restantes')
    expect(within(progression).getByRole('progressbar')).toHaveAttribute('aria-valuenow', '0')
  })
})

describe('« À faire aujourd\'hui » — état vide utile', () => {
  it('« Tout est traité pour maintenant. » + « Voir demain (n) » quand demain a des touches', async () => {
    crmApi.getRelanceEtapesDues.mockResolvedValue(reponse([]))
    mount()
    const vide = await screen.findByTestId('file-vide')
    expect(vide).toHaveTextContent('Tout est traité pour maintenant.')
    const bouton = within(vide).getByRole('button', { name: `Voir demain (${FILE.demain})` })
    crmApi.getRelanceEtapesDues.mockResolvedValue(reponse([APPEL], FILE))
    fireEvent.click(bouton)
    await waitFor(() => expect(crmApi.getRelanceEtapesDues).toHaveBeenCalledWith({ scope: 'tomorrow' }))
    expect(scopeRadio(`Demain (${FILE.demain})`)).toHaveAttribute('aria-checked', 'true')
    await attendreListe()
  })

  it('pas de bouton quand rien n\'est prévu demain (`file.demain` = 0)', async () => {
    crmApi.getRelanceEtapesDues.mockResolvedValue(reponse([], { ...FILE, demain: 0 }))
    mount()
    const vide = await screen.findByTestId('file-vide')
    expect(vide).toHaveTextContent('Tout est traité pour maintenant.')
    expect(within(vide).queryByRole('button')).not.toBeInTheDocument()
  })

  it('sans bloc `file` (ancien serveur) : le message reste, sans bouton', async () => {
    crmApi.getRelanceEtapesDues.mockResolvedValue(reponse([], null))
    mount()
    const vide = await screen.findByTestId('file-vide')
    expect(vide).toHaveTextContent('Tout est traité pour maintenant.')
    expect(within(vide).queryByRole('button')).not.toBeInTheDocument()
  })
})

describe('« À faire aujourd\'hui » — le sous-bloc « leads sans cadence » a disparu', () => {
  it('plus de compteur cliquable, et `getKpiAdherence` n\'est plus appelé', async () => {
    mount()
    await attendreListe()
    expect(screen.queryByTestId('cad117-sans-cadence')).not.toBeInTheDocument()
    expect(screen.queryByText(/sans cadence/)).not.toBeInTheDocument()
    expect(crmApi.getKpiAdherence).not.toHaveBeenCalled()
  })

  it('« cadences échues à clore » reste', async () => {
    crmApi.getCadencesEchues.mockResolvedValue({
      data: { count: 1, results: [{ etape_id: 9, lead_id: 5, lead: 'Dossier X', ville: '', libelle: 'Dernier essai', jours_de_retard: 9 }] },
    })
    mount()
    await attendreListe()
    expect(await screen.findByTestId('cad99-cadences-echues')).toBeInTheDocument()
    expect(screen.getByText('1 cadence échue à clore')).toBeInTheDocument()
  })
})
