import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat } from '../../../test/fixtures/contractSamples'
import { reinitialiserGestes } from '../lib/gestes'
import CoquilleTaches from '../coquille/CoquilleTaches'

vi.mock('../../../api/tachesApi', async (original) => ({
  ...(await original()),
  listerTousLesModeles: vi.fn(),
  lireModele: vi.fn(),
  instancierModele: vi.fn(),
  renommerModele: vi.fn(),
  supprimerModele: vi.fn(),
  enregistrerModele: vi.fn(),
  dupliquerProjet: vi.fn(),
  annulerGeste: vi.fn(),
  lireVueProjet: vi.fn(),
  modifierProjet: vi.fn(),
  listerToutesLesTaches: vi.fn(),
  listerTousLesProjets: vi.fn(),
}))

const api = await import('../../../api/tachesApi')
const { default: ProjetsModeles } = await import('../../../pages/taches/ProjetsModeles')
const { default: Projet } = await import('../../../pages/taches/Projet')
const { DialogueEnregistrerModele } = await import('./Dialogues')

/* TCH157 — l'écran Modèles (`modeles_liste.json`, `modele.json`, `modele_instancier.json`, `projet_ecrit.json`) :
   Utiliser ce modèle avec l'APERÇU des dates avant d'écrire, Renommer, Supprimer ; « Enregistrer comme modèle » et
   « Dupliquer » dans le ⋯ d'un projet. Les réponses viennent des échantillons committés (`exempleContrat`). */

const AUJOURDHUI = '2026-11-17'
const LUNDI_PROCHAIN = '2026-11-23' // R3-137 : « Dupliquer » part du lundi qui suit aujourd'hui (mar. 17), « Utiliser un modèle » d'aujourd'hui
const modeleServi = () => structuredClone(exempleContrat('taches', 'modele'))
const apercuServi = () => structuredClone(exempleContrat('taches', 'modele_instancier'))
const projetEcrit = () => structuredClone(exempleContrat('taches', 'projet_ecrit'))
const lignes = () => structuredClone(exempleContrat('taches', 'modeles_liste').results)

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(`${AUJOURDHUI}T09:00:00`))
  reinitialiserGestes()
  api.listerTousLesModeles.mockImplementation(async () => lignes())
  api.lireModele.mockImplementation(async () => ({ data: modeleServi() }))
})
afterEach(() => { vi.useRealTimers(); vi.clearAllMocks(); reinitialiserGestes() })

const monter = () => render(
  <MemoryRouter initialEntries={['/taches/projets/modeles']}>
    <Routes>
      <Route path="/taches/projets/modeles" element={<ProjetsModeles />} />
      <Route path="/taches/projets/:id" element={<CoquilleTaches ecran="projet" titre="Projet"><p>Écran du projet créé</p></CoquilleTaches>} />
    </Routes>
  </MemoryRouter>,
)
const utilisateur = () => userEvent.setup({ advanceTimers: vi.advanceTimersByTime })

describe('TCH157 — la liste des modèles', () => {
  it('une ligne par modèle servi, avec ses comptes ; rien d\'écrit en dur', async () => {
    monter()
    const ligne = (await screen.findByText('Salon')).closest('[role="listitem"]')
    expect(ligne).toHaveTextContent('12 tâches · 3 étapes')
    expect(within(ligne).getByRole('button', { name: 'Utiliser ce modèle' })).toBeInTheDocument()
    expect(api.listerTousLesModeles).toHaveBeenCalledTimes(1)
  })

  it('couture r2 — UN seul « ‹ Projets », celui de la coquille (plus de barre de retour dans la page)', async () => {
    monter()
    await screen.findByText('Salon')
    expect(screen.getAllByRole('button', { name: 'Projets' })).toHaveLength(1)
    expect(document.querySelector('.ep-barre')).toBeNull()
  })

  it('« Aucun modèle » quand le serveur n\'en sert aucun', async () => {
    api.listerTousLesModeles.mockResolvedValue([])
    monter()
    expect(await screen.findByText('Aucun modèle')).toBeInTheDocument()
  })

  it('un échec de lecture est dit, sans écran muet', async () => {
    api.listerTousLesModeles.mockRejectedValue(new Error('Network Error'))
    monter()
    expect(await screen.findByRole('alert')).toHaveTextContent('Connexion perdue')
  })
})

