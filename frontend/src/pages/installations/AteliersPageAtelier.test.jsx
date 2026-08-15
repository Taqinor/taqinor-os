import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent, within } from '@testing-library/react'

/* WIR247 — sept exports d'atelier n'avaient AUCUN appelant : la gamme
   d'exécution (XMFG14 : getEtapesAssemblage / cocherEtapeAssemblage), les
   lignes de composant éditables (XMFG6 : get/create/update/deleteLigne-
   Assemblage) et la quantité récupérée au démontage (XMFG12 :
   updateLigneDemontage). Ils sont montés dans le détail d'un ordre.
   WIR248 — déclaration de rebut (motif OBLIGATOIRE) + rapport agrégé.

   Charges utiles alignées sur les sérialiseurs serveur réels
   (EtapeOrdreSerializer, OrdreAssemblageLigneSerializer,
   OrdreDemontageLigneSerializer) — jamais une forme inventée. */

vi.mock('../../ui', async (importActual) => {
  const actual = await importActual()
  const Passthrough = ({ children }) => <>{children}</>
  return {
    ...actual,
    Select: ({ value, onValueChange, children }) => (
      <select role="combobox" value={value} onChange={(e) => onValueChange(e.target.value)}>
        <option value="" />
        {children}
      </select>
    ),
    SelectTrigger: Passthrough,
    SelectValue: () => null,
    SelectContent: Passthrough,
    SelectItem: ({ value, children }) => <option value={value}>{children}</option>,
    toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
  }
})

vi.mock('../../hooks/useHasPermission', () => ({
  useIsAdminOrResponsable: () => true,
  useHasPermission: () => true,
}))

vi.mock('../../api/installationsApi', () => ({
  default: {
    getOrdresAssemblage: vi.fn(),
    getOrdresDemontage: vi.fn(),
    getKitsAssemblage: vi.fn(),
    getDisponibiliteAssemblage: vi.fn(),
    getControleQualiteAssemblage: vi.fn(),
    getHistoriqueAssemblage: vi.fn(),
    getEtapesAssemblage: vi.fn(),
    cocherEtapeAssemblage: vi.fn(),
    getLignesAssemblage: vi.fn(),
    createLigneAssemblage: vi.fn(),
    updateLigneAssemblage: vi.fn(),
    deleteLigneAssemblage: vi.fn(),
    updateLigneDemontage: vi.fn(),
    declarerRebutAssemblage: vi.fn(),
    getRapportRebuts: vi.fn(),
    demarrerAssemblage: vi.fn(),
    noterAssemblage: vi.fn(),
    enregistrerControleQualiteAssemblage: vi.fn(),
    terminerDemontage: vi.fn(),
    bonAssemblageUrl: (id) => `/api/django/installations/ordres-assemblage/${id}/bon-pdf/`,
  },
}))

import installationsApi from '../../api/installationsApi'
import AteliersPage from './AteliersPage'

const ORDRE = {
  id: 7, reference: 'ASM-0007', kit: 3, kit_nom: 'Kit Toiture',
  quantite: 2, statut: 'planifie', date_prevue: null, lignes: [],
}

const ETAPE = {
  id: 21, ordre: 7, etape_modele: 5, libelle: 'Sertir les MC4',
  instructions: '', duree_attendue_min: 30, piece_jointe: null,
  fait: false, fait_par: null, fait_par_nom: null, fait_le: null,
  duree_reelle_min: null,
}

const LIGNE = {
  id: 31, ordre: 7, produit: 9, produit_nom: 'Panneau 550W',
  designation: 'Panneau 550W', quantite: '4.00', origine: 'kit',
}

beforeEach(() => {
  vi.clearAllMocks()
  installationsApi.getOrdresAssemblage.mockResolvedValue({ data: [ORDRE] })
  installationsApi.getOrdresDemontage.mockResolvedValue({ data: [] })
  installationsApi.getKitsAssemblage.mockResolvedValue({
    data: [{
      id: 3, nom: 'Kit Toiture', reference_interne: 'KT-1', produit_compose: 2,
      produit_compose_nom: 'Toiture', active: true, note: '',
      composants: [{ id: 1, produit: 9, produit_nom: 'Panneau 550W', quantite: '4.00' }],
      created_by: 1, date_creation: '2026-07-01', date_modification: '2026-07-01',
    }],
  })
  installationsApi.getDisponibiliteAssemblage.mockResolvedValue({ data: [] })
  installationsApi.getControleQualiteAssemblage.mockResolvedValue({ data: [] })
  installationsApi.getHistoriqueAssemblage.mockResolvedValue({ data: [] })
  installationsApi.getEtapesAssemblage.mockResolvedValue({ data: [ETAPE] })
  installationsApi.getLignesAssemblage.mockResolvedValue({ data: [LIGNE] })
  installationsApi.getRapportRebuts.mockResolvedValue({ data: [] })
})
afterEach(() => { cleanup() })

