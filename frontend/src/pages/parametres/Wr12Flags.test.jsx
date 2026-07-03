import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'

/* WR12 — exposition des flags backend-only en Paramètres :
   - DevisSection : commission (N99) + export DGI (N105) réservés à l'admin ;
   - LeadsSection : délai SLA de premier contact (FG28), éditable. */

import DevisSection from './DevisSection'
import LeadsSection from './LeadsSection'

afterEach(() => cleanup())

const baseForm = {
  payment_terms: {}, doc_prefixes: {}, doc_numbering: {},
  quote_validity_days: 30, agricole_pump_hours: 7,
  commission_mode: 'off', commission_valeur: '',
  dgi_export_actif: false, tva_standard: 20, tva_panneaux: 10,
  referral_enabled: false, referral_reward: '', lead_sla_hours: 24,
  responsable_defaut_leads: '', default_installer: '',
}

const devisProps = {
  form: baseForm, set: vi.fn(), setForm: vi.fn(), setPT: vi.fn(),
  setPrefix: vi.fn(), setNumbering: vi.fn(), numberingPreview: () => 'DEV-1',
}

describe('WR12 — DevisSection (commission N99 + DGI N105, admin only)', () => {
  it('cache les réglages sensibles pour un non-admin', () => {
    render(<DevisSection {...devisProps} canManageSensitive={false} />)
    // Commission verrouillée : message + pas de sélecteur de mode.
    expect(screen.getByText(/Réservé à l'administrateur/)).toBeInTheDocument()
    expect(screen.queryByLabelText('Mode')).not.toBeInTheDocument()
    // DGI non affiché.
    expect(screen.queryByText("Activer l'export DGI")).not.toBeInTheDocument()
  })

  it('expose commission + DGI pour un admin', () => {
    render(<DevisSection {...devisProps} canManageSensitive />)
    expect(screen.queryByText(/Réservé à l'administrateur/)).not.toBeInTheDocument()
    expect(screen.getByText('Export DGI (facturation électronique)')).toBeInTheDocument()
    expect(screen.getByText("Activer l'export DGI")).toBeInTheDocument()
  })
})

const leadsProps = {
  form: baseForm, set: vi.fn(), setForm: vi.fn(),
  assignables: [], tags: [], motifs: [], canaux: [],
  newTag: '', setNewTag: vi.fn(), addTag: vi.fn(), renameTag: vi.fn(),
  delTag: vi.fn(), archiveTag: vi.fn(), setTagColor: vi.fn(),
  newMotif: '', setNewMotif: vi.fn(), addMotif: vi.fn(), renameMotif: vi.fn(),
  delMotif: vi.fn(), archiveMotif: vi.fn(),
  newCanal: '', setNewCanal: vi.fn(), addCanal: vi.fn(), renameCanal: vi.fn(),
  delCanal: vi.fn(), archiveCanal: vi.fn(), refLoading: {},
}

describe('WR12 — LeadsSection (SLA premier contact FG28)', () => {
  it('affiche le champ SLA lié à lead_sla_hours', () => {
    render(<LeadsSection {...leadsProps} />)
    const input = screen.getByLabelText('Délai SLA de premier contact (heures)')
    expect(input).toBeInTheDocument()
    expect(input).toHaveValue(24)
    expect(input).toHaveAttribute('name', 'lead_sla_hours')
  })
})