describe('TCH157 — Utiliser ce modèle (aperçu des dates avant d\'écrire)', () => {
  const ouvrir = async (user) => {
    await user.click(await screen.findByRole('button', { name: 'Utiliser ce modèle' }))
    return screen.findByRole('dialog', { name: 'Utiliser ce modèle' })
  }

  it('annonce « 1 tâche, première le … » depuis l\'aperçu du serveur, puis Créer écrit et ouvre le projet', async () => {
    api.instancierModele.mockImplementation(async (id, corps) => ({ data: corps.apercu ? apercuServi() : projetEcrit() }))
    const user = utilisateur()
    monter()
    const dialogue = await ouvrir(user)
    expect(await within(dialogue).findByText('Préparation')).toBeInTheDocument() // étapes lues du contenu figé
    expect(within(dialogue).getByLabelText('Date de lancement')).toHaveValue(AUJOURDHUI)
    // R2-065 — le nom est prérempli et l'aperçu est lu DÈS L'OUVERTURE (rien n'est écrit)
    expect(within(dialogue).getByLabelText('Nom du projet')).toHaveValue('Salon')
    await waitFor(() => expect(api.instancierModele).toHaveBeenCalledWith(2, { nom: 'Salon', date_lancement: AUJOURDHUI, apercu: true }, { erreurSousLeChamp: true }))
    expect(await within(dialogue).findByText('1 tâche, première le lun. 23')).toBeInTheDocument()

    const champ = within(dialogue).getByLabelText('Nom du projet')
    await user.clear(champ)
    await user.type(champ, 'Salon 2027')
    await user.tab() // l'aperçu se relit quand le nom est posé
    await waitFor(() => expect(api.instancierModele).toHaveBeenCalledWith(2, { nom: 'Salon 2027', date_lancement: AUJOURDHUI, apercu: true }, { erreurSousLeChamp: true }))
    expect(api.instancierModele.mock.calls.every(([, corps]) => corps.apercu === true)).toBe(true) // rien d'écrit à ce stade

    await user.click(within(dialogue).getByRole('button', { name: 'Créer' }))
    await waitFor(() => expect(api.instancierModele).toHaveBeenLastCalledWith(2, { nom: 'Salon 2027', date_lancement: AUJOURDHUI, apercu: false }, { erreurSousLeChamp: true }))
    expect(await screen.findByText('Écran du projet créé')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Annuler' })).toBeInTheDocument() // « Projet créé · Annuler »
  })

  it('Annuler supprime le projet créé par le geste du serveur', async () => {
    api.instancierModele.mockImplementation(async (id, corps) => ({ data: corps.apercu ? apercuServi() : projetEcrit() }))
    api.annulerGeste.mockResolvedValue({ data: {} })
    const user = utilisateur()
    monter()
    const dialogue = await ouvrir(user)
    expect(await within(dialogue).findByText('1 tâche, première le lun. 23')).toBeInTheDocument() // l'aperçu est déjà là
    await user.click(within(dialogue).getByRole('button', { name: 'Créer' })) // UN seul Créer : l'écriture
    await screen.findByText('Écran du projet créé')
    await user.click(screen.getByRole('button', { name: 'Annuler' }))
    expect(api.annulerGeste).toHaveBeenCalledWith(projetEcrit().geste_id)
  })

  it('R2-065 — taper un nom puis toucher Créer tout de suite écrit AU PREMIER TOUCHER (plus de « premier Créer qui ne crée rien »)', async () => {
    api.instancierModele.mockImplementation(async (id, corps) => ({ data: corps.apercu ? apercuServi() : projetEcrit() }))
    const user = utilisateur()
    monter()
    const dialogue = await ouvrir(user)
    const champ = within(dialogue).getByLabelText('Nom du projet')
    await user.clear(champ)
    await user.type(champ, 'Salon 2027')
    await user.click(within(dialogue).getByRole('button', { name: 'Créer' })) // sans quitter le champ avant
    await waitFor(() => expect(api.instancierModele).toHaveBeenLastCalledWith(2, { nom: 'Salon 2027', date_lancement: AUJOURDHUI, apercu: false }, { erreurSousLeChamp: true }))
    expect(await screen.findByText('Écran du projet créé')).toBeInTheDocument()
  })

  it('changer la date relit l\'aperçu avec la nouvelle date', async () => {
    api.instancierModele.mockImplementation(async (id, corps) => ({ data: corps.apercu ? apercuServi() : projetEcrit() }))
    const user = utilisateur()
    monter()
    const dialogue = await ouvrir(user)
    await within(dialogue).findByText(/première le/)
    const champ = within(dialogue).getByLabelText('Date de lancement')
    await user.clear(champ)
    await user.type(champ, '2026-12-01')
    await waitFor(() => expect(api.instancierModele).toHaveBeenLastCalledWith(2, { nom: 'Salon', date_lancement: '2026-12-01', apercu: true }, { erreurSousLeChamp: true }))
  })

  it('un nom de projet déjà pris est dit sous le champ, rien n\'est créé', async () => {
    api.instancierModele.mockRejectedValue({ response: { status: 400, statutServeur: 409, data: { nom: ['Un projet « Ventes » existe déjà.'], detail: 'Un projet « Ventes » existe déjà.', code: 'state_conflict' } } })
    const user = utilisateur()
    monter()
    const dialogue = await ouvrir(user)
    const champ = within(dialogue).getByLabelText('Nom du projet')
    await user.clear(champ)
    await user.type(champ, 'Ventes')
    await user.tab()
    expect(await within(dialogue).findByText('Un projet « Ventes » existe déjà.')).toBeInTheDocument()
    expect(champ).toHaveAttribute('aria-invalid', 'true')
    expect(screen.queryByText('Écran du projet créé')).toBeNull()
  })

  it('Créer reste éteint sans nom (le nom effacé)', async () => {
    api.instancierModele.mockImplementation(async () => ({ data: apercuServi() }))
    const user = utilisateur()
    monter()
    const dialogue = await ouvrir(user)
    await user.clear(within(dialogue).getByLabelText('Nom du projet'))
    expect(within(dialogue).getByRole('button', { name: 'Créer' })).toBeDisabled()
  })
})

describe('TCH157 — Renommer et Supprimer un modèle', () => {
  const menu = async (user, action) => {
    await user.click(await screen.findByRole('button', { name: 'Actions pour « Salon »' }))
    await user.click(await screen.findByRole('menuitem', { name: action }))
  }

  it('Renommer met la ligne à jour sur place, sans relire la liste', async () => {
    api.renommerModele.mockResolvedValue({ data: { ...modeleServi(), nom: 'Foire' } })
    const user = utilisateur()
    monter()
    await menu(user, 'Renommer')
    const dialogue = await screen.findByRole('dialog', { name: 'Renommer' })
    const champ = within(dialogue).getByLabelText('Nom du modèle')
    await user.clear(champ)
    await user.type(champ, 'Foire')
    await user.click(within(dialogue).getByRole('button', { name: 'Renommer' }))
    expect(api.renommerModele).toHaveBeenCalledWith(2, { nom: 'Foire' }, { erreurSousLeChamp: true })
    expect(await screen.findByText('Foire')).toBeInTheDocument()
    expect(screen.queryByText('Salon')).toBeNull()
    expect(api.listerTousLesModeles).toHaveBeenCalledTimes(1)
  })

  it('un nom de modèle déjà pris est dit sous le champ et la ligne garde son nom', async () => {
    api.renommerModele.mockRejectedValue({ response: { status: 400, statutServeur: 409, data: { nom: ['Un modèle « Foire » existe déjà.'], detail: 'Un modèle « Foire » existe déjà.', code: 'state_conflict' } } })
    const user = utilisateur()
    monter()
    await menu(user, 'Renommer')
    const dialogue = await screen.findByRole('dialog', { name: 'Renommer' })
    const champ = within(dialogue).getByLabelText('Nom du modèle')
    await user.clear(champ)
    await user.type(champ, 'Foire')
    await user.click(within(dialogue).getByRole('button', { name: 'Renommer' }))
    expect(await within(dialogue).findByText('Un modèle « Foire » existe déjà.')).toBeInTheDocument()
    expect(champ).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getAllByText('Salon').length).toBeGreaterThan(0)
  })

  it('Supprimer demande confirmation, retire la ligne sur place ; un échec la garde', async () => {
    api.supprimerModele.mockRejectedValueOnce(new Error('Network Error')).mockResolvedValueOnce({ data: { geste_id: null } })
    const user = utilisateur()
    monter()
    await menu(user, 'Supprimer')
    const dialogue = await screen.findByRole('dialog', { name: 'Supprimer' })
    expect(within(dialogue).getByText('Supprimer « Salon » ?')).toBeInTheDocument()
    await user.click(within(dialogue).getByRole('button', { name: 'Supprimer' }))
    expect(await within(dialogue).findByRole('alert')).toHaveTextContent('Connexion perdue')
    expect(screen.getAllByText('Salon').length).toBeGreaterThan(0)
    await user.click(within(dialogue).getByRole('button', { name: 'Supprimer' }))
    await waitFor(() => expect(screen.queryByText('Salon')).toBeNull())
    expect(api.supprimerModele).toHaveBeenCalledWith(2)
    expect(api.listerTousLesModeles).toHaveBeenCalledTimes(1)
    expect(await screen.findByText('Aucun modèle')).toBeInTheDocument()
  })
})

