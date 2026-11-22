/* ACAL589 — l'onglet « Plan » de « Ma journée » : réponses tirées du contrat
   COMMITTÉ `installations/calepinage_plan_pose.json` ; le cache de lecture est
   le VRAI `createReadCache` sur un magasin mémoire (IndexedDB absente ici). */
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { exempleContrat } from '../../test/fixtures/contractSamples'

const api = vi.hoisted(() => ({ getPlanPose: vi.fn() }))
vi.mock('../../api/installationsApi', () => ({ default: api }))
vi.mock('../offlinesync/readCache', async (importOriginal) => {
  const vrai = await importOriginal()
  return { ...vrai, readCache: vrai.createReadCache() }
})

const { readCache } = await import('../offlinesync/readCache')
const { default: PlanPoseTerrain } = await import('./PlanPoseTerrain')

const PLAN = exempleContrat('installations', 'calepinage_plan_pose')
const SANS_PLAN = exempleContrat('installations', 'calepinage_plan_pose', 'exemple_sans_plan')

beforeEach(async () => { await readCache.vider() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('PlanPoseTerrain (ACAL589)', () => {
  it('en ligne : le SVG dans une <img> data:, jamais injecté dans le DOM', async () => {
    api.getPlanPose.mockResolvedValue({ data: PLAN })
    const { container } = render(<PlanPoseTerrain installationId={4} />)
    const image = await screen.findByTestId('plan-pose-image')
    expect(api.getPlanPose).toHaveBeenCalledWith(4)
    expect(image.getAttribute('src')).toBe(
      `data:image/svg+xml;charset=utf-8,${encodeURIComponent(PLAN.plan_pose_svg)}`)
    expect(container.querySelector('svg rect')).toBeNull()
    expect(screen.queryByTestId('bandeau-hors-ligne')).toBeNull()
  })

  it('réseau coupé ⇒ plan relu du cache avec sa mention d’âge', async () => {
    api.getPlanPose.mockResolvedValueOnce({ data: PLAN })
    render(<PlanPoseTerrain installationId={4} />)
    await screen.findByTestId('plan-pose-image')
    await vi.waitFor(async () => expect(await readCache.get('plan_pose', 4)).not.toBeNull())
    cleanup()

    api.getPlanPose.mockRejectedValueOnce(new Error('Network Error'))
    render(<PlanPoseTerrain installationId={4} />)
    expect(await screen.findByTestId('bandeau-hors-ligne'))
      .toHaveTextContent(/Données hors-ligne, dernière synchro à \d{2}:\d{2}/)
    expect(screen.getByTestId('plan-pose-image').getAttribute('src'))
      .toContain(encodeURIComponent(PLAN.plan_pose_svg))
  })

  it('réseau coupé sans plan jamais ouvert : le dit, aucun plan inventé', async () => {
    api.getPlanPose.mockRejectedValue(new Error('Network Error'))
    render(<PlanPoseTerrain installationId={5} />)
    expect(await screen.findByTestId('plan-pose-indisponible')).toBeInTheDocument()
    expect(screen.queryByTestId('plan-pose-image')).toBeNull()
  })

  it('sans plan : le motif servi, tel quel', async () => {
    api.getPlanPose.mockResolvedValue({ data: SANS_PLAN })
    render(<PlanPoseTerrain installationId={6} />)
    expect(await screen.findByTestId('plan-pose-motif')).toHaveTextContent(SANS_PLAN.motif)
    expect(screen.queryByTestId('plan-pose-image')).toBeNull()
  })
})
