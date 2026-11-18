import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import ATrier from '../../../pages/taches/ATrier'
import Reglages from '../../../pages/taches/Reglages'
import { exempleContrat } from '../../../test/fixtures/contractSamples'
import { reinitialiserGestes } from '../lib/gestes'

const api = vi.hoisted(() => ({
  listerToutesLesTaches: vi.fn(), lireAujourdhui: vi.fn(), listerSuggestions: vi.fn(), accepterSuggestion: vi.fn(),
  refuserSuggestion: vi.fn(), annulerGeste: vi.fn(), lireReglages: vi.fn(), modifierReglages: vi.fn(),
  listerAgendasExternes: vi.fn(), listerJetons: vi.fn(),
}))
vi.mock('../../../api/tachesApi', async (importOriginal) => ({ ...(await importOriginal()), ...api }))

/* TCH167 — « Suggéré par l'ERP » dans À trier (Ajouter, Pas utile) et Réglages → « L'ERP me suggère ».
   Réponses = `suggestions.json`, `suggestion_refusee.json`, `tache_ecrite.json`, `reglages.json`, `aujourdhui.json`
   du contrat ; le serveur des réglages est gardé en mémoire (enregistrer → relire rend ce qui a été écrit). */

const exemple = (nom) => structuredClone(exempleContrat('taches', nom))
const suggestions = exemple('suggestions')
const refusee = exemple('suggestion_refusee')
const ecrite = exemple('tache_ecrite')
const AUJOURD = '2026-11-17'
const erreurHttp = (data, status) => Object.assign(new Error('http'), { response: { status, data } })
const TITRE_PROPOSE = suggestions.results[0].titre

