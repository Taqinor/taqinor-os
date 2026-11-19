import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { ReactReduxContext } from 'react-redux'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'
import { reinitialiserGestes } from '../../features/taches/lib/gestes'
import { ecrireProjetsCache } from '../../features/taches/horsligne/cacheProjets'
import { ZoneAnnonces } from '../../features/taches/coquille/CoquilleTaches'
import { poserRectangles } from '../../features/taches/projets/rectanglesDeTest'

vi.mock('../../api/tachesApi', async (original) => ({
  ...(await original()),
  lireVueProjet: vi.fn(),
  creerTache: vi.fn(),
  modifierProjet: vi.fn(),
  terminerTache: vi.fn(),
  rouvrirTache: vi.fn(),
  supprimerTache: vi.fn(),
  restaurerTache: vi.fn(),
  traiterLot: vi.fn(),
  planifierTache: vi.fn(),
  listerTousLesProjets: vi.fn(),
  annulerGeste: vi.fn(),
  attendreTache: vi.fn(),
  listerToutesLesTaches: vi.fn(),
  modifierTache: vi.fn(),
  supprimerProjet: vi.fn(),
  creerProjet: vi.fn(),
  lireTache: vi.fn(),
  listerProjets: vi.fn(),
  reordonnerProjet: vi.fn(),
  reordonnerTache: vi.fn(),
}))

const api = await import('../../api/tachesApi')
const { default: Projet } = await import('./Projet')

/* TCH89 — l'écran rend `projet_vue.json` : en-tête (priorité, avancement, jalon, santé, Détails), étapes,
   « Sans étape », « Faites (n) ». Cocher et ajouter se font sur place, sans relire la vue. */

const monter = (chemin = '/taches/projets/3') => render(
  <MemoryRouter initialEntries={[chemin]}>
    <Routes>
      <Route path="/taches/projets/:id" element={<Projet />} />
      <Route path="/taches/projets" element={<div className="tch"><p>Liste des projets</p><ZoneAnnonces /></div>} />
    </Routes>
  </MemoryRouter>,
)
const tacheEcrite = () => structuredClone(exempleContrat('taches', 'tache_ecrite'))

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date('2026-11-17T09:00:00'))
  reinitialiserGestes()
  api.lireVueProjet.mockResolvedValue(reponseContrat('taches', 'projet_vue'))
  api.listerTousLesProjets.mockResolvedValue([]) // la feuille de saisie lit la liste des projets à son ouverture
})
afterEach(() => { vi.useRealTimers(); vi.clearAllMocks(); reinitialiserGestes() })

describe('TCH89 — Un projet : en-tête', () => {
  it('avancement, échéance, jalon, santé et priorité viennent de la vue', async () => {
    monter()
    expect(await screen.findByText('12 sur 20')).toBeInTheDocument()
    // passe visuelle n° 40 : l'échéance a son mois, comme dans la liste (« mar. 15 déc. », jamais « 15/12 »)
    expect(screen.getByText('échéance mar. 15 déc.')).toBeInTheDocument()
    expect(screen.getByText("Prochain jalon : Devis Settat · aujourd'hui")).toBeInTheDocument()
    expect(screen.getByText('Rien de fait depuis 10 jours travaillés.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Priorité haute, changer' })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: '12 sur 20' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Ventes')
    expect(api.lireVueProjet).toHaveBeenCalledWith('3', { vue: 'liste' })
  })

  it('Détails montre « Fini quand… » et « dernière faite le 03/11 »', async () => {
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    // passe visuelle n° 43 : le repli s'intitule « Fini quand… » (projet-liste.html), plus « Détails »
    await user.click(await screen.findByRole('button', { name: 'Fini quand…' }))
    expect(screen.queryByRole('button', { name: 'Détails' })).toBeNull()
    expect(screen.getByText('Fini quand les 4 devis sont signés')).toBeInTheDocument()
    expect(screen.getByText('dernière faite le 03/11')).toBeInTheDocument()
  })

  it('passe visuelle n° 43 — point de couleur devant le nom ; échéance menacée (d) : « À ce rythme : … » en une ligne, le détail au toucher', async () => {
    const vue = exempleContrat('taches', 'projet_vue')
    // la phrase SERVIE (R3-011) : la conséquence, puis UN chiffre déjà soustrait
    const longue = 'À ce rythme, pas prêt pour le mar. 8 déc. : il manque environ 2 jours.'
    vue.projet.sante = [{ code: 'echeance_menacee', phrase: longue, donnees: { besoin: 10, reste: 8, f28: 12, j28: 20, signal: 'd', echeance: '2026-12-08' } }]
    api.lireVueProjet.mockResolvedValue({ data: vue })
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    const sante = await screen.findByRole('button', { name: 'À ce rythme, pas prêt pour le mar. 8 déc.' })
    const titre = screen.getByRole('heading', { level: 1 })
    expect(titre.querySelector('.ep-projet-nom[data-p="vert"] > .point')).not.toBeNull()
    expect(screen.queryByText(longue)).toBeNull()
    await user.click(sante)
    expect(sante).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText(longue)).toBeInTheDocument()
  })

  it("R2-034 — échéance servie : la santé courte dit la conséquence « À ce rythme, pas prêt pour le jeu. 26 »", async () => {
    const vue = exempleContrat('taches', 'projet_vue')
    const longue = 'À ce rythme, pas prêt pour le jeu. 26 : il manque environ 2 jours.'
    vue.projet.sante = [{ code: 'echeance_menacee', phrase: longue, donnees: { besoin: 10, reste: 8, f28: 12, j28: 20, signal: 'd', echeance: '2026-11-26' } }]
    api.lireVueProjet.mockResolvedValue({ data: vue })
    const { unmount } = monter()
    expect(await screen.findByRole('button', { name: 'À ce rythme, pas prêt pour le jeu. 26' })).toBeInTheDocument()
    unmount()
    vue.projet.sante[0].donnees.echeance = '2026-11-18'
    api.lireVueProjet.mockResolvedValue({ data: structuredClone(vue) })
    monter()
    expect(await screen.findByRole('button', { name: 'À ce rythme, pas prêt pour demain' })).toBeInTheDocument()
  })

  it('pas de signal de santé : aucune ligne de santé', async () => {
    const vue = exempleContrat('taches', 'projet_vue')
    vue.projet.sante = []
    api.lireVueProjet.mockResolvedValue({ data: vue })
    monter()
    await screen.findByText('12 sur 20')
    expect(screen.queryByText(/Rien de fait depuis/)).toBeNull()
  })

  it('un projet qui n\'existe plus est dit, sans écran vide muet', async () => {
    api.lireVueProjet.mockRejectedValue({ response: { status: 404, data: { detail: 'Introuvable.' } } })
    monter('/taches/projets/99')
    expect(await screen.findByRole('alert')).toHaveTextContent('Ce projet n\'existe plus.')
  })
})

