import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

/* ============================================================================
   CAL41 — le lien vers le calepinage 3D sur la fiche affaire.
   ----------------------------------------------------------------------------
   Après CAL32 l'affaire PORTE un `calepinage_id` (servi en lecture seule par
   `AppelOffreSerializer`), mais aucun écran ne le montrait : le module autonome
   restait injoignable depuis l'affaire qui l'a fait naître.

   Ce que ce fichier prouve :
   1. affaire AVEC `calepinage_id` ⇒ un lien vers `/calepinage/<id>` ;
   2. affaire SANS ⇒ RIEN (jamais un lien mort) ;
   3. la phrase de préséance de `docs/calepinage-module.md` (CAL239) est citée ;
   4. la route `design` (studio 2D opposable) n'est pas touchée — l'atelier
      reste monté dans le même onglet.
   ========================================================================== */

const mocks = vi.hoisted(() => ({
  get: vi.fn(), affairesList: vi.fn(), toituresList: vi.fn(),
  getComments: vi.fn(), getAttachments: vi.fn(),
  transitions: vi.fn(), lead: vi.fn(),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useParams: () => ({ id: '1' }) }
})

vi.mock('../../api/aoApi', () => ({
  default: {
    affaires: {
      get: mocks.get, list: mocks.affairesList,
      transitions: mocks.transitions, changerStatut: vi.fn(),
      lead: mocks.lead, rattacherLead: vi.fn(),
    },
    toitures: { list: mocks.toituresList, create: vi.fn(), reprendreContour3d: vi.fn() },
    batiments: { list: vi.fn().mockResolvedValue({ data: [] }) },
    variantes: { list: vi.fn().mockResolvedValue({ data: [] }) },
    dossiers: {
      list: vi.fn().mockResolvedValue({ data: [] }), get: vi.fn(),
      genererPiece: vi.fn(), controlesAvantDepot: vi.fn(), completude: vi.fn(),
      changerStatut: vi.fn(),
    },
    checklistPartenaire: { list: vi.fn(), pointer: vi.fn() },
    piecesDossierAo: { list: vi.fn(), update: vi.fn() },
    piecesConsultation: { list: vi.fn(), create: vi.fn(), update: vi.fn(), additif: vi.fn() },
    seriesQR: { list: vi.fn(), create: vi.fn() },
    calepinages: { get: vi.fn(), calculer: vi.fn() },
    equipements: { list: vi.fn(), bascule: vi.fn() },
    exigencesCps: { list: vi.fn(), create: vi.fn() },
    bordereaux: { list: vi.fn(), get: vi.fn(), controles: vi.fn() },
    lignesBordereau: { update: vi.fn() },
    cautionsSoumission: { list: vi.fn(), create: vi.fn(), deriverDefinitive: vi.fn() },
    echeancesAo: { list: vi.fn(), create: vi.fn(), update: vi.fn() },
    resultatsAo: { list: vi.fn(), enregistrer: vi.fn() },
    planches: { list: vi.fn(), upload: vi.fn() },
  },
}))

vi.mock('../../hooks/useHasPermission', () => ({
  useHasPermission: () => false, useHasRole: () => false,
  useIsAdmin: () => false, useIsAdminOrResponsable: () => false,
}))

vi.mock('../../api/recordsApi', () => ({
  default: {
    getComments: mocks.getComments, getAttachments: mocks.getAttachments,
    createComment: vi.fn(), uploadAttachment: vi.fn(),
  },
}))

import AffaireDetail from './AffaireDetail'

const AFFAIRE = {
  id: 1, reference: 'AO-2026-001', objet: 'Centrale solaire école',
  acheteur: 'Commune X', statut: 'depose', calepinage_id: 314,
}

const rendre = () => render(<MemoryRouter><AffaireDetail /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.get.mockResolvedValue({ data: AFFAIRE })
  mocks.getComments.mockResolvedValue({ data: [] })
  mocks.getAttachments.mockResolvedValue({ data: [] })
  mocks.toituresList.mockResolvedValue({ data: [] })
  mocks.affairesList.mockResolvedValue({ data: [] })
  mocks.transitions.mockResolvedValue({
    data: { statut: 'depose', statut_display: 'Déposé', transitions: [] },
  })
  mocks.lead.mockResolvedValue({ data: { lead_id: null, fiche: null } })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('AffaireDetail — lien calepinage 3D (CAL41)', () => {
  it('affiche le lien vers /calepinage/<id> quand l’affaire en porte un', async () => {
    rendre()
    await screen.findAllByText('AO-2026-001')
    await userEvent.click(screen.getByRole('tab', { name: 'Calepinages' }))

    const lien = await screen.findByRole('link', { name: 'Ouvrir le calepinage 3D' })
    expect(lien).toHaveAttribute('href', '/calepinage/314')
  })

  it('cite la règle de préséance (CAL239), mot pour mot', async () => {
    rendre()
    await screen.findAllByText('AO-2026-001')
    await userEvent.click(screen.getByRole('tab', { name: 'Calepinages' }))

    expect(await screen.findByText(
      'Le bordereau est servi par la variante 2D retenue. Le calepinage 3D est un document de travail.',
    )).toBeInTheDocument()
  })

  it('affaire SANS calepinage : aucun bloc, aucun lien mort', async () => {
    mocks.get.mockResolvedValue({ data: { ...AFFAIRE, calepinage_id: null } })
    rendre()
    await screen.findAllByText('AO-2026-001')
    await userEvent.click(screen.getByRole('tab', { name: 'Calepinages' }))

    await waitFor(() => expect(mocks.toituresList).toHaveBeenCalled())
    expect(screen.queryByRole('link', { name: 'Ouvrir le calepinage 3D' })).toBeNull()
    expect(document.querySelector('[data-ao-lien-calepinage]')).toBeNull()
  })

  it('l’onglet garde son contenu existant (studio 2D opposable intact)', async () => {
    rendre()
    await screen.findAllByText('AO-2026-001')
    await userEvent.click(screen.getByRole('tab', { name: 'Calepinages' }))

    // Sans toiture relevée, l'onglet affiche SON état vide d'origine : le lien
    // CAL41 s'ajoute au-dessus, il ne remplace rien.
    expect(await screen.findByText('Aucune toiture à calepiner')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ouvrir le calepinage 3D' }))
      .toBeInTheDocument()
  })
})
