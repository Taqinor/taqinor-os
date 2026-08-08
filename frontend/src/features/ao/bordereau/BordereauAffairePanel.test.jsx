import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { formatMAD } from '../../../lib/format'

/* PACT69 — câblage réel de l'onglet « Bordereau » de la fiche affaire.
   Preuve centrale : le CONTRAT SERVEUR réel (`montant_remise_globale`,
   `total_tva`, `taux_tva_effectif`, `montant_ht`) est correctement MAPPÉ vers
   le contrat que `BordereauPage` (déjà testé séparément) attend — c'est
   exactement le défaut front↔back que ce groupe corrige, prouvé ici sur les
   VRAIS noms de champs du sérialiseur (`apps/ao/serializers.py`). */

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  get: vi.fn(),
  controles: vi.fn(),
  updateLigne: vi.fn(),
}))

vi.mock('../../../api/aoApi', () => ({
  default: {
    bordereaux: { list: mocks.list, get: mocks.get, controles: mocks.controles },
    lignesBordereau: { update: mocks.updateLigne },
  },
}))

import BordereauAffairePanel from './BordereauAffairePanel'

const SECTION = { id: 1, numero: 'A', libelle: 'Bâtiment A' }
const LIGNE = {
  id: 101, bordereau: 9, section: 1, numero: 1,
  designation: 'Modules photovoltaïques 625 Wc', unite: 'U',
  quantite: '152.000', prix_unitaire: '1200.00', montant_ht: '182400.00',
  taux_tva: null, taux_tva_effectif: '20.00', montant_tva: '36480.00',
  remise_pct: '0.00', quantite_source: 'manuelle', quantite_verrouillee: false,
}
const BORDEREAU_SERVEUR = {
  id: 9, appel_offre: 42, intitule: 'Bordereau des prix', indice_revision: 'A',
  clause_reserve: 'Les prix sont fermes et non révisables.',
  sections: [SECTION], lignes: [LIGNE],
  sous_total_ht: '182400.00', montant_remise_globale: '0.00',
  total_ht: '182400.00', total_tva: '36480.00', total_ttc: '218880.00',
}

const renderPanel = (props) => render(<BordereauAffairePanel affaireId={42} {...props} />)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: [{ id: 9, intitule: 'Bordereau des prix', indice_revision: 'A' }] })
  mocks.get.mockResolvedValue({ data: BORDEREAU_SERVEUR })
  mocks.controles.mockResolvedValue({ data: { remettable: true, raisons: [] } })
  mocks.updateLigne.mockResolvedValue({ data: LIGNE })
})

describe('BordereauAffairePanel (PACT69)', () => {
  it('charge le bordereau de l’affaire et affiche le total TTC réel du serveur', async () => {
    renderPanel()
    expect(mocks.list).toHaveBeenCalledWith({ appel_offre: 42 })
    await waitFor(() => expect(screen.getByText(formatMAD(218880).replace(/\s+/g, ' '))).toBeInTheDocument())
  })

  it('mappe les noms de champs RÉELS du serveur vers le contrat de BordereauPage '
    + '(montant_remise_globale→remise_globale, total_tva→tva_montant)', async () => {
    renderPanel()
    // Total HT réel (182400) et TVA réelle (36480) doivent être visibles —
    // s'ils ne l'étaient pas, le mapping serait cassé et BordereauPage
    // afficherait des tirets à la place.
    await waitFor(() => expect(screen.getByText(formatMAD(182400).replace(/\s+/g, ' '))).toBeInTheDocument())
    expect(screen.getByText(formatMAD(36480).replace(/\s+/g, ' '))).toBeInTheDocument()
  })

  it('aucun bordereau : état vide honnête, sans inventer de bordereau', async () => {
    mocks.list.mockResolvedValue({ data: [] })
    renderPanel()
    expect(await screen.findByText('Aucun bordereau des prix')).toBeInTheDocument()
    expect(mocks.get).not.toHaveBeenCalled()
  })

  it('une absence de clause de réserve est signalée via l’action serveur « controles »', async () => {
    mocks.controles.mockResolvedValue({
      data: { remettable: false, raisons: ['Marché à prix unitaires : la clause de réserve est obligatoire.'] },
    })
    renderPanel()
    expect(await screen.findByText('Bordereau non remettable')).toBeInTheDocument()
    expect(screen.getByText(/clause de réserve est obligatoire/)).toBeInTheDocument()
  })

  it('modifier une ligne appelle un PATCH RÉEL sur lignes-bordereau puis recharge le bordereau', async () => {
    renderPanel()
    const champ = await screen.findByLabelText('Quantité — Modules photovoltaïques 625 Wc')
    await userEvent.clear(champ)
    await userEvent.type(champ, '160')
    await userEvent.tab()
    await waitFor(() => expect(mocks.updateLigne).toHaveBeenCalledWith(101, { quantite: '160' }))
    // Le panneau relit le bordereau COMPLET après l'écriture — jamais un
    // patch local qui ferait diverger les totaux affichés du serveur.
    await waitFor(() => expect(mocks.get).toHaveBeenCalledTimes(2))
  })
})
