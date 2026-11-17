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
    expect(screen.getByText('Faites (12)')).toBeInTheDocument()
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

describe('TCH89 — Un projet : ajouter une tâche', () => {
  it('« Ajouter une tâche » dans une étape crée la tâche dans cette étape', async () => {
    const creee = tacheEcrite()
    creee.tache.id = 77
    creee.tache.titre = 'Relancer Settat'
    creee.tache.jour_prevu = null
    api.creerTache.mockResolvedValue({ data: creee })
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    const etape = await screen.findByRole('region', { name: 'Études' })
    await user.click(within(etape).getByRole('button', { name: 'Ajouter une tâche' }))
    await user.type(within(etape).getByLabelText('Ajouter une tâche'), 'Relancer Settat{Enter}')
    expect(api.creerTache).toHaveBeenCalledWith({
      titre: 'Relancer Settat', projet_id: 3, section_id: 8, client_id: expect.any(String),
    })
    expect(await within(etape).findByRole('button', { name: 'Relancer Settat' })).toBeInTheDocument()
    expect(screen.getByText('12 sur 21 · échéance 15/12')).toBeInTheDocument()
  })

  it('un refus du serveur s\'affiche sous le champ et la saisie reste', async () => {
    api.creerTache.mockRejectedValue({ response: { status: 400, data: { titre: ['Le titre est vide.'] } } })
    monter()
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
    const etape = await screen.findByRole('region', { name: 'Études' })
    await user.click(within(etape).getByRole('button', { name: 'Ajouter une tâche' }))
    const champ = within(etape).getByLabelText('Ajouter une tâche')
    await user.type(champ, 'x{Enter}')
    expect(await within(etape).findByRole('alert')).toHaveTextContent('Le titre est vide.')
    expect(champ).toHaveAttribute('aria-invalid', 'true')
    expect(champ).toHaveValue('x')
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
