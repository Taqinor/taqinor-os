import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { exempleContrat } from '../../../test/fixtures/contractSamples'
import { reinitialiserGestes } from '../lib/gestes'

vi.mock('../../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() },
}))

const api = (await import('../../../api/axios')).default
const { default: Aujourdhui } = await import('../../../pages/taches/Aujourdhui')

/* TCH81 — les lignes de l'ERP sur Aujourd'hui, sur aujourdhui.json, ailleurs.json et lier_activite.json :
   activité (badge ERP, case seulement si `peut_cloturer`, sans Annuler), Ailleurs dans l'ERP lu à
   l'ouverture seulement, « Lier une tâche » (l'activité reste ouverte), À revoir (Tout en réserve,
   Aujourd'hui · Choisir un jour · En réserve · Abandonner · Découper). */

const contrat = (nom) => structuredClone(exempleContrat('taches', nom))
const journee = () => {
  const d = contrat('aujourdhui')
  d.carte_du_moment = null
  return d
}

function servir({ aujourdhui = journee(), ailleurs = () => Promise.resolve({ data: contrat('ailleurs') }) } = {}) {
  api.get.mockImplementation((url) => {
    if (url === '/taches/aujourdhui/') return Promise.resolve({ data: aujourdhui })
    if (url === '/taches/aujourdhui/ailleurs/') return ailleurs()
    return Promise.reject(new Error(`GET inattendu ${url}`))
  })
  api.post.mockImplementation((url) => {
    if (url === '/taches/taches/lier-activite/') return Promise.resolve({ data: contrat('lier_activite') })
    if (url === '/taches/taches/lot/') return Promise.resolve({ data: { appliquees: [50], refusees: [], geste_id: 78 } })
    if (url.endsWith('/trancher/')) return Promise.resolve({ data: { ...contrat('tache_ecrite'), geste_id: 79 } })
    return Promise.resolve({ data: {} })
  })
}

const monter = () => render(
  <MemoryRouter initialEntries={['/taches/aujourdhui']}>
    <Routes>
      <Route path="/taches/aujourdhui" element={<Aujourdhui />} />
      <Route path="/activites" element={<p>Écran des activités</p>} />
    </Routes>
  </MemoryRouter>,
)
const ouvrirActions = (titre) => userEvent.click(screen.getByRole('button', { name: `Actions pour « ${titre} »` }))
const appelsAilleurs = () => api.get.mock.calls.filter((c) => c[0] === '/taches/aujourdhui/ailleurs/')

beforeEach(() => {
  vi.clearAllMocks()
  reinitialiserGestes()
  window.localStorage.clear()
  Object.defineProperty(window.navigator, 'onLine', { value: true, configurable: true })
})

