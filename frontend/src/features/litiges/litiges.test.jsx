import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import {
  transitionsPour, estTerminal, STATUT_MAP, GRAVITE_MAP,
} from './litigesStatus'
import FilterSelect from './FilterSelect'
import ReclamationDetail from './ReclamationDetail'
import ReclamationEditor from './ReclamationEditor'

function wrap(ui) {
  return (
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>
  )
}

// ── LITIGE4 — stub complet du client API litiges (aucun réseau) ──
const litigesApiMock = vi.hoisted(() => ({
  get: vi.fn(),
  historique: vi.fn(),
  update: vi.fn(),
  create: vi.fn(),
  noter: vi.fn(),
  prendreEnCharge: vi.fn(),
  resoudre: vi.fn(),
  rejeter: vi.fn(),
}))
vi.mock('../../api/litigesApi', () => ({ default: litigesApiMock }))

// WIR10 — stub du client API ventes (recherche de facture à lier).
const ventesApiMock = vi.hoisted(() => ({
  getFactures: vi.fn(() => Promise.resolve({ data: { results: [] } })),
  getFacture: vi.fn(() => Promise.resolve({ data: {} })),
}))
vi.mock('../../api/ventesApi', () => ({ default: ventesApiMock }))

// jsdom n'implémente pas ResizeObserver (Switch/Radix Switch dans l'éditeur).
beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

describe('litiges state machine helpers', () => {
  it('transitionsPour reflète la machine à états backend', () => {
    expect(transitionsPour('ouverte')).toEqual(['prendre_en_charge', 'rejeter'])
    expect(transitionsPour('en_traitement')).toEqual(['resoudre', 'rejeter'])
    expect(transitionsPour('resolue')).toEqual([])
    expect(transitionsPour('rejetee')).toEqual([])
  })

  it('estTerminal marque resolue/rejetee comme terminaux', () => {
    expect(estTerminal('resolue')).toBe(true)
    expect(estTerminal('rejetee')).toBe(true)
    expect(estTerminal('ouverte')).toBe(false)
    expect(estTerminal('en_traitement')).toBe(false)
  })

  it('les cartes de statut/gravité couvrent toutes les valeurs backend', () => {
    expect(Object.keys(STATUT_MAP).sort()).toEqual(
      ['en_traitement', 'ouverte', 'rejetee', 'resolue'],
    )
    expect(Object.keys(GRAVITE_MAP).sort()).toEqual(
      ['elevee', 'faible', 'moyenne'],
    )
  })
})

describe('FilterSelect (smoke)', () => {
  it('rend les options de gravité et la valeur courante', () => {
    render(wrap(
      <FilterSelect
        value="elevee"
        onChange={() => {}}
        options={Object.entries(GRAVITE_MAP).map(([value, v]) => ({ value, label: v.label }))}
        aria-label="Gravité"
      />,
    ))
    const select = screen.getByRole('combobox', { name: 'Gravité' })
    expect(select.value).toBe('elevee')
    expect(screen.getByText('Élevée')).toBeTruthy()
  })
})

