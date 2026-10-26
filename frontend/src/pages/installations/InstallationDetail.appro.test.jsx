import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from 'vitest'
import { screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { render } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import InstallationDetail from './InstallationDetail'
import { polyfillResizeObserver } from '../../test/selectNatif'
// PACT13 — la réponse mockée est l'exemple COMMITTÉ côté serveur.
import CONTRAT from '../../../../backend/django_core/apps/installations/contract_samples/chantier_approvisionnement.json'

/* Revue chantier 26/10/2026 — la fiche lit UNE réponse « approvisionnement » :
   carte « Prêt à poser ? » + bannière « Commander le matériel » (Aperçu), onglet
   Matériel & BC, séries attendues filtrées par `serie_attendue`, et le bouton
   « Créer les interventions standard » de l'onglet Interventions. */

beforeAll(polyfillResizeObserver)

const mocks = vi.hoisted(() => ({
  getApprovisionnement: vi.fn(),
  creerInterventionsStandard: vi.fn(),
}))

vi.mock('../../api/installationsApi', async () => ({
  default: {
    ...(await import('../../test/selectNatif')).installationsLecturesVides,
    getApprovisionnement: (...a) => mocks.getApprovisionnement(...a),
    creerInterventionsStandard: (...a) => mocks.creerInterventionsStandard(...a),
  },
}))
vi.mock('../../api/savApi', async () => (await import('../../test/selectNatif')).savApiMock)
vi.mock('../../api/crmApi', async () => (await import('../../test/selectNatif')).crmApiMock)
vi.mock('../../api/ventesApi', async () => (await import('../../test/selectNatif')).ventesApiMock)
vi.mock('./ChantierGateTimeline', async () => (await import('../../test/selectNatif')).composantNul)
vi.mock('./ChantierChecklist', async () => (await import('../../test/selectNatif')).composantNul)
vi.mock('../../features/installations/offline/OfflineSyncIndicator', async () => (await import('../../test/selectNatif')).composantNul)

// L'onglet Matériel monte le picker d'équipements (permissions) : le harnais
// partagé n'a pas de tranche `auth`, on la fournit ici.
const rendre = (installation) => render(
  <Provider store={configureStore({
    reducer: {
      stock: (state = { produits: [{ id: 1, nom: 'Panneau' }] }) => state,
      auth: (state = { permissions: [], role_nom: 'admin' }) => state,
    },
  })}>
    <MemoryRouter initialEntries={['/chantiers']}>
      <ThemeProvider>
        <InstallationDetail installation={installation} onClose={() => {}} onSaved={() => {}} />
      </ThemeProvider>
    </MemoryRouter>
  </Provider>,
)

const CHANTIER = {
  id: 43,
  reference: 'CHT-202610-0043',
  statut: 'signe',
  annule: false,
  client: 12,
  client_nom: 'Client Appro',
  interventions: [],
  bom: [
    { produit_id: 34, designation: 'Panneau Canadian Solar 710W', quantite: 10 },
    { produit_id: 12, designation: 'Câble solaire 6 mm² (au mètre)', quantite: 60 },
  ],
}

beforeEach(() => {
  mocks.getApprovisionnement.mockResolvedValue({ data: CONTRAT.exemple })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('InstallationDetail — approvisionnement', () => {
  it('Aperçu : carte « Prêt à poser ? » et bannière « Commander le matériel » quand il y a des manques', async () => {
    rendre(CHANTIER)
    expect(await screen.findByText('Prêt à poser ?')).toBeTruthy()
    expect(screen.getAllByText('Pas encore prêt à poser').length).toBeGreaterThan(0)
    expect(screen.getByText('Commander le matériel')).toBeTruthy()
    expect(mocks.getApprovisionnement).toHaveBeenCalledWith(43)
  })

  it('sans manque, la bannière ne réclame plus de commander le matériel', async () => {
    mocks.getApprovisionnement.mockResolvedValue({
      data: { ...CONTRAT.exemple, resume: { ...CONTRAT.exemple.resume, nb_manques: 0 } },
    })
    rendre(CHANTIER)
    expect(await screen.findByText('Prêt à poser ?')).toBeTruthy()
    expect(screen.queryByText('Commander le matériel')).toBeNull()
    expect(screen.getByText('Matériel couvert : planifier la pose')).toBeTruthy()
  })

  it('Matériel & BC : charge sans bouton « Calculer » et montre le manque', async () => {
    const user = userEvent.setup()
    rendre(CHANTIER)
    await user.click(await screen.findByRole('tab', { name: /Matériel/ }))
    expect(await screen.findByRole('button', { name: /Commander les manques \(1\)/ })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Calculer le besoin' })).toBeNull()
  })

  it('« Nomenclature vs séries capturées » ne garde que les articles à numéro de série', async () => {
    const user = userEvent.setup()
    rendre(CHANTIER)
    await user.click(await screen.findByRole('tab', { name: /Matériel/ }))
    await screen.findByRole('button', { name: /Commander les manques/ })
    // Le câble (serie_attendue=false) n'est plus attendu ; le panneau l'est : 0/10 rouge.
    const entete = screen.getByText('Nomenclature vs séries capturées')
    const bloc = entete.closest('div')
    expect(bloc.textContent).toContain('Panneau Canadian Solar 710W')
    expect(bloc.textContent).not.toContain('Câble solaire')
    expect(bloc.textContent).toContain('0/10')
  })
})

describe('InstallationDetail — interventions standard', () => {
  it('« Créer les interventions standard » appelle le serveur puis recharge la fiche', async () => {
    mocks.creerInterventionsStandard.mockResolvedValue({ data: { created: [{ id: 1 }, { id: 2 }] } })
    const user = userEvent.setup()
    rendre(CHANTIER)
    await user.click(await screen.findByRole('tab', { name: /Interventions/ }))
    await user.click(await screen.findByRole('button', { name: 'Créer les interventions standard' }))
    await waitFor(() => expect(mocks.creerInterventionsStandard).toHaveBeenCalledWith(43))
    expect(screen.getByRole('button', { name: 'Ouvrir la planification' })).toBeTruthy()
    expect(screen.getByLabelText('Technicien')).toBeTruthy()
  })

  it('le bouton est désactivé quand des interventions existent déjà', async () => {
    const user = userEvent.setup()
    rendre({ ...CHANTIER, interventions: [{ id: 5, type_intervention: 'pose', date_prevue: '2026-11-02' }] })
    await user.click(await screen.findByRole('tab', { name: /Interventions/ }))
    const bouton = await screen.findByRole('button', { name: 'Créer les interventions standard' })
    expect(bouton.disabled).toBe(true)
    expect(bouton.getAttribute('title')).toMatch(/déjà des interventions/)
  })
})
