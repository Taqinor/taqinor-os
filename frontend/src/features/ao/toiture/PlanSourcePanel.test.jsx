import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* PACT76 — plan source de la toiture : le calibrage ENFIN persisté (AOF20).
   Preuves : (1) la toiture affiche la liste RÉELLE de ses plans sources avec
   leur état ; (2) calibrer un plan appelle un PATCH réel puis relit
   l'échelle CALCULÉE PAR LE SERVEUR (jamais un facteur px→m recalculé ici) —
   c'est ce PATCH qui fait survivre le calibrage à un rechargement. */

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  update: vi.fn(),
  upload: vi.fn(),
}))

vi.mock('../../../api/aoApi', () => ({
  default: {
    plansSources: { list: mocks.list, create: mocks.create, update: mocks.update, upload: mocks.upload },
  },
}))

import PlanSourcePanel from './PlanSourcePanel'

const PLAN_BRUT = {
  id: 1, toiture: 9, origine: 'plan_fourni', origine_display: 'Plan fourni (PDF/DXF/image)',
  type_fichier: 'image', etat: 'brut', etat_display: 'Brut (non calibré)',
  calib_point_a_px: [], calib_point_b_px: [], calib_distance_reelle_m: null, echelle_m_par_px: null,
  fourni_par: '',
}
const PLAN_CALIBRE = {
  id: 2, toiture: 9, origine: 'trace_manuel', origine_display: 'Tracé manuel',
  type_fichier: 'aucun', etat: 'calibre', etat_display: 'Calibré',
  calib_point_a_px: [10, 20], calib_point_b_px: [410, 20], calib_distance_reelle_m: '8.000',
  echelle_m_par_px: '0.02000000', fourni_par: 'Reda Kasri',
}

const renderPanel = (props) => render(<PlanSourcePanel toitureId={9} {...props} />)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: [PLAN_BRUT, PLAN_CALIBRE] })
  mocks.create.mockResolvedValue({ data: { id: 3 } })
  mocks.update.mockResolvedValue({ data: {} })
  mocks.upload.mockResolvedValue({ data: {} })
})

describe('PlanSourcePanel (PACT76)', () => {
  it('la toiture affiche la liste RÉELLE de ses plans sources, avec leur état', async () => {
    renderPanel()
    await waitFor(() => expect(mocks.list).toHaveBeenCalledWith({ toiture: 9 }))
    expect(await screen.findByText('Brut (non calibré)')).toBeInTheDocument()
    expect(screen.getByText('Calibré')).toBeInTheDocument()
  })

  it('un plan calibré affiche l’échelle CALCULÉE PAR LE SERVEUR (jamais recalculée ici)', async () => {
    renderPanel()
    expect(await screen.findByText('échelle : 0.020000 m/px')).toBeInTheDocument()
  })

  it('créer un plan sans fichier n’appelle aucun upload', async () => {
    renderPanel()
    await screen.findByText('Brut (non calibré)')
    await userEvent.click(screen.getByRole('button', { name: 'Enregistrer le plan' }))
    await waitFor(() => expect(mocks.create).toHaveBeenCalledWith(
      expect.objectContaining({ toiture: 9, origine: 'plan_fourni', type_fichier: 'aucun' }),
    ))
    expect(mocks.upload).not.toHaveBeenCalled()
  })

  it('calibrer un plan appelle un PATCH réel avec les deux points et la distance, puis recharge la liste', async () => {
    renderPanel()
    const badgeBrut = await screen.findByText('Brut (non calibré)')
    // Deux plans, DEUX formulaires de calibration avec les MÊMES libellés :
    // on scope la saisie à la ligne du plan BRUT (id 1), jamais à « un »
    // formulaire pris au hasard parmi les deux.
    const ligne = within(badgeBrut.closest('li'))

    await userEvent.type(ligne.getByLabelText('Point A — x (px)'), '15')
    await userEvent.type(ligne.getByLabelText('Point A — y (px)'), '30')
    await userEvent.type(ligne.getByLabelText('Point B — x (px)'), '415')
    await userEvent.type(ligne.getByLabelText('Point B — y (px)'), '30')
    await userEvent.type(ligne.getByLabelText('Distance réelle A→B (m)'), '8')
    await userEvent.click(ligne.getByRole('button', { name: 'Calibrer' }))

    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith(1, {
      calib_point_a_px: [15, 30], calib_point_b_px: [415, 30], calib_distance_reelle_m: '8',
    }))
    await waitFor(() => expect(mocks.list).toHaveBeenCalledTimes(2))
  })

  it('aucune toiture choisie : état vide honnête, sans appel réseau', () => {
    renderPanel({ toitureId: undefined })
    expect(screen.getByText('Plans sources indisponibles')).toBeInTheDocument()
    expect(mocks.list).not.toHaveBeenCalled()
  })
})
