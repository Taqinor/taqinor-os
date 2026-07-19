import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, act, cleanup, waitFor, fireEvent, within } from '@testing-library/react'

/* WIR66 — smoke de l'onglet Référentiels : il se monte, charge les trois
   référentiels (TVA / conditions / unités), affiche leurs lignes et permet
   d'en créer un nouveau. */

vi.mock('../../api/parametresApi', () => ({
  default: {
    getTauxTva: vi.fn(async () => ({
      data: [{ id: 1, code: 'tva20', libelle: 'Normal', taux: '20', defaut: true, actif: true }],
    })),
    createTauxTva: vi.fn(async () => ({ data: {} })),
    updateTauxTva: vi.fn(async () => ({ data: {} })),
    deleteTauxTva: vi.fn(async () => ({ data: {} })),
    setDefautTauxTva: vi.fn(async () => ({ data: {} })),
    getConditionsPaiement: vi.fn(async () => ({
      data: [{ id: 2, libelle: 'Comptant', delai_jours: 0, fin_de_mois: false, escompte_pct: '0', actif: true }],
    })),
    createConditionPaiement: vi.fn(async () => ({ data: {} })),
    updateConditionPaiement: vi.fn(async () => ({ data: {} })),
    deleteConditionPaiement: vi.fn(async () => ({ data: {} })),
    getUnitesMesure: vi.fn(async () => ({
      data: [{ id: 3, code: 'm', libelle: 'Mètre', actif: true }],
    })),
    createUniteMesure: vi.fn(async () => ({ data: {} })),
    updateUniteMesure: vi.fn(async () => ({ data: {} })),
    deleteUniteMesure: vi.fn(async () => ({ data: {} })),
  },
}))

import parametresApi from '../../api/parametresApi'
import { ThemeProvider } from '../../design/ThemeProvider'
import ReferentielsSection from './ReferentielsSection'

beforeEach(() => {
  parametresApi.getTauxTva.mockClear()
  parametresApi.createUniteMesure.mockClear()
})
afterEach(() => cleanup())

const renderSection = async () => {
  await act(async () => {
    render(
      <ThemeProvider>
        <ReferentielsSection />
      </ThemeProvider>,
    )
  })
}

describe('WIR66 ReferentielsSection', () => {
  it('charge et affiche les trois référentiels', async () => {
    await renderSection()
    await waitFor(() => expect(parametresApi.getTauxTva).toHaveBeenCalled())
    expect(await screen.findByText('Normal')).toBeInTheDocument()
    expect(screen.getByText('Comptant')).toBeInTheDocument()
    expect(screen.getByText('Mètre')).toBeInTheDocument()
    expect(screen.getByText('Par défaut')).toBeInTheDocument()
  })

  it('crée une nouvelle unité de mesure', async () => {
    await renderSection()
    await screen.findByText('Mètre')
    const scope = screen.getByTestId('ref-unites')
    const [codeInput, libelleInput] = scope.querySelectorAll('input')
    fireEvent.change(codeInput, { target: { value: 'kg' } })
    fireEvent.change(libelleInput, { target: { value: 'Kilogramme' } })
    // Le scope contient déjà une ligne (Mètre) avec ses propres boutons
    // (interrupteur Actif + Supprimer) AVANT le bouton "Ajouter" du formulaire :
    // cibler par nom évite de cliquer le premier bouton venu (l'interrupteur).
    fireEvent.click(within(scope).getByRole('button', { name: /Ajouter/ }))
    await waitFor(() =>
      expect(parametresApi.createUniteMesure).toHaveBeenCalledWith(
        { code: 'kg', libelle: 'Kilogramme' }))
  })
})
