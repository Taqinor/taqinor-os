import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  render, screen, waitFor, fireEvent, act, within,
} from '@testing-library/react'
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
  controlesAvantDepot: vi.fn(),
  // PACT71 — `ChecklistPartenaire` est désormais monté PAR DÉFAUT (pleine
  // largeur, sous la grille) : sans ces bouchons, l'écran appellerait des
  // méthodes non définies dès son montage.
  checklistList: vi.fn(),
  completude: vi.fn(),
  // PACT72 — `PiecesFournies` est désormais monté PAR DÉFAUT (pleine largeur).
  piecesFourniesList: vi.fn(),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useParams: () => ({ id: '7' }) }
})

vi.mock('../../../api/aoApi', () => ({
  default: {
    dossiers: {
      get: mocks.get,
      genererPiece: mocks.genererPiece,
      // AOF176 — endpoint RÉEL, appelé par le contenu par défaut de
      // l'emplacement « actions ».
      controlesAvantDepot: mocks.controlesAvantDepot,
      // PACT71 — complétude dérivée, lue par `ChecklistPartenaire`.
      completude: mocks.completude,
    },
    // `EcheancesDossier` ne l'appelle que depuis le formulaire de prorogation,
    // que cet écran ne monte pas (`peutProroger={false}` — le serveur ne
    // connaît pas les champs de prorogation).
    affaires: { update: vi.fn() },
    checklistPartenaire: { list: mocks.checklistList, pointer: vi.fn() },
    piecesDossierAo: { list: mocks.piecesFourniesList, update: vi.fn() },
  },
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

/* Le libellé d'une pièce apparaît DEUX fois à l'écran : dans sa ligne de la
   colonne « Pièces du dossier » ET dans la colonne « Aperçu », qui nomme la
   pièce sélectionnée (la première l'est d'office). Les assertions de LISTE
   visent donc la ligne, repérée par le hook e2e figé `data-ao-piece`
   (`../E2E_HOOKS.md`, AOF8) — plus précis qu'une recherche de texte sur toute
   la page, et robuste au branchement de l'aperçu réel (AOF175). */
const ligneP = async (code) => {
  await waitFor(() => {
    expect(document.querySelector(`[data-ao-piece="${code}"]`)).not.toBeNull()
  })
  return within(document.querySelector(`[data-ao-piece="${code}"]`))
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.get.mockResolvedValue({ data: DOSSIER_V1 })
  mocks.genererPiece.mockResolvedValue({ data: {} })
  mocks.controlesAvantDepot.mockResolvedValue({
    data: { controles: [{ id: 1, code: 'caution', libelle: 'Caution constituée', severite: 'ok' }] },
  })
  mocks.checklistList.mockResolvedValue({ data: [] })
  mocks.completude.mockResolvedValue({ data: { complet: false, raisons_de_non_depot: [] } })
  mocks.piecesFourniesList.mockResolvedValue({ data: [] })
})

describe('DossierPage (AOF174)', () => {
  it('liste les pièces du gabarit avec leur pastille d’état (transitions rendues)', async () => {
    renderScreen()
    expect((await ligneP('memoire')).getByText('Mémoire technique')).toBeInTheDocument()
    // à produire / généré / à jour : les 3 transitions rendues par statusAo.
    expect(screen.getByText('À jour')).toBeInTheDocument()
    expect(screen.getByText('Généré')).toBeInTheDocument()
    expect(screen.getByText('À produire')).toBeInTheDocument()
  })

  it('ne liste AUCUNE pièce de visibilité interne ou directeur', async () => {
    renderScreen()
    await ligneP('memoire')
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
    await ligneP('memoire')
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

/* ══ Les 3 EMPLACEMENTS ont un contenu PAR DÉFAUT ═══════════════════════════
   `renderEcheances` et `actions` étaient facultatifs et AUCUN des deux
   monteurs réels (l'onglet « Dossier » de la fiche affaire, la route
   `/ao/dossiers/:id`) ne les remplissait : `ControlesAvantDepot` (AOF176),
   `ZipButton` (AOF177) et `EcheancesDossier` (AOF178) n'étaient importés par
   AUCUN fichier de l'application. Ils sont désormais le contenu par défaut —
   et les props gardent la priorité pour qui veut la main. */
describe('DossierPage — contenu par défaut des emplacements (AOF176/177/178)', () => {
  it('monte les contrôles avant dépôt, le bouton ZIP et les échéances sans qu’un monteur ait à les passer', async () => {
    renderScreen()

    // AOF176 — l'endpoint est RÉEL, il est appelé avec l'id du DOSSIER.
    await waitFor(() => expect(mocks.controlesAvantDepot).toHaveBeenCalledWith(7))
    expect(await screen.findByRole('heading', { name: 'Contrôles avant dépôt' })).toBeInTheDocument()
    expect(screen.getByText('Caution constituée')).toBeInTheDocument()
    // AOF177 — le ZIP est rendu DANS le panneau de contrôles (`zipSlot`).
    expect(screen.getByRole('button', { name: /Constituer le ZIP de dépôt/ })).toBeInTheDocument()
    // AOF178 — les échéances du dossier, pas le simple centre d'échéances.
    expect(screen.getByText('Date limite de remise des plis')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Jalons' })).toBeInTheDocument()
  })

  it('écrit le motif SUR le bouton ZIP quand un contrôle bloquant est rouge (jamais un bouton grisé muet)', async () => {
    mocks.controlesAvantDepot.mockResolvedValue({
      data: {
        controles: [{
          id: 2, code: 'caution', libelle: 'Caution constituée',
          severite: 'bloquant', message: 'caution expirée le 01/09',
        }],
      },
    })
    renderScreen()

    const zip = await screen.findByRole('button', { name: /ZIP bloqué — caution expirée le 01\/09/ })
    expect(zip).toBeDisabled()
  })

  it('bloque aussi le ZIP quand le dossier porte un verrou, en le DISANT', async () => {
    mocks.get.mockResolvedValue({
      data: { ...DOSSIER_V1, verrou: { porteur: 'Sami B.', operation_label: 'cascade de prix' } },
    })
    renderScreen()

    expect(
      await screen.findByRole('button', { name: /ZIP bloqué — une opération est déjà en cours/ }),
    ).toBeDisabled()
  })

  it('le compte à rebours n’invente aucune date : « — » sans `dateLimite`, la date fournie sinon', async () => {
    const { unmount } = renderScreen()
    await screen.findByText('Date limite de remise des plis')
    // `DossierAOSerializer` ne publie AUCUNE date limite : sans la prop, rien.
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)
    unmount()

    renderScreen({ dateLimite: '2026-09-15' })
    expect((await screen.findAllByText('15/09/2026')).length).toBeGreaterThan(0)
  })

  it('n’affiche AUCUN formulaire de prorogation (AppelOffre ne porte pas ces champs)', async () => {
    renderScreen()
    await screen.findByRole('heading', { name: 'Jalons' })
    expect(screen.queryByText(/Prorogation écrite/)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/Référence du courrier/)).not.toBeInTheDocument()
  })

  it('les props gardent la PRIORITÉ : un monteur qui injecte ses emplacements les garde', async () => {
    renderScreen({
      renderEcheances: () => <p>Échéances injectées</p>,
      actions: () => <p>Actions injectées</p>,
    })

    expect(await screen.findByText('Échéances injectées')).toBeInTheDocument()
    expect(screen.getByText('Actions injectées')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Contrôles avant dépôt' })).not.toBeInTheDocument()
    expect(mocks.controlesAvantDepot).not.toHaveBeenCalled()
  })
})
