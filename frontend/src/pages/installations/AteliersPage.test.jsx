import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { screen, cleanup, waitFor, fireEvent, within } from '@testing-library/react'

/* XMFG1-16 — AteliersPage : câble le sous-système MRP-lite (ordres
   d'assemblage / démontage, kits). On vérifie : (1) le chargement liste les
   ordres d'assemblage et rend une ligne par ordre ; (2) le bouton de création
   est masqué pour un rôle sans écriture (normal) ; (3) le passage à l'onglet
   Démontage recharge la bonne source. Tout le réseau est mocké. */

const api = vi.hoisted(() => ({
  getOrdresAssemblage: vi.fn(),
  getOrdresDemontage: vi.fn(),
  getKitsAssemblage: vi.fn(),
  bonAssemblageUrl: (id) => `/api/x/${id}/bon-pdf/`,
  getDisponibiliteAssemblage: vi.fn(),
  getControleQualiteAssemblage: vi.fn(),
  enregistrerControleQualiteAssemblage: vi.fn(),
  getHistoriqueAssemblage: vi.fn(),
  getEtapesAssemblage: vi.fn(),
  getLignesAssemblage: vi.fn(),
  deleteLigneAssemblage: vi.fn(),
}))

vi.mock('../../api/installationsApi', () => ({ default: api }))

import AteliersPage from './AteliersPage'
import { renderAvecAuth } from '../../test/renderAvecAuth'

const renderPage = (role = 'responsable') => renderAvecAuth(<AteliersPage />, { role }, { theme: true })

