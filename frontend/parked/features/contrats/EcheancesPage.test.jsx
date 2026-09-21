import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR74 — les 4 onglets Règles d'approbation / Jalons / Obligations / SLA
   d'EcheancesPage.jsx étaient lecture seule alors que les wrappers de création
   (`createRegleApprobation`/`createJalon`/`createObligation`/`createSla`)
   étaient déjà exposés par contratsApi.js, sans aucun appelant. Vérifie que
   chaque onglet ouvre bien un dialogue de création, appelle le bon wrapper
   avec le bon payload, et recharge la liste. jsdom ne fournit pas
   ResizeObserver ; les onglets Radix ne basculent pas sous `fireEvent.click`
   (cf. wiring.test.jsx) — `userEvent.click` est utilisé pour les changer. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

const {
  createRegleApprobation, createJalon, createObligation, createSla,
  getJalons, getObligations, getSla, getReglesApprobation, penaliteSla,
} = vi.hoisted(() => ({
  createRegleApprobation: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
  createJalon: vi.fn(() => Promise.resolve({ data: { id: 2 } })),
  createObligation: vi.fn(() => Promise.resolve({ data: { id: 3 } })),
  createSla: vi.fn(() => Promise.resolve({ data: { id: 4 } })),
  getJalons: vi.fn(() => Promise.resolve({ data: [] })),
  getObligations: vi.fn(() => Promise.resolve({ data: [] })),
  getSla: vi.fn(() => Promise.resolve({ data: [] })),
  getReglesApprobation: vi.fn(() => Promise.resolve({ data: [] })),
  // CONTRAT27/WIR252 — calcul déclaratif de la pénalité SLA.
  penaliteSla: vi.fn(() => Promise.resolve({ data: {
    penalite: '150.00', respecte: false, taux_cible: '98.00', taux_realise: '95.00',
  } })),
}))

vi.mock('../../api/contratsApi', () => {
  const empty = () => Promise.resolve({ data: [] })
  const contrat = { id: 7, reference: 'CT-2026-07-0001', objet: 'Maintenance PV' }
  return {
    default: {
      getPreavis: empty,
      getARenouveler: empty,
      getAlertes: empty,
      getJalons,
      getObligations,
      getSla,
      getReglesApprobation,
      getContrats: () => Promise.resolve({ data: [contrat] }),
      declencherAlertes: () => Promise.resolve({ data: {} }),
      semerAlertes: () => Promise.resolve({ data: {} }),
      marquerJalonAtteint: () => Promise.resolve({ data: {} }),
      marquerObligationFaite: () => Promise.resolve({ data: {} }),
      createRegleApprobation,
      createJalon,
      createObligation,
      createSla,
      penaliteSla,
    },
  }
})

import EcheancesPage from './EcheancesPage'

beforeEach(() => { vi.clearAllMocks() })

function renderPage() {
  return render(<MemoryRouter><ThemeProvider><EcheancesPage /></ThemeProvider></MemoryRouter>)
}

describe('EcheancesPage — création depuis les onglets (WIR74)', () => {
  it('crée une règle d’approbation depuis l’onglet Approbation', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Échéances & alertes')).toBeInTheDocument())

    await userEvent.click(screen.getByRole('tab', { name: /Approbation/ }))
    fireEvent.click(await screen.findByRole('button', { name: /Nouvelle règle d’approbation/ }))

    fireEvent.change(await screen.findByLabelText(/^Libellé/), {
      target: { value: 'Approbation grands montants' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Créer la règle' }))

    await waitFor(() => expect(createRegleApprobation).toHaveBeenCalledWith({
      libelle: 'Approbation grands montants', niveau_approbation: 'responsable',
    }))
    // Recharge la liste après création (2e appel : mount + après création).
    await waitFor(() => expect(getReglesApprobation).toHaveBeenCalledTimes(2))
  })

  it('crée un jalon rattaché à un contrat depuis l’onglet Jalons', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Échéances & alertes')).toBeInTheDocument())

    await userEvent.click(screen.getByRole('tab', { name: /Jalons/ }))
    fireEvent.click(await screen.findByRole('button', { name: /Nouveau jalon/ }))

    fireEvent.change(await screen.findByLabelText(/^Contrat/), { target: { value: '7' } })
    fireEvent.change(screen.getByLabelText(/^Intitulé/), { target: { value: 'Mise en service' } })
    fireEvent.click(screen.getByRole('button', { name: 'Créer le jalon' }))

    await waitFor(() => expect(createJalon).toHaveBeenCalledWith({
      contrat: 7, intitule: 'Mise en service',
    }))
    await waitFor(() => expect(getJalons).toHaveBeenCalledTimes(2))
  })

  it('crée une obligation depuis l’onglet Obligations', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Échéances & alertes')).toBeInTheDocument())

    await userEvent.click(screen.getByRole('tab', { name: /Obligations/ }))
    fireEvent.click(await screen.findByRole('button', { name: /Nouvelle obligation/ }))

    fireEvent.change(await screen.findByLabelText(/^Contrat/), { target: { value: '7' } })
    fireEvent.change(screen.getByLabelText(/^Intitulé/), { target: { value: 'Remise du dossier ONEE' } })
    fireEvent.click(screen.getByRole('button', { name: "Créer l'obligation" }))

    await waitFor(() => expect(createObligation).toHaveBeenCalledWith({
      contrat: 7, intitule: 'Remise du dossier ONEE', redevable: 'prestataire',
    }))
    await waitFor(() => expect(getObligations).toHaveBeenCalledTimes(2))
  })

  it('crée un engagement SLA depuis l’onglet SLA', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('Échéances & alertes')).toBeInTheDocument())

    await userEvent.click(screen.getByRole('tab', { name: /^SLA/ }))
    fireEvent.click(await screen.findByRole('button', { name: /Nouvel engagement SLA/ }))

    fireEvent.change(await screen.findByLabelText(/^Contrat/), { target: { value: '7' } })
    fireEvent.change(screen.getByLabelText(/^Libellé/), { target: { value: 'Disponibilité ≥ 98 %' } })
    fireEvent.click(screen.getByRole('button', { name: "Créer l'engagement" }))

    await waitFor(() => expect(createSla).toHaveBeenCalledWith({
      contrat: 7, libelle: 'Disponibilité ≥ 98 %', mode_penalite: 'fixe',
    }))
    await waitFor(() => expect(getSla).toHaveBeenCalledTimes(2))
  })
})

