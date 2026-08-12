import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* PACT73 — Bibliothèque des pièces administratives (AOF137).
   Preuves : (1) une pièce se crée une fois, SCOPÉE SOCIÉTÉ (jamais un AO) ;
   (2) `date_expiration` vient TELLE QUELLE du serveur, jamais recalculée ;
   (3) le rattachement à un dossier compare deux dates SERVEUR (expiration de
   la pièce vs remise des plis de l'affaire choisie) avec le MÊME comparateur
   pur que le volet Administratif — jamais une seconde règle de péremption. */

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  rattacher: vi.fn(),
  affairesList: vi.fn(),
  dossiersList: vi.fn(),
}))

vi.mock('../../api/aoApi', () => ({
  default: {
    piecesAdministratives: { list: mocks.list, create: mocks.create, rattacher: mocks.rattacher },
    affaires: { list: mocks.affairesList },
    dossiers: { list: mocks.dossiersList },
  },
}))

import PiecesAdministratives from './PiecesAdministratives'

const PIECE = {
  id: 1, type_piece: 'attestation_fiscale', type_piece_display: 'Attestation fiscale',
  libelle: 'Attestation fiscale 2026', emetteur: 'DGI', date_emission: '2026-01-10',
  date_expiration: '2027-01-10', actif: true,
}
const PIECE_EXPIRE_BIENTOT = {
  id: 2, type_piece: 'attestation_cnss', type_piece_display: 'Attestation CNSS',
  libelle: 'Attestation CNSS T3', emetteur: 'CNSS', date_emission: '2026-06-01',
  date_expiration: '2026-08-30', actif: true,
}
const AFFAIRE = { id: 42, reference: 'AO-2026-005', objet: 'Centrale solaire', date_ouverture_plis: '2026-09-15' }

const renderEcran = () => render(<PiecesAdministratives />)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: [PIECE, PIECE_EXPIRE_BIENTOT] })
  mocks.create.mockResolvedValue({ data: {} })
  mocks.affairesList.mockResolvedValue({ data: [AFFAIRE] })
  mocks.dossiersList.mockResolvedValue({ data: [{ id: 900, reference: 'AODOS-202608-0001' }] })
  mocks.rattacher.mockResolvedValue({ data: {} })
})

describe('PiecesAdministratives (PACT73)', () => {
  it('charge la bibliothèque, groupée par type — la même pièce sert plusieurs AO', async () => {
    renderEcran()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    expect((await screen.findAllByText('Attestation fiscale 2026')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Attestation CNSS T3').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Attestation fiscale').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Attestation CNSS').length).toBeGreaterThan(0)
  })

  it('la date d’expiration affichée est celle DU SERVEUR, jamais recalculée', async () => {
    renderEcran()
    expect((await screen.findAllByText('valable jusqu’au 10/01/2027')).length).toBeGreaterThan(0)
  })

  it('crée une pièce SCOPÉE SOCIÉTÉ (aucun champ d’affaire dans le payload)', async () => {
    renderEcran()
    await screen.findAllByText('Attestation fiscale 2026')
    await userEvent.type(screen.getByLabelText('Libellé'), 'RIB Attijariwafa')
    await userEvent.click(screen.getAllByRole('button', { name: 'Enregistrer la pièce' })[0])
    await waitFor(() => expect(mocks.create).toHaveBeenCalledWith(
      expect.objectContaining({ type_piece: 'declaration_honneur', libelle: 'RIB Attijariwafa', rappel_jours: 30 }),
    ))
    expect(mocks.create.mock.calls[0][0]).not.toHaveProperty('appel_offre')
  })

  const choisirAffaire = async () => {
    await userEvent.click(screen.getByRole('combobox', { name: 'Affaire' }))
    await userEvent.click(await screen.findByRole('option', { name: 'AO-2026-005 — Centrale solaire' }))
  }

  it('rattacher une pièce résout le DOSSIER de l’affaire choisie puis appelle rattacher(piece, dossier)', async () => {
    renderEcran()
    await screen.findAllByText('Attestation fiscale 2026')
    const boutons = await screen.findAllByRole('button', { name: 'Rattacher à une affaire' })
    await userEvent.click(boutons[0])

    await choisirAffaire()
    await userEvent.click(screen.getAllByRole('button', { name: 'Rattacher' })[0])

    await waitFor(() => expect(mocks.dossiersList).toHaveBeenCalledWith({ appel_offre: 42 }))
    await waitFor(() => expect(mocks.rattacher).toHaveBeenCalledWith(1, 900))
  })

  it('une pièce qui expirera AVANT la remise des plis de l’affaire choisie affiche une alerte explicite', async () => {
    renderEcran()
    await screen.findAllByText('Attestation CNSS T3')
    const boutons = await screen.findAllByRole('button', { name: 'Rattacher à une affaire' })
    // La 2e ligne (CNSS, expire 30/08/2026) rattachée à l'affaire dont la
    // remise des plis est le 15/09/2026 : AVANT la remise → alerte.
    await userEvent.click(boutons[1])
    await choisirAffaire()

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /expire le 30\/08\/2026, AVANT la remise des plis du 15\/09\/2026/,
    )
  })

  it('aucun dossier de dépôt pour l’affaire choisie : le rattachement est refusé, sans ID deviné', async () => {
    mocks.dossiersList.mockResolvedValue({ data: [] })
    renderEcran()
    await screen.findAllByText('Attestation fiscale 2026')
    const boutons = await screen.findAllByRole('button', { name: 'Rattacher à une affaire' })
    await userEvent.click(boutons[0])
    await choisirAffaire()
    await userEvent.click(screen.getAllByRole('button', { name: 'Rattacher' })[0])

    await waitFor(() => expect(mocks.dossiersList).toHaveBeenCalled())
    expect(mocks.rattacher).not.toHaveBeenCalled()
  })
})
