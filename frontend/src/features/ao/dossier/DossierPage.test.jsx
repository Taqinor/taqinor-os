import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, act } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* AOF174 — l'écran « Dossier de soumission ».
   Trois garanties prouvées ici :
     1. la PÉREMPTION arrive SANS rafraîchir la page (le resondage
        `useVisibilityAwarePolling` est déclenché par un `visibilitychange`,
        pas par un remontage) et NOMME son motif ;
     2. les TRANSITIONS d'état (à produire → généré → à jour → périmé) sont
        rendues par la pastille partagée `statusAo` ;
     3. AUCUNE pièce de visibilité interne ou directeur n'est listée. */

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  genererPiece: vi.fn(),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useParams: () => ({ id: '7' }) }
})

vi.mock('../../../api/aoApi', () => ({
  default: { dossiers: { get: mocks.get, genererPiece: mocks.genererPiece } },
}))

import DossierPage from './DossierPage'

const piece = (over) => ({
  id: 1, code: 'memoire', type: 'memoire', libelle: 'Mémoire technique',
  statut: 'a_jour', visibilite: 'client', ...over,
})

const DOSSIER_V1 = {
  id: 7, reference: 'DS-2026-014', verrou: null,
  echeances: [{ id: 1, libelle: 'Remise des plis', date_echeance: '2026-09-15', type: 'remise' }],
  pieces: [
    piece({ id: 1, code: 'memoire', libelle: 'Mémoire technique', statut: 'a_jour' }),
    piece({ id: 2, code: 'bordereau', libelle: 'Bordereau des prix', statut: 'genere' }),
    piece({ id: 3, code: 'acte', libelle: "Acte d'engagement", statut: 'a_produire' }),
    piece({
      id: 4, code: 'attestation_fiscale', libelle: 'Attestation fiscale',
      statut: 'fourni', controlee: false, motif_hors_controle: 'Fournie par le partenaire',
    }),
    // JAMAIS listées : l'économie est réservée au directeur.
    piece({ id: 90, code: 'cout_revient', libelle: 'Coût de revient', visibilite: 'directeur' }),
    piece({ id: 91, code: 'note_interne', libelle: 'Note interne', visibilite: 'interne' }),
  ],
}

// V2 : le calepinage du bâtiment C a bougé → le serveur périme la planche.
const DOSSIER_V2 = {
  ...DOSSIER_V1,
  pieces: DOSSIER_V1.pieces.map((p) => (p.id === 1
    ? {
      ...p,
      statut: 'perime',
      motif_peremption: 'le calepinage du bâtiment C est passé de 264 à 314',
    }
    : p)),
}

const renderScreen = (props) => render(<MemoryRouter><DossierPage {...props} /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.get.mockResolvedValue({ data: DOSSIER_V1 })
  mocks.genererPiece.mockResolvedValue({ data: {} })
})

describe('DossierPage (AOF174)', () => {
  it('liste les pièces du gabarit avec leur pastille d’état (transitions rendues)', async () => {
    renderScreen()
    expect(await screen.findByText('Mémoire technique')).toBeInTheDocument()
    // à produire / généré / à jour : les 3 transitions rendues par statusAo.
    expect(screen.getByText('À jour')).toBeInTheDocument()
    expect(screen.getByText('Généré')).toBeInTheDocument()
    expect(screen.getByText('À produire')).toBeInTheDocument()
  })

  it('ne liste AUCUNE pièce de visibilité interne ou directeur', async () => {
    renderScreen()
    await screen.findByText('Mémoire technique')
    expect(screen.queryByText('Coût de revient')).not.toBeInTheDocument()
    expect(screen.queryByText('Note interne')).not.toBeInTheDocument()
    expect(document.querySelectorAll('[data-ao-piece]')).toHaveLength(4)
  })

  it('une pièce fournie hors fabrique est « hors contrôle » avec son motif — jamais verte', async () => {
    renderScreen()
    await screen.findByText('Attestation fiscale')
    expect(screen.getByText('Hors contrôle')).toBeInTheDocument()
    expect(screen.getByText(/Fournie par le partenaire/)).toBeInTheDocument()
  })

  it('la péremption se déclenche SANS rafraîchir la page, avec le MOTIF et un bandeau « régénérer »', async () => {
    renderScreen()
    await screen.findByText('Mémoire technique')
    expect(screen.queryByText('Périmé')).not.toBeInTheDocument()

    // Le serveur a périmé la pièce ; l'écran resonde (aucun remontage).
    mocks.get.mockResolvedValue({ data: DOSSIER_V2 })
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'))
    })

    expect(await screen.findByText('Périmé')).toBeInTheDocument()
    expect(
      screen.getByText(/le calepinage du bâtiment C est passé de 264 à 314/),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Régénérer « Mémoire technique »/ }),
    ).toBeInTheDocument()
  })

  it('« Régénérer » appelle le service serveur de génération de pièce', async () => {
    mocks.get.mockResolvedValue({ data: DOSSIER_V2 })
    renderScreen()
    fireEvent.click(await screen.findByRole('button', { name: /Régénérer « Mémoire technique »/ }))
    await waitFor(() => expect(mocks.genererPiece).toHaveBeenCalledWith('7', 'memoire'))
  })

  it('le verrou de dossier (AOF155) est affiché et suspend les actions d’écriture', async () => {
    mocks.get.mockResolvedValue({
      data: {
        ...DOSSIER_V2,
        verrou: {
          porteur: 'Sami B.', depuis: '2026-08-01T09:30:00Z',
          operation: 'cascade de prix', operation_label: 'cascade de prix',
        },
      },
    })
    renderScreen()
    expect(await screen.findByText(/Opération en cours sur ce dossier/)).toBeInTheDocument()
    expect(screen.getByText(/Sami B\./)).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Régénérer « Mémoire technique »/ }),
    ).toBeDisabled()
  })
})
