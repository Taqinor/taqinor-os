import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import migrationApi from '../../api/migrationApi'
import PlaybookPanel from './PlaybookPanel'

/* ============================================================================
   NTMIG25 — Panneau playbook interactif : instancier un playbook pour un
   déploiement, cocher ses étapes, voir la progression en direct.
   ========================================================================== */

vi.mock('../../api/migrationApi', () => ({
  default: {
    listPlaybookInstances: vi.fn(),
    instancierPlaybook: vi.fn(),
    cocherEtapePlaybook: vi.fn(),
    terminerPlaybookInstance: vi.fn(),
  },
}))

vi.mock('../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn() } }
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function withProviders(ui) {
  return render(<ThemeProvider>{ui}</ThemeProvider>)
}

const INSTANCE = {
  id: 9,
  playbook_article: 1,
  playbook_titre: 'Déploiement module Compta',
  client_final: 'Coopérative Souss',
  etapes: [
    { cle: 'p1', libelle: 'Créer les accès', phase: 'prerequis', phase_titre: 'Prérequis' },
    { cle: 'p2', libelle: 'Créer les rôles', phase: 'prerequis', phase_titre: 'Prérequis' },
  ],
  avancement: {},
  statut: 'en_cours',
  progression: 0,
  nb_etapes: 2,
  nb_faites: 0,
}

describe('PlaybookPanel (NTMIG25)', () => {
  it("propose d'instancier quand aucun déploiement n'existe", async () => {
    migrationApi.listPlaybookInstances.mockResolvedValue({ data: [] })
    withProviders(<PlaybookPanel articleId={1} />)
    expect(await screen.findByText(/Aucun déploiement instancié/i)).toBeTruthy()
    expect(screen.getByRole('button', { name: /Instancier pour un déploiement/i })).toBeTruthy()
  })

  it('instancie puis affiche les phases/étapes cochables', async () => {
    migrationApi.listPlaybookInstances.mockResolvedValue({ data: [] })
    migrationApi.instancierPlaybook.mockResolvedValue({ data: INSTANCE })
    const user = userEvent.setup()
    withProviders(<PlaybookPanel articleId={1} />)
    await screen.findByText(/Aucun déploiement instancié/i)

    await user.type(screen.getByLabelText(/Client final/i), 'Coopérative Souss')
    await user.click(screen.getByRole('button', { name: /Instancier pour un déploiement/i }))

    await waitFor(() => expect(migrationApi.instancierPlaybook).toHaveBeenCalledWith({
      playbook_article: 1, client_final: 'Coopérative Souss',
    }))
    expect(await screen.findByText('Créer les accès')).toBeTruthy()
    expect(screen.getByText('0 / 2 étapes (0 %)')).toBeTruthy()
  })

  it('cocher une étape met à jour la progression en direct', async () => {
    migrationApi.listPlaybookInstances.mockResolvedValue({ data: [INSTANCE] })
    const coche = { ...INSTANCE, avancement: { p1: true }, nb_faites: 1, progression: 50 }
    migrationApi.cocherEtapePlaybook.mockResolvedValue({ data: coche })
    const user = userEvent.setup()
    withProviders(<PlaybookPanel articleId={1} />)

    await screen.findByText('Créer les accès')
    await user.click(screen.getByRole('checkbox', { name: 'Créer les accès' }))

    await waitFor(() => expect(migrationApi.cocherEtapePlaybook).toHaveBeenCalledWith(9, 'p1', true))
    expect(await screen.findByText('1 / 2 étapes (50 %)')).toBeTruthy()
  })

  it('clôture le déploiement une fois toutes les étapes faites', async () => {
    const complet = { ...INSTANCE, avancement: { p1: true, p2: true }, nb_faites: 2, progression: 100 }
    migrationApi.listPlaybookInstances.mockResolvedValue({ data: [complet] })
    migrationApi.terminerPlaybookInstance.mockResolvedValue({
      data: { ...complet, statut: 'termine' },
    })
    const user = userEvent.setup()
    withProviders(<PlaybookPanel articleId={1} />)

    await screen.findByText('Créer les accès')
    await user.click(screen.getByRole('button', { name: /Clôturer ce déploiement/i }))

    await waitFor(() => expect(migrationApi.terminerPlaybookInstance).toHaveBeenCalledWith(9))
    expect(await screen.findByText('Terminé')).toBeTruthy()
  })
})