describe('TCH81 — activités ERP', () => {
  it('badge « Activité ERP », lien vers le lead, pas de case quand elle ne peut pas se clore', async () => {
    servir()
    monter()
    const ligne = (await screen.findByText('Rappeler Benali')).closest('[data-ligne]')
    expect(within(ligne).getByText('Activité ERP')).toBeInTheDocument()
    expect(ligne).toHaveTextContent('Karim Benali')
    expect(within(ligne).queryByRole('checkbox')).toBeNull()
  })

  it('une activité qui peut se clore a sa case : close dans l\'ERP, sans Annuler', async () => {
    const d = journee()
    d.journee.find((i) => i.type === 'activite').peut_cloturer = true
    servir({ aujourdhui: d })
    monter()
    await screen.findByText('Rappeler Benali')
    fireEvent.click(screen.getByRole('checkbox', { name: 'Marquer « Rappeler Benali » comme faite' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/records/activities/101/done/', {}))
    expect(await screen.findByRole('group', { name: 'Geste effectué' })).toHaveTextContent("Close dans l'ERP")
    expect(screen.queryByRole('button', { name: 'Annuler' })).toBeNull()
  })
})

describe('TCH81 — Ailleurs dans l\'ERP', () => {
  it('n\'est lu qu\'à l\'ouverture ; ne montre que les familles non vides ; une ligne mène à l\'ERP', async () => {
    servir()
    monter()
    await screen.findByText('Devis Settat')
    expect(appelsAilleurs()).toHaveLength(0)
    await userEvent.click(screen.getByRole('button', { name: "Ailleurs dans l'ERP" }))
    const chantiers = await screen.findByRole('listitem', { name: 'Chantiers : 1. Ouvrir' })
    expect(appelsAilleurs()).toHaveLength(1)
    expect(screen.getByRole('listitem', { name: 'Leads chauds : 3. Ouvrir' })).toBeInTheDocument()
    expect(screen.getByRole('listitem', { name: 'Devis expirant : 1. Ouvrir' })).toBeInTheDocument()
    expect(screen.queryByRole('listitem', { name: /^Tickets/ })).toBeNull()
    await userEvent.click(chantiers)
    expect(await screen.findByText('Écran des activités')).toBeInTheDocument()
  })

  it('Raccord F2 — une famille absente de la réponse ou servie à 0 (approbations, mentions) n\'a pas de ligne : aucun 0 inventé', async () => {
    const { chantiers, ...sansChantiers } = contrat('ailleurs')
    expect(chantiers).toBeDefined()
    servir({ ailleurs: () => Promise.resolve({ data: { ...sansChantiers, approbations: 0, mentions: 0, relances: 2 } }) })
    monter()
    await screen.findByText('Devis Settat')
    await userEvent.click(screen.getByRole('button', { name: "Ailleurs dans l'ERP" }))
    expect(await screen.findByRole('listitem', { name: 'Relances : 2. Ouvrir' })).toBeInTheDocument()
    expect(screen.queryByRole('listitem', { name: /^Chantiers/ })).toBeNull()
    expect(screen.queryByRole('listitem', { name: /^Approbations/ })).toBeNull()
    expect(screen.queryByRole('listitem', { name: /^Mentions/ })).toBeNull()
    expect(screen.queryByText(/ 0\. Ouvrir/)).toBeNull()
  })

  it('une famille illisible est dite, avec Réessayer', async () => {
    let appel = 0
    servir({ ailleurs: () => (appel++ === 0 ? Promise.reject(new Error('Network Error')) : Promise.resolve({ data: contrat('ailleurs') })) })
    monter()
    await screen.findByText('Devis Settat')
    await userEvent.click(screen.getByRole('button', { name: "Ailleurs dans l'ERP" }))
    expect(await screen.findByText("Certaines informations de l'ERP n'ont pas pu être lues.")).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Réessayer' }))
    expect(await screen.findByRole('listitem', { name: 'Chantiers : 1. Ouvrir' })).toBeInTheDocument()
  })
})

describe('TCH81 — Lier une tâche', () => {
  it('appui long (Actions) → Lier une tâche : crée la tâche liée, l\'activité reste ouverte, Annuler proposé', async () => {
    servir()
    monter()
    await screen.findByText('Rappeler Benali')
    await ouvrirActions('Rappeler Benali')
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Lier une tâche' }))
    const feuille = await screen.findByRole('dialog', { name: 'Lier une tâche' })
    expect(within(feuille).getByRole('textbox', { name: 'Titre de la tâche' })).toHaveValue('Rappeler Benali')
    await userEvent.click(within(feuille).getByRole('button', { name: 'Lier une tâche' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/taches/taches/lier-activite/', { activite_id: 101, titre: 'Rappeler Benali', jour_prevu: null }, expect.anything(),
    ))
    expect(await screen.findByText("Préparer l'appel Benali")).toBeInTheDocument()
    expect(screen.getByText('Rappeler Benali')).toBeInTheDocument()
    expect(await screen.findByRole('group', { name: 'Geste effectué' })).toHaveTextContent("Tâche liée à l'activité")
  })

  it('déjà liée : le serveur le dit (409 deja_lie), rien n\'est ajouté', async () => {
    servir()
    monter()
    await screen.findByText('Rappeler Benali')
    api.post.mockRejectedValue(Object.assign(new Error('409'), {
      response: { status: 409, data: contrat('erreurs').deja_lie, headers: {} },
    }))
    await ouvrirActions('Rappeler Benali')
    await userEvent.click(await screen.findByRole('menuitem', { name: 'Lier une tâche' }))
    await userEvent.click(within(await screen.findByRole('dialog', { name: 'Lier une tâche' })).getByRole('button', { name: 'Lier une tâche' }))
    await waitFor(() => expect(screen.getAllByRole('status').some((n) => n.textContent.includes('Cette activité a déjà sa tâche.'))).toBe(true))
    expect(screen.queryByText("Préparer l'appel Benali")).toBeNull()
  })
})

describe('TCH81 — À revoir', () => {
  const ouvrirARevoir = async () => {
    servir()
    monter()
    await screen.findByText('Devis Settat')
    await userEvent.click(screen.getByRole('button', { name: /^À revoir/ }))
    return (await screen.findByText('Site web')).closest('[data-ligne]')
  }

  it('Tout en réserve : lot planifier quelque_jour ; la ligne part, « 1 en réserve · Annuler »', async () => {
    await ouvrirARevoir()
    await userEvent.click(screen.getByRole('button', { name: 'Tout en réserve' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/taches/taches/lot/', { ids: [50], action: 'planifier', valeurs: { quelque_jour: true } }, expect.anything(),
    ))
    await waitFor(() => expect(screen.queryByText('Site web')).toBeNull())
    expect(await screen.findByRole('group', { name: 'Geste effectué' })).toHaveTextContent('1 en réserve')
  })

  it('par ligne : Aujourd\'hui · Choisir un jour · En réserve · Abandonner · Découper (reportée 3 fois)', async () => {
    const ligne = await ouvrirARevoir()
    const actions = within(ligne.parentElement).getByRole('group', { name: 'Que faire de « Site web » ?' })
    expect(within(actions).getAllByRole('button').map((b) => b.textContent)).toEqual([
      "Aujourd'hui", 'Choisir un jour', 'En réserve', 'Abandonner', 'Découper',
    ])
  })

  it('Abandonner poste trancher/ {choix: "abandonner"}, la ligne part, Annuler la remet', async () => {
    const ligne = await ouvrirARevoir()
    await userEvent.click(within(ligne.parentElement).getByRole('button', { name: 'Abandonner' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/taches/taches/50/trancher/', { choix: 'abandonner' }))
    await waitFor(() => expect(screen.queryByText('Site web')).toBeNull())
    await userEvent.click(await screen.findByRole('button', { name: 'Annuler' }))
    // la dernière ligne partie, l'en-tête replié avait disparu : il revient, refermé
    await userEvent.click(await screen.findByRole('button', { name: /^À revoir/ }))
    expect(await screen.findByText('Site web')).toBeInTheDocument()
  })

  it('Aujourd\'hui : la tâche passe dans Prévu ; Choisir un jour pose le jour', async () => {
    const ligne = await ouvrirARevoir()
    await userEvent.click(within(ligne.parentElement).getByRole('button', { name: "Aujourd'hui" }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/taches/taches/50/trancher/', { choix: 'aujourdhui' }))
    const prevu = (await screen.findAllByText('Site web')).map((n) => n.closest('section')).find(Boolean)
    expect(prevu).toHaveTextContent('Prévu')
  })

  it('Choisir un jour poste {choix: "jour", jour}', async () => {
    const ligne = await ouvrirARevoir()
    await userEvent.click(within(ligne.parentElement).getByRole('button', { name: 'Choisir un jour' }))
    fireEvent.change(screen.getByLabelText('Jour pour « Site web »'), { target: { value: '2026-11-23' } })
    await waitFor(() => expect(api.post).toHaveBeenCalledWith('/taches/taches/50/trancher/', { choix: 'jour', jour: '2026-11-23' }))
  })

  it('hors ligne : Tout en réserve est grisé', async () => {
    await ouvrirARevoir()
    api.post.mockClear()
    Object.defineProperty(window.navigator, 'onLine', { value: false, configurable: true })
    act(() => { window.dispatchEvent(new Event('offline')) })
    const bouton = screen.getByRole('button', { name: 'Tout en réserve' })
    expect(bouton).toHaveAttribute('aria-disabled', 'true')
    await userEvent.click(bouton)
    expect(api.post).not.toHaveBeenCalled()
  })
})