beforeEach(() => {
  api.getOrdresAssemblage.mockResolvedValue({
    data: [
      { id: 1, reference: 'ASM-001', kit_nom: 'Kit onduleur', quantite: 2, statut: 'planifie', date_creation: '2026-01-01' },
    ],
  })
  api.getOrdresDemontage.mockResolvedValue({
    data: [
      { id: 9, reference: 'DSM-001', kit_nom: 'Kit batterie', quantite: 1, statut: 'planifie', date_creation: '2026-01-02' },
    ],
  })
  api.getKitsAssemblage.mockResolvedValue({
    data: [{ id: 3, nom: 'Kit onduleur', reference_interne: 'K-ONP', active: true }],
  })
})

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('AteliersPage (XMFG1-16)', () => {
  it("charge et liste les ordres d'assemblage", async () => {
    renderPage('responsable')
    await waitFor(() => expect(api.getOrdresAssemblage).toHaveBeenCalled())
    // DataTable rend potentiellement desktop + mobile → getAllByText.
    await waitFor(() =>
      expect(screen.getAllByText('ASM-001').length).toBeGreaterThan(0))
  })

  it('masque la création pour un rôle sans écriture', async () => {
    renderPage('normal')
    await waitFor(() => expect(api.getOrdresAssemblage).toHaveBeenCalled())
    expect(screen.queryByText(/Ordre d'assemblage$/)).toBeNull()
  })

  it('bascule sur le démontage et affiche ses ordres', async () => {
    renderPage('responsable')
    await waitFor(() => expect(api.getOrdresDemontage).toHaveBeenCalled())
    fireEvent.click(screen.getByRole('radio', { name: 'Démontage' }))
    await waitFor(() =>
      expect(screen.getAllByText('DSM-001').length).toBeGreaterThan(0))
  })

  // ACHT115 — valeurs du serveur (pass/fail/en_attente), blocage = tout sauf pass.
  it("contrôle qualité : envoie pass/fail, Forcer visible tant qu'un item n'est pas pass", async () => {
    api.getOrdresAssemblage.mockResolvedValue({
      data: [{ id: 1, reference: 'ASM-001', kit_nom: 'Kit', quantite: 1, statut: 'en_cours', date_creation: '2026-01-01' }],
    })
    let controles = [
      { id: 1, item_modele: 11, item_libelle: 'Serrage', resultat: 'en_attente' },
      { id: 2, item_modele: 12, item_libelle: 'Isolement', resultat: 'en_attente' },
    ]
    api.getDisponibiliteAssemblage.mockResolvedValue({ data: [] })
    api.getHistoriqueAssemblage.mockResolvedValue({ data: [] })
    api.getEtapesAssemblage.mockResolvedValue({ data: [] })
    api.getLignesAssemblage.mockResolvedValue({ data: [] })
    api.getControleQualiteAssemblage.mockImplementation(() => Promise.resolve({ data: controles }))
    api.enregistrerControleQualiteAssemblage.mockImplementation((_id, item, { resultat }) => {
      controles = controles.map((c) => (c.item_modele === item ? { ...c, resultat } : c))
      return Promise.resolve({ data: {} })
    })
    renderPage('responsable')
    fireEvent.click((await screen.findAllByText('ASM-001'))[0])
    const conformes = await screen.findAllByRole('button', { name: 'Conforme' })
    fireEvent.click(conformes[0])
    await waitFor(() => expect(api.enregistrerControleQualiteAssemblage)
      .toHaveBeenLastCalledWith(1, 11, { resultat: 'pass' }))
    fireEvent.click(screen.getAllByRole('button', { name: 'Échec' })[1])
    await waitFor(() => expect(api.enregistrerControleQualiteAssemblage)
      .toHaveBeenLastCalledWith(1, 12, { resultat: 'fail' }))
    await waitFor(() => expect(api.getControleQualiteAssemblage.mock.calls.length).toBeGreaterThan(2))
    fireEvent.click(screen.getByRole('button', { name: /Clôturer/ }))
    expect(await screen.findByLabelText(/Forcer malgré/)).toBeInTheDocument()
    cleanup()
    controles = controles.map((c) => ({ ...c, resultat: 'pass' }))
    renderPage('responsable')
    fireEvent.click((await screen.findAllByText('ASM-001'))[0])
    fireEvent.click(await screen.findByRole('button', { name: /Clôturer/ }))
    await screen.findByLabelText(/Quantité produite/)
    expect(screen.queryByLabelText(/Forcer malgré/)).toBeNull()
  })
})

// AERR81 — retirer une ligne d'assemblage demande une confirmation nommée.
describe('AteliersPage — AERR81 suppression de ligne confirmée', () => {
  it('Supprimer puis Annuler : aucune suppression ; Supprimer ⇒ un appel', async () => {
    const { ConfirmProvider } = await import('../../providers/ConfirmProvider')
    api.getDisponibiliteAssemblage.mockResolvedValue({ data: [] })
    api.getControleQualiteAssemblage.mockResolvedValue({ data: [] })
    api.getHistoriqueAssemblage.mockResolvedValue({ data: [] })
    api.getEtapesAssemblage.mockResolvedValue({ data: [] })
    api.getLignesAssemblage.mockResolvedValue({
      data: [{ id: 77, ordre: 1, produit_nom: 'Coffret AC 6 kW', quantite: '2', origine: 'kit' }],
    })
    api.deleteLigneAssemblage.mockResolvedValue({ data: {} })
    renderAvecAuth(<ConfirmProvider><AteliersPage /></ConfirmProvider>, { role: 'responsable' }, { theme: true })
    fireEvent.click((await screen.findAllByText('ASM-001'))[0])
    fireEvent.click((await screen.findAllByRole('button', { name: 'Retirer' }))[0])
    const boite = await screen.findByRole('alertdialog')
    expect(boite).toHaveTextContent('Coffret AC 6 kW × 2')
    fireEvent.click(within(boite).getByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull())
    expect(api.deleteLigneAssemblage).not.toHaveBeenCalled()

    // CAD177 — le verrou anti-double-clic du Button tombe après 400 ms sans
    // rendu du bouton (Annuler ne le re-rend pas).
    await new Promise((r) => setTimeout(r, 450))
    fireEvent.click(screen.getAllByRole('button', { name: 'Retirer' })[0])
    const boite2 = await screen.findByRole('alertdialog')
    fireEvent.click(within(boite2).getByRole('button', { name: 'Supprimer' }))
    await waitFor(() => expect(api.deleteLigneAssemblage).toHaveBeenCalledWith(77))
    expect(api.deleteLigneAssemblage).toHaveBeenCalledTimes(1)
  })
})
