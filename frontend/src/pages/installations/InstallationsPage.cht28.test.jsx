import { describe, it, expect, vi, beforeAll, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent, within } from '@testing-library/react'
import { polyfillResizeObserver } from '../../test/selectNatif'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { ConfirmProvider } from '../../providers/ConfirmProvider'
import crmApi from '../../api/crmApi'
import installationsReducer from '../../features/installations/store/installationsSlice'

/* ============================================================================
   CHT28 — InstallationsPage.jsx n'avait AUCUN test unitaire : (1) rendu liste
   (les chantiers chargés apparaissent, le compte du titre reflète le total
   filtré) et (2) deep-link `?id=` ouvre la fiche du chantier ciblé en Sheet
   (VX79, déjà exercé par notification/lien copié — jamais testé côté écran).
   ----------------------------------------------------------------------------
   Piège RTL connu (mémoire, "4 pièges RTL") : DataTable rend en DOUBLE sous
   jsdom (le responsive mobile/desktop ne s'applique pas sans vrai viewport,
   les deux mises en page restent dans le DOM) — `getAllByText`/
   `toBeGreaterThan(0)` partout où une cellule de ligne est lue, JAMAIS
   `getByText` qui échouerait en mode strict. Le second piège (heading
   ambigu : le SheetTitle de la fiche ouverte contient AUSSI « Chantier ») est
   évité en scopant chaque assertion (dialog / texte précis), jamais un
   `getByRole('heading', /chantier/i)` générique.
   ========================================================================== */

beforeAll(polyfillResizeObserver)

const mocks = vi.hoisted(() => ({
  getInstallations: vi.fn(),
  updateInstallation: vi.fn(),
  toastWithUndo: vi.fn(),
}))

vi.mock('../../lib/toast', async (importOriginal) => ({
  ...(await importOriginal()),
  toastWithUndo: (...a) => mocks.toastWithUndo(...a),
}))

vi.mock('../../api/installationsApi', async () => ({
  default: {
    ...(await import('../../test/selectNatif')).installationsLecturesVides,
    getInstallations: (...args) => mocks.getInstallations(...args),
    updateInstallation: (...args) => mocks.updateInstallation(...args),
    // Appelés au montage de InstallationDetail (deep-link) — voir
    // InstallationDetail.cht20/21/22.test.jsx pour le même patron.
  },
}))

vi.mock('../../api/crmApi', async () => (await import('../../test/selectNatif')).crmApiMock)

vi.mock('../../api/savApi', async () => (await import('../../test/selectNatif')).savApiMock)

vi.mock('../../api/ventesApi', async () => (await import('../../test/selectNatif')).ventesApiMock)

import InstallationsPage from './InstallationsPage'

function makeStore(auth = { user: { id: 1 }, role: 'admin' }) {
  return configureStore({
    reducer: {
      installations: installationsReducer,
      auth: (state = auth) => state,
      stock: (state = { produits: [{ id: 1, nom: 'Panneau' }] }) => state,
    },
  })
}

function renderPage(route = '/chantiers', auth) {
  return render(
    <Provider store={makeStore(auth)}>
      <MemoryRouter initialEntries={[route]}>
        <ThemeProvider>
          <ConfirmProvider>
            <InstallationsPage />
          </ConfirmProvider>
        </ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  try { localStorage.clear() } catch { /* indisponible */ }
})

