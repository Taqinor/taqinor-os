import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from 'vitest'
import { screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderInstallationDetail } from '../../test/installationDetailHarness'
import { polyfillResizeObserver } from '../../test/selectNatif'

/* ACHT60 — dérogations émises depuis la fiche chantier : « Motif (acompte non
   reçu) » → motif_override_acompte, « Motif de réouverture » → motif_reouverture,
   et « Marquer réceptionné » seulement depuis « Installé ». Faux serveur en
   mémoire qui applique les règles réelles (400 sans motif, 200 avec). */

beforeAll(polyfillResizeObserver)

vi.mock('../../ui', async (importActual) => (
  (await import('../../test/selectNatif')).avecSelectNatif(await importActual())
))
const db = {}
vi.mock('../../api/installationsApi', async () => ({
  default: {
    ...(await import('../../test/selectNatif')).installationsLecturesVides,
    updateInstallation: (id, body) => {
      const row = db[id]
      if (body.statut && body.statut !== row.statut) {
        if (body.statut === 'planifie' && !body.motif_override_acompte) {
          return Promise.reject({ response: { data: { statut: [
            'Planification refusée : l’acompte n’est pas encore reçu.'] } } })
        }
        if (row.statut === 'cloture' && !body.motif_reouverture) {
          return Promise.reject({ response: { data: { statut: [
            'Ce chantier est CLÔTURÉ : sa réouverture exige un motif explicite.'] } } })
        }
        row.statut = body.statut
      }
      return Promise.resolve({ data: { ...row } })
    },
    getInstallation: (id) => Promise.resolve({ data: { ...db[id] } }),
  },
}))
vi.mock('../../api/savApi', async () => (await import('../../test/selectNatif')).savApiMock)
vi.mock('../../api/crmApi', async () => (await import('../../test/selectNatif')).crmApiMock)
vi.mock('../../api/ventesApi', async () => (await import('../../test/selectNatif')).ventesApiMock)

vi.mock('./ChantierGateTimeline', async () => (await import('../../test/selectNatif')).composantNul)
vi.mock('./ChantierChecklist', async () => (await import('../../test/selectNatif')).composantNul)
vi.mock('../../features/installations/offline/OfflineSyncIndicator', async () => (await import('../../test/selectNatif')).composantNul)

const rendre = (row) => renderInstallationDetail({ ...row })

beforeEach(() => {
  db[1] = { id: 1, reference: 'CH-1', statut: 'materiel_commande', annule: false }
  db[2] = { id: 2, reference: 'CH-2', statut: 'cloture', annule: false }
  db[3] = { id: 3, reference: 'CH-3', statut: 'receptionne', annule: false }
  db[4] = { id: 4, reference: 'CH-4', statut: 'installe', annule: false }
})
afterEach(() => cleanup())

describe('InstallationDetail — ACHT60 dérogations de statut', () => {
  it('acompte non reçu : le motif apparaît et le passage à Planifié aboutit', async () => {
    const user = userEvent.setup()
    rendre(db[1])
    await user.selectOptions(await screen.findByLabelText('Statut'), 'planifie')
    await user.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    const motif = await screen.findByLabelText(/Motif \(acompte non reçu\)/)
    expect(db[1].statut).toBe('materiel_commande')
    await user.type(motif, 'Virement annoncé')
    await user.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    await waitFor(() => expect(db[1].statut).toBe('planifie'))
  })

  it('clôturé : le motif de réouverture apparaît et l’envoi aboutit', async () => {
    const user = userEvent.setup()
    rendre(db[2])
    await user.selectOptions(await screen.findByLabelText('Statut'), 'receptionne')
    await user.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    const motif = await screen.findByLabelText(/Motif de réouverture/)
    expect(db[2].statut).toBe('cloture')
    await user.type(motif, 'Réserve oubliée')
    await user.click(screen.getByRole('button', { name: 'Mettre à jour' }))
    await waitFor(() => expect(db[2].statut).toBe('receptionne'))
  })

  it('« Marquer réceptionné » seulement depuis Installé', async () => {
    rendre(db[2])
    await screen.findByLabelText('Statut')
    expect(screen.queryByRole('button', { name: 'Marquer réceptionné' })).toBeNull()
    cleanup()
    rendre(db[3])
    await screen.findByLabelText('Statut')
    expect(screen.queryByRole('button', { name: 'Marquer réceptionné' })).toBeNull()
    cleanup()
    rendre(db[4])
    expect(await screen.findByRole('button', { name: 'Marquer réceptionné' })).toBeInTheDocument()
  })
})
