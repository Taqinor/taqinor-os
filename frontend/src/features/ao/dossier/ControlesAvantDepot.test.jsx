import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'

/* AOF176 — la porte de cohérence croisée devient VISIBLE.
   Les 4 classes de défaut testées ici sont celles RÉELLEMENT observées pendant
   la session AO FRDISI du 27/07/2026 :
     1. la justification dit encore « 2 800 DH HT/kWh » alors que le bordereau
        final est à 2 600 (le montant a été cascadé, sa justification non) ;
     2. un bordereau frère PÉRIMÉ subsiste (5 219 280) ;
     3. le LISEZ-MOI est FIGÉ (il décrit un état qui n'existe plus) ;
     4. l'en-tête est CONTREDIT par son propre addendum. */

const mocks = vi.hoisted(() => ({ controlesAvantDepot: vi.fn() }))

vi.mock('../../../api/aoApi', () => ({
  default: { dossiers: { controlesAvantDepot: mocks.controlesAvantDepot } },
}))

import ControlesAvantDepot from './ControlesAvantDepot'
import { motifBlocage, severiteDe } from './ControlesAvantDepot.utils'

const JUSTIFICATION = {
  id: 1, code: 'justification_prix_coherente',
  libelle: 'Justification de prix cohérente avec le bordereau',
  message: 'La justification annonce 2 800 DH HT/kWh alors que le bordereau final est à 2 600.',
  severite: 'bloquant', piece_id: 11, piece_libelle: 'À REMPLIR PAR ACCORDIA', ancre: 'parenthèse de justification',
}
const FRERE_PERIME = {
  id: 2, code: 'aucun_artefact_perime',
  libelle: 'Aucun artefact périmé dans le manifeste',
  message: 'Un bordereau frère périmé subsiste (total 5 219 280).',
  severite: 'bloquant', piece_id: 12, piece_libelle: 'Bordereau des prix (frère)',
}
const LISEZ_MOI = {
  id: 3, code: 'lisez_moi_a_jour',
  libelle: 'LISEZ-MOI régénéré avec le pack',
  message: 'Le LISEZ-MOI est figé : il décrit un pack qui n’existe plus.',
  severite: 'avertissement', piece_id: 13, piece_libelle: 'LISEZ-MOI',
}
const ENTETE = {
  id: 4, code: 'entete_non_contredit',
  libelle: 'En-tête non contredit par son addendum',
  message: 'L’en-tête est contredit par son propre addendum.',
  severite: 'bloquant', piece_id: 14, piece_libelle: 'Mémoire technique',
}
const OK = {
  id: 5, code: 'lettres_egales_chiffres',
  libelle: 'Montant en lettres identique aux chiffres', severite: 'ok',
}

const HORS_CONTROLE = [
  { id: 21, libelle: 'Caution bancaire provisoire', motif: 'Pièce fournie par la banque' },
  { id: 22, libelle: "Acte d'engagement (modèle acheteur)", motif: "Cadre imposé par l'acheteur" },
]

const PAYLOAD = {
  controles: [JUSTIFICATION, FRERE_PERIME, LISEZ_MOI, ENTETE, OK],
  pieces_hors_controle: HORS_CONTROLE,
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.controlesAvantDepot.mockResolvedValue({ data: PAYLOAD })
})

describe('ControlesAvantDepot (AOF176)', () => {
  it('affiche les 4 classes de défaut réellement observées, chacune avec sa gravité', async () => {
    render(<ControlesAvantDepot dossierId={7} />)
    expect(await screen.findByText(/2 800 DH HT\/kWh alors que le bordereau final est à 2 600/))
      .toBeInTheDocument()
    expect(screen.getByText(/bordereau frère périmé subsiste \(total 5 219 280\)/)).toBeInTheDocument()
    expect(screen.getByText(/LISEZ-MOI est figé/)).toBeInTheDocument()
    expect(screen.getByText(/contredit par son propre addendum/)).toBeInTheDocument()

    // Gravités rendues par la pastille partagée (statusAo) : 3 bloquants,
    // 1 avertissement, 1 OK.
    expect(screen.getAllByText('Bloquant')).toHaveLength(3)
    expect(screen.getByText('Avertissement')).toBeInTheDocument()
    expect(screen.getByText('OK')).toBeInTheDocument()
    expect(document.querySelectorAll('[data-ao-controle]')).toHaveLength(5)
  })

  it('le bouton ZIP est désactivé AVEC le motif écrit dessus — jamais un bouton grisé sans explication', async () => {
    render(<ControlesAvantDepot dossierId={7} />)
    const zip = await screen.findByRole('button', { name: /^ZIP bloqué —/ })
    expect(zip).toBeDisabled()
    expect(zip).toHaveAccessibleName(
      /2 800 DH HT\/kWh alors que le bordereau final est à 2 600/,
    )
  })

  it('sans contrôle bloquant, le ZIP redevient actif et nommé', async () => {
    mocks.controlesAvantDepot.mockResolvedValue({
      data: { controles: [OK, { ...LISEZ_MOI, severite: 'avertissement' }], pieces_hors_controle: [] },
    })
    render(<ControlesAvantDepot dossierId={7} />)
    const zip = await screen.findByRole('button', { name: 'Constituer le ZIP de dépôt' })
    expect(zip).toBeEnabled()
  })

  it('les pièces « hors contrôle » sont distinguées et nommées — jamais présumées vertes', async () => {
    render(<ControlesAvantDepot dossierId={7} />)
    expect(await screen.findByText(/2 pièce\(s\) hors contrôle/)).toBeInTheDocument()
    expect(screen.getByText('Caution bancaire provisoire')).toBeInTheDocument()
    expect(screen.getByText(/Cadre imposé par l'acheteur/)).toBeInTheDocument()
  })

  it('un lien ouvre directement la pièce fautive à l’endroit du défaut', async () => {
    const onOuvrirPiece = vi.fn()
    render(<ControlesAvantDepot dossierId={7} onOuvrirPiece={onOuvrirPiece} />)
    fireEvent.click(
      await screen.findByRole('button', { name: /À REMPLIR PAR ACCORDIA.*parenthèse de justification/ }),
    )
    expect(onOuvrirPiece).toHaveBeenCalledWith(JUSTIFICATION)
  })

  it('accepte un tableau nu de contrôles (enveloppe serveur non figée)', async () => {
    mocks.controlesAvantDepot.mockResolvedValue({ data: [FRERE_PERIME] })
    render(<ControlesAvantDepot dossierId={7} />)
    expect(await screen.findByText(/bordereau frère périmé subsiste/)).toBeInTheDocument()
    await waitFor(() => expect(screen.getByRole('button', { name: /^ZIP bloqué —/ })).toBeDisabled())
  })

  it('motifBlocage / severiteDe : le verdict vient du serveur, jamais du front', () => {
    expect(severiteDe({ statut: 'bloquant' })).toBe('bloquant')
    expect(severiteDe({ severite: 'avertissement', statut: 'ok' })).toBe('avertissement')
    expect(severiteDe({})).toBe('ok')
    expect(motifBlocage([OK, LISEZ_MOI])).toBeNull()
    expect(motifBlocage([OK, ENTETE, JUSTIFICATION])).toBe(ENTETE.message)
  })
})
