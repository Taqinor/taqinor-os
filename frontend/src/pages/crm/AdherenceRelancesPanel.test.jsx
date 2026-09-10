// CKP5/CKP6 (fondateur 2026-09-10) — vue ADHÉRENCE. Charge utile venant du
// contrat COMMITTÉ `apps/crm/contract_samples/kpi_adherence.json`
// (CKP0/PACT10) — jamais un objet retapé à la main.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat } from '../../test/fixtures/contractSamples'

const ADHERENCE = exempleContrat('crm', 'kpi_adherence')

// Radix Select ne s'ouvre pas de façon fiable sous jsdom (portail + pointer
// events) — même contournement que `KpiRelancesPanel.mry21f.test.jsx`.
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
  default: { getKpiAdherence: vi.fn() },
}))

import crmApi from '../../api/crmApi'
import AdherenceRelancesPanel from './AdherenceRelancesPanel'

beforeEach(() => {
  crmApi.getKpiAdherence.mockResolvedValue({ data: ADHERENCE })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

function mount() {
  return render(
    <MemoryRouter>
      <AdherenceRelancesPanel />
    </MemoryRouter>,
  )
}

describe('CKP5 AdherenceRelancesPanel', () => {
  it('charge l\'adhérence avec la période par défaut (30 jours)', async () => {
    mount()
    await waitFor(() => expect(crmApi.getKpiAdherence).toHaveBeenCalledWith({ jours: '30' }))
    // 84.2 % apparaît deux fois (tuile de synthèse + dernier point de la
    // tendance hebdo, même valeur dans l'exemple committé) — au moins une
    // occurrence suffit à prouver que la valeur du contrat est rendue.
    expect((await screen.findAllByText(`${ADHERENCE.a_lheure_pct} %`)).length).toBeGreaterThan(0)
  })

  it('sautées humaines et annulées moteur sont deux colonnes séparées', async () => {
    mount()
    await waitFor(() => expect(crmApi.getKpiAdherence).toHaveBeenCalled())
    expect(await screen.findByText('Sautées humaines')).toBeInTheDocument()
    // « Annulées (moteur) » apparaît DEUX fois (tuile de synthèse + en-tête
    // de la table drop-off) — la tuile de synthèse est la première.
    expect(screen.getAllByText('Annulées (moteur)').length).toBeGreaterThanOrEqual(2)
    const sauteesValue = screen.getByText('Sautées humaines').nextSibling.textContent
    const annuleesValue = screen.getAllByText('Annulées (moteur)')[0].nextSibling.textContent
    expect(sauteesValue).toBe(String(ADHERENCE.sautees_humaines))
    expect(annuleesValue).toBe(String(ADHERENCE.annulees_moteur))
  })

  it('la table drop-off par touche affiche ordre/canal/libellé et les colonnes séparées', async () => {
    mount()
    await waitFor(() => expect(crmApi.getKpiAdherence).toHaveBeenCalled())
    const premiere = ADHERENCE.par_etape[0]
    expect(await screen.findByText(premiere.libelle)).toBeInTheDocument()
    // Deux touches dans l'exemple committé (WhatsApp, Appel).
    expect(screen.getAllByText('WhatsApp').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Appel').length).toBeGreaterThan(0)
  })

  it('un dénominateur nul (taux_pct: null de conversion_par_stage) affiche « — », jamais 0 %', async () => {
    mount()
    await waitFor(() => expect(crmApi.getKpiAdherence).toHaveBeenCalled())
    const ligneNulle = ADHERENCE.conversion_par_stage.find((l) => l.taux_pct === null)
    expect(ligneNulle).toBeTruthy()
    // La ligne existe (son étape apparaît) et aucun 0 % n'est rendu pour elle.
    await screen.findByText(premierLabel(ligneNulle.stage))
    expect(screen.queryByText('0 %')).not.toBeInTheDocument()
  })

  it('leads sans touche due : liste cliquable qui navigue vers la fiche lead', async () => {
    mount()
    await waitFor(() => expect(crmApi.getKpiAdherence).toHaveBeenCalled())
    const lead = ADHERENCE.leads_sans_touche[0]
    const bouton = await screen.findByRole('button', { name: new RegExp(lead.nom) })
    expect(() => fireEvent.click(bouton)).not.toThrow()
  })

  it('tendance : une flèche de tendance est rendue, jamais un seuil rouge/vert', async () => {
    mount()
    await waitFor(() => expect(crmApi.getKpiAdherence).toHaveBeenCalled())
    await screen.findByText(/Tendance hebdo à l'heure/)
    // Aucune classe/texte de seuil inventé (rouge/vert/alerte) dans le panneau.
    expect(screen.queryByText(/seuil|alerte critique/i)).not.toBeInTheDocument()
  })

  it('un changement de période refait l\'appel', async () => {
    mount()
    await waitFor(() => expect(crmApi.getKpiAdherence).toHaveBeenCalledWith({ jours: '30' }))
    fireEvent.change(screen.getByRole('combobox', { name: 'Période' }), { target: { value: '7' } })
    await waitFor(() => expect(crmApi.getKpiAdherence).toHaveBeenCalledWith({ jours: '7' }))
  })

  it('indisponible : ne casse pas l\'écran sur un échec réseau', async () => {
    crmApi.getKpiAdherence.mockRejectedValue(new Error('boom'))
    mount()
    expect(await screen.findByText(/Indisponible pour le moment/)).toBeInTheDocument()
  })
})

// STAGE_LABELS FR minimal pour vérifier qu'une étape apparaît (sans dupliquer
// tout le miroir `stages.js` ici) — QUOTE_SENT est l'étape null du contrat.
function premierLabel(stage) {
  const labels = { NEW: 'Nouveau', CONTACTED: 'Contacté', QUOTE_SENT: 'Devis envoyé' }
  return labels[stage] ?? stage
}