describe('TCH157 — Enregistrer comme modèle', () => {
  const vue = () => structuredClone(exempleContrat('taches', 'projet_vue'))

  it('F4 revue #11 — résumé et étapes sont ceux de la COPIE (aperçu du serveur), pas ceux du projet ; « Inclure les notes » éteint par défaut', async () => {
    const onFait = vi.fn()
    api.dupliquerProjet.mockResolvedValue({ data: apercuServi() }) // la copie : 1 tâche, 1 étape (le projet en compte 20)
    api.enregistrerModele.mockResolvedValue({ data: modeleServi() })
    const user = utilisateur()
    render(<DialogueEnregistrerModele projet={vue().projet} onFait={onFait} onFermer={() => {}} />)
    const dialogue = screen.getByRole('dialog', { name: 'Enregistrer comme modèle' })
    expect(await within(dialogue).findByText('1 tâche · 1 étape')).toBeInTheDocument()
    expect(api.dupliquerProjet).toHaveBeenCalledWith(3, expect.objectContaining({ apercu: true })) // aperçu : rien n'est écrit
    expect(within(dialogue).getByText('Préparation')).toBeInTheDocument()
    expect(within(dialogue).queryByText('20 tâches · 1 étape')).toBeNull()
    expect(within(dialogue).queryByText('5 tâches')).toBeNull()
    const notes = within(dialogue).getByRole('switch', { name: 'Inclure les notes' })
    expect(notes).toHaveAttribute('aria-checked', 'false')
    await user.click(notes)
    await user.click(within(dialogue).getByRole('button', { name: 'Créer' }))
    expect(api.enregistrerModele).toHaveBeenCalledWith(3, { nom: 'Ventes', inclure_notes: true }, { erreurSousLeChamp: true })
    await waitFor(() => expect(onFait).toHaveBeenCalledWith(modeleServi()))
  })

  it('F4 revue #11 — des tâches confidentielles non reprises sont dites quand le serveur en compte (clé `confidentielles_non_reprises`)', async () => {
    api.dupliquerProjet.mockResolvedValue({ data: { ...apercuServi(), confidentielles_non_reprises: 2 } })
    render(<DialogueEnregistrerModele projet={vue().projet} onFait={vi.fn()} onFermer={() => {}} />)
    const dialogue = screen.getByRole('dialog', { name: 'Enregistrer comme modèle' })
    expect(await within(dialogue).findByText('2 tâches confidentielles non reprises')).toBeInTheDocument()
  })

  it('F4 revue #11 — sans aperçu lisible (nom pris, réseau), aucun nombre du projet n\'est montré à la place', async () => {
    api.dupliquerProjet.mockRejectedValue({ response: { status: 400, statutServeur: 409, data: { nom: ['Un projet existe déjà.'], detail: 'Un projet existe déjà.', code: 'state_conflict' } } })
    render(<DialogueEnregistrerModele projet={vue().projet} onFait={vi.fn()} onFermer={() => {}} />)
    const dialogue = screen.getByRole('dialog', { name: 'Enregistrer comme modèle' })
    await waitFor(() => expect(api.dupliquerProjet).toHaveBeenCalled())
    expect(within(dialogue).queryByText(/tâches? · /)).toBeNull()
    expect(within(dialogue).queryByText('Études')).toBeNull()
  })

  it('un nom de modèle déjà pris est dit sous le champ', async () => {
    api.enregistrerModele.mockRejectedValue({ response: { status: 400, statutServeur: 409, data: { nom: ['Un modèle « Ventes » existe déjà.'], detail: 'Un modèle « Ventes » existe déjà.', code: 'state_conflict' } } })
    const user = utilisateur()
    render(<DialogueEnregistrerModele projet={vue().projet} onFait={vi.fn()} onFermer={() => {}} />)
    await user.click(screen.getByRole('button', { name: 'Créer' }))
    const champ = screen.getByLabelText('Nom du modèle')
    expect(await screen.findByText('Un modèle « Ventes » existe déjà.')).toBeInTheDocument()
    expect(champ).toHaveAttribute('aria-invalid', 'true')
  })

  it('enregistrer → rouvrir : le modèle enregistré est celui que l\'écran Modèles relit du serveur', async () => {
    const serveur = []
    api.enregistrerModele.mockImplementation(async (id, corps) => {
      const modele = { ...modeleServi(), id: 9, nom: corps.nom }
      serveur.push(modele)
      return { data: structuredClone(modele) }
    })
    api.listerTousLesModeles.mockImplementation(async () => serveur.map((m) => ({
      id: m.id, nom: m.nom, created_at: m.created_at, nb_taches: m.contenu.taches.length, nb_sections: m.contenu.sections.length,
    })))
    const user = utilisateur()
    const premier = render(<DialogueEnregistrerModele projet={vue().projet} onFait={vi.fn()} onFermer={() => {}} />)
    await user.click(screen.getByRole('button', { name: 'Créer' }))
    await waitFor(() => expect(serveur).toHaveLength(1))
    premier.unmount()
    monter()
    const ligne = (await screen.findByText('Ventes')).closest('[role="listitem"]')
    expect(ligne).toHaveTextContent('1 tâche · 1 étape') // comptes calculés du contenu servi, pas écrits dans l'écran
    const avant = structuredClone(serveur)
    await user.click(within(ligne).getByRole('button', { name: 'Utiliser ce modèle' })) // sans rien enregistrer de plus
    await screen.findByRole('dialog', { name: 'Utiliser ce modèle' })
    expect(serveur).toEqual(avant)
  })
})

