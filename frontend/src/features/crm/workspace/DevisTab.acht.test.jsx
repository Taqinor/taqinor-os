import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { initState } from './draftCore'
import DevisTab from './DevisTab'

/* ACHT5 — « Créer le chantier » n'est proposé que sur la TÊTE de chaîne
   active : une version remplacée (is_active=false) n'a jamais de chantier. */

vi.mock('../../../api/ventesApi', () => ({
  default: {
    genererFacture: vi.fn(), shareLinkDevis: vi.fn(),
    getOffresTaillesDevis: vi.fn(() => Promise.resolve({ data: { editable: false } })),
    reviserDevis: vi.fn(),
  },
}))
vi.mock('../../../api/installationsApi', () => ({ default: { createFromDevis: vi.fn() } }))
vi.mock('../../../api/stockApi', () => ({
  default: { getProduits: vi.fn(() => Promise.resolve({ data: { results: [], count: 0, next: null } })) },
}))
vi.mock('../../../api/crmApi', () => ({
  default: {
    whatsappDevis: vi.fn(),
    whatsappDevisApercu: vi.fn(),
    getLeadSalleVenteAnalytics: () => Promise.resolve({ data: null }),
  },
}))

beforeAll(() => {
  if (!window.HTMLElement.prototype.scrollIntoView) window.HTMLElement.prototype.scrollIntoView = () => {}
})
afterEach(cleanup)

const base = {
  statut: 'accepte', total_ttc: '15000', date_creation: '2026-01-05',
  option_acceptee: 'A', chantier: null, is_active: true,
}

function rendre(devis) {
  const state = initState({
    lead: {
      id: 7, nom: 'Karim', telephone: '0612345678', whatsapp: '',
      devis, devis_auto: { pret: true, manquants: [], message: null },
    },
    mode: 'edit',
  })
  return render(
    <MemoryRouter>
      <DevisTab
        state={state} onAction={vi.fn()}
        wa={{ selected: [], langue: 'fr', preview: null }}
        onWaToggle={vi.fn()} onWaLangue={vi.fn()} onWaPreview={vi.fn()} onWaReset={vi.fn()}
      />
    </MemoryRouter>,
  )
}

describe('ACHT5 — création de chantier sur la tête de chaîne seulement', () => {
  it('pas de création sur version remplacée', () => {
    rendre([
      { ...base, id: 1, reference: 'DEV-V1', is_active: false, superseded_by: 2 },
      { ...base, id: 2, reference: 'DEV-V2', version: 2, chantier: { id: 5, reference: 'CHT-5' } },
    ])
    expect(screen.queryByRole('button', { name: /Créer le chantier/ })).toBeNull()
    expect(screen.getByRole('link', { name: /CHT-5/ })).toHaveAttribute('href', '/chantiers?id=5')
  })

  it('bouton gardé sur tête active', () => {
    rendre([{ ...base, id: 3, reference: 'DEV-V3' }])
    expect(screen.getByRole('button', { name: /Créer le chantier/ })).toBeInTheDocument()
  })
})