describe('InstallationsPage (CHT28)', () => {
  it('rendu liste : les chantiers chargés apparaissent, le titre reflète le total', async () => {
    mocks.getInstallations.mockResolvedValue({
      data: {
        count: 2,
        results: [
          { id: 11, reference: 'CH-CHT28-011', client_nom: 'Client A', statut: 'signe' },
          { id: 12, reference: 'CH-CHT28-012', client_nom: 'Client B', statut: 'planifie' },
        ],
      },
    })
    renderPage()

    await waitFor(() => expect(
      screen.getAllByText('CH-CHT28-011').length,
    ).toBeGreaterThan(0))
    expect(screen.getAllByText('CH-CHT28-012').length).toBeGreaterThan(0)

    // Une seule fiche h2 à ce stade (aucun Sheet ouvert) : sans ambiguïté.
    const titre = screen.getByRole('heading', { level: 2 })
    expect(titre).toHaveTextContent('Chantiers')
    expect(titre).toHaveTextContent('2')
  })

  it("deep-link ?id= ouvre la fiche du chantier ciblé en Sheet (VX79)", async () => {
    mocks.getInstallations.mockResolvedValue({
      data: {
        count: 1,
        results: [
          { id: 21, reference: 'CH-CHT28-021', client_nom: 'Client Deep', statut: 'signe' },
        ],
      },
    })
    renderPage('/chantiers?id=21')

    await waitFor(() => expect(screen.getByRole('dialog')).toBeVisible())
    expect(screen.getAllByText(/CH-CHT28-021/).length).toBeGreaterThan(0)
  })

  it('assignable-users : aucun appel (403) pour un Technicien, appel pour un admin', async () => {
    const appel = vi.spyOn(crmApi, 'getAssignableUsers')
    mocks.getInstallations.mockResolvedValue({ data: { count: 0, results: [] } })
    renderPage('/chantiers', { user: { id: 2 }, role: 'technicien', role_nom: 'Technicien', permissions: ['chantiers_voir'] })
    await waitFor(() => expect(mocks.getInstallations).toHaveBeenCalled())
    expect(appel).not.toHaveBeenCalled()
    cleanup()
    renderPage()
    await waitFor(() => expect(appel).toHaveBeenCalled())
    appel.mockRestore()
  })

  // ADRG21 — « Exporter Excel » suit le code de la route d'export.
  it('sans installation_export : pas d’Exporter Excel ; avec : présent', async () => {
    mocks.getInstallations.mockResolvedValue({ data: { count: 0, results: [] } })
    renderPage('/chantiers', { user: { id: 3 }, role: 'normal', role_nom: 'Commercial', permissions: ['ventes_voir'] })
    await waitFor(() => expect(mocks.getInstallations).toHaveBeenCalled())
    expect(screen.queryByRole('button', { name: /Exporter Excel/ })).toBeNull()
    cleanup()
    renderPage('/chantiers', { user: { id: 1 }, role: 'admin', permissions: ['installation_export'] })
    expect(await screen.findByRole('button', { name: /Exporter Excel/ })).toBeInTheDocument()
  })

  // ADRG99 — (ré)affecter l'installateur exige `technicien_assign` (route PATCH).
  it('Technicien sans technicien_assign : aucun sélecteur « Installateur » ; avec : présent', async () => {
    localStorage.setItem('taqinor.chantiers.view', 'kanban')
    mocks.getInstallations.mockResolvedValue({
      data: { count: 1, results: [{ id: 31, reference: 'CH-ADRG99', client_nom: 'Client K', statut: 'signe' }] },
    })
    renderPage('/chantiers', { user: { id: 4 }, role: 'normal', role_nom: 'Technicien',
      permissions: ['chantiers_voir', 'installation_gerer', 'intervention_gerer'] })
    await waitFor(() => expect(screen.getAllByText('CH-ADRG99').length).toBeGreaterThan(0))
    expect(screen.queryByLabelText('Installateur')).toBeNull()
    cleanup()
    localStorage.setItem('taqinor.chantiers.view', 'kanban')
    renderPage('/chantiers', { user: { id: 5 }, role: 'normal', role_nom: 'Technicien responsable',
      permissions: ['chantiers_voir', 'installation_gerer', 'technicien_assign'] })
    await waitFor(() => expect(screen.getAllByLabelText('Installateur').length).toBeGreaterThan(0))
  })

  // AERR28 — Installé a des effets durables (stock sorti) : confirmation nommée.
  it('vue kanban, sélecteur En cours → Installé : confirmation nommée, Annuler ⇒ aucun PATCH', async () => {
    localStorage.setItem('taqinor.chantiers.view', 'kanban')
    const inst = { id: 41, reference: 'CH-2026-0123', client_nom: 'Client E', statut: 'en_cours' }
    mocks.getInstallations.mockResolvedValue({ data: { count: 1, results: [inst] } })
    mocks.updateInstallation.mockResolvedValue({ data: { ...inst, statut: 'installe' } })
    renderPage()
    const select = (await screen.findAllByLabelText(/Changer le statut du chantier CH-2026-0123/))[0]
    fireEvent.change(select, { target: { value: 'installe' } })
    const dialog = await screen.findByRole('alertdialog')
    expect(dialog).toHaveTextContent('CH-2026-0123')
    expect(dialog).toHaveTextContent('Installé')
    expect(dialog).toHaveTextContent('le matériel réservé sortira du stock')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull())
    expect(mocks.updateInstallation).not.toHaveBeenCalled()

    fireEvent.change(select, { target: { value: 'installe' } })
    const dialog2 = await screen.findByRole('alertdialog')
    fireEvent.click(within(dialog2).getByRole('button', { name: 'Confirmer' }))
    await waitFor(() => expect(mocks.updateInstallation).toHaveBeenCalledWith(41, { statut: 'installe' }))
    expect(mocks.toastWithUndo).not.toHaveBeenCalled()
  })

  it('vue kanban, Planifié → En cours : PATCH immédiat puis « Annuler » qui repasse Planifié', async () => {
    localStorage.setItem('taqinor.chantiers.view', 'kanban')
    const inst = { id: 42, reference: 'CH-2026-0124', client_nom: 'Client F', statut: 'planifie' }
    mocks.getInstallations.mockResolvedValue({ data: { count: 1, results: [inst] } })
    mocks.updateInstallation.mockImplementation((id, data) => Promise.resolve({ data: { ...inst, ...data } }))
    renderPage()
    const select = (await screen.findAllByLabelText(/Changer le statut du chantier CH-2026-0124/))[0]
    fireEvent.change(select, { target: { value: 'en_cours' } })
    await waitFor(() => expect(mocks.updateInstallation).toHaveBeenCalledWith(42, { statut: 'en_cours' }))
    expect(screen.queryByRole('alertdialog')).toBeNull()
    await waitFor(() => expect(mocks.toastWithUndo).toHaveBeenCalled())
    expect(mocks.toastWithUndo.mock.calls[0][0].message).toContain('CH-2026-0124')
    expect(mocks.toastWithUndo.mock.calls[0][0].onCommit).toBeUndefined()
    await mocks.toastWithUndo.mock.calls[0][0].onUndo()
    expect(mocks.updateInstallation).toHaveBeenLastCalledWith(42, { statut: 'planifie' })
  })

  // AERR30 — dépôt calendrier : toast nommé, « Annuler » remet l'ancienne date.
  it('dépôt calendrier : toast nommé, Annuler ⇒ PATCH de l’ancienne date', async () => {
    localStorage.setItem('taqinor.chantiers.view', 'calendrier')
    const now = new Date()
    const ym = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
    const inst = { id: 51, reference: 'CH-2026-0123', client_nom: 'Client G', statut: 'planifie',
      date_pose_prevue: `${ym}-12` }
    mocks.getInstallations.mockResolvedValue({ data: { count: 1, results: [inst] } })
    mocks.updateInstallation.mockImplementation((id, data) => Promise.resolve({ data: { ...inst, ...data } }))
    const { container } = renderPage()
    const puce = await waitFor(() => {
      const el = container.querySelector('.cal-chip')
      expect(el).not.toBeNull()
      return el
    })
    const cible = [...container.querySelectorAll('.cal-cell:not(.cal-cell-out)')]
      .find((c) => c.querySelector('.cal-day-number')?.textContent === '19')
    fireEvent.dragStart(puce, { dataTransfer: { setData: vi.fn(), effectAllowed: '' } })
    fireEvent.drop(cible)
    await waitFor(() => expect(mocks.updateInstallation).toHaveBeenCalledWith(51, { date_pose_prevue: `${ym}-19` }))
    await waitFor(() => expect(mocks.toastWithUndo).toHaveBeenCalled())
    const opts = mocks.toastWithUndo.mock.calls[0][0]
    expect(opts.message).toBe(`Pose de CH-2026-0123 déplacée au 19/${ym.slice(5)}`)
    expect(opts.onCommit).toBeUndefined()
    await opts.onUndo()
    expect(mocks.updateInstallation).toHaveBeenLastCalledWith(51, { date_pose_prevue: `${ym}-12` })
  })
})
