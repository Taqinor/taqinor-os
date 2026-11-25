/* Nouveau fichier car : DevisList.test.jsx (≥ 2 000 lignes) ne grossit plus (C20).

   Lot « listes, envoi, PDF à l'écran » du tour 3 :
   - T4-X1-003 : le suivi d'un PDF ne meurt plus sur un sondage manqué, la ligne
     reste « en génération » jusqu'à l'issue, un serveur muet est dit après 5 min.
   - M6 (revue du lot 4) : « Générer les PDF » traite EXACTEMENT la sélection,
     y compris les devis cochés sur une autre page.
   - T4-X1-012 : la colonne « Validité » montre la date que le PDF imprime.
   - T4-X4-009 : « Envoyer » sans numéro dit ce qui manque et offre le lien.
   Le VRAI code tourne ; seule l'API HTTP est simulée.

   Run : npx vitest run src/pages/ventes/DevisListEnvoiPdf.test.jsx */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, within, act, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('../../features/ventes/store/ventesSlice', async (importOriginal) =>
  (await import('../../test/devisListMocks.js')).ventesSliceMock(importOriginal))

vi.mock('../../api/ventesApi', async (importOriginal) =>
  (await import('../../test/etendreApi')).etendreApi(importOriginal, {
    getDevisById: vi.fn(() => Promise.resolve({ data: {} })),
    etatPdfDevis: vi.fn(() => Promise.resolve({
      data: { devis: 7, statut: 'en_cours', fichier_pdf: false, erreur: null, date: null },
    })),
    whatsappPreviewDevis: vi.fn(() => Promise.resolve({ data: { wa_url: 'https://wa.me/1', message: 'Bonjour' } })),
    getVariantes: vi.fn(() => Promise.resolve({ data: [] })),
    historiqueDevis: vi.fn(() => Promise.resolve({ data: [] })),
  }))

vi.mock('../../api/crmApi', async (importOriginal) =>
  (await import('../../test/devisListMocks.js')).crmApiMotifsMock(importOriginal))

vi.mock('../../api/uxviewsApi', async () =>
  (await import('../../test/devisListMocks.js')).uxviewsApiMock())

import { renderList, renderListAvecStore } from './devisList.testHelpers.jsx'
import { configureStore } from '@reduxjs/toolkit'
import ventesApi from '../../api/ventesApi'
import { toast } from '../../ui'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { useDevisPdf } from './devisList/useDevisPdf.js'

const brouillon = (extra) => ({
  id: 61, reference: 'DEV-X1-012', client_nom: 'ACME', statut: 'brouillon', is_active: true,
  date_creation: '2026-11-25', total_ttc: 4000, nb_options: 1, version: 1, date_validite: null, ...extra,
})

// ── T4-X1-003 : le suivi du PDF ─────────────────────────────────────────────
describe('T4-X1-003 — un PDF « Devis Final » qui n’arrive pas est suivi puis dit', () => {
  beforeEach(() => { vi.useFakeTimers() })
  afterEach(() => { vi.runOnlyPendingTimers(); vi.useRealTimers() })

  async function lancer(etat) {
    const { renderHook } = await import('@testing-library/react')
    ventesApi.etatPdfDevis.mockImplementation(etat)
    const dispatch = vi.fn(() => ({ unwrap: () => Promise.resolve({ demande: 'D1' }) }))
    const rendu = renderHook(() => useDevisPdf({ dispatch, devis: [], selectedIds: [], setSelectedIds: () => {} }))
    await act(async () => { await rendu.result.current.genererUnPdf({ id: 7, reference: 'DEV-7' }) })
    return rendu
  }

  it('la ligne reste « en génération » pendant tout le sondage, puis se referme', async () => {
    let pret = false
    const { result } = await lancer(() => Promise.resolve({
      data: { devis: 7, statut: pret ? 'pret' : 'en_cours', fichier_pdf: pret, erreur: null, date: null },
    }))
    await act(async () => { await vi.advanceTimersByTimeAsync(10 * 1000) })
    expect(result.current.pdfSuivi[7]).toBe(true)
    pret = true
    await act(async () => { await vi.advanceTimersByTimeAsync(12 * 1000) })
    expect(result.current.pdfSuivi[7]).toBe(false)
  })

  it('un sondage en erreur ou sans réponse ne coupe plus le suivi : l’échec du serveur est dit', async () => {
    const erreur = vi.spyOn(toast, 'error')
    let appel = 0
    const { result } = await lancer(() => {
      appel += 1
      if (appel === 1) return Promise.reject(new Error('502'))
      if (appel === 2) return new Promise(() => {}) // jamais de réponse
      return Promise.resolve({ data: { devis: 7, statut: 'echec', fichier_pdf: false,
        erreur: 'Moteur indisponible', date: null } })
    })
    await act(async () => { await vi.advanceTimersByTimeAsync(60 * 1000) })
    expect(appel).toBeGreaterThanOrEqual(3)
    expect(erreur).toHaveBeenCalledWith(
      'DEV-7 : la génération du PDF a échoué — Moteur indisponible',
      expect.objectContaining({ action: expect.objectContaining({ label: 'Réessayer' }) }))
    expect(result.current.pdfSuivi[7]).toBe(false)
    erreur.mockRestore()
  })

  it('un serveur qui ne répond jamais : après 5 min, « Réessayer » et la ligne se referme', async () => {
    const erreur = vi.spyOn(toast, 'error')
    const { result } = await lancer(() => new Promise(() => {}))
    await act(async () => { await vi.advanceTimersByTimeAsync(6 * 60 * 1000) })
    expect(erreur).toHaveBeenCalledWith(
      'DEV-7 : le PDF n’est toujours pas prêt après 5 minutes — la génération n’a pas abouti.',
      expect.objectContaining({ action: expect.objectContaining({ label: 'Réessayer' }) }))
    expect(result.current.pdfSuivi[7]).toBe(false)
    erreur.mockRestore()
  })
})

