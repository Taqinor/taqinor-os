import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'

/* AOF180 — équipements retenus, bascule et rapport.
   Cas réel de la session : la bascule batterie BOS-G → BOS-B Pro-A3 a exigé
   23 remplacements cohérents, et son rapport a rattrapé le défaut « la
   justification dit 2 800 DH HT/kWh alors que le bordereau est à 2 600 ». */

const mocks = vi.hoisted(() => ({ list: vi.fn(), bascule: vi.fn(), getProduits: vi.fn() }))

vi.mock('../../../api/aoApi', () => ({
  default: { equipements: { list: mocks.list, bascule: mocks.bascule } },
}))
vi.mock('../../../api/stockApi', () => ({ default: { getProduits: mocks.getProduits } }))

import EquipementsPage from './EquipementsPage'
import { payloadBascule } from './BasculeAssistant.utils'

const EQUIPEMENTS = [
  {
    id: 1, role: 'module', designation: 'Module 625 Wc', marque: 'JA Solar',
    reference_constructeur: 'JAM72D40-625', quantite: 560,
    caracteristiques: { puissance: '625 Wc', dimensions: '2382 × 1134 mm' },
    approvisionnement: { statut: 'disponible', libelle: 'Disponible', aucun_appro_nouveau: true },
  },
  {
    id: 2, role: 'batterie', designation: 'Batterie BOS-G', marque: 'BOS',
    reference_constructeur: 'BOS-G', quantite: 12,
    caracteristiques: { capacite: '10 kWh' },
    approvisionnement: { statut: 'archive', libelle: 'Produit archivé', aucun_appro_nouveau: false },
  },
]

const CATALOGUE = [
  {
    id: 77, nom: 'Batterie BOS-B Pro-A3', marque: 'BOS', reference: 'BOS-B-PRO-A3',
    prix_vente: 26000,
    // Le catalogue PORTE un prix d'achat — il ne doit JAMAIS être affiché.
    prix_achat: 18500,
  },
]

const RAPPORT = {
  ancien_libelle: 'Batterie BOS-G', nouveau_libelle: 'Batterie BOS-B Pro-A3',
  motif: 'BOS-G indisponible',
  emplacements_modifies: [
    { id: 1, emplacement: 'Mémoire technique — 12 désignations' },
    { id: 2, emplacement: 'Bordereau — 3 lignes' },
  ],
  emplacements_suspects: [
    {
      id: 3, emplacement: 'À REMPLIR PAR ACCORDIA — parenthèse de justification',
      extrait: 'batteries 2 800 DH HT/kWh',
    },
  ],
  fiches_retirees: [{ id: 4, libelle: 'Fiche BOS-G' }],
  fiches_ajoutees: [{ id: 5, libelle: 'Fiche BOS-B Pro-A3' }],
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: EQUIPEMENTS })
  mocks.getProduits.mockResolvedValue({ data: CATALOGUE })
  mocks.bascule.mockResolvedValue({ data: { rapport: RAPPORT } })
})

