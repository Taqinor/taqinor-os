import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { initState } from './draftCore'
import IdentityRail from './IdentityRail'
import crmApi from '../../../api/crmApi'

/* crmApi mocké → aucune requête réelle au montage ; chaque test peut surcharger
   le retour (mockResolvedValueOnce) pour les bannières LW18. */
vi.mock('../../../api/crmApi', () => ({
  default: {
    getLeadDuplicates: vi.fn(() => Promise.resolve({ data: [] })),
    getLeadClientMatch: vi.fn(() => Promise.resolve({ data: [] })),
    mergeLeads: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))
vi.mock('../../../hooks/useDuplicateCheck', () => ({ useDuplicateCheck: () => [] }))
// AssigneePicker mocké en bouton cliquable pour tester le PATCH du responsable.
vi.mock('../../../components/AssigneePicker', () => ({
  default: ({ value, onChange }) => (
    <button type="button" data-testid="assignee" onClick={() => onChange(9)}>{String(value ?? '')}</button>
  ),
}))
// DatePicker (relance) → input date natif pour émettre onChange(Date) simplement.
// Le reste du barrel ui reste RÉEL (Button/Badge/Avatar/FieldSavedPulse).
vi.mock('../../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    DatePicker: ({ value, onChange }) => (
      <input
        data-testid="relance-input"
        type="date"
        defaultValue={value instanceof Date && !Number.isNaN(value.getTime())
          ? value.toISOString().slice(0, 10) : ''}
        onChange={(e) => onChange(e.target.value ? new Date(`${e.target.value}T00:00:00`) : null)}
      />
    ),
  }
})

afterEach(() => { cleanup(); vi.clearAllMocks() })

const makeState = (over = {}) => initState({
  lead: {
    id: 7, nom: 'Karim', prenom: 'B.', societe: 'Ferme Atlas', ville: 'Agadir',
    telephone: '0612345678', email: 'karim@ex.ma', is_archived: false,
    devis_auto: { pret: false, message: 'Renseignez la facture.' },
    ...over,
  },
  mode: 'edit',
})

describe('LW14 — IdentityRail identité + actions', () => {
  let onAction
  beforeEach(() => { onAction = vi.fn() })

  it('affiche le nom, la société/ville et le testid du rail', () => {
    render(<IdentityRail state={makeState()} onAction={onAction} users={[]} />)
    expect(screen.getByTestId('lw-identity-rail')).toBeInTheDocument()
    expect(screen.getByText('Karim B.')).toBeInTheDocument()
    expect(screen.getByText(/Ferme Atlas · Agadir/)).toBeInTheDocument()
  })

  it('rend les liens de contact tel:/mailto:', () => {
    render(<IdentityRail state={makeState()} onAction={onAction} users={[]} />)
    expect(document.querySelector('a[href="tel:0612345678"]')).toBeInTheDocument()
    expect(document.querySelector('a[href="mailto:karim@ex.ma"]')).toBeInTheDocument()
  })

  it('WhatsApp armé sur un numéro valide, désactivé sur un numéro invalide', () => {
    const { rerender } = render(<IdentityRail state={makeState()} onAction={onAction} users={[]} />)
    expect(screen.getByRole('button', { name: /Envoyer WhatsApp/ })).not.toBeDisabled()
    rerender(<IdentityRail state={makeState({ telephone: '123', whatsapp: '' })} onAction={onAction} users={[]} />)
    expect(screen.getByRole('button', { name: /Envoyer WhatsApp/ })).toBeDisabled()
  })

  it('Devis automatique verrouillé tant que devis_auto.pret est faux', () => {
    render(<IdentityRail state={makeState()} onAction={onAction} users={[]} />)
    expect(screen.getByRole('button', { name: /Devis automatique/ })).toBeDisabled()
  })

  it('Devis automatique déverrouillé appelle onAction(open-devis, auto)', () => {
    render(<IdentityRail state={makeState({ devis_auto: { pret: true } })} onAction={onAction} users={[]} />)
    fireEvent.click(screen.getByRole('button', { name: /Devis automatique/ }))
    expect(onAction).toHaveBeenCalledWith('open-devis', 'auto')
  })

  it('Toiture 3D, Convertir et Archiver routent par onAction', () => {
    render(<IdentityRail state={makeState()} onAction={onAction} users={[]} />)
    fireEvent.click(screen.getByRole('button', { name: /Concevoir la toiture/ }))
    expect(onAction).toHaveBeenCalledWith('toiture-3d')
    fireEvent.click(screen.getByRole('button', { name: /Convertir en client/ }))
    expect(onAction).toHaveBeenCalledWith('convert')
    fireEvent.click(screen.getByRole('button', { name: /Archiver/ }))
    expect(onAction).toHaveBeenCalledWith('archive')
  })

  it('masque « Convertir » quand le lead est déjà rattaché à un client', () => {
    render(<IdentityRail state={makeState({ client: 42 })} onAction={onAction} users={[]} />)
    expect(screen.queryByRole('button', { name: /Convertir en client/ })).toBeNull()
  })

  it('affiche « Restaurer » pour un lead archivé', () => {
    render(<IdentityRail state={makeState({ is_archived: true })} onAction={onAction} users={[]} />)
    expect(screen.getByRole('button', { name: /Restaurer/ })).toBeInTheDocument()
  })

  it('rend les chips QX28 selon les données prêtes', () => {
    render(<IdentityRail
      state={makeState({ roof_point: { lat: 30, lng: -9 }, facture_hiver: 650, devis_auto: { pret: true } })}
      onAction={onAction}
      users={[]}
    />)
    expect(screen.getByText(/Toit épinglé/)).toBeInTheDocument()
    expect(screen.getByText(/Facture saisie/)).toBeInTheDocument()
    expect(screen.getByText(/Prêt à deviser/)).toBeInTheDocument()
  })
})

