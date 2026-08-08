import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

/* PACT70 — Suivi administratif de l'AO : cautions, échéances, résultat.
   Preuve centrale : les TROIS écritures passent par les VRAIES ressources
   serveur (`cautions-soumission`, `echeances-ao`, `resultats-ao/enregistrer`)
   — jamais un champ imaginaire de l'affaire. */

const mocks = vi.hoisted(() => ({
  cautionsList: vi.fn(),
  cautionsCreate: vi.fn(),
  deriverDefinitive: vi.fn(),
  echeancesList: vi.fn(),
  echeancesCreate: vi.fn(),
  echeancesUpdate: vi.fn(),
  resultatsList: vi.fn(),
  resultatsEnregistrer: vi.fn(),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useParams: () => ({ id: '1' }) }
})

vi.mock('../../api/aoApi', () => ({
  default: {
    cautionsSoumission: {
      list: mocks.cautionsList, create: mocks.cautionsCreate, deriverDefinitive: mocks.deriverDefinitive,
    },
    echeancesAo: { list: mocks.echeancesList, create: mocks.echeancesCreate, update: mocks.echeancesUpdate },
    resultatsAo: { list: mocks.resultatsList, enregistrer: mocks.resultatsEnregistrer },
  },
}))

import SuiviAdministratifAO from './SuiviAdministratifAO'

const renderEcran = (props) => render(
  <MemoryRouter><SuiviAdministratifAO affaireId={1} {...props} /></MemoryRouter>,
)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.cautionsList.mockResolvedValue({ data: [] })
  mocks.cautionsCreate.mockResolvedValue({ data: {} })
  mocks.deriverDefinitive.mockResolvedValue({ data: {} })
  mocks.echeancesList.mockResolvedValue({ data: [] })
  mocks.echeancesCreate.mockResolvedValue({ data: {} })
  mocks.echeancesUpdate.mockResolvedValue({ data: {} })
  mocks.resultatsList.mockResolvedValue({ data: [] })
  mocks.resultatsEnregistrer.mockResolvedValue({ data: {} })
})

describe('SuiviAdministratifAO (PACT70)', () => {
  it('charge les trois ressources filtrées sur CETTE affaire (jamais toute la société)', async () => {
    renderEcran()
    await waitFor(() => expect(mocks.cautionsList).toHaveBeenCalledWith({ appel_offre: 1 }))
    expect(mocks.echeancesList).toHaveBeenCalledWith({ appel_offre: 1 })
    expect(mocks.resultatsList).toHaveBeenCalledWith({ appel_offre: 1 })
  })

  it('enregistrer une caution appelle un POST réel sur cautions-soumission', async () => {
    renderEcran()
    await screen.findByText('Aucune caution enregistrée pour cette affaire.')
    await userEvent.type(screen.getByLabelText('Montant (MAD)'), '25000')
    await userEvent.type(screen.getByLabelText('Banque'), 'Attijariwafa')
    await userEvent.click(screen.getByRole('button', { name: 'Enregistrer la caution' }))
    await waitFor(() => expect(mocks.cautionsCreate).toHaveBeenCalledWith(
      expect.objectContaining({ appel_offre: 1, type_caution: 'provisoire', montant: '25000', banque: 'Attijariwafa' }),
    ))
  })

  it('dériver la caution définitive appelle l’action serveur dédiée', async () => {
    renderEcran()
    await screen.findByText('Aucune caution enregistrée pour cette affaire.')
    await userEvent.click(screen.getByRole('button', { name: 'Dériver la caution définitive (taux CPS)' }))
    await waitFor(() => expect(mocks.deriverDefinitive).toHaveBeenCalledWith({ appel_offre: 1 }))
  })

  it('enregistrer une échéance exige une date et appelle un POST réel sur echeances-ao', async () => {
    renderEcran()
    await screen.findByText('Aucune échéance enregistrée pour cette affaire.')
    expect(screen.getByRole('button', { name: "Enregistrer l'échéance" })).toBeDisabled()
    await userEvent.type(screen.getByLabelText("Libellé"), 'Remise des plis')
    await userEvent.type(screen.getByLabelText("Date d'échéance"), '2026-09-15')
    await userEvent.click(screen.getByRole('button', { name: "Enregistrer l'échéance" }))
    await waitFor(() => expect(mocks.echeancesCreate).toHaveBeenCalledWith(
      expect.objectContaining({ appel_offre: 1, libelle: 'Remise des plis', date_echeance: '2026-09-15' }),
    ))
  })

  it('cocher une échéance traitée appelle un PATCH réel', async () => {
    mocks.echeancesList.mockResolvedValue({
      data: [{
        id: 5, type_echeance: 'ouverture', type_echeance_display: 'Ouverture des plis',
        libelle: 'Ouverture', date_echeance: '2026-09-20', traitee: false,
      }],
    })
    renderEcran()
    const case1 = await screen.findByLabelText('Traitée — Ouverture')
    await userEvent.click(case1)
    await waitFor(() => expect(mocks.echeancesUpdate).toHaveBeenCalledWith(5, { traitee: true }))
  })

  it('enregistrer le résultat appelle l’action serveur unique resultats-ao/enregistrer (upsert)', async () => {
    renderEcran()
    await screen.findByRole('heading', { name: 'Résultat (ouverture des plis)' })
    await userEvent.type(screen.getByLabelText('Attributaire'), 'Société Y')
    await userEvent.click(screen.getByRole('button', { name: 'Enregistrer le résultat' }))
    await waitFor(() => expect(mocks.resultatsEnregistrer).toHaveBeenCalledWith(
      expect.objectContaining({ appel_offre: 1, issue: 'perdu', attributaire: 'Société Y' }),
    ))
  })

  it('un résultat déjà enregistré affiche son issue et l’écart de prix DÉRIVÉ du serveur (jamais recalculé)', async () => {
    mocks.resultatsList.mockResolvedValue({
      data: [{
        id: 9, issue: 'perdu', issue_display: 'Perdu', attributaire: 'Concurrent Z',
        notre_prix: '4400000.00', prix_gagnant: '4200000.00', ecart_prix_pct: '4.76',
      }],
    })
    renderEcran()
    expect(await screen.findByText('Perdu')).toBeInTheDocument()
    expect(screen.getByText('Attributaire : Concurrent Z')).toBeInTheDocument()
    expect(screen.getByText('Écart vs gagnant : 4.76 %')).toBeInTheDocument()
  })
})