describe('EquipementsPage (AOF180)', () => {
  it('liste par rôle avec les caractéristiques SNAPSHOT et le statut d’approvisionnement', async () => {
    render(<EquipementsPage projetId={3} />)
    expect(await screen.findByText('Modules')).toBeInTheDocument()
    expect(screen.getByText('Batteries')).toBeInTheDocument()
    expect(screen.getByText('Module 625 Wc')).toBeInTheDocument()
    expect(screen.getByText(/JA Solar · réf\. JAM72D40-625 · qté 560/)).toBeInTheDocument()
    expect(screen.getByText('625 Wc')).toBeInTheDocument()
    expect(screen.getByText('Disponible')).toBeInTheDocument()
    expect(screen.getByText('Produit archivé')).toBeInTheDocument()
  })

  it('l’argument « aucun approvisionnement nouveau » n’est affiché que si le SERVEUR le confirme', async () => {
    render(<EquipementsPage projetId={3} />)
    await screen.findByText('Module 625 Wc')
    // Une batterie archivée : l'argument est indisponible.
    expect(screen.queryByText('Aucun approvisionnement nouveau')).not.toBeInTheDocument()
  })

  it('affiche l’argument quand TOUS les matériels sont confirmés approvisionnés', async () => {
    mocks.list.mockResolvedValue({
      data: EQUIPEMENTS.map((e) => ({
        ...e, approvisionnement: { ...e.approvisionnement, aucun_appro_nouveau: true },
      })),
    })
    render(<EquipementsPage projetId={3} />)
    expect(await screen.findByText('Aucun approvisionnement nouveau')).toBeInTheDocument()
  })

  it('bascule en trois clics, motif OBLIGATOIRE, et AUCUN coût dans le payload', async () => {
    render(<EquipementsPage projetId={3} />)
    await screen.findByText('Batterie BOS-G')

    // Clic 1 — ouvrir l'assistant sur la batterie.
    fireEvent.click(screen.getAllByRole('button', { name: 'Basculer' })[1])
    expect(await screen.findByText(/Basculer « Batterie BOS-G »/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Confirmer la bascule' })).toBeDisabled()

    // Clic 2 — choisir le nouveau matériel dans le catalogue.
    fireEvent.click(await screen.findByRole('button', { name: /Batterie BOS-B Pro-A3/ }))
    // Motif encore vide : la confirmation reste refusée.
    expect(screen.getByRole('button', { name: 'Confirmer la bascule' })).toBeDisabled()
    fireEvent.change(screen.getByLabelText(/Motif de la bascule/), {
      target: { value: 'BOS-G indisponible — remplacée par BOS-B Pro-A3.' },
    })

    // Clic 3 — confirmer.
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer la bascule' }))
    await waitFor(() => expect(mocks.bascule).toHaveBeenCalledWith(2, {
      nouveau_produit: 77,
      motif: 'BOS-G indisponible — remplacée par BOS-B Pro-A3.',
    }))

    const corps = JSON.stringify(mocks.bascule.mock.calls[0][1])
    expect(corps).not.toMatch(/prix_achat|cout|coût|marge|benefice|bénéfice/i)
  })

  it('n’affiche JAMAIS le prix d’achat d’un produit du catalogue', async () => {
    render(<EquipementsPage projetId={3} />)
    await screen.findByText('Batterie BOS-G')
    fireEvent.click(screen.getAllByRole('button', { name: 'Basculer' })[1])
    await screen.findByRole('button', { name: /Batterie BOS-B Pro-A3/ })
    expect(screen.queryByText(/18\s?500/)).not.toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/18500|18 500/)
  })

  it('le rapport affiche les emplacements SUSPECTS sans les masquer (2 800 vs 2 600)', async () => {
    render(<EquipementsPage projetId={3} />)
    await screen.findByText('Batterie BOS-G')
    fireEvent.click(screen.getAllByRole('button', { name: 'Basculer' })[1])
    fireEvent.click(await screen.findByRole('button', { name: /Batterie BOS-B Pro-A3/ }))
    fireEvent.change(screen.getByLabelText(/Motif de la bascule/), { target: { value: 'BOS-G indisponible' } })
    fireEvent.click(screen.getByRole('button', { name: 'Confirmer la bascule' }))

    expect(await screen.findByText(/1 emplacement\(s\) SUSPECT\(S\)/)).toBeInTheDocument()
    expect(screen.getByText(/batteries 2 800 DH HT\/kWh/)).toBeInTheDocument()
    expect(screen.getByText(/À REMPLIR PAR ACCORDIA/)).toBeInTheDocument()
    // Les 4 catégories du rapport sont rendues.
    expect(screen.getByText('Emplacements modifiés')).toBeInTheDocument()
    expect(screen.getByText('Fiches techniques retirées')).toBeInTheDocument()
    expect(screen.getByText('Fiches techniques ajoutées')).toBeInTheDocument()
  })

  it('payloadBascule est une ALLOWLIST : rien d’autre ne peut partir sur le réseau', () => {
    expect(payloadBascule({ produitId: 5, motif: '  raison  ' }))
      .toEqual({ nouveau_produit: 5, motif: 'raison' })
    expect(payloadBascule({ produitId: 5, motif: 'r', quantite: 12 }))
      .toEqual({ nouveau_produit: 5, motif: 'r', quantite: 12 })
    expect(Object.keys(payloadBascule({ produitId: 5, motif: 'r' })).sort())
      .toEqual(['motif', 'nouveau_produit'])
  })
})