describe('LW15 — triade responsable · prochaine action · relance', () => {
  let onAction
  beforeEach(() => { onAction = vi.fn() })

  it('affiche le badge d\'alerte quand le lead n\'a pas de prochaine action', () => {
    render(<IdentityRail state={makeState()} onAction={onAction} users={[]} />)
    expect(screen.getByText('Sans prochaine action')).toBeInTheDocument()
  })

  it('« Planifier » (sans prochaine action) ouvre le plan via onAction(plan)', () => {
    render(<IdentityRail state={makeState()} onAction={onAction} users={[]} />)
    fireEvent.click(screen.getByRole('button', { name: /Planifier/ }))
    expect(onAction).toHaveBeenCalledWith('plan')
  })

  it('affiche le résumé de la prochaine action quand elle existe', () => {
    const state = makeState({
      next_activity: { state: 'today', due_date: '2026-08-01', summary: 'Rappeler le client' },
    })
    render(<IdentityRail state={state} onAction={onAction} users={[]} />)
    expect(screen.getByText(/Rappeler le client/)).toBeInTheDocument()
    expect(screen.queryByText('Sans prochaine action')).toBeNull()
  })

  it('changer le responsable PATCHe via onAction(set-field, owner)', () => {
    render(<IdentityRail state={makeState()} onAction={onAction} users={[{ id: 9, username: 'Meriem' }]} />)
    fireEvent.click(screen.getByTestId('assignee'))
    expect(onAction).toHaveBeenCalledWith('set-field', { key: 'owner', value: 9 })
  })

  it('changer la relance PATCHe via onAction(set-field, relance_date) en date locale', () => {
    render(<IdentityRail state={makeState()} onAction={onAction} users={[]} />)
    fireEvent.change(screen.getByTestId('relance-input'), { target: { value: '2026-08-01' } })
    expect(onAction).toHaveBeenCalledWith('set-field', { key: 'relance_date', value: '2026-08-01' })
  })
})

describe('LW17 — score expliqué (popover des raisons)', () => {
  let onAction
  beforeEach(() => { onAction = vi.fn() })

  it('le badge de score ouvre un popover listant les raisons + le pied', async () => {
    const state = makeState({
      score: 72,
      score_label: 'Chaud',
      score_reasons: [
        { facteur: 'facture', label: 'Facture élevée', points: 20 },
        { facteur: 'canal', label: 'Canal direct', points: 15 },
        { facteur: 'recence', label: 'Lead récent', points: -8 },
      ],
    })
    render(<IdentityRail state={state} onAction={onAction} users={[]} />)
    fireEvent.click(screen.getByRole('button', { name: /Score de qualité 72/ }))
    expect(await screen.findByText('Facture élevée')).toBeInTheDocument()
    expect(screen.getByText('Canal direct')).toBeInTheDocument()
    expect(screen.getByText('Lead récent')).toBeInTheDocument()
    expect(screen.getByText(/Le score se recalcule/)).toBeInTheDocument()
  })

  it('n\'affiche pas le bloc score quand le lead n\'a pas de score', () => {
    render(<IdentityRail state={makeState()} onAction={onAction} users={[]} />)
    expect(screen.queryByRole('button', { name: /Score de qualité/ })).toBeNull()
  })
})

describe('LW18 — bannières intelligentes (doublons · client_match)', () => {
  let onAction
  beforeEach(() => { onAction = vi.fn() })

  it('2 doublons → bannière + dialog listant 2 lignes « Fusionner ici »', async () => {
    crmApi.getLeadDuplicates.mockResolvedValueOnce({ data: [
      { id: 11, nom: 'Karim', prenom: 'B.', telephone: '0612345678', ville: 'Agadir' },
      { id: 12, nom: 'Karim', prenom: 'C.', telephone: '0612345679', ville: 'Rabat' },
    ] })
    render(<IdentityRail state={makeState()} onAction={onAction} users={[]} />)
    expect(await screen.findByText(/2 doublons probables/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Examiner/ }))
    expect(await screen.findByText('Doublons probables')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /Fusionner ici/ })).toHaveLength(2)
  })

  it('client_match → bannière avec lien vers /crm/clients/:id', async () => {
    crmApi.getLeadClientMatch.mockResolvedValueOnce({ data: [
      { id: 42, nom: 'Atlas Agri SARL', nb_devis: 3, nb_chantiers: 1 },
    ] })
    render(<IdentityRail state={makeState()} onAction={onAction} users={[]} />)
    expect(await screen.findByText(/correspond au client Atlas Agri SARL/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Ouvrir la fiche/ })).toHaveAttribute('href', '/crm/clients/42')
  })

  it('aucune bannière quand ni doublon ni client correspondant (silencieux)', async () => {
    render(<IdentityRail state={makeState()} onAction={onAction} users={[]} />)
    expect(await screen.findByText('Karim B.')).toBeInTheDocument()
    expect(screen.queryByText(/doublon/)).toBeNull()
    expect(screen.queryByText(/correspond au client/)).toBeNull()
  })
})
