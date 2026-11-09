import { describe, it, expect, vi, beforeAll, afterEach } from 'vitest'
import { screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderInstallationDetail as rendre } from '../../test/installationDetailHarness'
import crmApi from '../../api/crmApi'
import installationsApi from '../../api/installationsApi'
import { polyfillResizeObserver } from '../../test/selectNatif'

/* ACHT3 — l'écran du chantier masque les gestes que le serveur refuse :
   « Enregistrer la mise en service » seulement depuis « Installé » et hors
   chantier annulé ; sélecteur de statut désactivé sur un chantier annulé. */

beforeAll(polyfillResizeObserver)

vi.mock('../../ui', async (importActual) => (
  (await import('../../test/selectNatif')).avecSelectNatif(await importActual())
))
vi.mock('./ChantierGateTimeline', async () => (await import('../../test/selectNatif')).composantNul)
vi.mock('./ChantierChecklist', async () => (await import('../../test/selectNatif')).composantNul)
vi.mock('../../features/installations/offline/OfflineSyncIndicator', async () => (await import('../../test/selectNatif')).composantNul)
vi.mock('../../api/installationsApi', async () => ({
  default: {
    ...(await import('../../test/selectNatif')).installationsLecturesVides,
  },
}))
vi.mock('../../api/savApi', async () => (await import('../../test/selectNatif')).savApiMock)
vi.mock('../../api/crmApi', async () => (await import('../../test/selectNatif')).crmApiMock)
vi.mock('../../api/ventesApi', async () => (await import('../../test/selectNatif')).ventesApiMock)

const ouvrirJalons = async (user) => {
  await user.click(await screen.findByRole('tab', { name: /Jalons/ }))
}
const BTN = { name: 'Enregistrer la mise en service' }

afterEach(() => cleanup())

describe('InstallationDetail — ACHT3 gestes refusés masqués', () => {
  it('masque mise en service sur signé', async () => {
    const user = userEvent.setup()
    rendre({ id: 1, reference: 'CH-1', statut: 'signe', annule: false })
    await ouvrirJalons(user)
    expect(screen.queryByRole('button', BTN)).toBeNull()
    expect(screen.getByText(/disponible à partir d’Installé/)).toBeInTheDocument()
  })

  it('désactive le statut sur annulé', async () => {
    const user = userEvent.setup()
    rendre({ id: 2, reference: 'CH-2', statut: 'installe', annule: true })
    expect(await screen.findByLabelText('Statut')).toBeDisabled()
    expect(screen.getByText(/Chantier annulé — réactivez-le/)).toBeInTheDocument()
    await ouvrirJalons(user)
    expect(screen.queryByRole('button', BTN)).toBeNull()
    expect(screen.queryByText('Date de mise en service')).toBeNull()
  })

  it('garde actif sur installé', async () => {
    const user = userEvent.setup()
    rendre({ id: 3, reference: 'CH-3', statut: 'installe', annule: false })
    expect(await screen.findByLabelText('Statut')).toBeEnabled()
    await ouvrirJalons(user)
    expect(screen.getByRole('button', BTN)).toBeInTheDocument()
  })

  it('réceptionné ou mise_en_service hérité : bouton présent', async () => {
    for (const [id, statut] of [[4, 'receptionne'], [5, 'mise_en_service']]) {
      const user = userEvent.setup()
      rendre({ id, reference: `CH-${id}`, statut, annule: false })
      await ouvrirJalons(user)
      expect(screen.getByRole('button', BTN)).toBeInTheDocument()
      cleanup()
    }
  })

  it('clôturé : bouton absent, texte de réouverture', async () => {
    const user = userEvent.setup()
    rendre({ id: 6, reference: 'CH-6', statut: 'cloture', annule: false })
    await ouvrirJalons(user)
    expect(screen.queryByRole('button', BTN)).toBeNull()
    expect(screen.getByText(/Chantier clôturé : rouvrez-le d’abord avec un motif de réouverture\./)).toBeInTheDocument()
  })

  // ERR-ACHT123 — plus de window.confirm natif : le dialogue de l'application.
  it('mise en service avec champs vides : dialogue applicatif, aucun confirm natif', async () => {
    const user = userEvent.setup()
    const natif = vi.spyOn(window, 'confirm').mockReturnValue(true)
    installationsApi.miseEnService = vi.fn(() => Promise.resolve({ data: {} }))
    rendre({ id: 7, reference: 'CH-7', statut: 'installe', annule: false })
    await ouvrirJalons(user)
    await user.type(screen.getByLabelText('Date de mise en service'), '2026-10-30')
    await user.click(screen.getByRole('button', BTN))
    expect(await screen.findByRole('alertdialog')).toHaveTextContent(/Champs non renseignés : test de production et tension/)
    expect(natif).not.toHaveBeenCalled()
    expect(installationsApi.miseEnService).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Enregistrer quand même' }))
    await waitFor(() => expect(installationsApi.miseEnService).toHaveBeenCalledTimes(1))
    expect(natif).not.toHaveBeenCalled()
    natif.mockRestore()
  })

  it('mise en service sous 100 % de checklist : annonce la réception, annuler n’envoie rien', async () => {
    // ACSV36
    const user = userEvent.setup()
    installationsApi.miseEnService = vi.fn(() => Promise.resolve({ data: {} }))
    rendre({ id: 10, reference: 'CH-10', statut: 'installe', annule: false, checklist_completion: 60,
      mes_production_test: 5, mes_tension: 230 })
    await ouvrirJalons(user)
    await user.type(screen.getByLabelText('Date de mise en service'), '2026-10-28')
    await user.click(screen.getByRole('button', BTN))
    expect(await screen.findByRole('alertdialog')).toHaveTextContent(/réceptionne le chantier.*60 %/)
    await user.click(screen.getByRole('button', { name: 'Annuler' }))
    expect(installationsApi.miseEnService).not.toHaveBeenCalled()
    // CAD177 — le verrou anti-double-clic du Button tombe après 400 ms sans
    // rendu (confirmation annulée) : un humain ne re-clique pas plus vite.
    await new Promise((r) => setTimeout(r, 450))
    await user.click(screen.getByRole('button', BTN))
    await user.click(await screen.findByRole('button', { name: 'Continuer' }))
    await waitFor(() => expect(installationsApi.miseEnService).toHaveBeenCalledTimes(1))
  })

  it('assignable-users : aucun appel pour un Technicien, appel pour un admin', async () => {
    const appel = vi.spyOn(crmApi, 'getAssignableUsers')
    rendre({ id: 8, reference: 'CH-8', statut: 'installe', annule: false },
      { role: 'technicien', role_nom: 'Technicien', permissions: ['chantiers_voir'] })
    expect(await screen.findByLabelText('Statut')).toBeEnabled()
    expect(appel).not.toHaveBeenCalled()
    cleanup()
    rendre({ id: 9, reference: 'CH-9', statut: 'installe', annule: false })
    await waitFor(() => expect(appel).toHaveBeenCalled())
    appel.mockRestore()
  })
})
