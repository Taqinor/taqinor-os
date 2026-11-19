import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat } from '../../../test/fixtures/contractSamples'
import { ZoneAnnonces } from '../coquille/CoquilleTaches'
import { EVENEMENT_CREEES, EVENEMENT_ECRITE, useApresCreation } from '../lib/fiche'
import { reinitialiserGestes } from '../lib/gestes'
import Fiche from './Fiche'

const api = vi.hoisted(() => ({
  lireTache: vi.fn(), modifierTache: vi.fn(), planifierTache: vi.fn(), terminerTache: vi.fn(), rouvrirTache: vi.fn(),
  marquerEssentiel: vi.fn(), repeterRappel: vi.fn(), annulerGeste: vi.fn(), ajouterPoint: vi.fn(), modifierPoint: vi.fn(),
  retirerPoint: vi.fn(), listerTousLesProjets: vi.fn(), creerProjet: vi.fn(), modifierReglages: vi.fn(), trancherTache: vi.fn(),
}))
vi.mock('../../../api/tachesApi', async (importOriginal) => ({ ...(await importOriginal()), ...api }))

/* TCH84 — la fiche d'une tâche : champs, enregistrement par champ, erreur sous le champ,
   conflit entre deux appareils SANS perte, rappel ouvert. Réponses = échantillons du contrat. */

const tache = exempleContrat('taches', 'tache')
const ecrite = exempleContrat('taches', 'tache_ecrite')
const recurrente = exempleContrat('taches', 'tache_recurrente_ecrite')
const rappel = exempleContrat('taches', 'rappel_repeter')
const erreurs = exempleContrat('taches', 'erreurs')
const AUJOURDHUI = '2026-11-17'

const erreurHttp = (data, status) => Object.assign(new Error('http'), { response: { status, data } })
const monter = (props = {}) => render(
  <div className="tch"><Fiche id={20} aujourdhui={AUJOURDHUI} onFermer={() => {}} {...props} /><ZoneAnnonces /></div>,
)

beforeEach(() => {
  api.lireTache.mockResolvedValue({ data: tache })
  api.modifierTache.mockResolvedValue({ data: ecrite })
  api.planifierTache.mockResolvedValue({ data: ecrite })
  api.terminerTache.mockResolvedValue({ data: recurrente })
  api.rouvrirTache.mockResolvedValue({ data: ecrite })
  api.marquerEssentiel.mockResolvedValue({ data: ecrite })
  api.repeterRappel.mockResolvedValue({ data: rappel })
  api.annulerGeste.mockResolvedValue({ data: {} })
  api.listerTousLesProjets.mockResolvedValue([exempleContrat('taches', 'projets_liste').results[0]])
})
afterEach(() => {
  vi.clearAllMocks()
  reinitialiserGestes()
})

