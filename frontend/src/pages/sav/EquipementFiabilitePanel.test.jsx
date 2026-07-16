import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* XSAV15/16/17 — panneau fiabilité (MTBF/MTTR/coût gated), disponibilité,
   immobilisation, relevés compteur. savApi mocké. */

vi.mock('../../api/savApi', () => ({
  default: {
    getEquipementFiabilite: vi.fn(),
    getEquipementDisponibilite: vi.fn(),
    getEquipementDowntime: vi.fn(),
    getEquipementReleves: vi.fn(),
    getEquipementEstimations: vi.fn(() => Promise.resolve({ data: null })),
    ouvrirEquipementDowntime: vi.fn(),
    cloturerEquipementDowntime: vi.fn(),
    addEquipementReleve: vi.fn(),
  },
}))

import savApi from '../../api/savApi'
import EquipementFiabilitePanel from './EquipementFiabilitePanel'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function makeStore(permissions = []) {
  return configureStore({
    reducer: { auth: (state = { role_nom: 'Technicien', permissions }) => state },
  })
}

function renderPanel(permissions = []) {
  const store = makeStore(permissions)
  return render(
    <Provider store={store}>
      <EquipementFiabilitePanel equipementId={1} />
    </Provider>,
  )
}

describe('EquipementFiabilitePanel — XSAV15 MTBF/MTTR', () => {
  it('affiche MTBF/MTTR mais masque le coût cumulé sans la permission prix_achat_voir', async () => {
    savApi.getEquipementFiabilite.mockResolvedValue({
      data: { mtbf_jours: 45.5, mttr_jours: 2.1, cout_cumule: 1500, reparer_vs_remplacer: 'reparer' },
    })
    savApi.getEquipementDisponibilite.mockResolvedValue({ data: { disponibilite_pct: 98.2 } })
    savApi.getEquipementDowntime.mockResolvedValue({ data: [] })
    savApi.getEquipementReleves.mockResolvedValue({ data: [] })

    renderPanel([]) // pas de permission prix_achat_voir
    expect(await screen.findByText('45.5 j')).toBeInTheDocument()
    expect(screen.getByText('2.1 j')).toBeInTheDocument()
    expect(screen.queryByText(/Coût cumulé/)).not.toBeInTheDocument()
  })

  it('affiche le coût cumulé avec la permission prix_achat_voir', async () => {
    savApi.getEquipementFiabilite.mockResolvedValue({
      data: { mtbf_jours: 10, mttr_jours: 1, cout_cumule: 2500, reparer_vs_remplacer: 'remplacer' },
    })
    savApi.getEquipementDisponibilite.mockResolvedValue({ data: { disponibilite_pct: 90 } })
    savApi.getEquipementDowntime.mockResolvedValue({ data: [] })
    savApi.getEquipementReleves.mockResolvedValue({ data: [] })

    renderPanel(['prix_achat_voir'])
    expect(await screen.findByText(/Coût cumulé/)).toBeInTheDocument()
    // VX75 — formatMAD : « 2 500,00 DH » (séparateur milliers + virgule décimale).
    expect(screen.getByText(/2\s?500,00 DH/)).toBeInTheDocument()
    expect(screen.getByText('À remplacer')).toBeInTheDocument()
  })
})

describe('EquipementFiabilitePanel — ZMFG11 estimations de maintenance', () => {
  it('affiche la prochaine défaillance estimée et le prochain entretien dû', async () => {
    savApi.getEquipementFiabilite.mockResolvedValue({ data: { mtbf_jours: 30, mttr_jours: 2 } })
    savApi.getEquipementDisponibilite.mockResolvedValue({ data: { disponibilite_pct: 95 } })
    savApi.getEquipementDowntime.mockResolvedValue({ data: [] })
    savApi.getEquipementReleves.mockResolvedValue({ data: [] })
    savApi.getEquipementEstimations.mockResolvedValue({
      data: { prochaine_defaillance_estimee: '2026-08-01', prochain_entretien_du: '2026-07-15' },
    })
    renderPanel()
    expect(await screen.findByText('Prochaine défaillance estimée :')).toBeInTheDocument()
    expect(screen.getByText('Prochain entretien dû :')).toBeInTheDocument()
  })
})

describe('EquipementFiabilitePanel — XSAV16 disponibilité + immobilisation', () => {
  it('affiche la disponibilité et propose d\'ouvrir une immobilisation', async () => {
    savApi.getEquipementFiabilite.mockResolvedValue({ data: { mtbf_jours: null, mttr_jours: null } })
    savApi.getEquipementDisponibilite.mockResolvedValue({ data: { disponibilite_pct: 97.3 } })
    savApi.getEquipementDowntime.mockResolvedValue({ data: [] })
    savApi.getEquipementReleves.mockResolvedValue({ data: [] })
    savApi.ouvrirEquipementDowntime.mockResolvedValue({ data: {} })

    renderPanel()
    // VX75 — formatPercent fr-MA : « 97,3 % » (virgule décimale).
    expect(await screen.findByText(/97,3\s?%/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Ouvrir une immobilisation/ }))
    await waitFor(() => expect(savApi.ouvrirEquipementDowntime).toHaveBeenCalledWith(1, {}))
  })

  it('propose de clôturer une immobilisation en cours', async () => {
    savApi.getEquipementFiabilite.mockResolvedValue({ data: { mtbf_jours: null, mttr_jours: null } })
    savApi.getEquipementDisponibilite.mockResolvedValue({ data: { disponibilite_pct: 80 } })
    savApi.getEquipementDowntime.mockResolvedValue({
      data: [{ id: 9, debut: '2026-07-01T10:00:00Z', fin: null, en_cours: true, motif: 'Panne onduleur' }],
    })
    savApi.getEquipementReleves.mockResolvedValue({ data: [] })
    savApi.cloturerEquipementDowntime.mockResolvedValue({ data: {} })

    renderPanel()
    await screen.findByText(/En cours depuis/)
    fireEvent.click(screen.getByRole('button', { name: 'Clôturer' }))
    await waitFor(() => expect(savApi.cloturerEquipementDowntime).toHaveBeenCalledWith(1, 9))
  })
})

describe('EquipementFiabilitePanel — XSAV17 relevés compteur', () => {
  it('enregistre un relevé et affiche le ticket généré si le seuil est atteint', async () => {
    savApi.getEquipementFiabilite.mockResolvedValue({ data: { mtbf_jours: null, mttr_jours: null } })
    savApi.getEquipementDisponibilite.mockResolvedValue({ data: { disponibilite_pct: 100 } })
    savApi.getEquipementDowntime.mockResolvedValue({ data: [] })
    savApi.getEquipementReleves.mockResolvedValue({ data: [] })
    savApi.addEquipementReleve.mockResolvedValue({
      data: { id: 5, type: 'heures', valeur: '500', ticket_genere: { id: 3, reference: 'SAV-PREV-1' } },
    })

    renderPanel()
    await screen.findByText('Relevés compteur')
    fireEvent.change(screen.getByPlaceholderText('Valeur'), { target: { value: '500' } })
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer/ }))
    await waitFor(() => expect(savApi.addEquipementReleve).toHaveBeenCalledWith(
      1, { type: 'heures', valeur: '500' }))
  })
})
