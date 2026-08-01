import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'

/* AOF182 — le volet administratif cesse d'être suivi par téléphone.
   Trois garanties prouvées ici :
     1. une caution ou une attestation dont la validité s'achève AVANT
        l'ouverture des plis est signalée EN ROUGE AVEC SA DATE (et pas
        seulement « expirée », qui ne dit pas quand) ;
     2. une case obligatoire ouverte bloque VISIBLEMENT le dépôt, motif nommé ;
     3. chaque ligne trace son responsable — et son absence est signalée, parce
        qu'une vérification sans nom n'est faite par personne.
   Les dates sont assertées par MOTIF (jj/mm/aaaa) et non en dur : le rendu
   dépend du fuseau de la machine de test. */

const mocks = vi.hoisted(() => ({ get: vi.fn() }))
const toastMocks = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useParams: () => ({ id: '7' }) }
})

vi.mock('../../../api/aoApi', () => ({
  default: { affaires: { get: mocks.get } },
}))

vi.mock('../../../ui', async () => {
  const actual = await vi.importActual('../../../ui')
  return { ...actual, toast: { success: toastMocks.success, error: toastMocks.error } }
})

import AdministratifPage from './AdministratifPage'
import {
  expireAvant, verificationsOuvertes, motifBlocageDepot, elementsExpires, VERIFICATIONS_LABELS,
} from './AdministratifPage.utils'

const CAUTION_PROVISOIRE = {
  id: 1, type: 'provisoire', montant: 40000, banque: 'BMCE', reference: 'CAU-2026-014',
  // Expire AVANT l'ouverture des plis du 15/09 : le dossier serait rejeté.
  date_validite: '2026-09-10', statut: 'fourni',
  piece_jointe: { id: 5, nom: 'caution-provisoire.pdf' }, responsable: 'Meryem B.',
}

const AFFAIRE = {
  id: 7, reference: 'AO-2026-014', date_ouverture_plis: '2026-09-15',
  cautions: [CAUTION_PROVISOIRE],
  pieces_administratives: [
    {
      id: 11, code: 'attestation_fiscale', libelle: 'Attestation fiscale',
      date_delivrance: '2026-06-01', valide_jusqu_au: '2026-09-30',
      responsable: 'Sami R.', statut: 'fourni', obligatoire: true,
    },
    {
      id: 12, code: 'attestation_cnss', libelle: 'Attestation CNSS',
      date_delivrance: '2026-03-02', valide_jusqu_au: '2026-09-01',
      responsable: null, statut: 'fourni', obligatoire: true,
    },
  ],
  verifications_avant_depot: [
    { id: 21, code: 'prorogation_ecrite', obligatoire: true, fait: false, responsable: 'Reda K.' },
    { id: 22, code: 'attestation_visite', obligatoire: true, fait: true, responsable: 'Sami R.' },
    { id: 23, code: 'plis_separes', obligatoire: false, fait: false, responsable: null },
  ],
}

const toutFait = (affaire) => ({
  ...affaire,
  verifications_avant_depot: affaire.verifications_avant_depot.map((v) => ({ ...v, fait: true })),
})

beforeEach(() => {
  vi.clearAllMocks()
  mocks.get.mockResolvedValue({ data: AFFAIRE })
})