describe('TCH84 — fiche d\'une tâche', () => {
  it('montre Quand · Échéance · Projet · Priorité · Essentielle · Notes · Check-list de la tâche lue', async () => {
    const user = userEvent.setup()
    monter()
    expect(await screen.findByRole('textbox', { name: 'Titre' })).toHaveValue('Devis Settat')
    expect(api.lireTache).toHaveBeenCalledWith(20)
    expect(screen.getByRole('button', { name: /Quand je la fais/ })).toHaveTextContent('Aujourd\'hui · 10:00')
    await user.click(screen.getByRole('button', { name: 'Échéance : jeu. 19' }))
    expect(screen.getByLabelText('Échéance')).toHaveValue('2026-11-19')
    expect(screen.getByRole('button', { name: /Projet/ })).toHaveTextContent('Ventes')
    await user.click(screen.getByRole('button', { name: 'Priorité : moyenne' }))
    expect(within(screen.getByRole('radiogroup', { name: 'Priorité' })).getByRole('radio', { name: 'Moyenne' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('checkbox', { name: 'Essentielle : Devis Settat' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('textbox', { name: 'Notes' })).toHaveValue('Appeler avant 11 h.')
    expect(screen.getByText('Prix')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Ajouter un point' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Fait' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reporter à mer. 18' })).toBeInTheDocument()
  })

  it('passe visuelle n° 27/57 — Quand · Échéance · Projet · Priorité sont des PUCES (plus de formulaire en liste)', async () => {
    const user = userEvent.setup()
    const { container } = monter()
    await screen.findByRole('textbox', { name: 'Titre' })
    const puces = container.querySelector('.puces.fiche-champs')
    expect([...puces.querySelectorAll('button.puce')].map((b) => b.textContent)).toEqual(
      ['Aujourd\'hui · 10:00', 'échéance jeu. 19', 'Ventes', 'Priorité moyenne'],
    )
    expect(within(puces).getByRole('button', { name: 'Projet : Ventes' })).toHaveAttribute('data-p', 'vert')
    expect(container.querySelector('.fiche-ligne')).toBeNull()
    expect(screen.queryByText('Quand je la fais')).toBeNull()
    // une priorité posée est MARQUÉE dans le choix qui s'ouvre sous la puce
    await user.click(within(puces).getByRole('button', { name: 'Priorité : moyenne' }))
    expect(screen.getByRole('radio', { name: 'Moyenne' })).toHaveAttribute('aria-checked', 'true')
    await user.click(screen.getByRole('radio', { name: 'Haute' }))
    await waitFor(() => expect(api.modifierTache).toHaveBeenCalledWith(20, { priorite: 3, lock_version: 4 }))
  })

  it('passe visuelle n° 27 — sans échéance, sans projet, sans priorité : puces vides, aucun champ date nu', async () => {
    api.lireTache.mockResolvedValue({ data: { ...tache, echeance: null, projet: null, priorite: 0 } })
    const { container } = monter()
    await screen.findByRole('textbox', { name: 'Titre' })
    const vides = [...container.querySelectorAll('.fiche-champs .puce.vide')].map((b) => b.textContent)
    expect(vides).toEqual(['Échéance', 'Sans projet', 'Priorité'])
    expect(container.querySelector('input[type="date"]')).toBeNull()
  })

  it('passe visuelle n° 30/31 — UN seul titre ; ☆ et ⋯ dans l\'en-tête ; ⋯ = Abandonner · Supprimer', async () => {
    const user = userEvent.setup()
    api.trancherTache.mockResolvedValue({ data: { geste_id: 5 } })
    const onFermer = vi.fn()
    const { container } = monter({ onFermer })
    await screen.findByRole('textbox', { name: 'Titre' })
    // le titre ne s'écrit qu'une fois À L'ÉCRAN : celui de la barre est masqué (nom du dialogue gardé)
    expect(screen.getByRole('dialog', { name: 'Devis Settat' })).toBeInTheDocument()
    expect(container.querySelector('.fiche .feuille-entete .feuille-titre')).not.toBeNull()
    const actions = container.querySelector('.fiche-entete-actions')
    expect(within(actions).getByRole('checkbox', { name: 'Essentielle : Devis Settat' })).toBeInTheDocument()
    await user.click(within(actions).getByRole('button', { name: 'Actions' }))
    await user.click(await screen.findByRole('menuitem', { name: 'Supprimer' }))
    expect(await screen.findByRole('alertdialog', { name: 'Supprimer « Devis Settat »' })).toBeInTheDocument()
    await user.click(within(actions).getByRole('button', { name: 'Actions' }))
    await user.click(await screen.findByRole('menuitem', { name: 'Abandonner' }))
    await waitFor(() => expect(api.trancherTache).toHaveBeenCalledWith(20, { choix: 'abandonner' }))
    await waitFor(() => expect(onFermer).toHaveBeenCalled())
  })

  it('relecture adverse F4 n° 5 — Échap ferme le menu ⋯ de l\'en-tête, PAS la fiche', async () => {
    const user = userEvent.setup()
    const onFermer = vi.fn()
    const { container } = monter({ onFermer })
    await screen.findByRole('textbox', { name: 'Titre' })
    const actions = container.querySelector('.fiche-entete-actions')
    await user.click(within(actions).getByRole('button', { name: 'Actions' }))
    expect(await screen.findByRole('menuitem', { name: 'Abandonner' })).toBeInTheDocument()
    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('menuitem', { name: 'Abandonner' })).toBeNull())
    expect(onFermer).not.toHaveBeenCalled()
    // menu fermé : Échap ferme maintenant la fiche, comme avant
    await user.keyboard('{Escape}')
    expect(onFermer).toHaveBeenCalled()
  })

  it('passe visuelle n° 29/56 — « ✓ Fait » vert (bouton fait) ; « Plus » avec indice et chevron, nom lu « Plus »', async () => {
    monter()
    await screen.findByRole('textbox', { name: 'Titre' })
    const fait = screen.getByRole('button', { name: 'Fait' })
    expect(fait).toHaveClass('bouton', 'fait')
    expect(fait).not.toHaveClass('plein')
    expect(fait.querySelector('svg')).not.toBeNull()
    expect(screen.getByRole('button', { name: /^Reporter à/ })).toHaveClass('accent')
    const plus = screen.getByRole('button', { name: 'Plus' })
    expect(plus).toHaveTextContent('Répéter, durée, étiquettes, en attente de…')
    expect(screen.getByText('1/1')).toBeInTheDocument() // compte de la check-list
  })

  it('une tâche introuvable est dite, la fiche reste montée', async () => {
    api.lireTache.mockRejectedValue(erreurHttp(erreurs.introuvable, 404))
    const { container } = monter()
    expect(await screen.findByText('Introuvable.')).toBeInTheDocument()
    expect(container.querySelector('[data-fiche="20"]')).not.toBeNull()
  })

  it('Quand : « Demain » planifie avec le lock_version, l\'avertissement du serveur est dit, toast Annuler', async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByRole('textbox', { name: 'Titre' })
    await user.click(screen.getByRole('button', { name: /Quand je la fais/ }))
    await user.click(screen.getByRole('radio', { name: /Demain/ }))
    await waitFor(() => expect(api.planifierTache).toHaveBeenCalledTimes(1))
    expect(api.planifierTache).toHaveBeenCalledWith(20, expect.objectContaining({ jour_prevu: '2026-11-18', quelque_jour: false, lock_version: 4 }))
    expect(await screen.findByText('Prévue après l\'échéance.')).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Geste effectué' })).toHaveTextContent('Prévue demain')
    await user.click(screen.getByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(api.annulerGeste).toHaveBeenCalledWith(77))
  })

  it('une erreur du serveur s\'affiche SOUS le champ fautif', async () => {
    const user = userEvent.setup()
    api.planifierTache.mockRejectedValue(erreurHttp({ heure_debut: ['Une heure demande un jour prévu.'] }, 400))
    monter()
    await screen.findByRole('textbox', { name: 'Titre' })
    await user.click(screen.getByRole('button', { name: /Quand je la fais/ }))
    await user.click(screen.getByRole('radio', { name: 'Sans jour' }))
    const alerte = await screen.findByRole('alert')
    expect(alerte).toHaveTextContent('Une heure demande un jour prévu.')
    expect(screen.getByRole('button', { name: /Quand je la fais/ }).getAttribute('aria-describedby')).toBe(alerte.id)
  })

  it('Fait : la tâche est terminée, le bouton devient « Rouvrir », toast « Faite · Annuler »', async () => {
    const user = userEvent.setup()
    monter()
    await screen.findByRole('textbox', { name: 'Titre' })
    await user.click(screen.getByRole('button', { name: 'Fait' }))
    expect(await screen.findByRole('button', { name: 'Rouvrir' })).toBeInTheDocument()
    expect(api.terminerTache).toHaveBeenCalledWith(20, {})
    expect(screen.getByRole('group', { name: 'Geste effectué' })).toHaveTextContent('Faite')
    await user.click(screen.getByRole('button', { name: 'Rouvrir' }))
    await waitFor(() => expect(api.rouvrirTache).toHaveBeenCalledWith(20))
  })

  it('conflit entre deux appareils : la saisie reste, « Prendre l\'autre » adopte l\'autre tâche sans la vider', async () => {
    const user = userEvent.setup()
    api.modifierTache.mockRejectedValueOnce(erreurHttp(erreurs.conflit_version, 409))
    monter()
    const champ = await screen.findByRole('textbox', { name: 'Notes' })
    await user.clear(champ)
    await user.type(champ, 'Rappeler Karim avant 9 h')
    await user.tab()
    expect(await screen.findByRole('group', { name: 'Conflit entre appareils' })).toBeInTheDocument()
    // F2 acceptation (P144.1) — l'heure vient de la réponse 409 (`actuel.updated_at` = 10:42), jamais de l'horloge
    expect(screen.getByRole('group', { name: 'Conflit entre appareils' })).toHaveTextContent('Modifiée sur ton autre appareil à 10:42')
    expect(screen.getByRole('textbox', { name: 'Notes' })).toHaveValue('Rappeler Karim avant 9 h')
    await user.click(screen.getByRole('button', { name: 'Prendre l\'autre' }))
    expect(screen.queryByRole('group', { name: 'Conflit entre appareils' })).toBeNull()
    expect(screen.getByRole('textbox', { name: 'Notes' })).toHaveValue('Rappeler Karim avant 9 h')
    expect(api.modifierTache).toHaveBeenCalledTimes(1)
  })

  it('conflit : « Garder la mienne » renvoie la saisie avec la version de l\'autre', async () => {
    const user = userEvent.setup()
    api.modifierTache.mockRejectedValueOnce(erreurHttp(erreurs.conflit_version, 409))
    monter()
    const champ = await screen.findByRole('textbox', { name: 'Notes' })
    await user.clear(champ)
    await user.type(champ, 'Ma version')
    await user.tab()
    await user.click(await screen.findByRole('button', { name: 'Garder la mienne' }))
    await waitFor(() => expect(api.modifierTache).toHaveBeenCalledTimes(2))
    expect(api.modifierTache).toHaveBeenLastCalledWith(20, { notes: 'Ma version', lock_version: erreurs.conflit_version.lock_version })
    await waitFor(() => expect(screen.queryByRole('group', { name: 'Conflit entre appareils' })).toBeNull())
  })

  it('ouverte par un rappel envoyé : Encore 10 min · Encore 1 h · Demain 9 h', async () => {
    const user = userEvent.setup()
    api.lireTache.mockResolvedValue({ data: { ...tache, rappels: [{ id: 31, jour: AUJOURDHUI, heure: '09:45', ancre: '', decalage_jours: 0, statut: 'envoye' }] } })
    monter()
    await screen.findByRole('button', { name: 'Encore 10 min' })
    expect(screen.getByRole('button', { name: 'Demain 9 h' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Encore 1 h' }))
    await waitFor(() => expect(api.repeterRappel).toHaveBeenCalledWith(31, { dans_minutes: 60 }))
    expect(screen.getByRole('group', { name: 'Geste effectué' })).toHaveTextContent('Rappel dans 1 h')
  })

  it('une tâche sans rappel envoyé n\'a pas la rangée « Encore »', async () => {
    monter()
    await screen.findByRole('textbox', { name: 'Titre' })
    expect(screen.queryByRole('button', { name: 'Encore 10 min' })).toBeNull()
  })

  it('R2-040 — chaque écriture réussie (Fait, Quand) et la fermeture préviennent les écrans : `taqinor:taches:ecrite`', async () => {
    const user = userEvent.setup()
    const recu = vi.fn()
    window.addEventListener('taqinor:taches:ecrite', recu)
    try {
      const { unmount } = monter()
      await screen.findByRole('textbox', { name: 'Titre' })
      expect(recu).not.toHaveBeenCalled() // une simple lecture ne dérange personne
      await user.click(screen.getByRole('button', { name: 'Fait' }))
      await waitFor(() => expect(recu).toHaveBeenCalledTimes(1))
      expect(recu.mock.calls[0][0].detail.tache).toEqual(recurrente.tache ?? recurrente)
      await user.click(screen.getByRole('button', { name: /Quand je la fais/ }))
      await user.click(screen.getByRole('radio', { name: /Demain/ }))
      await waitFor(() => expect(recu).toHaveBeenCalledTimes(2))
      unmount()
      expect(recu).toHaveBeenCalledTimes(3)
    } finally {
      window.removeEventListener('taqinor:taches:ecrite', recu)
    }
  })

  it('R2-040 — `useApresCreation` relit l\'écran après une création ET après une écriture de la fiche', () => {
    const rappel = vi.fn()
    function Ecran() { useApresCreation(rappel); return null }
    render(<Ecran />)
    act(() => { window.dispatchEvent(new CustomEvent(EVENEMENT_CREEES, { detail: { creees: [] } })) })
    act(() => { window.dispatchEvent(new CustomEvent(EVENEMENT_ECRITE, { detail: { tache: { id: 20 } } })) })
    expect(rappel).toHaveBeenCalledTimes(2)
    expect(rappel.mock.calls[1][0]).toEqual({ tache: { id: 20 } })
  })

  it('check-list : « Ajouter un point » écrit au serveur, le point apparaît sans relire la tâche', async () => {
    const user = userEvent.setup()
    api.ajouterPoint.mockResolvedValue({ data: { id: 72, libelle: 'Devis signé', fait: false, rang: 2048 } })
    monter()
    await screen.findByRole('textbox', { name: 'Titre' })
    await user.type(screen.getByRole('textbox', { name: 'Ajouter un point' }), 'Devis signé{Enter}')
    expect(await screen.findByText('Devis signé')).toBeInTheDocument()
    expect(api.ajouterPoint).toHaveBeenCalledWith({ tache_id: 20, libelle: 'Devis signé' })
    expect(api.lireTache).toHaveBeenCalledTimes(1)
  })
})
