import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, renderHook, screen, waitFor, fireEvent, act } from '@testing-library/react'

/* AOF177 — suivi de la génération asynchrone du pack et du ZIP.
   Le sondage passe par `useVisibilityAwarePolling` (VX56) : on le fait avancer
   dans les tests avec un `visibilitychange` (comme `useChatPolling.test.jsx`),
   jamais avec des minuteries factices. */

const mocks = vi.hoisted(() => ({ zip: vi.fn(), statutJob: vi.fn() }))
const toastMocks = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }))

vi.mock('../../../api/aoApi', () => ({
  default: { dossiers: { zip: mocks.zip, statutJob: mocks.statutJob } },
}))

vi.mock('../../../ui', async () => {
  const actual = await vi.importActual('../../../ui')
  return { ...actual, toast: { success: toastMocks.success, error: toastMocks.error } }
})

import useGenerationJob, { cleStockage, lireVerrou, etatDeJob } from './useGenerationJob'
import ZipButton from './ZipButton'

const EN_COURS = {
  statut: 'running', progress_pct: 40,
  pieces: [
    { code: 'memoire', libelle: 'Mémoire technique', statut: 'done' },
    { code: 'bordereau', libelle: 'Bordereau des prix', statut: 'running' },
    { code: 'planche_05H', libelle: 'Planche 05H', statut: 'queued' },
  ],
}
const ECHEC_PIECE = {
  statut: 'running', progress_pct: 60,
  pieces: [
    { code: 'memoire', libelle: 'Mémoire technique', statut: 'done' },
    {
      code: 'bordereau', libelle: 'Bordereau des prix', statut: 'echec',
      message_erreur: 'clause de réserve absente',
    },
  ],
}
const SUCCES = {
  statut: 'done', progress_pct: 100, resultat_url: '/media/ao/pack-DS-2026-014.zip',
  pieces: [{ code: 'memoire', libelle: 'Mémoire technique', statut: 'done' }],
}
const ECHEC = { statut: 'failed', progress_pct: 60, message_erreur: 'planche 06I illisible' }

const avancer = async () => {
  await act(async () => { document.dispatchEvent(new Event('visibilitychange')) })
}

beforeEach(() => {
  vi.clearAllMocks()
  globalThis.localStorage?.clear()
  mocks.zip.mockResolvedValue({ data: { job_id: 'job-42' } })
  mocks.statutJob.mockResolvedValue({ data: EN_COURS })
})

describe('useGenerationJob (AOF177)', () => {
  it('lancer() rend la main immédiatement et passe en « en cours » sans bloquer', async () => {
    const { result } = renderHook(() => useGenerationJob(7))
    expect(result.current.statut).toBe('idle')
    await act(async () => { await result.current.lancer() })
    expect(mocks.zip).toHaveBeenCalledWith(7)
    expect(result.current.statut).toBe('en_cours')
    expect(result.current.enCours).toBe(true)
  })

  it('suit l’avancement PIÈCE PAR PIÈCE renvoyé par le serveur', async () => {
    const { result } = renderHook(() => useGenerationJob(7))
    await act(async () => { await result.current.lancer() })
    await waitFor(() => expect(mocks.statutJob).toHaveBeenCalledWith(7, 'job-42'))
    await waitFor(() => expect(result.current.pieces).toHaveLength(3))
    expect(result.current.progression).toBe(40)
  })

  it('reprend le suivi après un départ/retour, sans relancer une seconde génération', async () => {
    globalThis.localStorage.setItem(cleStockage(7), 'job-99')
    const { result } = renderHook(() => useGenerationJob(7))
    await waitFor(() => expect(mocks.statutJob).toHaveBeenCalledWith(7, 'job-99'))
    expect(mocks.zip).not.toHaveBeenCalled()
    expect(result.current.statut).toBe('en_cours')
  })

  it('succès : notifie UNE seule fois, expose le résultat et oublie le job mémorisé', async () => {
    const onSucces = vi.fn()
    mocks.statutJob.mockResolvedValue({ data: SUCCES })
    const { result } = renderHook(() => useGenerationJob(7, { onSucces }))
    await act(async () => { await result.current.lancer() })
    await waitFor(() => expect(onSucces).toHaveBeenCalledTimes(1))
    expect(result.current.statut).toBe('succes')
    expect(result.current.resultatUrl).toBe(SUCCES.resultat_url)
    expect(globalThis.localStorage.getItem(cleStockage(7))).toBeNull()
    await avancer()
    expect(onSucces).toHaveBeenCalledTimes(1)
  })

  it('échec : l’état est « echec » et le motif remonte', async () => {
    const onEchec = vi.fn()
    mocks.statutJob.mockResolvedValue({ data: ECHEC })
    const { result } = renderHook(() => useGenerationJob(7, { onEchec }))
    await act(async () => { await result.current.lancer() })
    await waitFor(() => expect(result.current.statut).toBe('echec'))
    expect(onEchec).toHaveBeenCalledWith(ECHEC)
  })

  it('annulation : le suivi s’arrête, la mémoire est purgée et le serveur est prévenu s’il sait annuler', async () => {
    const onAnnulerServeur = vi.fn().mockResolvedValue({})
    const { result } = renderHook(() => useGenerationJob(7, { onAnnulerServeur }))
    await act(async () => { await result.current.lancer() })
    await waitFor(() => expect(mocks.statutJob).toHaveBeenCalled())
    const appelsAvant = mocks.statutJob.mock.calls.length

    await act(async () => { await result.current.annuler() })
    expect(onAnnulerServeur).toHaveBeenCalledWith('job-42')
    expect(result.current.statut).toBe('idle')
    expect(globalThis.localStorage.getItem(cleStockage(7))).toBeNull()

    await avancer()
    expect(mocks.statutJob.mock.calls.length).toBe(appelsAvant)
  })

  it('lireVerrou / etatDeJob : le 409 nommé et les deux vocabulaires de statut', () => {
    expect(lireVerrou({ response: { status: 400, data: {} } })).toBeNull()
    expect(lireVerrou({
      response: { status: 409, data: { detail: 'Dossier verrouillé.', verrou: { porteur: 'Sami B.', depuis: '2026-08-01T09:30:00Z' } } },
    })).toEqual({ porteur: 'Sami B.', depuis: '2026-08-01T09:30:00Z', detail: 'Dossier verrouillé.' })
    expect(etatDeJob(null)).toBe('idle')
    expect(etatDeJob({ statut: 'done' })).toBe('succes')
    expect(etatDeJob({ status: 'failed' })).toBe('echec')
    expect(etatDeJob({ statut: 'en_cours' })).toBe('en_cours')
  })
})

