import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat } from '../../../test/fixtures/contractSamples'
import { ZoneAnnonces } from '../coquille/CoquilleTaches'
import { reinitialiserGestes } from '../lib/gestes'
import Fiche from './Fiche'

const api = vi.hoisted(() => ({
  lireTache: vi.fn(), modifierTache: vi.fn(), planifierTache: vi.fn(), terminerTache: vi.fn(), rouvrirTache: vi.fn(),
  marquerEssentiel: vi.fn(), repeterRappel: vi.fn(), annulerGeste: vi.fn(), ajouterPoint: vi.fn(), modifierPoint: vi.fn(),
  retirerPoint: vi.fn(), listerTousLesProjets: vi.fn(), creerProjet: vi.fn(), modifierReglages: vi.fn(),
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
    monter()
    expect(await screen.findByRole('textbox', { name: 'Titre' })).toHaveValue('Devis Settat')
    expect(api.lireTache).toHaveBeenCalledWith(20)
    expect(screen.getByRole('button', { name: /Quand je la fais/ })).toHaveTextContent('aujourd\'hui · 10:00')
    expect(screen.getByLabelText('Échéance')).toHaveValue('2026-11-19')
    expect(screen.getByRole('button', { name: /Projet/ })).toHaveTextContent('Ventes')
    expect(within(screen.getByRole('radiogroup', { name: 'Priorité' })).getByRole('radio', { name: 'Moyenne' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('checkbox', { name: 'Essentielle : Devis Settat' })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByRole('textbox', { name: 'Notes' })).toHaveValue('Appeler avant 11 h.')
    expect(screen.getByText('Prix')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Ajouter un point' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Fait' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reporter à mer. 18' })).toBeInTheDocument()
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