describe('TCH167 — Suggéré par l\'ERP dans À trier', () => {
  const monter = () => render(
    <MemoryRouter initialEntries={['/taches/a-trier']}><ATrier aujourdhui={AUJOURD} /></MemoryRouter>,
  )
  const section = () => screen.findByRole('region', { name: "Suggéré par l'ERP" })
  const tacheExistante = { ...ecrite.tache, id: 41, titre: 'Appeler Karim', projet: null, jour_prevu: null }

  beforeEach(() => {
    api.listerToutesLesTaches.mockResolvedValue([tacheExistante])
    api.lireAujourdhui.mockResolvedValue({ data: exemple('aujourdhui') })
    api.listerSuggestions.mockResolvedValue({ data: structuredClone(suggestions) })
    api.accepterSuggestion.mockResolvedValue({ data: structuredClone(ecrite) })
    api.refuserSuggestion.mockResolvedValue({ data: structuredClone(refusee) })
    api.annulerGeste.mockResolvedValue({ data: { restaurees: [], conflits: [], deja: false } })
  })
  afterEach(() => {
    vi.clearAllMocks()
    reinitialiserGestes()
  })

  it('montre la suggestion : titre proposé, « Lié à : {libellé} » (lien vers la fiche), Ajouter, Pas utile', async () => {
    monter()
    const region = await section()
    expect(within(region).getByRole('textbox', { name: `Titre : ${TITRE_PROPOSE}` })).toHaveValue(TITRE_PROPOSE)
    expect(within(region).getByRole('link', { name: 'Lié à : DEV-2026-11-0042' })).toHaveAttribute('href', '/ventes/devis?devis=512')
    expect(within(region).getByRole('button', { name: 'Ajouter' })).toBeInTheDocument()
    expect(within(region).getByRole('button', { name: 'Pas utile' })).toBeInTheDocument()
  })

  it('Ajouter : la ligne part tout de suite, la tâche arrive dans la liste sans relecture, « Annuler » défait le geste', async () => {
    const user = userEvent.setup()
    monter()
    const region = await section()
    await user.click(within(region).getByRole('button', { name: 'Ajouter' }))
    expect(screen.queryByRole('region', { name: "Suggéré par l'ERP" })).toBeNull()
    expect(api.accepterSuggestion).toHaveBeenCalledWith(5, {})
    expect(await screen.findByText(ecrite.tache.titre)).toBeInTheDocument()
    const toast = await screen.findByRole('group', { name: 'Geste effectué' })
    expect(toast).toHaveTextContent('Ajoutée')
    await user.click(within(toast).getByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(api.annulerGeste).toHaveBeenCalledWith(ecrite.geste_id))
    expect(await section()).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByText(ecrite.tache.titre)).toBeNull())
    expect(api.listerToutesLesTaches).toHaveBeenCalledTimes(1)
    expect(api.listerSuggestions).toHaveBeenCalledTimes(1)
  })

  it('Ajouter avec un titre modifié envoie ce titre', async () => {
    const user = userEvent.setup()
    monter()
    const region = await section()
    const champ = within(region).getByRole('textbox', { name: `Titre : ${TITRE_PROPOSE}` })
    await user.clear(champ)
    await user.type(champ, 'Appeler le client du chantier')
    await user.click(within(region).getByRole('button', { name: 'Ajouter' }))
    await waitFor(() => expect(api.accepterSuggestion).toHaveBeenCalledWith(5, { titre: 'Appeler le client du chantier' }))
  })

  it('Pas utile : la ligne part, le serveur refuse la suggestion, « Annuler » la ramène', async () => {
    const user = userEvent.setup()
    monter()
    const region = await section()
    await user.click(within(region).getByRole('button', { name: 'Pas utile' }))
    expect(screen.queryByRole('region', { name: "Suggéré par l'ERP" })).toBeNull()
    expect(api.refuserSuggestion).toHaveBeenCalledWith(5)
    const toast = await screen.findByRole('group', { name: 'Geste effectué' })
    await user.click(within(toast).getByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(api.annulerGeste).toHaveBeenCalledWith(refusee.geste_id))
    expect(await section()).toBeInTheDocument()
  })

  it('un refus du serveur ramène la ligne à sa place avec son erreur dessous', async () => {
    const user = userEvent.setup()
    api.accepterSuggestion.mockRejectedValue(erreurHttp({ titre: ['280 caractères au plus.'] }, 400))
    monter()
    const region = await section()
    await user.click(within(region).getByRole('button', { name: 'Ajouter' }))
    const retour = await section()
    expect(within(retour).getByRole('alert')).toHaveTextContent('280 caractères au plus.')
    expect(within(retour).getByRole('textbox', { name: `Titre : ${TITRE_PROPOSE}` })).toHaveValue(TITRE_PROPOSE)
    expect(screen.queryByText(ecrite.tache.titre)).toBeNull()
  })

  it('une cible sortie de la portée du compte : « Hors de ta portée », ni libellé ni lien inventés', async () => {
    api.listerSuggestions.mockResolvedValue({
      data: { results: [{ ...suggestions.results[0], lien: { cible: 'ventes.devis', id: 512, libelle: null, url: null, etat: 'inaccessible' } }] },
    })
    monter()
    const region = await section()
    expect(within(region).getByText('Hors de ta portée')).toBeInTheDocument()
    expect(within(region).queryByRole('link')).toBeNull()
    expect(region).not.toHaveTextContent('DEV-2026')
    expect(region).not.toHaveTextContent('Lié à')
  })

  it('une suggestion sans cible ne montre aucun lien', async () => {
    api.listerSuggestions.mockResolvedValue({ data: { results: [{ ...suggestions.results[0], lien: null }] } })
    monter()
    const region = await section()
    expect(within(region).queryByRole('link')).toBeNull()
    expect(region).not.toHaveTextContent('Lié à')
  })

  it('sans suggestion, pas de section ; une lecture qui échoue se dit sans toucher la liste', async () => {
    api.listerSuggestions.mockResolvedValue({ data: { results: [] } })
    const { unmount } = monter()
    expect(await screen.findByText('Appeler Karim')).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: "Suggéré par l'ERP" })).toBeNull()
    unmount()

    api.listerSuggestions.mockRejectedValue(erreurHttp({ detail: 'Oups.' }, 500))
    monter()
    expect(await screen.findByText('Appeler Karim')).toBeInTheDocument()
    expect(within(await section()).getByRole('alert')).toBeInTheDocument()
  })
})