describe('ZipButton (AOF177)', () => {
  it('affiche l’avancement et NOMME chaque pièce en échec, sans bloquer l’écran', async () => {
    mocks.statutJob.mockResolvedValue({ data: ECHEC_PIECE })
    render(<ZipButton dossierId={7} />)
    fireEvent.click(screen.getByRole('button', { name: 'Constituer le ZIP de dépôt' }))
    expect(await screen.findByText(/vous pouvez continuer à travailler/)).toBeInTheDocument()
    expect(await screen.findByText(/clause de réserve absente/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Annuler le suivi' })).toBeEnabled()
  })

  it('succès : toast avec un LIEN vers le résultat + bouton de téléchargement', async () => {
    mocks.statutJob.mockResolvedValue({ data: SUCCES })
    render(<ZipButton dossierId={7} />)
    fireEvent.click(screen.getByRole('button', { name: 'Constituer le ZIP de dépôt' }))
    await waitFor(() => expect(toastMocks.success).toHaveBeenCalled())
    expect(toastMocks.success.mock.calls[0][1].action.label).toBe('Ouvrir le ZIP')
    const lien = await screen.findByRole('link', { name: /Télécharger le ZIP/ })
    expect(lien).toHaveAttribute('href', SUCCES.resultat_url)
  })

  it('le 409 du verrou de dossier s’affiche en NOMMANT le porteur', async () => {
    mocks.zip.mockRejectedValue({
      response: {
        status: 409,
        data: {
          detail: 'Une cascade de prix est en cours sur ce dossier.',
          verrou: { porteur: 'Sami B.', depuis: '2026-08-01T09:30:00Z' },
        },
      },
    })
    render(<ZipButton dossierId={7} />)
    fireEvent.click(screen.getByRole('button', { name: 'Constituer le ZIP de dépôt' }))
    expect(await screen.findByText(/Une cascade de prix est en cours sur ce dossier/)).toBeInTheDocument()
    expect(screen.getByText(/Porteur : Sami B\./)).toBeInTheDocument()
  })

  it('un contrôle bloquant écrit son motif SUR le bouton — jamais un bouton grisé muet', () => {
    render(<ZipButton dossierId={7} bloque motifBlocage="justification à 2 800 vs bordereau à 2 600" />)
    const zip = screen.getByRole('button', { name: /^ZIP bloqué —/ })
    expect(zip).toBeDisabled()
    expect(zip).toHaveAccessibleName(/justification à 2 800 vs bordereau à 2 600/)
    expect(mocks.zip).not.toHaveBeenCalled()
  })
})
