import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'
import { reinitialiserGestes } from '../../features/taches/lib/gestes'

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
}))

const api = await import('../../api/tachesApi')
const { default: Projet } = await import('./Projet')

/* TCH89 — l'écran rend `projet_vue.json` : en-tête (priorité, avancement, jalon, santé, Détails), étapes,
   « Sans étape », « Faites (n) ». Cocher et ajouter se font sur place, sans relire la vue. */

const monter = (chemin = '/taches/projets/3') => render(
  <MemoryRouter initialEntries={[chemin]}>
    <Routes><Route path="/taches/projets/:id" element={<Projet />} /></Routes>
  </MemoryRouter>,
)
const tacheEcrite = () => structuredClone(exempleContrat('taches', 'tache_ecrite'))

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date('2026-11-17T09:00:00'))
  reinitialiserGestes()
  api.lireVueProjet.mockResolvedValue(reponseContrat('taches', 'projet_vue'))
})
afterEach(() => { vi.useRealTimers(); vi.clearAllMocks(); reinitialiserGestes() })

describe('TCH89 — Un projet : en-tête', () => {
  it('avancement, échéance, jalon, santé et priorité viennent de la vue', async () => {
    monter()
    expect(await screen.findByText('12 sur 20 · échéance 15/12')).toBeInTheDocument()
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
    await user.click(await screen.findByRole('button', { name: 'Détails' }))
    expect(screen.getByText('Fini quand les 4 devis sont signés')).toBeInTheDocument()
    expect(screen.getByText('dernière faite le 03/11')).toBeInTheDocument()
  })

  it('pas de signal de santé : aucune ligne de santé', async () => {
    const vue = exempleContrat('taches', 'projet_vue')
    vue.projet.sante = []
    api.lireVueProjet.mockResolvedValue({ data: vue })
    monter()
    await screen.findByText('12 sur 20 · échéance 15/12')
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
    expect(await screen.findByText('13 sur 20 · échéance 15/12')).toBeInTheDocument()
    expect(api.lireVueProjet).toHaveBeenCalledTimes(1)

    await user.click(screen.getByRole('button', { name: 'Annuler' }))
    expect(api.rouvrirTache).toHaveBeenCalledWith(20)
    expect(await screen.findByText('12 sur 20 · échéance 15/12')).toBeInTheDocument()
  })

  it('un échec réseau remet la case et l\'avancement comme avant', async () => {
    api.terminerTache.mockRejectedValue(new Error('Network Error'))
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    const etape = await screen.findByRole('region', { name: 'Études' })
    const case_ = within(etape).getByRole('checkbox', { name: /Marquer « Devis Settat »/ })
    await user.click(case_)
    await waitFor(() => expect(case_).not.toBeChecked())
    expect(screen.getByText('12 sur 20 · échéance 15/12')).toBeInTheDocument()
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
    await screen.findByText('12 sur 20 · échéance 15/12')
    await user.click(screen.getByRole('button', { name: "Plus d'actions" }))
    await user.click(await screen.findByRole('menuitem', { name: 'Mettre en pause' }))
    expect(api.modifierProjet).toHaveBeenCalledWith(3, { statut: 'en_pause', lock_version: 4 })
    expect(await screen.findByText('En pause')).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Geste effectué' })).toHaveTextContent('« Ventes » en pause')
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

  it('Déplacer… vers un autre projet : la ligne part tout de suite, Annuler la remet', async () => {
    api.traiterLot.mockResolvedValue({ data: { appliquees: [20], refusees: [], geste_id: 91 } })
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    const etape = await ouvrirMenu(user, 'Devis Settat')
    await user.click(await screen.findByRole('menuitem', { name: 'Déplacer…' }))
    await user.click(await screen.findByRole('option', { name: 'Site web' }))
    expect(api.traiterLot).toHaveBeenCalledWith({ ids: [20], action: 'deplacer', valeurs: { projet_id: 5 } })
    await waitFor(() => expect(within(etape).queryByRole('button', { name: 'Devis Settat' })).toBeNull())
    expect(screen.getByRole('group', { name: 'Geste effectué' })).toHaveTextContent('Déplacée dans « Site web »')
    await user.click(screen.getByRole('button', { name: 'Annuler' }))
    expect(api.annulerGeste).toHaveBeenCalledWith(91)
    expect(await within(etape).findByRole('button', { name: 'Devis Settat' })).toBeInTheDocument()
    expect(api.lireVueProjet).toHaveBeenCalledTimes(1)
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
    await user.click(await screen.findByRole('menuitem', { name: 'Déplacer…' }))
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
  it('le menu porte les trois entrées et « Supprimer le projet… » ouvre le dialogue', async () => {
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    await screen.findByText('12 sur 20 · échéance 15/12')
    await user.click(screen.getByRole('button', { name: "Plus d'actions" }))
    const menu = await screen.findByRole('menu')
    const libelles = within(menu).getAllByRole('menuitem').map((m) => m.textContent)
    expect(libelles).toEqual(expect.arrayContaining(['Décaler les dates…', 'Terminer le projet…', 'Supprimer le projet…', 'Planifier le projet', "Voir dans l'agenda"]))
    await user.click(within(menu).getByRole('menuitem', { name: 'Supprimer le projet…' }))
    expect(await screen.findByRole('dialog', { name: 'Supprimer le projet' })).toHaveTextContent('Supprimer « Ventes » et ses 20 tâches ?')
  })
})