async function ouvrirOrdre() {
  render(<AteliersPage />)
  const ligne = await screen.findByText('ASM-0007')
  fireEvent.click(ligne)
  return await screen.findByRole('dialog')
}

describe('AteliersPage — exports d’atelier enfin câblés (WIR247/WIR248)', () => {
  it('la gamme d’exécution est rendue et une étape se coche', async () => {
    installationsApi.cocherEtapeAssemblage.mockResolvedValue({ data: { ...ETAPE, fait: true } })
    const dialog = await ouvrirOrdre()

    await waitFor(() => expect(installationsApi.getEtapesAssemblage).toHaveBeenCalledWith(7))
    expect(within(dialog).getByText(/Gamme d'exécution/)).toBeInTheDocument()
    expect(within(dialog).getByText(/Sertir les MC4/)).toBeInTheDocument()

    fireEvent.click(within(dialog).getByRole('checkbox', { name: /Sertir les MC4/ }))
    await waitFor(() => expect(installationsApi.cocherEtapeAssemblage)
      .toHaveBeenCalledWith(7, 5, expect.objectContaining({ fait: true })))
  })

  it('les lignes de composant sont éditables tant que l’ordre est planifié', async () => {
    installationsApi.updateLigneAssemblage.mockResolvedValue({ data: LIGNE })
    const dialog = await ouvrirOrdre()

    await waitFor(() => expect(installationsApi.getLignesAssemblage).toHaveBeenCalledWith(7))
    const champ = within(dialog).getByLabelText(/Quantité de Panneau 550W/)
    fireEvent.change(champ, { target: { value: '6' } })
    fireEvent.blur(champ)
    await waitFor(() => expect(installationsApi.updateLigneAssemblage)
      .toHaveBeenCalledWith(31, { quantite: '6' }))
  })

  it('ordre DÉMARRÉ : plus d’édition des lignes (composition figée)', async () => {
    installationsApi.getOrdresAssemblage.mockResolvedValue({
      data: [{ ...ORDRE, statut: 'en_cours' }],
    })
    const dialog = await ouvrirOrdre()

    await waitFor(() => expect(installationsApi.getEtapesAssemblage).toHaveBeenCalled())
    expect(within(dialog).queryByText('Lignes de composant')).toBeNull()
    expect(within(dialog).queryByLabelText(/Quantité de Panneau 550W/)).toBeNull()
  })

  it('la nomenclature du kit s’ouvre depuis le détail', async () => {
    const dialog = await ouvrirOrdre()
    fireEvent.click(within(dialog).getByRole('button', { name: 'Nomenclature' }))
    // Rendue depuis `installations.Kit.composants` (déjà imbriqué au
    // serializer) — jamais via l'endpoint stock, dont les ids ne correspondent pas.
    expect(await within(dialog).findByText('×4.00')).toBeInTheDocument()
  })

  it('rebut : refusé sans motif, puis POST avec motif (WIR248)', async () => {
    installationsApi.declarerRebutAssemblage.mockResolvedValue({ data: { id: 1 } })
    const dialog = await ouvrirOrdre()
    await waitFor(() => expect(installationsApi.getLignesAssemblage).toHaveBeenCalled())

    fireEvent.click(within(dialog).getByRole('button', { name: /Déclarer un rebut/ }))
    const dialogs = await screen.findAllByRole('dialog')
    const rebut = dialogs[dialogs.length - 1]

    // Composant choisi mais PAS de motif → refus côté écran, aucun appel.
    const selects = within(rebut).getAllByRole('combobox')
    fireEvent.change(selects[0], { target: { value: '9' } })
    fireEvent.click(within(rebut).getByRole('button', { name: /Déclarer le rebut/ }))
    expect(await within(rebut).findByRole('alert')).toHaveTextContent(/motif/i)
    expect(installationsApi.declarerRebutAssemblage).not.toHaveBeenCalled()

    // Avec motif → POST.
    fireEvent.change(selects[1], { target: { value: 'casse' } })
    fireEvent.click(within(rebut).getByRole('button', { name: /Déclarer le rebut/ }))
    await waitFor(() => expect(installationsApi.declarerRebutAssemblage)
      .toHaveBeenCalledWith(7, expect.objectContaining({ produit: '9', motif: 'casse' })))
  })

  it('le rapport des rebuts rend ses lignes agrégées (WIR248)', async () => {
    installationsApi.getRapportRebuts.mockResolvedValue({
      data: [{
        produit_id: 9, produit_nom: 'Panneau 550W', quantite_totale: 3,
        motifs: { casse: 2, defaut: 1 },
      }],
    })
    render(<AteliersPage />)

    await waitFor(() => expect(installationsApi.getRapportRebuts).toHaveBeenCalled())
    expect(await screen.findByText('Rebuts')).toBeInTheDocument()
    expect(await screen.findByText(/Casse : 2/)).toBeInTheDocument()
  })
})