describe('TCH167 — Réglages → L\'ERP me suggère', () => {
  let serveur
  const monter = () => render(
    <MemoryRouter initialEntries={['/taches/reglages/suggestions']}>
      <Routes><Route path="/taches/reglages/:rubrique?" element={<Reglages />} /></Routes>
    </MemoryRouter>,
  )

  beforeEach(() => {
    serveur = exemple('reglages')
    api.lireReglages.mockImplementation(async () => ({ data: structuredClone(serveur) }))
    api.modifierReglages.mockImplementation(async (corps) => { Object.assign(serveur, corps); return { data: structuredClone(serveur) } })
    api.listerAgendasExternes.mockResolvedValue({ data: { results: [] } })
    api.listerJetons.mockResolvedValue({ data: { results: [] } })
  })
  afterEach(() => {
    vi.clearAllMocks()
    reinitialiserGestes()
  })

  const interrupteur = (nom) => screen.findByRole('switch', { name: nom })

  it('lit les familles allumées du serveur et le résumé « {k} suggestions sur 4 »', async () => {
    monter()
    expect(await interrupteur('Devis accepté : préparer le chantier')).toBeChecked()
    expect(screen.getByRole('switch', { name: 'Chantier réceptionné : demander un avis' })).toBeChecked()
    expect(screen.getByRole('switch', { name: 'Chantier annulé : comprendre pourquoi' })).toBeChecked()
    expect(screen.getByRole('switch', { name: 'Visite validée : préparer le devis' })).not.toBeChecked()
    expect(screen.getByRole('switch', { name: "Afficher mes activités ERP dans Aujourd'hui" })).toBeChecked()
    expect(screen.getByRole('button', { name: /L'ERP me suggère/ })).toHaveTextContent('3 suggestions sur 4')
    expect(screen.queryByRole('switch', { name: 'Toute la société (administrateur)' })).toBeNull()
  })

  it('allumer une famille écrit la liste entière, le résumé suit, et rouvrir relit la même chose', async () => {
    const user = userEvent.setup()
    const { unmount } = monter()
    await user.click(await interrupteur('Visite validée : préparer le devis'))
    await waitFor(() => expect(api.modifierReglages).toHaveBeenCalledWith({
      familles_suggestions: ['devis_accepte', 'chantier_receptionne', 'chantier_annule', 'visite_validee'],
    }))
    expect(await screen.findByRole('button', { name: /L'ERP me suggère/ })).toHaveTextContent('4 suggestions sur 4')
    unmount()
    monter()
    expect(await interrupteur('Visite validée : préparer le devis')).toBeChecked()
    expect(serveur.familles_suggestions).toEqual(['devis_accepte', 'chantier_receptionne', 'chantier_annule', 'visite_validee'])
  })

  it('éteindre une famille la retire de la liste écrite', async () => {
    const user = userEvent.setup()
    monter()
    await user.click(await interrupteur('Chantier annulé : comprendre pourquoi'))
    await waitFor(() => expect(api.modifierReglages).toHaveBeenCalledWith({ familles_suggestions: ['devis_accepte', 'chantier_receptionne'] }))
    expect(screen.getByRole('switch', { name: 'Chantier annulé : comprendre pourquoi' })).not.toBeChecked()
  })

  it('« Afficher mes activités ERP dans Aujourd\'hui » écrit `erp_dans_journee`', async () => {
    const user = userEvent.setup()
    monter()
    await user.click(await interrupteur("Afficher mes activités ERP dans Aujourd'hui"))
    await waitFor(() => expect(api.modifierReglages).toHaveBeenCalledWith({ erp_dans_journee: false }))
  })

  it('l\'administrateur voit « Toute la société » ; un refus du serveur s\'affiche sous le réglage, rien ne bascule', async () => {
    const user = userEvent.setup()
    serveur.est_admin = true
    monter()
    await user.click(await interrupteur('Toute la société (administrateur)'))
    await waitFor(() => expect(api.modifierReglages).toHaveBeenCalledWith({ suggestions_societe: true }))
    expect(screen.getByRole('switch', { name: 'Toute la société (administrateur)' })).toBeChecked()

    api.modifierReglages.mockRejectedValueOnce(erreurHttp({ suggestions_societe: ['Réservé à un administrateur.'] }, 403))
    await user.click(screen.getByRole('switch', { name: 'Toute la société (administrateur)' }))
    expect(await screen.findByText('Réservé à un administrateur.')).toBeInTheDocument()
    expect(screen.getByRole('switch', { name: 'Toute la société (administrateur)' })).toBeChecked()
  })
})
