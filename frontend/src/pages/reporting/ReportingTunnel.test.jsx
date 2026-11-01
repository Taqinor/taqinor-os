import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

/* AANA57 — le tunnel de conversion de /reporting n'affiche aucun pourcentage
   calculé à l'écran (effectifs seuls, largeur bornée) : {10 devis, 3 acceptés,
   15 factures} ne rend ni « 150 % » ni taux recalculé ; le seul pourcentage est
   `conversion.taux_acceptation_pct` SERVI. Données CHARGÉES du contrat partagé. */

vi.mock('../../features/reporting/store/reportingSlice', () => ({
  fetchDashboard: () => ({ type: 'reporting/noop' }),
  default: (s = null) => s,
}))
vi.mock('../../api/reportingApi', () => ({
  default: {
    kpiFederes: vi.fn(() => Promise.resolve({ data: { tuiles: [] } })),
    getPipeline: vi.fn(() => new Promise(() => {})),
  },
}))
vi.mock('../../features/reporting/KpiP2pCard', () => ({ default: () => null }))
vi.mock('../../api/axios', () => ({ default: { get: vi.fn(() => Promise.resolve({ data: {} })) } }))

import { Component as Reporting } from '../Reporting'

const contrat = JSON.parse(readFileSync(join(
  import.meta.dirname, '..', '..', '..', '..', 'backend', 'django_core', 'apps', 'reporting',
  'contract_samples', 'dashboard.json'), 'utf8')).exemple

describe('Reporting — tunnel de conversion', () => {
  it('tunnel sans pourcentage recalculé', () => {
    const data = {
      ...contrat,
      conversion: { ...contrat.conversion, nb_devis: 10, nb_acceptes: 3, nb_factures: 15 },
    }
    const store = configureStore({
      reducer: { reporting: () => ({ data, loading: false, error: null }) },
    })
    render(
      <Provider store={store}><MemoryRouter><Reporting /></MemoryRouter></Provider>,
    )
    const carte = screen.getByText('Tunnel de conversion').parentElement.parentElement
    const texte = carte.textContent
    expect(texte).not.toContain('150')
    // aucune barre n'affiche « (NN %) » : le seul pourcentage est le taux servi.
    const pourcentages = texte.match(/\d+(?:[.,]\d+)?\s*%/g) || []
    expect(pourcentages).toHaveLength(1)
    expect(texte).toMatch(/Devis acceptés \/ envoyés/)
    expect(texte).toMatch(/60\s*%/)
    // largeur bornée à 100 % même avec plus de factures que de devis.
    carte.querySelectorAll('[role="progressbar"]').forEach((el) => {
      expect(Number(el.getAttribute('aria-valuenow'))).toBeLessThanOrEqual(100)
    })
  })
})