describe('TCH89 — Un projet : étapes', () => {
  it('étape, « Sans étape » et « Faites (12) » dans l\'ordre du serveur', async () => {
    monter()
    const etape = await screen.findByRole('region', { name: 'Études' })
    expect(within(etape).getByRole('button', { name: 'Devis Settat' })).toBeInTheDocument()
    const sans = screen.getByRole('region', { name: 'Sans étape' })
    expect(within(sans).getByRole('button', { name: 'Timbres' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Faites/ })).toHaveTextContent('12')
  })

  it('cocher met la ligne et l\'avancement à jour sur place ; Annuler la rouvre', async () => {
    const faite = tacheEcrite()
    faite.tache.statut = 'fait'
    api.terminerTache.mockResolvedValue({ data: faite })
    const rouverte = tacheEcrite()
    api.rouvrirTache.mockResolvedValue({ data: rouverte })
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    const etape = await screen.findByRole('region', { name: 'Études' })
    await user.click(within(etape).getByRole('checkbox', { name: /Marquer « Devis Settat »/ }))
    expect(api.terminerTache).toHaveBeenCalledWith(20)
    expect(await screen.findByText('13 sur 20')).toBeInTheDocument()
    expect(api.lireVueProjet).toHaveBeenCalledTimes(1)

    await user.click(screen.getByRole('button', { name: 'Annuler' }))
    expect(api.rouvrirTache).toHaveBeenCalledWith(20)
    expect(await screen.findByText('12 sur 20')).toBeInTheDocument()
  })

  it('un échec réseau remet la case et l\'avancement comme avant', async () => {
    api.terminerTache.mockRejectedValue(new Error('Network Error'))
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    const etape = await screen.findByRole('region', { name: 'Études' })
    const case_ = within(etape).getByRole('checkbox', { name: /Marquer « Devis Settat »/ })
    await user.click(case_)
    await waitFor(() => expect(case_).not.toBeChecked())
    expect(screen.getByText('12 sur 20')).toBeInTheDocument()
  })
})

describe('Raccord F2 — Un projet : chiffres servis seulement', () => {
  it('compteurs servis par le contrat : « 4 sur 5 » (Études), « 8 sur 15 » (Sans étape) ; sans compteurs, aucun « n sur m »', async () => {
    const { unmount } = monter()
    const etape = await screen.findByRole('region', { name: 'Études' })
    expect(within(etape).getByText('4 sur 5')).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Sans étape' })).getByText('8 sur 15')).toBeInTheDocument()
    unmount()
    const vue = exempleContrat('taches', 'projet_vue')
    vue.sections.forEach((s) => { delete s.compteurs })
    delete vue.sans_section_compteurs
    api.lireVueProjet.mockResolvedValue({ data: vue })
    monter()
    const nue = await screen.findByRole('region', { name: 'Études' })
    expect(within(nue).queryByText(/ sur /)).toBeNull()
    expect(screen.getByRole('button', { name: /^Faites/ })).toHaveTextContent('12')
  })

  it('servis par le serveur : « {faites} sur {total} » par étape (`compteurs`) ; « Faites (n) » déplié lit les faites', async () => {
    const vue = exempleContrat('taches', 'projet_vue')
    vue.sections[0].compteurs = { ouvertes: 3, faites: 2 }
    vue.sans_section_compteurs = { ouvertes: 1, faites: 4 }
    api.lireVueProjet.mockResolvedValue({ data: vue })
    api.listerToutesLesTaches.mockResolvedValue([{ ...vue.sections[0].taches[0], id: 99, titre: 'Dossier signé', statut: 'fait' }])
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    const etape = await screen.findByRole('region', { name: 'Études' })
    expect(within(etape).getByText('2 sur 5')).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Sans étape' })).getByText('4 sur 5')).toBeInTheDocument()
    expect(api.listerToutesLesTaches).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: /^Faites/ }))
    expect(api.listerToutesLesTaches).toHaveBeenCalledWith({ projet: 3, statut: 'fait', tri: 'fait_le' })
    expect(await screen.findByRole('button', { name: 'Dossier signé' })).toBeInTheDocument()
  })
})