describe('WIR252 — calcul de la pénalité SLA (déclaratif)', () => {
  const SLA = {
    id: 9, libelle: 'Disponibilité ≥ 98 %', taux_cible: '98.00',
    mode_penalite: 'fixe', mode_penalite_display: 'Montant fixe', actif: true,
  }

  it('calcule la pénalité avec des valeurs saisies, sans aucune écriture', async () => {
    getSla.mockResolvedValueOnce({ data: [SLA] })
    renderPage()
    await waitFor(() => expect(screen.getByText('Échéances & alertes')).toBeInTheDocument())
    await userEvent.click(screen.getByRole('tab', { name: /^SLA/ }))

    await userEvent.click(await screen.findByRole('button', { name: /Calculer la pénalité/i }))

    const dialog = await screen.findByRole('dialog')
    // La mention déclarative est visible AVANT tout calcul.
    expect(within(dialog).getByText(/Calcul déclaratif/)).toBeInTheDocument()

    fireEvent.change(within(dialog).getByLabelText(/Taux réalisé/), { target: { value: '95' } })
    fireEvent.change(within(dialog).getByLabelText(/Montant du contrat/), { target: { value: '10000' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Calculer' }))

    await waitFor(() => expect(penaliteSla).toHaveBeenCalledWith(9, {
      taux_realise: 95, montant_contrat: 10000,
    }))
    expect(await within(dialog).findByText('150.00')).toBeInTheDocument()
    expect(within(dialog).getByText('Non respecté')).toBeInTheDocument()
    expect(within(dialog).getByText('98.00 %')).toBeInTheDocument()

    // Déclaratif : aucune écriture ailleurs (ni SLA, ni tout autre wrapper).
    expect(createSla).not.toHaveBeenCalled()
  })

  it('appelle le calcul SANS corps quand aucune valeur n’est saisie', async () => {
    getSla.mockResolvedValueOnce({ data: [SLA] })
    renderPage()
    await waitFor(() => expect(screen.getByText('Échéances & alertes')).toBeInTheDocument())
    await userEvent.click(screen.getByRole('tab', { name: /^SLA/ }))

    await userEvent.click(await screen.findByRole('button', { name: /Calculer la pénalité/i }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Calculer' }))

    await waitFor(() => expect(penaliteSla).toHaveBeenCalledWith(9, {}))
  })

  // Fable — `respecte` est TRI-ÉTAT (bool|null) : le barème théorique (sans
  // `taux_realise`) renvoie `respecte: null` (indéterminé), jamais assimilé
  // à un faux « Non respecté » inventé côté client.
  it('affiche « — » (neutre), jamais « Non respecté », quand respecte est null', async () => {
    getSla.mockResolvedValueOnce({ data: [SLA] })
    penaliteSla.mockResolvedValueOnce({ data: {
      penalite: '500.00', respecte: null, taux_cible: '98.00', taux_realise: null,
    } })
    renderPage()
    await waitFor(() => expect(screen.getByText('Échéances & alertes')).toBeInTheDocument())
    await userEvent.click(screen.getByRole('tab', { name: /^SLA/ }))

    await userEvent.click(await screen.findByRole('button', { name: /Calculer la pénalité/i }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Calculer' }))

    await waitFor(() => expect(penaliteSla).toHaveBeenCalledWith(9, {}))
    // « Taux réalisé » affiche AUSSI « — » (déjà null-tolérant) : on scope
    // précisément à la carte « Respect du SLA » pour ne pas les confondre.
    const carteRespect = (await within(dialog).findByText('Respect du SLA')).closest('div')
    expect(within(carteRespect).getByText('—')).toBeInTheDocument()
    expect(within(carteRespect).queryByText('Non respecté')).not.toBeInTheDocument()
    expect(within(carteRespect).queryByText('Respecté')).not.toBeInTheDocument()
  })
})