// ── M6 : « Générer les PDF » sur deux pages ─────────────────────────────────
describe('M6 — « Générer les PDF » agit sur toute la sélection, sur deux pages', () => {
  async function lot({ selection, page, relire }) {
    const { renderHook } = await import('@testing-library/react')
    ventesApi.getDevisById.mockClear()
    ventesApi.getDevisById.mockImplementation(relire)
    const dispatch = vi.fn(() => ({ unwrap: () => Promise.resolve({ demande: 'D' }) }))
    const setSelectedIds = vi.fn()
    const rendu = renderHook(() => useDevisPdf({ dispatch, devis: page, selectedIds: selection, setSelectedIds }))
    await act(async () => { await rendu.result.current.handleGenererPdfLot() })
    return { dispatch, setSelectedIds, ...rendu }
  }
  const sur = (id) => ({ id, reference: `DEV-${id}`, mode_installation: 'residentiel' })

  beforeEach(() => { vi.useFakeTimers() })
  afterEach(() => { vi.runOnlyPendingTimers(); vi.useRealTimers() })

  it('trois cochés dont un sur l’autre page : les trois PDF sont lancés, l’absent est relu', async () => {
    const { dispatch, setSelectedIds } = await lot({
      selection: [1, 2, 9], page: [sur(1), sur(2)],
      relire: (id) => Promise.resolve({ data: sur(id) }),
    })
    expect(ventesApi.getDevisById).toHaveBeenCalledTimes(1)
    expect(ventesApi.getDevisById).toHaveBeenCalledWith(9)
    expect(dispatch).toHaveBeenCalledTimes(3)
    expect(setSelectedIds).toHaveBeenCalledWith([])
  })

  it('un coché illisible n’est pas perdu en silence : dit, et il reste coché', async () => {
    const erreur = vi.spyOn(toast, 'error')
    const { dispatch, setSelectedIds } = await lot({
      selection: [1, 9], page: [sur(1)], relire: () => Promise.reject(new Error('404')),
    })
    expect(dispatch).toHaveBeenCalledTimes(1)
    expect(erreur).toHaveBeenCalledWith(expect.stringContaining('1 devis coché n’a pas pu être relu'))
    expect(setSelectedIds).toHaveBeenCalledWith([9])
    erreur.mockRestore()
  })
})

// ── T4-X1-012 : la validité affichée est celle du PDF ───────────────────────
describe('T4-X1-012 — la colonne « Validité » montre la date du PDF', () => {
  it('brouillon sans date saisie : la date servie (date_expiration) s’affiche', () => {
    renderList([brouillon({ date_expiration: '2026-12-25' })])
    const ligne = screen.getByText('DEV-X1-012').closest('tr')
    expect(within(ligne).getByText('25/12/2026')).toBeInTheDocument()
  })

  it('date saisie par le vendeur : c’est elle que le serveur sert, et la liste l’affiche', () => {
    renderList([brouillon({ date_validite: '2026-12-31', date_expiration: '2026-12-31' })])
    const ligne = screen.getByText('DEV-X1-012').closest('tr')
    expect(within(ligne).getByText('31/12/2026')).toBeInTheDocument()
  })
})

// ── Revue de la liste : jamais « 0 devis » pendant le chargement ────────────
describe('En-tête — chargement de la première page', () => {
  it('pendant le chargement : « Chargement des devis… », jamais « 0 devis »', () => {
    const store = configureStore({
      reducer: {
        ventes: (state = { devis: [], loading: true, error: null }) => state,
        auth: (state = { role: 'admin', role_nom: 'Directeur', permissions: [] }) => state,
      },
    })
    renderListAvecStore(store)
    expect(screen.queryByText(/^0 devis/)).toBeNull()
    expect(screen.getByText('Chargement des devis…')).toBeInTheDocument()
  })
})

// ── T4-X4-009 : « Envoyer » sans numéro ─────────────────────────────────────
describe('T4-X4-009 — « Envoyer » sans numéro sur la fiche', () => {
  it('409 « Numéro de téléphone invalide » : le manque est dit, avec « Copier le lien »', async () => {
    const user = userEvent.setup()
    const erreur = vi.spyOn(toast, 'error')
    ventesApi.whatsappPreviewDevis.mockRejectedValueOnce(Object.assign(new Error('409'), {
      response: { status: 409, data: { detail: 'Numéro de téléphone invalide.' } } }))
    renderList([brouillon({ id: 62, reference: 'DEV-X4-009' })])
    const ligne = screen.getByText('DEV-X4-009').closest('tr')
    await user.click(within(ligne).getByRole('button', { name: /Envoyer/ }))
    await waitFor(() => expect(erreur).toHaveBeenCalled())
    const [message, options] = erreur.mock.calls.at(-1)
    expect(message).toContain('aucun numéro de téléphone exploitable')
    expect(message).not.toContain('invalide')
    expect(options.action.label).toBe('Copier le lien')
    erreur.mockRestore()
  })
})