// ── LITIGE4 — NCR / audit QHSE lié : affichage (détail) + saisie (éditeur) ──
describe('ReclamationDetail — onglet NCR / Audit lié', () => {
  it('affiche les aperçus NCR et audit renvoyés par le serializer', async () => {
    litigesApiMock.get.mockResolvedValue({
      data: {
        id: 1,
        reference: 'REC-0001',
        objet: 'Fissure panneau',
        statut: 'ouverte',
        ncr_id: 5,
        audit_id: 9,
        ncr: {
          id: 5, reference: 'NCR-0005', titre: 'Casse transport',
          gravite: 'elevee', gravite_display: 'Élevée',
          statut: 'ouverte', statut_display: 'Ouverte', chantier_id: 2,
        },
        audit: {
          id: 9, grille: 'Grille réception', date_audit: '2026-06-01',
          statut: 'termine', statut_display: 'Terminé', score: 87, chantier_id: 2,
        },
      },
    })
    litigesApiMock.historique.mockResolvedValue({ data: [] })

    render(wrap(<ReclamationDetail reclamationId={1} onBack={() => {}} onEdit={() => {}} />))

    await waitFor(() => expect(screen.getByText('Fissure panneau')).toBeTruthy())
    const user = userEvent.setup()
    await user.click(screen.getByRole('tab', { name: 'NCR / Audit lié' }))

    expect(await screen.findByText('NCR-0005')).toBeTruthy()
    expect(screen.getByText('Casse transport')).toBeTruthy()
    expect(screen.getByText('Grille réception')).toBeTruthy()
  })

  it("affiche des états vides quand aucune NCR/audit n'est liée", async () => {
    litigesApiMock.get.mockResolvedValue({
      data: {
        id: 2, reference: 'REC-0002', objet: 'Retard livraison', statut: 'ouverte',
        ncr_id: null, audit_id: null, ncr: null, audit: null,
      },
    })
    litigesApiMock.historique.mockResolvedValue({ data: [] })

    render(wrap(<ReclamationDetail reclamationId={2} onBack={() => {}} onEdit={() => {}} />))

    await waitFor(() => expect(screen.getByText('Retard livraison')).toBeTruthy())
    const user = userEvent.setup()
    await user.click(screen.getByRole('tab', { name: 'NCR / Audit lié' }))

    expect(await screen.findByText('Aucune NCR liée')).toBeTruthy()
    expect(screen.getByText('Aucun audit lié')).toBeTruthy()
  })
})

describe('ReclamationEditor — rattachement NCR / audit', () => {
  it('poste ncr_id/audit_id saisis lors de l’enregistrement', async () => {
    litigesApiMock.update.mockResolvedValue({ data: { id: 3 } })

    render(wrap(
      <ReclamationEditor
        reclamation={{ id: 3, objet: 'Litige existant', ncr_id: null, audit_id: null }}
        onCancel={() => {}}
        onSaved={() => {}}
      />,
    ))

    fireEvent.change(screen.getByLabelText('ID de la NCR liée'), { target: { value: '7' } })
    fireEvent.change(screen.getByLabelText("ID de l'audit fin de chantier lié"), { target: { value: '11' } })
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer/ }))

    await waitFor(() => expect(litigesApiMock.update).toHaveBeenCalled())
    const [, payload] = litigesApiMock.update.mock.calls[0]
    expect(payload.ncr_id).toBe('7')
    expect(payload.audit_id).toBe('11')
  })
})

// WIR10 — jusqu'ici AUCUN chemin UI ne posait `source_type='facture'`/
// `source_id` sur une réclamation : `litiges.selectors.relances_suspendues_pour_facture`
// (consommé par `ventes.scheduled`) ne trouvait donc jamais rien à bloquer.
describe('ReclamationEditor — facture liée (WIR10)', () => {
  it('lie une facture réelle et poste source_type/source_id à la création', async () => {
    ventesApiMock.getFactures.mockResolvedValueOnce({
      data: { results: [{ id: 55, reference: 'FA-2026-0099' }] },
    })
    litigesApiMock.create.mockResolvedValue({ data: { id: 10 } })

    render(wrap(
      <ReclamationEditor onCancel={() => {}} onSaved={() => {}} />,
    ))

    fireEvent.change(screen.getByLabelText('Objet'), { target: { value: 'Facture contestée' } })

    fireEvent.click(screen.getByRole('combobox', { name: /Facture liée/ }))
    const search = await screen.findByRole('searchbox')
    fireEvent.change(search, { target: { value: 'FA-2026' } })
    fireEvent.click(await screen.findByRole('option', { name: /FA-2026-0099/ }))

    fireEvent.click(screen.getByRole('button', { name: /Enregistrer/ }))

    await waitFor(() => expect(litigesApiMock.create).toHaveBeenCalled())
    const [payload] = litigesApiMock.create.mock.calls[0]
    expect(payload.source_type).toBe('facture')
    expect(payload.source_id).toBe(55)
    expect(payload.bloque_relances).toBe(true)
  })
})