describe('TCH89 — Un projet : ajouter une tâche', () => {
  it('Raccord F2 — « Ajouter une tâche » d\'une étape ouvre LA feuille de saisie avec ce projet et cette étape', async () => {
    const ouverture = vi.fn()
    window.addEventListener('taqinor:taches:saisir', ouverture)
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    const etape = await screen.findByRole('region', { name: 'Études' })
    await user.click(within(etape).getByRole('button', { name: 'Ajouter une tâche' }))
    expect(ouverture).toHaveBeenCalledTimes(1)
    expect(ouverture.mock.calls[0][0].detail).toEqual({ projet_id: 3, projet_nom: 'Ventes', section_id: 8 })
    expect(await screen.findByRole('dialog', { name: 'Ajouter une tâche' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retirer « Ventes »' })).toBeInTheDocument()
    window.removeEventListener('taqinor:taches:saisir', ouverture)
  })

  it('« + » touché AVANT que la vue du projet soit lue : la saisie s\'ouvre quand même dans ce projet (id de l\'adresse)', async () => {
    // Constaté en acceptation (réseau lent) : le « + » ouvrait la saisie SANS projet, la tâche partait dans À trier.
    api.lireVueProjet.mockReturnValue(new Promise(() => {})) // la vue n'arrive pas encore
    const ouverture = vi.fn()
    window.addEventListener('taqinor:taches:saisir', ouverture)
    monter('/taches/projets/3')
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    await user.click(screen.getAllByRole('button', { name: 'Ajouter une tâche' })[0])
    expect(ouverture).toHaveBeenCalledTimes(1)
    expect(ouverture.mock.calls[0][0].detail).toEqual({ projet_id: 3 })
    window.removeEventListener('taqinor:taches:saisir', ouverture)
  })

  it('Raccord F2 — après une création (`taqinor:taches:creees`), la vue se relit une fois, sans recharger la page', async () => {
    monter()
    await screen.findByRole('region', { name: 'Études' })
    expect(api.lireVueProjet).toHaveBeenCalledTimes(1)
    window.dispatchEvent(new CustomEvent('taqinor:taches:creees', { detail: { creees: [] } }))
    await waitFor(() => expect(api.lireVueProjet).toHaveBeenCalledTimes(2))
  })
})

describe('TCH89 — Un projet : priorité', () => {
  it('la puce de l\'en-tête change la priorité avec le lock_version de la vue', async () => {
    const vue = exempleContrat('taches', 'projet_vue')
    api.modifierProjet.mockResolvedValue({ data: { ...vue.projet, priorite: 2, lock_version: 5 } })
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    await user.click(await screen.findByRole('button', { name: 'Priorité haute, changer' }))
    await user.click(await screen.findByRole('menuitem', { name: 'Moyenne' }))
    expect(api.modifierProjet).toHaveBeenCalledWith(3, { priorite: 2, lock_version: 4 })
    expect(await screen.findByRole('button', { name: 'Priorité moyenne, changer' })).toBeInTheDocument()
  })

  it('⋯ → Mettre en pause met le projet en pause, avec Annuler', async () => {
    const vue = exempleContrat('taches', 'projet_vue')
    api.modifierProjet.mockResolvedValueOnce({ data: { ...vue.projet, statut: 'en_pause', lock_version: 5 } })
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    await screen.findByText('12 sur 20')
    await user.click(screen.getByRole('button', { name: "Plus d'actions" }))
    await user.click(await screen.findByRole('menuitem', { name: 'Mettre en pause' }))
    expect(api.modifierProjet).toHaveBeenCalledWith(3, { statut: 'en_pause', lock_version: 4 })
    expect(await screen.findByText('En pause')).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Geste effectué' })).toHaveTextContent('« Ventes » en pause')
  })
})

describe('R2-071 — Un projet vide : l\'invite', () => {
  it('sans aucune tâche : « Ajoute la première tâche » et « Planifier le projet » ; l\'invite ouvre la saisie du projet', async () => {
    const vue = exempleContrat('taches', 'projet_vue')
    vue.sections.forEach((s) => { s.taches = [] })
    vue.sans_section = []
    vue.faites_nb = 0
    vue.avancement = { ...vue.avancement, faites: 0, total: 0 }
    vue.projet.compteurs = { ouvertes: 0, faites: 0 }
    api.lireVueProjet.mockResolvedValue({ data: vue })
    const ouverture = vi.fn()
    window.addEventListener('taqinor:taches:saisir', ouverture)
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    const invite = await screen.findByRole('region', { name: 'Projet vide' })
    expect(invite).toHaveTextContent('Ajoute la première tâche')
    await user.click(within(invite).getByRole('button', { name: 'Ajoute la première tâche' }))
    expect(ouverture.mock.calls[0][0].detail).toEqual({ projet_id: 3, projet_nom: 'Ventes', section_id: null })
    await user.click(within(invite).getByRole('button', { name: 'Planifier le projet' }))
    expect(await screen.findByRole('region', { name: 'Planifier le projet' })).toBeInTheDocument()
    window.removeEventListener('taqinor:taches:saisir', ouverture)
  })

  it('R3-139 — sans aucune tâche : ni « 0 sur 0 » ni barre d\'avancement vide au-dessus de l\'invite', async () => {
    const vue = exempleContrat('taches', 'projet_vue')
    vue.sections.forEach((s) => { s.taches = [] })
    vue.sans_section = []
    vue.faites_nb = 0
    vue.avancement = { ...vue.avancement, faites: 0, total: 0 }
    vue.projet.compteurs = { ouvertes: 0, faites: 0 }
    api.lireVueProjet.mockResolvedValue({ data: vue })
    const { container } = monter()
    await screen.findByRole('region', { name: 'Projet vide' })
    expect(screen.queryByText(/0 sur 0/)).toBeNull()
    expect(container.querySelector('.ep-barre-avance')).toBeNull()
    expect(container.querySelector('.ep-avance')).toBeNull()
    // le reste de la ligne (priorité, vues) est là
    expect(screen.getByRole('button', { name: 'Priorité haute, changer' })).toBeInTheDocument()
  })

  it('R3-127 — une étape VIDE garde « Ajouter une tâche » visible en permanence (sa seule invite) ; les étapes à tâches le montrent au survol', async () => {
    const vue = exempleContrat('taches', 'projet_vue')
    vue.sections.push({ ...vue.sections[0], id: 99, nom: 'Démarches', taches: [], compteurs: { ouvertes: 0, faites: 0 } })
    api.lireVueProjet.mockResolvedValue({ data: vue })
    monter()
    await screen.findByText('12 sur 20')
    expect(screen.getByRole('region', { name: 'Démarches' })).toHaveClass('etape-vide')
    expect(screen.getByRole('region', { name: vue.sections[0].nom })).not.toHaveClass('etape-vide')
  })

  it('un projet qui a des tâches ne montre pas l\'invite', async () => {
    monter()
    await screen.findByText('12 sur 20')
    expect(screen.queryByRole('region', { name: 'Projet vide' })).toBeNull()
  })
})

describe('R2-070 — Un projet : sans réseau, la dernière vue lue', () => {
  const connecte = (id) => ({ getState: () => ({ auth: { user: { id, active_company_id: 7 } } }) })
  const monterConnecte = (id = 42) => render(
    <ReactReduxContext.Provider value={{ store: connecte(id) }}>
      <MemoryRouter initialEntries={['/taches/projets/3']}>
        <Routes><Route path="/taches/projets/:id" element={<Projet />} /></Routes>
      </MemoryRouter>
    </ReactReduxContext.Provider>,
  )
  beforeEach(() => { window.localStorage.clear() })
  afterEach(() => { window.localStorage.clear() })

  it('relu sans réseau, le projet gardé s\'affiche (l\'erreur est dite) ; un autre compte ne le voit pas', async () => {
    const premier = monterConnecte(42)
    await screen.findByText('12 sur 20')
    premier.unmount()
    api.lireVueProjet.mockRejectedValue(new Error('Network Error'))
    const hors = monterConnecte(42)
    expect(await screen.findByText('12 sur 20')).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Études' })).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('Connexion perdue')
    hors.unmount()
    monterConnecte(43)
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.queryByText('12 sur 20')).toBeNull()
  })
})

describe('R3-136 — Un projet jamais ouvert, sans réseau : son NOM en titre (lu dans la liste gardée), pas « Projet » et une page muette', () => {
  const connecte = { getState: () => ({ auth: { user: { id: 42, active_company_id: 7 } } }) }
  const monterHorsLigne = () => render(
    <ReactReduxContext.Provider value={{ store: connecte }}>
      <MemoryRouter initialEntries={['/taches/projets/3']}>
        <Routes><Route path="/taches/projets/:id" element={<Projet />} /></Routes>
      </MemoryRouter>
    </ReactReduxContext.Provider>,
  )
  let enLigne
  beforeEach(() => {
    window.localStorage.clear()
    enLigne = vi.spyOn(window.navigator, 'onLine', 'get').mockReturnValue(false)
    api.lireVueProjet.mockRejectedValue(new Error('Network Error'))
  })
  afterEach(() => { enLigne.mockRestore(); window.localStorage.clear() })

  it('le titre est le nom du projet gardé dans la liste ; la page dit ce qui va se passer, sans promettre de saisies', async () => {
    ecrireProjetsCache(42, 'liste', { actifs: [{ id: 3, nom: 'Chantier Benali 9 kWc', couleur: 'terre' }], enPause: [], constat: null })
    monterHorsLigne()
    expect(await screen.findByRole('alert')).toHaveTextContent("Ses tâches s'afficheront au retour du réseau.")
    expect(screen.getByRole('alert')).not.toHaveTextContent('saisies')
    const titre = screen.getByRole('heading', { level: 1 })
    expect(titre).toHaveTextContent('Chantier Benali 9 kWc')
    expect(titre.querySelector('.ep-projet-nom')).toHaveAttribute('data-p', 'terre')
  })

  it('un projet absent de la liste gardée garde le titre « Projet » (jamais un nom inventé)', async () => {
    monterHorsLigne()
    expect(await screen.findByRole('alert')).toHaveTextContent("Ses tâches s'afficheront au retour du réseau.")
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/^Projet$/)
  })
})

describe('R2-060 — Un projet : « Mettre en haut » dans le ⋯ de l\'écran', () => {
  it('⋯ → Mettre en haut place le projet avant le premier projet actif DE SA PRIORITÉ (R3-129 : la liste est groupée)', async () => {
    // « Ventes » est de priorité haute (3) : le projet 9, de priorité basse, est en tête de la liste mais pas de son groupe
    api.listerTousLesProjets.mockResolvedValue([
      { id: 9, nom: 'Admin', priorite: 1 }, { id: 7, nom: 'Chantier', priorite: 3 }, { id: 3, nom: 'Ventes', priorite: 3 },
    ])
    api.reordonnerProjet.mockResolvedValue({ data: {} })
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    await screen.findByText('12 sur 20')
    await user.click(screen.getByRole('button', { name: "Plus d'actions" }))
    await user.click(await screen.findByRole('menuitem', { name: 'Mettre en haut' }))
    await waitFor(() => expect(api.reordonnerProjet).toHaveBeenCalledWith(3, { avant_id: 7 }))
    expect(api.listerTousLesProjets).toHaveBeenCalledWith({ statut: 'actif' })
  })

  it('déjà premier : rien n\'est écrit', async () => {
    api.listerTousLesProjets.mockResolvedValue([{ id: 3, nom: 'Ventes', priorite: 3 }])
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    await screen.findByText('12 sur 20')
    await user.click(screen.getByRole('button', { name: "Plus d'actions" }))
    await user.click(await screen.findByRole('menuitem', { name: 'Mettre en haut' }))
    await waitFor(() => expect(api.listerTousLesProjets).toHaveBeenCalledWith({ statut: 'actif' }))
    expect(api.reordonnerProjet).not.toHaveBeenCalled()
  })
})

describe('R2-061 — Un projet : renommer, couleur, échéance, « Fini quand… »', () => {
  const envoye = (champs) => ({ data: { ...exempleContrat('taches', 'projet_vue').projet, lock_version: 5, ...champs } })
  const ouvrirMenu = async (user, libelle) => {
    await user.click(screen.getByRole('button', { name: "Plus d'actions" }))
    await user.click(await screen.findByRole('menuitem', { name: libelle }))
  }

  it('toucher le titre le rend éditable ; Entrée enregistre le nom (lock_version de la vue) et le titre suit', async () => {
    api.modifierProjet.mockResolvedValue(envoye({ nom: 'Ventes Maroc' }))
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    await user.click(await screen.findByRole('button', { name: 'Renommer « Ventes »' }))
    const champ = screen.getByRole('textbox', { name: 'Nom du projet' })
    await user.clear(champ)
    await user.type(champ, 'Ventes Maroc{Enter}')
    expect(api.modifierProjet).toHaveBeenCalledWith(3, { nom: 'Ventes Maroc', lock_version: 4 }, { erreurSousLeChamp: true })
    expect(await screen.findByRole('button', { name: 'Renommer « Ventes Maroc »' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Geste effectué' })).toHaveTextContent('Projet renommé')
  })

  it('Échap annule : rien n\'est écrit, l\'ancien nom reste', async () => {
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    await user.click(await screen.findByRole('button', { name: 'Renommer « Ventes »' }))
    await user.type(screen.getByRole('textbox', { name: 'Nom du projet' }), ' X{Escape}')
    expect(api.modifierProjet).not.toHaveBeenCalled()
    expect(await screen.findByRole('button', { name: 'Renommer « Ventes »' })).toBeInTheDocument()
  })

  it('un nom refusé (déjà pris) s\'affiche SOUS le champ, le texte tapé reste et le titre garde l\'ancien nom', async () => {
    api.modifierProjet.mockRejectedValue(Object.assign(new Error('409'), {
      response: { status: 400, statutServeur: 409, headers: {}, data: { nom: ['Un projet actif porte déjà ce nom.'], detail: 'Un projet actif porte déjà ce nom.', code: 'state_conflict' } },
    }))
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    await user.click(await screen.findByRole('button', { name: 'Renommer « Ventes »' }))
    const champ = screen.getByRole('textbox', { name: 'Nom du projet' })
    await user.clear(champ)
    await user.type(champ, 'Chantier{Enter}')
    expect(await screen.findByRole('alert')).toHaveTextContent('Un projet actif porte déjà ce nom.')
    expect(screen.getByRole('textbox', { name: 'Nom du projet' })).toHaveValue('Chantier')
    expect(screen.getByRole('textbox', { name: 'Nom du projet' })).toHaveAttribute('aria-invalid', 'true')
  })

  it('⋯ → Renommer : une feuille avec le nom ; Enregistrer l\'écrit, un refus s\'affiche sous le champ', async () => {
    api.modifierProjet.mockRejectedValueOnce(Object.assign(new Error('409'), {
      response: { status: 400, statutServeur: 409, headers: {}, data: { nom: ['Un projet actif porte déjà ce nom.'], detail: 'Un projet actif porte déjà ce nom.', code: 'state_conflict' } },
    }))
    api.modifierProjet.mockResolvedValueOnce(envoye({ nom: 'Ventes 2027' }))
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    await screen.findByText('12 sur 20')
    await ouvrirMenu(user, 'Renommer')
    const dialogue = await screen.findByRole('dialog', { name: 'Renommer' })
    const champ = within(dialogue).getByLabelText('Nom du projet')
    expect(champ).toHaveValue('Ventes')
    await user.clear(champ)
    await user.type(champ, 'Ventes 2027')
    await user.click(within(dialogue).getByRole('button', { name: 'Enregistrer' }))
    expect(await within(dialogue).findByRole('alert')).toHaveTextContent('Un projet actif porte déjà ce nom.')
    expect(champ).toHaveAttribute('aria-invalid', 'true')
    await user.click(within(dialogue).getByRole('button', { name: 'Enregistrer' }))
    expect(api.modifierProjet).toHaveBeenLastCalledWith(3, { nom: 'Ventes 2027', lock_version: 4 }, { erreurSousLeChamp: true })
    expect(await screen.findByRole('button', { name: 'Renommer « Ventes 2027 »' })).toBeInTheDocument()
  })

  it('⋯ → Couleur… : dix couleurs ; en choisir une l\'écrit et change le point du titre', async () => {
    api.modifierProjet.mockResolvedValue(envoye({ couleur: 'bleu' }))
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    await screen.findByText('12 sur 20')
    await ouvrirMenu(user, 'Couleur…')
    const groupe = await screen.findByRole('radiogroup', { name: 'Couleur du projet' })
    expect(within(groupe).getAllByRole('radio')).toHaveLength(10)
    expect(within(groupe).getByRole('radio', { name: 'Vert' })).toBeChecked()
    await user.click(within(groupe).getByRole('radio', { name: 'Bleu' }))
    expect(api.modifierProjet).toHaveBeenCalledWith(3, { couleur: 'bleu', lock_version: 4 }, { erreurSousLeChamp: true })
    await waitFor(() => expect(screen.getByRole('heading', { level: 1 }).querySelector('.ep-projet-nom')).toHaveAttribute('data-p', 'bleu'))
  })

  it('⋯ → Échéance… : une date enregistrée ; Retirer l\'échéance écrit null', async () => {
    api.modifierProjet.mockResolvedValueOnce(envoye({ echeance: '2026-12-31' }))
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    await screen.findByText('12 sur 20')
    await ouvrirMenu(user, 'Échéance…')
    const dialogue = await screen.findByRole('dialog', { name: 'Échéance' })
    fireEvent.change(within(dialogue).getByLabelText('Échéance du projet'), { target: { value: '2026-12-31' } })
    await user.click(within(dialogue).getByRole('button', { name: 'Enregistrer' }))
    expect(api.modifierProjet).toHaveBeenCalledWith(3, { echeance: '2026-12-31', lock_version: 4 }, { erreurSousLeChamp: true })
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Échéance' })).toBeNull())
    expect(await screen.findByText('échéance jeu. 31 déc.')).toBeInTheDocument()

    api.modifierProjet.mockResolvedValueOnce(envoye({ echeance: null, lock_version: 6 }))
    await ouvrirMenu(user, 'Échéance…')
    await user.click(await screen.findByRole('button', { name: "Retirer l'échéance" }))
    expect(api.modifierProjet).toHaveBeenLastCalledWith(3, { echeance: null, lock_version: 5 }, { erreurSousLeChamp: true })
  })

  it('« Fini quand… » se corrige sur place : le texte devient un champ, la sortie enregistre l\'objectif', async () => {
    api.modifierProjet.mockResolvedValue(envoye({ objectif: 'les 5 devis sont signés' }))
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    await user.click(await screen.findByRole('button', { name: 'Fini quand…' }))
    await user.click(screen.getByRole('button', { name: 'Modifier « Fini quand… »' }))
    const champ = screen.getByRole('textbox', { name: 'Fini quand…' })
    await user.clear(champ)
    await user.type(champ, 'les 5 devis sont signés')
    await user.tab()
    expect(api.modifierProjet).toHaveBeenCalledWith(3, { objectif: 'les 5 devis sont signés', lock_version: 4 }, { erreurSousLeChamp: true })
    expect(await screen.findByText('Fini quand : les 5 devis sont signés')).toBeInTheDocument()
  })
})

describe('R2-063 — Un projet : l\'ordre des tâches d\'une étape (liste et tableau)', () => {
  // trois tâches dans « Études » : A (20), B (21), C (22)
  const vueTrois = () => {
    const vue = exempleContrat('taches', 'projet_vue')
    const base = vue.sections[0].taches[0]
    vue.sections[0].taches = [
      { ...base, id: 20, titre: 'Devis Settat' },
      { ...base, id: 21, titre: 'Préparer le matériel' },
      { ...base, id: 22, titre: 'Appeler le client' },
    ]
    return vue
  }
  const ordre = () => [...screen.getByRole('region', { name: 'Études' }).querySelectorAll('.ligne-corps-bouton')].map((b) => b.textContent)
  const reorganiser = async (user) => {
    await user.click(screen.getByRole('button', { name: "Plus d'actions" }))
    await user.click(await screen.findByRole('menuitem', { name: 'Réorganiser' }))
  }
  beforeEach(() => {
    api.lireVueProjet.mockResolvedValue({ data: vueTrois() })
    api.reordonnerTache.mockResolvedValue({ data: {} })
  })

  it('⋯ → Réorganiser : « Descendre » change l\'ordre TOUT DE SUITE et écrit avec les deux voisines', async () => {
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    await screen.findByRole('region', { name: 'Études' })
    await reorganiser(user)
    await user.click(screen.getByRole('button', { name: 'Descendre « Devis Settat »' }))
    expect(ordre()).toEqual(['Préparer le matériel', 'Devis Settat', 'Appeler le client'])
    expect(api.reordonnerTache).toHaveBeenCalledWith(20, { liste: 'projet', avant_id: 21, apres_id: 22 })
    expect(api.lireVueProjet).toHaveBeenCalledTimes(1)
    expect(await screen.findByRole('group', { name: 'Geste effectué' })).toHaveTextContent('Ordre changé')
  })

  it('« Monter » de la première et « Descendre » de la dernière sont éteints', async () => {
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    await screen.findByRole('region', { name: 'Études' })
    await reorganiser(user)
    expect(screen.getByRole('button', { name: 'Monter « Devis Settat »' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Descendre « Appeler le client »' })).toBeDisabled()
  })

  it('Annuler remet les voisines d\'avant ; un refus du serveur remet l\'ordre et le dit', async () => {
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    await screen.findByRole('region', { name: 'Études' })
    await reorganiser(user)
    await user.click(screen.getByRole('button', { name: 'Monter « Appeler le client »' }))
    expect(ordre()).toEqual(['Devis Settat', 'Appeler le client', 'Préparer le matériel'])
    expect(api.reordonnerTache).toHaveBeenLastCalledWith(22, { liste: 'projet', avant_id: 20, apres_id: 21 })
    await user.click(await screen.findByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(ordre()).toEqual(['Devis Settat', 'Préparer le matériel', 'Appeler le client']))
    expect(api.reordonnerTache).toHaveBeenLastCalledWith(22, { liste: 'projet', avant_id: 21, apres_id: null })

    api.reordonnerTache.mockRejectedValueOnce({ response: { status: 500, data: {} } })
    await user.click(screen.getByRole('button', { name: 'Monter « Appeler le client »' }))
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(ordre()).toEqual(['Devis Settat', 'Préparer le matériel', 'Appeler le client'])
  })

  it('Alt+↓ sur une ligne la descend (clavier, sans mode) ; j puis j parcourt les lignes (R2-036)', async () => {
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    await screen.findByRole('region', { name: 'Études' })
    await user.keyboard('j')
    expect(document.activeElement).toHaveTextContent('Devis Settat')
    await user.keyboard('j')
    expect(document.activeElement).toHaveTextContent('Préparer le matériel')
    await user.keyboard('{Alt>}{ArrowDown}{/Alt}')
    expect(ordre()).toEqual(['Devis Settat', 'Appeler le client', 'Préparer le matériel'])
    expect(api.reordonnerTache).toHaveBeenCalledWith(21, { liste: 'projet', avant_id: 22, apres_id: null })
  })

  describe('Tableau', () => {
    let remettreRectangles = () => {}
    beforeEach(() => { remettreRectangles = poserRectangles() })
    afterEach(() => { remettreRectangles() })
    const touche = async (cible, code) => {
      await act(async () => {
        fireEvent.keyDown(cible, { code, key: code === 'Space' ? ' ' : code })
        await new Promise((fin) => { setTimeout(fin, 15) })
      })
    }

    it('au clavier, ↓ sur la poignée d\'une carte la descend DANS sa colonne : l\'ordre est écrit', async () => {
      monter('/taches/projets/3?vue=tableau')
      await screen.findByRole('region', { name: 'Études' })
      const poignee = screen.getByRole('button', { name: 'Déplacer « Devis Settat »' })
      poignee.focus()
      await touche(poignee, 'Space')
      await touche(document, 'ArrowDown')
      await touche(document, 'Space')
      await waitFor(() => expect(api.reordonnerTache).toHaveBeenCalledWith(20, { liste: 'projet', avant_id: 21, apres_id: 22 }))
      expect(api.modifierTache).not.toHaveBeenCalled() // la carte n'a pas changé d'étape
      const cartes = [...screen.getByRole('region', { name: 'Études' }).querySelectorAll('.ep-carte .ligne-corps-bouton')].map((b) => b.textContent)
      expect(cartes).toEqual(['Préparer le matériel', 'Devis Settat', 'Appeler le client'])
    })
  })
})

describe('F2 acceptation (P138.3) — supprimer le projet ramène à la liste, toast « Annuler »', () => {
  it('Supprimer le projet… → la liste des projets, sans retour arrière qui rouvrirait le projet supprimé', async () => {
    const retour = vi.spyOn(window.history, 'back')
    api.supprimerProjet.mockResolvedValueOnce({ data: { geste_id: 9 } })
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    await screen.findByText('12 sur 20')
    await user.click(screen.getByRole('button', { name: "Plus d'actions" }))
    await user.click(await screen.findByRole('menuitem', { name: 'Supprimer le projet…' }))
    const dialogue = await screen.findByRole('dialog', { name: 'Supprimer le projet' })
    await vi.waitFor(() => expect(window.history.state?.tchFeuille).toBeTruthy())
    await user.click(within(dialogue).getByRole('button', { name: 'Supprimer', exact: true }))
    expect(await screen.findByText('Liste des projets')).toBeInTheDocument()
    expect(retour).not.toHaveBeenCalled()
    expect(screen.getByRole('group', { name: 'Geste effectué' })).toHaveTextContent('« Ventes » et ses')
    expect(screen.getByRole('button', { name: 'Annuler' })).toBeInTheDocument()
    retour.mockRestore()
  })
})

describe('Raccord F2 — Un projet : le menu ⋯ d\'une ligne passe par le gestionnaire commun', () => {
  const ouvrirMenu = async (user, titre) => {
    const etape = await screen.findByRole('region', { name: 'Études' })
    await user.click(within(etape).getByRole('button', { name: `Actions pour « ${titre} »` }))
    return etape
  }
  beforeEach(() => {
    api.annulerGeste.mockResolvedValue({ data: { restaurees: [], conflits: [], deja: false } })
    api.listerTousLesProjets.mockResolvedValue([
      { id: 3, nom: 'Ventes', couleur: 'vert', priorite: 3 }, { id: 5, nom: 'Site web', couleur: 'ciel', priorite: 2 },
    ])
  })

  it('F2 acceptation (S5) — Changer de projet… → Créer « Chantier » refusé (409 `nom_pris`) : le refus s\'affiche', async () => {
    api.creerProjet.mockRejectedValueOnce(Object.assign(new Error('409'), {
      response: { status: 400, statutServeur: 409, headers: {}, data: { nom: ['Un projet actif porte déjà ce nom.'], detail: 'Un projet actif porte déjà ce nom.', code: 'state_conflict' } },
    }))
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    await ouvrirMenu(user, 'Devis Settat')
    await user.click(await screen.findByRole('menuitem', { name: 'Changer de projet…' }))
    await user.type(await screen.findByRole('combobox', { name: 'Chercher un projet' }), 'Chantier')
    await user.click(await screen.findByRole('option', { name: 'Créer « Chantier »' }))
    expect(await screen.findByRole('group', { name: 'Geste effectué' })).toHaveTextContent('Un projet actif porte déjà ce nom.')
    expect(api.creerProjet).toHaveBeenCalledWith({ nom: 'Chantier' }, { erreurSousLeChamp: true }) // le toast ci-dessus, seul
    expect(api.traiterLot).not.toHaveBeenCalled()
  })

  it('Changer de projet… vers un autre projet : la ligne part tout de suite, Annuler la remet', async () => {
    api.traiterLot.mockResolvedValue({ data: { appliquees: [20], refusees: [], geste_id: 91 } })
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    const etape = await ouvrirMenu(user, 'Devis Settat')
    await user.click(await screen.findByRole('menuitem', { name: 'Changer de projet…' }))
    await user.click(await screen.findByRole('option', { name: 'Site web' }))
    expect(api.traiterLot).toHaveBeenCalledWith({ ids: [20], action: 'deplacer', valeurs: { projet_id: 5 } })
    await waitFor(() => expect(within(etape).queryByRole('button', { name: 'Devis Settat' })).toBeNull())
    expect(screen.getByRole('group', { name: 'Geste effectué' })).toHaveTextContent('Déplacée dans « Site web »')
    await user.click(screen.getByRole('button', { name: 'Annuler' }))
    expect(api.annulerGeste).toHaveBeenCalledWith(91)
    expect(await within(etape).findByRole('button', { name: 'Devis Settat' })).toBeInTheDocument()
    expect(api.lireVueProjet).toHaveBeenCalledTimes(1)
  })

  it('F4 revue #7 — En réserve, « Annuler », En réserve encore : la ligne garde la version rendue par le serveur', async () => {
    api.planifierTache.mockResolvedValue({ data: { ...tacheEcrite(), geste_id: 93 } })
    api.lireTache.mockResolvedValue({ data: { ...tacheEcrite().tache, id: 20, lock_version: 9 } })
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    await ouvrirMenu(user, 'Devis Settat')
    await user.click(await screen.findByRole('menuitem', { name: 'En réserve' }))
    await user.click(await screen.findByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(api.annulerGeste).toHaveBeenCalledWith(93))
    await waitFor(() => expect(api.lireTache).toHaveBeenCalledWith(20))
    await ouvrirMenu(user, 'Devis Settat')
    await user.click(await screen.findByRole('menuitem', { name: 'En réserve' }))
    await waitFor(() => expect(api.planifierTache).toHaveBeenCalledTimes(2))
    expect(api.planifierTache.mock.calls[1][1].lock_version).toBe(9)
    expect(api.lireVueProjet).toHaveBeenCalledTimes(1) // la vue n'est jamais relue : seule cette tâche l'est
  })

  it('Priorité → Basse passe par le lot `prioriser` ; En réserve par `planifier/` avec le lock_version', async () => {
    api.traiterLot.mockResolvedValue({ data: { appliquees: [20], refusees: [], geste_id: 92 } })
    api.planifierTache.mockResolvedValue({ data: { ...tacheEcrite(), geste_id: 93 } })
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    await ouvrirMenu(user, 'Devis Settat')
    await user.click(await screen.findByRole('menuitem', { name: 'Priorité' }))
    await user.click(await screen.findByRole('radio', { name: 'Basse' }))
    expect(api.traiterLot).toHaveBeenCalledWith({ ids: [20], action: 'prioriser', valeurs: { priorite: 1 } })
    expect(await screen.findByRole('group', { name: 'Geste effectué' })).toHaveTextContent('Priorité basse')
    await ouvrirMenu(user, 'Devis Settat')
    await user.click(await screen.findByRole('menuitem', { name: 'En réserve' }))
    expect(api.planifierTache).toHaveBeenCalledWith(20, expect.objectContaining({ quelque_jour: true, jour_prevu: null, lock_version: expect.any(Number) }))
  })

  it('Supprimer demande confirmation, retire la ligne ; Annuler la restaure à sa place', async () => {
    api.supprimerTache.mockResolvedValue({ data: { geste_id: 94 } })
    api.annulerGeste.mockResolvedValue({ data: { restaurees: [{ objet: 'tache', id: 20 }], conflits: [], deja: false } })
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    const etape = await ouvrirMenu(user, 'Devis Settat')
    await user.click(await screen.findByRole('menuitem', { name: 'Supprimer' }))
    const dialogue = await screen.findByRole('dialog', { name: 'Supprimer' })
    expect(dialogue).toHaveTextContent('Supprimer « Devis Settat » ?')
    await user.click(within(dialogue).getByRole('button', { name: 'Supprimer' }))
    await waitFor(() => expect(within(etape).queryByRole('button', { name: 'Devis Settat' })).toBeNull())
    expect(api.supprimerTache).toHaveBeenCalledWith(20)
    await user.click(screen.getByRole('button', { name: 'Annuler' }))
    // A7 : « Annuler » défait le geste côté serveur (le DELETE a rendu `geste_id`), jamais `restaurer/`.
    await waitFor(() => expect(api.annulerGeste).toHaveBeenCalledWith(94))
    expect(api.restaurerTache).not.toHaveBeenCalled()
    expect(await within(etape).findByRole('button', { name: 'Devis Settat' })).toBeInTheDocument()
  })

  it('un refus du serveur remet la ligne et le dit', async () => {
    api.traiterLot.mockResolvedValue({ data: { appliquees: [], refusees: [{ id: 20, raison: 'close' }], geste_id: null } })
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    const etape = await ouvrirMenu(user, 'Devis Settat')
    await user.click(await screen.findByRole('menuitem', { name: 'Changer de projet…' }))
    await user.click(await screen.findByRole('option', { name: 'Site web' }))
    expect(await within(etape).findByRole('button', { name: 'Devis Settat' })).toBeInTheDocument()
  })
})

describe('TCH91 — Un projet : ?planifier=1 ouvre Planifier le projet', () => {
  it('le rituel remplace la liste ; Passer revient à la liste sans rien écrire', async () => {
    monter('/taches/projets/3?planifier=1')
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    expect(await screen.findByRole('region', { name: 'Planifier le projet' })).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Études' })).toBeNull()
    await user.click(screen.getByRole('button', { name: 'Passer' }))
    expect(await screen.findByRole('region', { name: 'Études' })).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Planifier le projet' })).toBeNull()
    expect(api.modifierProjet).not.toHaveBeenCalled()
  })
})

describe('TCH92 — Un projet : ⋯ ouvre Décaler, Terminer, Supprimer', () => {
  it('F4 revue #17 — l\'ordre du ⋯ est celui de la référence (textes.md « ⋯ d\'un projet »)', async () => {
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    await screen.findByText('12 sur 20')
    await user.click(screen.getByRole('button', { name: "Plus d'actions" }))
    const menu = await screen.findByRole('menu')
    const libelles = within(menu).getAllByRole('menuitem').map((m) => m.textContent)
    const ordre = ['Planifier le projet', "Voir dans l'agenda", 'Avancement par semaine', 'Décaler les dates…', 'Dupliquer', 'Modèle…',
      'Mettre en pause', 'Terminer le projet…', 'Supprimer le projet…']
    expect(libelles.filter((l) => ordre.includes(l))).toEqual(ordre)
  })

  it('le menu porte les trois entrées et « Supprimer le projet… » ouvre le dialogue', async () => {
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    await screen.findByText('12 sur 20')
    await user.click(screen.getByRole('button', { name: "Plus d'actions" }))
    const menu = await screen.findByRole('menu')
    const libelles = within(menu).getAllByRole('menuitem').map((m) => m.textContent)
    expect(libelles).toEqual(expect.arrayContaining(['Décaler les dates…', 'Terminer le projet…', 'Supprimer le projet…', 'Planifier le projet', "Voir dans l'agenda"]))
    await user.click(within(menu).getByRole('menuitem', { name: 'Supprimer le projet…' }))
    expect(await screen.findByRole('dialog', { name: 'Supprimer le projet' })).toHaveTextContent('Supprimer « Ventes » et ses 20 tâches ?')
  })
})

/* F4 revue #6 + #8 — Tableau : « Annuler » rend la version du serveur (le geste suivant n'est pas refusé), et les
   compteurs des colonnes suivent le déplacement, puis l'annulation (même règle que le serveur, `_compteurs`). */
describe('F4 revue — Tableau : déplacer, Annuler, redéplacer', () => {
  let remettreRectangles = () => {}
  beforeEach(() => { remettreRectangles = poserRectangles() })
  afterEach(() => { remettreRectangles() })

  const touche = async (cible, code) => {
    await act(async () => {
      fireEvent.keyDown(cible, { code, key: code === 'Space' ? ' ' : code })
      await new Promise((fin) => { setTimeout(fin, 15) })
    })
  }
  const deplacer = async (nom, fleche) => {
    const poignee = screen.getByRole('button', { name: `Déplacer « ${nom} »` })
    poignee.focus()
    await touche(poignee, 'Space')
    await touche(document, fleche)
    await touche(document, 'Space')
  }
  const compte = (nom) => within(screen.getByRole('region', { name: nom })).getByText(/^\d+ sur \d+$/).textContent
  // un serveur qui verrouille la tâche 20 : chaque écriture et chaque « Annuler » changent sa version
  const fauxServeur = () => {
    const tache = { verrou: 4 }
    api.modifierTache.mockImplementation(async (id, corps) => {
      if (corps.lock_version !== tache.verrou) {
        throw Object.assign(new Error('conflit'), { response: { status: 409, data: { code: 'conflit_version', detail: 'Modifiée ailleurs.' } } })
      }
      tache.verrou += 1
      const ecrite = tacheEcrite()
      ecrite.tache.lock_version = tache.verrou
      return { data: { ...ecrite, geste_id: 91 } }
    })
    api.annulerGeste.mockImplementation(async () => { tache.verrou += 1; return { data: { restaurees: [{ objet: 'tache', id: 20 }], conflits: [], deja: false } } })
    api.lireTache.mockImplementation(async (id) => ({ data: { ...tacheEcrite().tache, id, lock_version: tache.verrou } }))
    return tache
  }

  it('après Annuler, la carte garde la version du serveur : le déplacement suivant n\'est pas refusé', async () => {
    fauxServeur()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    monter('/taches/projets/3?vue=tableau')
    await screen.findByRole('region', { name: 'Études' })
    await deplacer('Devis Settat', 'ArrowRight')
    await waitFor(() => expect(api.modifierTache).toHaveBeenCalledTimes(1))
    await user.click(await screen.findByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(within(screen.getByRole('region', { name: 'Études' })).getByRole('button', { name: 'Devis Settat' })).toBeInTheDocument())
    await deplacer('Devis Settat', 'ArrowRight')
    await waitFor(() => expect(api.modifierTache).toHaveBeenCalledTimes(2))
    expect(api.modifierTache.mock.calls[1][1].lock_version).toBe(6) // 4 → écriture 5 → annulation 6
    await act(async () => { await new Promise((fin) => { setTimeout(fin, 30) }) })
    expect(within(screen.getByRole('region', { name: 'Sans étape' })).getByRole('button', { name: 'Devis Settat' })).toBeInTheDocument()
    expect(document.body.textContent).not.toContain('Modifiée ailleurs')
  })

  it('les compteurs des colonnes bougent avec la carte, et reviennent avec Annuler', async () => {
    fauxServeur()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    monter('/taches/projets/3?vue=tableau')
    await screen.findByRole('region', { name: 'Études' })
    expect([compte('Études'), compte('Sans étape')]).toEqual(['4 sur 5', '8 sur 15'])
    await deplacer('Devis Settat', 'ArrowRight')
    await waitFor(() => expect(api.modifierTache).toHaveBeenCalledTimes(1))
    await waitFor(() => expect([compte('Études'), compte('Sans étape')]).toEqual(['4 sur 4', '8 sur 16']))
    await user.click(await screen.findByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect([compte('Études'), compte('Sans étape')]).toEqual(['4 sur 5', '8 sur 15']))
  })

  it('cocher une carte met à jour le compteur de SA colonne', async () => {
    api.terminerTache.mockResolvedValue({ data: { ...tacheEcrite(), geste_id: 92 } })
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    monter('/taches/projets/3?vue=tableau')
    await screen.findByRole('region', { name: 'Études' })
    await user.click(screen.getByRole('checkbox', { name: 'Marquer « Devis Settat » comme faite' }))
    await waitFor(() => expect(compte('Études')).toBe('5 sur 5'))
  })
})

describe('R2-093 — Un projet : UN seul « ‹ Projets », celui de la coquille, au-dessus du titre', () => {
  it('iPhone / < 1024 px : un seul bouton « Projets », avant le titre, qui ramène à la liste', async () => {
    monter()
    const titre = await screen.findByRole('heading', { level: 1 })
    const retours = screen.getAllByRole('button', { name: 'Projets' })
    expect(retours).toHaveLength(1)
    expect(retours[0].compareDocumentPosition(titre) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(document.querySelector('.ep-barre')).toBeNull() // plus de barre de retour dans la page
    await userEvent.setup({ advanceTimers: vi.advanceTimersByTime }).click(retours[0])
    expect(await screen.findByText('Liste des projets')).toBeInTheDocument()
  })
})

describe('R2-067 — Projets au bureau (≥ 1024 px) : la liste à gauche, le projet à droite', () => {
  const ancienne = window.matchMedia
  const media = (bureau) => vi.fn().mockImplementation((requete) => ({
    matches: bureau, media: requete, addEventListener: vi.fn(), removeEventListener: vi.fn(),
  }))
  const liste = () => {
    const base = exempleContrat('taches', 'projets_liste')
    const un = base.results[0]
    return { ...base, count: 3, results: [
      un, { ...un, id: 5, nom: 'Site web', couleur: 'ciel', priorite: 2, lock_version: 7 }, { ...un, id: 8, nom: 'Salon', couleur: 'prune', priorite: 1 },
    ] }
  }
  function Lieu() {
    const l = useLocation()
    return <div data-testid="lieu">{`${l.pathname}${l.search}`}</div>
  }
  const monterBureau = (chemin = '/taches/projets/3') => render(
    <MemoryRouter initialEntries={[chemin]}>
      <Routes>
        <Route path="/taches/projets/:id" element={<><Projet /><Lieu /></>} />
        <Route path="/taches/projets" element={<div className="tch"><p>Liste des projets</p></div>} />
      </Routes>
    </MemoryRouter>,
  )
  beforeEach(() => {
    window.matchMedia = media(true)
    window.localStorage.clear()
    api.listerProjets.mockImplementation(async (params) => (
      params?.statut === 'en_pause' ? { data: { count: 0, next: null, previous: null, results: [] } } : { data: liste() }))
  })
  afterEach(() => { window.matchMedia = ancienne })

  it('la colonne montre TOUS les projets, le projet ouvert est surligné ; pas de « ‹ Projets » (la liste est là), loupe et Copilote restent', async () => {
    monterBureau()
    const colonne = await screen.findByRole('complementary', { name: 'Liste des projets' })
    const ouvert = await within(colonne).findByRole('button', { name: 'Ventes' })
    expect(within(colonne).getByRole('button', { name: 'Site web' })).toBeInTheDocument()
    expect(within(colonne).getByRole('button', { name: 'Salon' })).toBeInTheDocument()
    expect(ouvert).toHaveAttribute('aria-current', 'true')
    expect(ouvert.closest('.ligne')).toHaveClass('ouvert-bureau')
    expect(within(colonne).getByRole('button', { name: 'Site web' })).not.toHaveAttribute('aria-current')
    // le projet est à droite, dans la même page
    expect((await screen.findAllByText('12 sur 20')).length).toBeGreaterThan(1) // la ligne de la colonne ET l'en-tête du projet
    expect(screen.queryByRole('button', { name: 'Projets' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Chercher dans mes tâches' })).toBeInTheDocument()
  })

  it("cliquer un autre projet change l'adresse (/taches/projets/<id>), sans retour à la liste", async () => {
    monterBureau()
    const colonne = await screen.findByRole('complementary', { name: 'Liste des projets' })
    await userEvent.setup({ advanceTimers: vi.advanceTimersByTime }).click(await within(colonne).findByRole('button', { name: 'Site web' }))
    expect(screen.getByTestId('lieu')).toHaveTextContent('/taches/projets/5')
  })

  it('j (focus dans la colonne) passe au projet suivant', async () => {
    monterBureau('/taches/projets/5')
    const colonne = await screen.findByRole('complementary', { name: 'Liste des projets' })
    const ouvert = await within(colonne).findByRole('button', { name: 'Site web' })
    ouvert.focus()
    await userEvent.setup({ advanceTimers: vi.advanceTimersByTime }).keyboard('j')
    expect(screen.getByTestId('lieu')).toHaveTextContent('/taches/projets/8')
  })

  it('↑ (focus dans la colonne) revient au projet précédent', async () => {
    monterBureau('/taches/projets/5')
    const colonne = await screen.findByRole('complementary', { name: 'Liste des projets' })
    ;(await within(colonne).findByRole('button', { name: 'Site web' })).focus()
    await userEvent.setup({ advanceTimers: vi.advanceTimersByTime }).keyboard('{ArrowUp}')
    expect(screen.getByTestId('lieu')).toHaveTextContent('/taches/projets/3')
  })

  it('renommer le projet ouvert met la colonne à jour tout de suite', async () => {
    api.modifierProjet.mockResolvedValue({ data: { ...exempleContrat('taches', 'projet_vue').projet, nom: 'Ventes 2027', lock_version: 5 } })
    monterBureau()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    const colonne = await screen.findByRole('complementary', { name: 'Liste des projets' })
    await within(colonne).findByRole('button', { name: 'Ventes' })
    await user.click(await screen.findByRole('button', { name: 'Renommer « Ventes »' }))
    const champ = screen.getByRole('textbox', { name: 'Nom du projet' })
    await user.clear(champ)
    await user.type(champ, 'Ventes 2027{Enter}')
    expect(await within(colonne).findByRole('button', { name: 'Ventes 2027' })).toBeInTheDocument()
  })

  it("cocher une tâche du projet ouvert met l'avancement de sa ligne à jour", async () => {
    api.terminerTache.mockResolvedValue({ data: { ...tacheEcrite(), geste_id: 92 } })
    monterBureau()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    const colonne = await screen.findByRole('complementary', { name: 'Liste des projets' })
    const ligne = (await within(colonne).findByRole('button', { name: 'Ventes' })).closest('.ligne')
    expect(within(ligne).getByText('12 sur 20')).toBeInTheDocument()
    await user.click(await screen.findByRole('checkbox', { name: 'Marquer « Devis Settat » comme faite' }))
    await waitFor(() => expect(within(ligne).getByText('13 sur 20')).toBeInTheDocument())
  })

  it('« Nouveau projet » dans la colonne ouvre la feuille de création', async () => {
    monterBureau()
    const colonne = await screen.findByRole('complementary', { name: 'Liste des projets' })
    await userEvent.setup({ advanceTimers: vi.advanceTimersByTime }).click(await within(colonne).findByRole('button', { name: 'Nouveau projet' }))
    expect(await screen.findByRole('dialog', { name: 'Nouveau projet' })).toBeInTheDocument()
  })

  it('R3-126 — l\'en-tête du projet tient sur DEUX lignes : priorité · barre · jalon · vues, puis santé · « Fini quand… »', async () => {
    const { container } = monterBureau()
    await screen.findAllByText('12 sur 20')
    const tete = container.querySelector('.ep-tete')
    expect([...tete.children].filter((e) => !e.matches('.ep-sante-detail')).map((e) => e.className)).toEqual(['ep-ligne-info', 'ep-ligne-suite'])
    const premiere = tete.querySelector('.ep-ligne-info')
    expect(premiere.querySelector('.ep-prio')).not.toBeNull()
    expect(premiere.querySelector('.ep-barre-avance')).not.toBeNull()
    expect(premiere.querySelector('.ep-avance-texte')).toHaveTextContent('12 sur 20')
    expect(premiere.querySelector('.ep-vues')).not.toBeNull() // le sélecteur de vue est dans la ligne, plus au-dessus
    const seconde = tete.querySelector('.ep-ligne-suite')
    expect(within(seconde).getByRole('button', { name: /Fini quand/ })).toBeInTheDocument()
    expect(container.querySelector('.ep-barre-projet')).toBeNull()
  })

  it('R3-126 — Tableau et Chronologie prennent toute la largeur : « ‹ Projets » (dans l\'en-tête) ramène à la liste, la Liste n\'en a pas', async () => {
    const { unmount } = monterBureau('/taches/projets/3?vue=tableau')
    await screen.findAllByText('12 sur 20')
    const retour = await screen.findByRole('button', { name: 'Projets' })
    expect(retour.closest('.ep-ligne-info')).not.toBeNull()
    // la loupe et le Copilote restent (la coquille n'est pas en mode « écran enfant »)
    expect(screen.getByRole('button', { name: 'Chercher dans mes tâches' })).toBeInTheDocument()
    await userEvent.setup({ advanceTimers: vi.advanceTimersByTime }).click(retour)
    expect(await screen.findByText('Liste des projets')).toBeInTheDocument()
    unmount()
    monterBureau('/taches/projets/3?vue=liste')
    await screen.findAllByText('12 sur 20')
    expect(screen.queryByRole('button', { name: 'Projets' })).toBeNull()
  })

  it('< 1024 px : aucune colonne (la liste, puis le projet)', async () => {
    window.matchMedia = media(false)
    monterBureau()
    await screen.findByText('12 sur 20')
    expect(screen.queryByRole('complementary', { name: 'Liste des projets' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Projets' })).toBeInTheDocument()
  })
})
