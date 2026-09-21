import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* NTAGR8 — alerte DAR en direct (miroir de `apps.agriculture.models.
   check_dar_guard`) : un traitement qui violerait le délai avant récolte
   affiche l'alerte ET bloque la soumission ; un traitement conforme laisse
   la soumission active. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const { etapesCreate } = vi.hoisted(() => ({
  etapesCreate: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
}))

vi.mock('../../api/agricultureApi', () => ({
  default: { etapesCampagne: { create: (...args) => etapesCreate(...args) } },
}))

import EtapeCampagneForm from './EtapeCampagneForm'
import { checkDarAlert } from '../../features/agriculture/darAlert'

beforeEach(() => { vi.clearAllMocks() })

const campagne = { id: 7, culture: 'Vigne', date_recolte_prevue: '2026-06-01' }
const intrantPhyto = {
  id: 3, categorie: 'phyto', matiere_active: 'Cuivre',
  delai_avant_recolte_jours: 21,
}

describe('checkDarAlert (miroir pur de check_dar_guard)', () => {
  it('bloque un traitement dont le DAR dépasse la récolte prévue', () => {
    const result = checkDarAlert({
      typeEtape: 'traitement', date: '2026-05-25', intrant: intrantPhyto, campagne,
    })
    expect(result.ok).toBe(false)
    expect(result.message).toMatch(/21/)
  })

  it('laisse passer un traitement conforme', () => {
    const result = checkDarAlert({
      typeEtape: 'traitement', date: '2026-05-01', intrant: intrantPhyto, campagne,
    })
    expect(result.ok).toBe(true)
  })

  it('ne bloque jamais sans DAR défini sur l’intrant', () => {
    const result = checkDarAlert({
      typeEtape: 'traitement', date: '2026-05-30',
      intrant: { id: 9, categorie: 'phyto' }, campagne,
    })
    expect(result.ok).toBe(true)
  })
})

describe('EtapeCampagneForm — alerte DAR en direct', () => {
  it('affiche l’alerte et bloque la soumission pour une date hors DAR', async () => {
    const user = userEvent.setup()
    render(
      <EtapeCampagneForm campagne={campagne} intrants={[intrantPhyto]} onClose={() => {}} />,
    )
    await user.selectOptions(screen.getByLabelText('Intrant appliqué'), '3')
    fireEvent.change(screen.getByLabelText('Date'), { target: { value: '2026-05-25' } })

    expect(await screen.findByText(/Traitement bloqué/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Enregistrer' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    expect(etapesCreate).not.toHaveBeenCalled()
  })

  it('autorise la soumission pour un traitement conforme au DAR', async () => {
    const user = userEvent.setup()
    render(
      <EtapeCampagneForm campagne={campagne} intrants={[intrantPhyto]} onClose={() => {}} />,
    )
    await user.selectOptions(screen.getByLabelText('Intrant appliqué'), '3')
    fireEvent.change(screen.getByLabelText('Date'), { target: { value: '2026-05-01' } })

    expect(await screen.findByText('Délai avant récolte respecté.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Enregistrer' })).toBeEnabled()

    await user.click(screen.getByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(etapesCreate).toHaveBeenCalledWith(
      expect.objectContaining({ campagne: 7, type_etape: 'traitement', date: '2026-05-01', intrant: '3' }),
    ))
  })
})