describe('TCH157 — Dupliquer et Modèle… dans le ⋯ d\'un projet', () => {
  const monterProjet = () => render(
    <MemoryRouter initialEntries={['/taches/projets/3']}>
      <Routes>
        <Route path="/taches/projets/:id" element={<Projet />} />
      </Routes>
    </MemoryRouter>,
  )
  const ouvrirMenu = async (user, libelle) => {
    await screen.findByRole('radiogroup', { name: 'Vue' })
    await user.click(screen.getByRole('button', { name: /Plus d'actions|Plus/ }))
    await user.click(await screen.findByRole('menuitem', { name: libelle }))
  }
  beforeEach(() => {
    api.lireVueProjet.mockImplementation(async () => ({ data: structuredClone(exempleContrat('taches', 'projet_vue')) }))
    api.listerToutesLesTaches.mockResolvedValue([])
  })

  it('Dupliquer : nom, date, aperçu puis Créer ; le double s\'ouvre', async () => {
    api.dupliquerProjet.mockImplementation(async (id, corps) => ({ data: corps.apercu ? apercuServi() : projetEcrit() }))
    const user = utilisateur()
    monterProjet()
    await ouvrirMenu(user, 'Dupliquer')
    const dialogue = await screen.findByRole('dialog', { name: 'Dupliquer' })
    expect(within(dialogue).getByText('Études')).toBeInTheDocument()
    expect(within(dialogue).queryByText('5 tâches')).toBeNull() // F4 revue #11 : le compte du projet n'est pas celui de la copie
    // R2-065 — nom prérempli « {nom} (copie) », aperçu lu à l'ouverture
    const champ = within(dialogue).getByLabelText('Nom du projet')
    expect(champ).toHaveValue('Ventes (copie)')
    await waitFor(() => expect(api.dupliquerProjet).toHaveBeenCalledWith(3, { nom: 'Ventes (copie)', date_debut: LUNDI_PROCHAIN, apercu: true }, { erreurSousLeChamp: true }))
    await user.clear(champ)
    await user.type(champ, 'Ventes 2027')
    await user.tab()
    await waitFor(() => expect(api.dupliquerProjet).toHaveBeenCalledWith(3, { nom: 'Ventes 2027', date_debut: LUNDI_PROCHAIN, apercu: true }, { erreurSousLeChamp: true }))
    expect(await within(dialogue).findByText('1 tâche, première le lun. 23')).toBeInTheDocument()
    await user.click(within(dialogue).getByRole('button', { name: 'Créer' }))
    await waitFor(() => expect(api.dupliquerProjet).toHaveBeenLastCalledWith(3, { nom: 'Ventes 2027', date_debut: LUNDI_PROCHAIN, apercu: false }, { erreurSousLeChamp: true }))
    expect(await screen.findByRole('button', { name: 'Annuler' })).toBeInTheDocument()
    // R3-137 — le toast dit où les premières tâches sont posées
    expect(screen.getByRole('group', { name: 'Geste effectué' })).toHaveTextContent('Projet créé · 1 tâche posée le lun. 23')
  })

  it('R3-137 — Dupliquer part du lundi PROCHAIN (un lundi : celui d\'après), Utiliser un modèle d\'aujourd\'hui', async () => {
    api.dupliquerProjet.mockImplementation(async (id, corps) => ({ data: corps.apercu ? apercuServi() : projetEcrit() }))
    const user = utilisateur()
    monterProjet()
    await ouvrirMenu(user, 'Dupliquer')
    const dialogue = await screen.findByRole('dialog', { name: 'Dupliquer' })
    expect(within(dialogue).getByLabelText('Date de lancement')).toHaveValue(LUNDI_PROCHAIN)
    const { lundiProchain } = await import('./Dialogues')
    expect(lundiProchain('2026-11-16')).toBe('2026-11-23') // un lundi → le lundi d'après
    expect(lundiProchain('2026-11-22')).toBe('2026-11-23') // un dimanche → le lendemain
    expect(lundiProchain('2026-11-19')).toBe('2026-11-23')
  })

  it('F4 revue #11 — Dupliquer dit les tâches confidentielles non reprises quand l\'aperçu du serveur en compte', async () => {
    api.dupliquerProjet.mockImplementation(async () => ({ data: { ...apercuServi(), confidentielles_non_reprises: 1 } }))
    const user = utilisateur()
    monterProjet()
    await ouvrirMenu(user, 'Dupliquer')
    const dialogue = await screen.findByRole('dialog', { name: 'Dupliquer' })
    expect(await within(dialogue).findByText('1 tâche, première le lun. 23')).toBeInTheDocument()
    expect(within(dialogue).getByText('1 tâche confidentielle non reprise')).toBeInTheDocument()
  })

  it('Modèle… ouvre « Enregistrer comme modèle » sans quitter le projet', async () => {
    api.enregistrerModele.mockResolvedValue({ data: modeleServi() })
    const user = utilisateur()
    monterProjet()
    await ouvrirMenu(user, 'Modèle…')
    const dialogue = await screen.findByRole('dialog', { name: 'Enregistrer comme modèle' })
    await user.click(within(dialogue).getByRole('button', { name: 'Créer' }))
    await waitFor(() => expect(api.enregistrerModele).toHaveBeenCalledWith(3, { nom: 'Ventes', inclure_notes: false }, { erreurSousLeChamp: true }))
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Enregistrer comme modèle' })).toBeNull())
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Ventes')
  })
})