describe('AdministratifPage (AOF182)', () => {
  it('suit les DEUX cautions : la provisoire avec sa pièce jointe, la définitive signalée non constituée', async () => {
    render(<AdministratifPage />)
    expect(await screen.findByText('Caution provisoire (soumission)')).toBeInTheDocument()
    expect(screen.getByText(/BMCE/)).toBeInTheDocument()
    expect(screen.getByText(/CAU-2026-014/)).toBeInTheDocument()
    expect(screen.getByText('caution-provisoire.pdf')).toBeInTheDocument()
    expect(screen.getByText('Caution définitive')).toBeInTheDocument()
    expect(screen.getByText(/Non constituée/)).toBeInTheDocument()
  })

  it('une caution ou une attestation expirant avant l’ouverture des plis est signalée en rouge AVEC SA DATE', async () => {
    render(<AdministratifPage />)
    const bandeau = await screen.findByText('Validité insuffisante à l’ouverture des plis')
    expect(bandeau).toBeInTheDocument()

    const lignes = screen.getAllByText(/expire le \d{2}\/\d{2}\/2026$/)
    expect(lignes).toHaveLength(2)
    const textes = lignes.map((n) => n.textContent)
    expect(textes.some((t) => t.startsWith('Caution provisoire (soumission)'))).toBe(true)
    expect(textes.some((t) => t.startsWith('Attestation CNSS'))).toBe(true)
    // L'attestation encore valable le jour de l'ouverture n'est PAS signalée.
    expect(textes.some((t) => t.startsWith('Attestation fiscale'))).toBe(false)

    // La ligne du tableau porte aussi la mention, avec la date.
    expect(screen.getAllByText(/expire AVANT l’ouverture des plis/).length).toBeGreaterThan(0)
  })

  it('une case obligatoire ouverte bloque VISIBLEMENT le dépôt, motif nommé', async () => {
    const onDeposer = vi.fn()
    render(<AdministratifPage onDeposer={onDeposer} />)
    // Le motif est écrit DEUX fois : dans le bandeau (visible même sans action
    // de dépôt branchée) et SUR le bouton — jamais un bouton grisé muet.
    expect(await screen.findAllByText('Dépôt bloqué — Prorogation écrite obtenue')).toHaveLength(2)
    const bouton = screen.getByRole('button', { name: /^Dépôt bloqué —/ })
    expect(bouton).toBeDisabled()
    expect(bouton).toHaveAccessibleName(/Prorogation écrite obtenue/)
    fireEvent.click(bouton)
    expect(onDeposer).not.toHaveBeenCalled()
  })

  it('toutes les vérifications obligatoires faites : le dépôt redevient possible', async () => {
    mocks.get.mockResolvedValue({ data: toutFait(AFFAIRE) })
    const onDeposer = vi.fn()
    render(<AdministratifPage onDeposer={onDeposer} />)
    const bouton = await screen.findByRole('button', { name: 'Déposer le pli' })
    expect(bouton).toBeEnabled()
    expect(screen.queryByText(/^Dépôt bloqué —/)).not.toBeInTheDocument()
    fireEvent.click(bouton)
    expect(onDeposer).toHaveBeenCalled()
  })

  it('chaque ligne trace son responsable — une ligne sans responsable est signalée', async () => {
    render(<AdministratifPage />)
    expect(await screen.findByText('Meryem B.')).toBeInTheDocument()
    expect(screen.getAllByText('Sami R.')).toHaveLength(2)
    expect(screen.getByText('Reda K.')).toBeInTheDocument()
    // Attestation CNSS + vérification « plis séparés » : personne n'est désigné.
    expect(screen.getAllByText('Responsable non désigné')).toHaveLength(2)
  })

  it('cocher une vérification passe par le service injecté, puis relit le dossier', async () => {
    const onCocherVerification = vi.fn().mockResolvedValue({})
    render(<AdministratifPage onCocherVerification={onCocherVerification} />)
    const case1 = await screen.findByRole('checkbox', { name: 'Prorogation écrite obtenue' })
    fireEvent.click(case1)
    await waitFor(() => expect(onCocherVerification).toHaveBeenCalledWith(
      AFFAIRE.verifications_avant_depot[0], true,
    ))
    await waitFor(() => expect(mocks.get).toHaveBeenCalledTimes(2))
  })

  it('sans service injecté, la checklist est en lecture seule (aucun endpoint inventé)', async () => {
    render(<AdministratifPage />)
    expect(await screen.findByRole('checkbox', { name: 'Prorogation écrite obtenue' })).toBeDisabled()
    expect(screen.getByText(/Consultation seule/)).toBeInTheDocument()
  })
})

describe('Règles pures du volet administratif (AOF182)', () => {
  it('expireAvant compare des JOURS, et ne signale jamais ce qu’il ne sait pas', () => {
    expect(expireAvant('2026-09-10', '2026-09-15')).toBe(true)
    expect(expireAvant('2026-09-15', '2026-09-15')).toBe(false)
    expect(expireAvant('2026-09-16', '2026-09-15')).toBe(false)
    expect(expireAvant(null, '2026-09-15')).toBe(false)
    expect(expireAvant('2026-09-10', null)).toBe(false)
    expect(expireAvant('pas une date', '2026-09-15')).toBe(false)
  })

  it('verificationsOuvertes / motifBlocageDepot ne retiennent que les OBLIGATOIRES non faites', () => {
    const v = AFFAIRE.verifications_avant_depot
    expect(verificationsOuvertes(v)).toEqual([v[0]])
    expect(motifBlocageDepot(v)).toBe(VERIFICATIONS_LABELS.prorogation_ecrite)
    expect(motifBlocageDepot(v.map((x) => ({ ...x, fait: true })))).toBeNull()
    expect(motifBlocageDepot([])).toBeNull()
    // Une case NON obligatoire ouverte ne bloque rien.
    expect(motifBlocageDepot([{ id: 9, code: 'plis_separes', obligatoire: false, fait: false }])).toBeNull()
  })

  it('elementsExpires réunit cautions et pièces datées, avec leur date', () => {
    const res = elementsExpires({
      cautions: AFFAIRE.cautions,
      pieces: AFFAIRE.pieces_administratives,
      dateOuverture: '2026-09-15',
    })
    expect(res.map((e) => e.libelle)).toEqual(['Caution provisoire (soumission)', 'Attestation CNSS'])
    expect(res.map((e) => e.date)).toEqual(['2026-09-10', '2026-09-01'])
    expect(elementsExpires({ cautions: AFFAIRE.cautions, pieces: [], dateOuverture: null })).toEqual([])
  })
})
