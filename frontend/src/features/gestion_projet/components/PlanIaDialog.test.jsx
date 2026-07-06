import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import gestionProjetApi from '../../../api/gestionProjetApi'
import PlanIaDialog from './PlanIaDialog'

/* XPRJ29 — Plan de tâches IA : propose (aucune écriture) puis confirme
   (matérialise) — deux actions distinctes, l'utilisateur peut retirer une
   tâche proposée avant de confirmer. */

vi.mock('../../../api/gestionProjetApi', () => ({
  default: {
    genererPlanIa: vi.fn(() => Promise.resolve({
      data: {
        taches: [
          { code: 'T1', libelle: 'Étude toiture', phase: 'etude', duree_jours: 2, dependances_fs: [] },
          { code: 'T2', libelle: 'Pose panneaux', phase: 'pose', duree_jours: 5, dependances_fs: ['T1'] },
        ],
      },
    })),
    confirmerPlanIa: vi.fn(() => Promise.resolve({
      data: [{ id: 1, libelle: 'Étude toiture' }, { id: 2, libelle: 'Pose panneaux' }],
    })),
  },
}))

vi.mock('../../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn() } }
})

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('PlanIaDialog', () => {
  it('propose un plan puis le confirme (deux actions distinctes)', async () => {
    const user = userEvent.setup()
    const onConfirmed = vi.fn()
    render(<PlanIaDialog projetId={10} onClose={vi.fn()} onConfirmed={onConfirmed} />)

    await user.type(screen.getByLabelText('ID du devis lié'), '99')
    await user.click(screen.getByRole('button', { name: /Proposer un plan/ }))
    await waitFor(() => expect(gestionProjetApi.genererPlanIa).toHaveBeenCalledWith(
      10, expect.objectContaining({ devis_id: '99' }),
    ))
    expect(gestionProjetApi.confirmerPlanIa).not.toHaveBeenCalled()

    expect(await screen.findByText('Étude toiture')).toBeInTheDocument()
    expect(screen.getByText('Pose panneaux')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Confirmer et créer 2 tâche/ }))
    await waitFor(() => expect(gestionProjetApi.confirmerPlanIa).toHaveBeenCalledWith(
      10, expect.objectContaining({ taches: expect.any(Array) }),
    ))
    await waitFor(() => expect(onConfirmed).toHaveBeenCalled())
  })

  it('retirer une tâche proposée l\'exclut de la confirmation', async () => {
    const user = userEvent.setup()
    render(<PlanIaDialog projetId={10} onClose={vi.fn()} onConfirmed={vi.fn()} />)
    await user.type(screen.getByLabelText('ID du devis lié'), '99')
    await user.click(screen.getByRole('button', { name: /Proposer un plan/ }))
    await screen.findByText('Étude toiture')

    await user.click(screen.getByRole('button', { name: 'Retirer Pose panneaux' }))
    expect(screen.queryByText('Pose panneaux')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Confirmer et créer 1 tâche/ }))
    await waitFor(() => expect(gestionProjetApi.confirmerPlanIa).toHaveBeenCalledWith(
      10, { taches: [expect.objectContaining({ libelle: 'Étude toiture' })] },
    ))
  })
})
