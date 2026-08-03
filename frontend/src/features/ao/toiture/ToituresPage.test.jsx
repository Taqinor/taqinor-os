import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

/* ============================================================================
   AOF190bis — encastrement de « Toitures & relevés » dans un onglet de fiche.
   ----------------------------------------------------------------------------
   `ToituresPage` ne prenait AUCUNE propriété : elle listait toutes les
   affaires de la société et retombait sur la première. Encastrée telle
   quelle sous le titre d'une affaire, elle aurait pu très bien afficher les
   toitures d'une AUTRE affaire — un défaut SILENCIEUX (aucune erreur, aucun
   404 : juste la mauvaise donnée sous le bon titre).

   `affaireId` FOURNI doit donc :
     - filtrer le serveur sur CETTE affaire (`?appel_offre=<id>`, le nom du
       champ réel — `ToitureAOViewSet.get_queryset`, `apps/ao/views.py`) ;
     - ne JAMAIS lister les affaires de la société (aucun sélecteur à
       nourrir, aucune requête à faire) ;
     - masquer le sélecteur d'affaire (proposer d'en changer serait le piège
       que l'encastrement doit précisément éviter).
   `affaireId` ABSENT doit laisser la page pleine largeur `/ao/toitures`
   strictement inchangée (sélecteur + repli sur la première affaire chargée).
   ========================================================================== */

const mocks = vi.hoisted(() => ({ affairesList: vi.fn(), toituresList: vi.fn() }))

vi.mock('../../../api/aoApi', () => ({
  default: {
    affaires: { list: mocks.affairesList },
    toitures: { list: mocks.toituresList },
  },
}))
vi.mock('../../../api/recordsApi', () => ({
  default: { uploadAttachment: vi.fn() },
}))

import ToituresPage from './ToituresPage'

const AFFAIRES = [
  { id: 5, reference_acheteur: 'AO-2026-005' },
  { id: 6, reference_acheteur: 'AO-2026-006' },
]

const TOITURE = {
  id: 41, designation: 'Toiture atelier', forme_display: 'Rectangle',
  surface_m2: '312.5', niveau: 'RDC', type_couverture_display: 'Bac acier',
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.affairesList.mockResolvedValue({ data: AFFAIRES })
  mocks.toituresList.mockResolvedValue({ data: [TOITURE] })
})

describe('ToituresPage — encastrée avec `affaireId` (AOF190bis)', () => {
  it('filtre le serveur sur `appel_offre` — CETTE affaire, jamais un repli sur une autre', async () => {
    render(<ToituresPage affaireId={7} />)
    await waitFor(() => expect(mocks.toituresList).toHaveBeenCalledWith({ appel_offre: 7 }))
    expect(await screen.findByText('Toiture atelier')).toBeInTheDocument()
  })

  it('ne liste JAMAIS les affaires de la société quand `affaireId` est fourni', async () => {
    render(<ToituresPage affaireId={7} />)
    await waitFor(() => expect(mocks.toituresList).toHaveBeenCalled())
    expect(mocks.affairesList).not.toHaveBeenCalled()
  })

  it('masque le sélecteur d’affaire — l’onglet a déjà choisi l’affaire', async () => {
    render(<ToituresPage affaireId={7} />)
    await screen.findByText('Toiture atelier')
    expect(screen.queryByLabelText('Affaire')).toBeNull()
    expect(document.getElementById('ao-toitures-affaire')).toBeNull()
  })

  it('affaire sans toiture → état vide EXPLICITE, jamais une liste muette ou celle d’une autre affaire', async () => {
    mocks.toituresList.mockResolvedValue({ data: [] })
    render(<ToituresPage affaireId={9} />)
    expect(await screen.findByText('Aucune toiture relevée pour cette affaire.')).toBeInTheDocument()
    expect(mocks.affairesList).not.toHaveBeenCalled()
  })
})

describe('ToituresPage — page pleine largeur `/ao/toitures`, sans `affaireId` (non-régression)', () => {
  it('liste les affaires, retombe sur la première et rend le sélecteur', async () => {
    render(<ToituresPage />)
    await waitFor(() => expect(mocks.affairesList).toHaveBeenCalled())
    await waitFor(() => expect(mocks.toituresList).toHaveBeenCalledWith({ appel_offre: 5 }))
    expect(await screen.findByText('Toiture atelier')).toBeInTheDocument()

    expect(screen.getByLabelText('Affaire')).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'AO-2026-005' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'AO-2026-006' })).toBeInTheDocument()
  })

  it('affaire sans toiture (page pleine largeur) → même état vide explicite', async () => {
    mocks.toituresList.mockResolvedValue({ data: [] })
    render(<ToituresPage />)
    await waitFor(() => expect(mocks.affairesList).toHaveBeenCalled())
    expect(await screen.findByText('Aucune toiture relevée pour cette affaire.')).toBeInTheDocument()
  })
})
