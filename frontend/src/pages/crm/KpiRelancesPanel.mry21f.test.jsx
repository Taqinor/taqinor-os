// MRY29 — panneau KPI du Cockpit : premier contact (MRY19) + bilan des
// cadences (MRY21). Charge utile issue des contrats committés
// `apps/crm/contract_samples/kpi_premier_contact.json` /
// `kpi_cadences.json` (PACT10) — jamais un objet retapé à la main.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { exempleContrat } from '../../test/fixtures/contractSamples'

const CONTACT = exempleContrat('crm', 'kpi_premier_contact')
const CONTACT_VIDE = exempleContrat('crm', 'kpi_premier_contact', 'exemple_vide')
const CADENCES = exempleContrat('crm', 'kpi_cadences')
const CADENCES_VIDE = exempleContrat('crm', 'kpi_cadences', 'exemple_vide')

// Radix Select ne s'ouvre pas de façon fiable sous jsdom (portail + pointer
// events) — pattern établi (ventes/ListesPrixPage.test.jsx) : remplacer les
// primitives Select par un <select> natif pour piloter le choix en test, le
// reste de `../../ui` reste réel.
vi.mock('../../ui', async (importActual) => {
  const actual = await importActual()
  const Passthrough = ({ children }) => <>{children}</>
  return {
    ...actual,
    Select: ({ value, onValueChange, children }) => (
      <select
        aria-label="Période" role="combobox" value={value}
        onChange={(e) => onValueChange(e.target.value)}
      >
        {children}
      </select>
    ),
    SelectTrigger: Passthrough,
    SelectValue: () => null,
    SelectContent: Passthrough,
    SelectItem: ({ value, children }) => <option value={value}>{children}</option>,
  }
})

vi.mock('../../api/crmApi', () => ({
  default: {
    getKpiPremierContact: vi.fn(),
    getKpiCadences: vi.fn(),
  },
}))

import crmApi from '../../api/crmApi'
import KpiRelancesPanel from './KpiRelancesPanel'

beforeEach(() => {
  crmApi.getKpiPremierContact.mockResolvedValue({ data: CONTACT })
  crmApi.getKpiCadences.mockResolvedValue({ data: CADENCES })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

// Plusieurs tuiles peuvent légitimement partager la même valeur numérique
// (ex. mediane_minutes_ouvrees=4 et signatures=4) : on lit la tuile PAR SON
// LIBELLÉ (la structure Metric — libellé puis valeur en frère suivant),
// jamais un texte nu ambigu.
const metricValue = (label) => screen.getByText(label).nextSibling.textContent

describe('MRY29 KpiRelancesPanel', () => {
  it('charge les deux KPI avec la période par défaut (30 jours)', async () => {
    render(<KpiRelancesPanel />)
    await waitFor(() => expect(crmApi.getKpiPremierContact).toHaveBeenCalledWith({ jours: '30' }))
    expect(crmApi.getKpiCadences).toHaveBeenCalledWith({ jours: '30' })
    await screen.findByText('Médiane (min ouvrées)')
    // Médiane (min ouvrées) et compteurs bruts, tels quels.
    expect(metricValue('Médiane (min ouvrées)')).toBe(String(CONTACT.mediane_minutes_ouvrees))
    expect(metricValue('Cadences complètes')).toBe(String(CADENCES.cadences_completes))
    expect(metricValue('Devis envoyés')).toBe(String(CADENCES.devis_envoyes))
  })

  it('affiche « — » (jamais 0 %) quand le dénominateur est 0', async () => {
    crmApi.getKpiPremierContact.mockResolvedValue({ data: CONTACT_VIDE })
    crmApi.getKpiCadences.mockResolvedValue({ data: CADENCES_VIDE })
    render(<KpiRelancesPanel />)
    await waitFor(() => expect(crmApi.getKpiPremierContact).toHaveBeenCalled())
    const tirets = await screen.findAllByText('—')
    // 2 tirets côté contact (pct_sous_objectif, médiane) + nb_nuit_rappeles
    // + 2 côté cadences (joints_sous_5j_pct, perdus_avec_motif_pct) + tentatives.
    expect(tirets.length).toBeGreaterThanOrEqual(5)
    expect(screen.queryByText('0 %')).not.toBeInTheDocument()
  })

  it('un changement de période refait les deux appels', async () => {
    render(<KpiRelancesPanel />)
    await waitFor(() => expect(crmApi.getKpiPremierContact).toHaveBeenCalledWith({ jours: '30' }))
    fireEvent.change(screen.getByRole('combobox', { name: 'Période' }), { target: { value: '7' } })
    await waitFor(() => expect(crmApi.getKpiPremierContact).toHaveBeenCalledWith({ jours: '7' }))
    expect(crmApi.getKpiCadences).toHaveBeenCalledWith({ jours: '7' })
  })

  it('affiche l\'objectif dynamique de la société dans le libellé', async () => {
    render(<KpiRelancesPanel />)
    expect(await screen.findByText(new RegExp(`% touchés < ${CONTACT.objectif_minutes} min`)))
      .toBeInTheDocument()
  })

  it('F6 — sans objectif_minutes dans la réponse, le titre affiche « — » (jamais un 5 en dur)', async () => {
    const { objectif_minutes: _omis, ...contactSansObjectif } = CONTACT
    crmApi.getKpiPremierContact.mockResolvedValue({ data: contactSansObjectif })
    render(<KpiRelancesPanel />)
    await waitFor(() => expect(crmApi.getKpiPremierContact).toHaveBeenCalled())
    expect(await screen.findByText(/Objectif « rappelé en moins de — min ouvrées »/))
      .toBeInTheDocument()
    expect(screen.queryByText(/rappelé en moins de 5 min/)).not.toBeInTheDocument()
    expect(await screen.findByText('% touchés < — min')).toBeInTheDocument()
  })

  it('indisponible : ne casse pas l\'écran sur un échec réseau', async () => {
    crmApi.getKpiPremierContact.mockRejectedValue(new Error('boom'))
    render(<KpiRelancesPanel />)
    expect(await screen.findByText(/Indisponible pour le moment/)).toBeInTheDocument()
  })
})
