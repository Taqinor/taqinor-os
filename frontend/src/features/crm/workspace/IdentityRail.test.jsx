import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { initState } from './draftCore'
import IdentityRail from './IdentityRail'
import crmApi from '../../../api/crmApi'
import { CANAL_LABELS, formatMAD } from '../stages'

// PUB53 — badge « Vient de la pub » gaté au rôle voyant /publicite. Comme
// ViewsManagerPopover.test.jsx, on mocke le hook plutôt que de monter un vrai
// Provider redux (ce fichier n'en a jamais eu besoin jusqu'ici) ; défaut à
// `true` pour ne rien changer aux tests LW14/LW15/LW17/LW18 existants (aucun
// n'affecte meta_ad_id, donc le badge reste absent chez eux quel que soit
// le rôle).
const isAdminOrResponsableMock = vi.fn(() => true)
vi.mock('../../../hooks/useHasPermission', () => ({
  useIsAdminOrResponsable: () => isAdminOrResponsableMock(),
}))

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

// LWC2 — les actions secondaires vivent dans le menu « ⋯ ». Radix ouvre au
// clavier comme au pointeur ; le clavier est le chemin stable en jsdom.
const ouvrirPlus = () => {
  fireEvent.keyDown(screen.getByRole('button', { name: /Plus d'actions/ }), { key: 'Enter' })
}

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
    expect(screen.getByRole('button', { name: /WhatsApp/ })).not.toBeDisabled()
    rerender(<IdentityRail state={makeState({ telephone: '123', whatsapp: '' })} onAction={onAction} users={[]} />)
    expect(screen.getByRole('button', { name: /WhatsApp/ })).toBeDisabled()
  })

  it('Devis auto verrouillé tant que devis_auto.pret est faux', () => {
    render(<IdentityRail state={makeState()} onAction={onAction} users={[]} />)
    expect(screen.getByRole('button', { name: /Devis auto/ })).toBeDisabled()
  })

  it('Devis auto déverrouillé appelle onAction(open-devis, auto)', () => {
    render(<IdentityRail state={makeState({ devis_auto: { pret: true } })} onAction={onAction} users={[]} />)
    fireEvent.click(screen.getByRole('button', { name: /Devis auto/ }))
    expect(onAction).toHaveBeenCalledWith('open-devis', 'auto')
  })

  // LWC2 — les 4 actions secondaires ont quitté la pile pour le menu « ⋯ » ;
  // les handlers, eux, sont les mêmes (mêmes clés onAction).
  it('Toiture 3D route par onAction depuis le menu « ⋯ »', async () => {
    render(<IdentityRail state={makeState()} onAction={onAction} users={[]} />)
    ouvrirPlus()
    fireEvent.click(await screen.findByRole('menuitem', { name: /Concevoir la toiture/ }))
    expect(onAction).toHaveBeenCalledWith('toiture-3d')
  })

  it('Convertir route par onAction depuis le menu « ⋯ »', async () => {
    render(<IdentityRail state={makeState()} onAction={onAction} users={[]} />)
    ouvrirPlus()
    fireEvent.click(await screen.findByRole('menuitem', { name: /Convertir en client/ }))
    expect(onAction).toHaveBeenCalledWith('convert')
  })

  it('Archiver route par onAction depuis le menu « ⋯ »', async () => {
    render(<IdentityRail state={makeState()} onAction={onAction} users={[]} />)
    ouvrirPlus()
    fireEvent.click(await screen.findByRole('menuitem', { name: /Archiver/ }))
    expect(onAction).toHaveBeenCalledWith('archive')
  })

  it('Archiver reste inerte pendant archiveBusy (garde destructive conservée)', async () => {
    render(<IdentityRail state={makeState()} onAction={onAction} users={[]} archiveBusy />)
    ouvrirPlus()
    const item = await screen.findByRole('menuitem', { name: /Archiver/ })
    expect(item).toHaveAttribute('data-disabled')
    fireEvent.click(item)
    expect(onAction).not.toHaveBeenCalledWith('archive')
  })

  it('masque « Convertir » quand le lead est déjà rattaché à un client', async () => {
    render(<IdentityRail state={makeState({ client: 42 })} onAction={onAction} users={[]} />)
    ouvrirPlus()
    await screen.findByRole('menuitem', { name: /Archiver/ })
    expect(screen.queryByRole('menuitem', { name: /Convertir en client/ })).toBeNull()
  })

  it('affiche « Restaurer » pour un lead archivé', async () => {
    render(<IdentityRail state={makeState({ is_archived: true })} onAction={onAction} users={[]} />)
    ouvrirPlus()
    expect(await screen.findByRole('menuitem', { name: /Restaurer/ })).toBeInTheDocument()
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

  // LW45 — état « manquant » discret RÉTABLI (l'ancien en-tête stylait aussi
  // ces chips en négatif ; le refactor LW14 les avait réduits à une absence
  // silencieuse, seule l'infobulle du CTA « Devis automatique » restait).
  it('rend les chips QX28 en état « manquant » discret quand les données sont absentes', () => {
    render(<IdentityRail state={makeState()} onAction={onAction} users={[]} />)
    expect(screen.getByText(/Toit non épinglé/)).toBeInTheDocument()
    expect(screen.getByText(/Facture manquante/)).toBeInTheDocument()
    expect(screen.getByText(/Devis non prêt/)).toBeInTheDocument()
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

  // APX1 — la cible était `/crm/clients/42`, une route INEXISTANTE (404 réel).
  // Le lien profond vivant est `?id=` (VX220, lu par ClientList.jsx).
  it('client_match → bannière avec lien profond vers /crm?id=<pk> (jamais le 404 /crm/clients/:id)', async () => {
    crmApi.getLeadClientMatch.mockResolvedValueOnce({ data: [
      { id: 42, nom: 'Atlas Agri SARL', nb_devis: 3, nb_chantiers: 1 },
    ] })
    render(<IdentityRail state={makeState()} onAction={onAction} users={[]} />)
    expect(await screen.findByText(/correspond au client Atlas Agri SARL/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Ouvrir la fiche/ })).toHaveAttribute('href', '/crm?id=42')
  })

  it('aucune bannière quand ni doublon ni client correspondant (silencieux)', async () => {
    render(<IdentityRail state={makeState()} onAction={onAction} users={[]} />)
    expect(await screen.findByText('Karim B.')).toBeInTheDocument()
    expect(screen.queryByText(/doublon/)).toBeNull()
    expect(screen.queryByText(/correspond au client/)).toBeNull()
  })

  // LW43 — garde d'identité : une réponse doublons LENTE pour le lead A ne
  // doit plus jamais peindre la bannière sur le lead B après un J/K rapide
  // (course reproduite en gardant la promesse de A EN VOL pendant le rerender
  // vers B — même patron `cancelled` que LeadDetailPage.jsx).
  it('réponse doublons du lead A résolue APRÈS navigation vers B → jamais peinte sur B', async () => {
    let resolveA
    crmApi.getLeadDuplicates.mockImplementationOnce(() => new Promise((res) => { resolveA = res }))
    const { rerender } = render(<IdentityRail state={makeState({ id: 7 })} onAction={onAction} users={[]} />)
    rerender(<IdentityRail state={makeState({ id: 8 })} onAction={onAction} users={[]} />)
    await waitFor(() => expect(crmApi.getLeadDuplicates).toHaveBeenCalledTimes(2))
    resolveA({ data: [{ id: 99, nom: 'Doublon de A', telephone: '0600000000', ville: 'Casablanca' }] })
    await screen.findByText('Karim B.')
    expect(screen.queryByText(/doublon/)).toBeNull()
  })
})

describe('LWC2 — bande « Faits clés » (remplace la pile de boutons)', () => {
  let onAction
  beforeEach(() => { onAction = vi.fn() })

  const DEVIS = [{
    id: 5, reference: 'DEV-2026-07-0003', statut: 'envoye',
    total_ttc: '48500.00', date_creation: '2026-07-30T12:00:00Z',
  }]

  it('affiche le montant du dernier devis, son statut et sa référence', () => {
    const { container } = render(<IdentityRail state={makeState({ devis: DEVIS })} onAction={onAction} users={[]} />)
    expect(screen.getByText('Montant estimé')).toBeInTheDocument()
    // `formatMAD` sépare les milliers par une espace fine insécable : on
    // compare des textes NORMALISÉS (le matcher texte de RTL, lui, normalise
    // le DOM mais pas la chaîne attendue — piège classique).
    const norm = (s) => s.replace(/\s/g, ' ')
    expect(norm(container.querySelector('.lw-facts-amount').textContent))
      .toBe(norm(formatMAD(48500)))
    expect(screen.getByText('Envoyé')).toBeInTheDocument()
    expect(screen.getByText('DEV-2026-07-0003')).toBeInTheDocument()
  })

  it('n’affiche JAMAIS un prix d’achat ni une marge (total TTC client seulement)', () => {
    const state = makeState({ devis: [{ ...DEVIS[0], prix_achat: '31000.00', marge: '17500.00' }] })
    const { container } = render(<IdentityRail state={state} onAction={onAction} users={[]} />)
    const facts = container.querySelector('.lw-facts')
    expect(facts.textContent).not.toMatch(/31\s?000|17\s?500|marge/i)
  })

  it('affiche le canal via CANAL_LABELS (jamais la clé brute)', () => {
    render(<IdentityRail state={makeState({ canal: 'meta_ads' })} onAction={onAction} users={[]} />)
    expect(screen.getByText('Canal')).toBeInTheDocument()
    expect(screen.getByText(CANAL_LABELS.meta_ads)).toBeInTheDocument()
  })

  // Le chatter embarqué (LW30) est trié ÉPINGLÉS D'ABORD : la 1re ligne n'est
  // pas la plus récente, et un log automatique n'est pas un « échange ».
  it('« Dernier échange » = touche humaine la PLUS RÉCENTE du chatter embarqué', () => {
    const state = makeState({
      chatter_recent: [
        { id: 1, kind: 'note', body: 'épinglée', created_at: '2026-06-01T12:00:00Z' },
        { id: 2, kind: 'modification', body: 'stage', created_at: '2026-07-31T12:00:00Z' },
        { id: 3, kind: 'appel', body: 'rappel', created_at: '2026-07-28T12:00:00Z' },
      ],
    })
    render(<IdentityRail state={state} onAction={onAction} users={[]} />)
    expect(screen.getByText('Dernier échange')).toBeInTheDocument()
    expect(screen.getByText('28/07/2026')).toBeInTheDocument()
  })

  it('omet « Dernier échange » quand le chatter embarqué ne porte aucune touche humaine', () => {
    const state = makeState({
      chatter_recent: [{ id: 2, kind: 'creation', body: 'créé', created_at: '2026-07-31T12:00:00Z' }],
      canal: 'site_web',
    })
    render(<IdentityRail state={state} onAction={onAction} users={[]} />)
    expect(screen.queryByText('Dernier échange')).toBeNull()
  })

  it('aucune bande du tout quand le lead ne porte aucun fait', () => {
    const { container } = render(<IdentityRail state={makeState()} onAction={onAction} users={[]} />)
    expect(container.querySelector('.lw-facts')).toBeNull()
  })

  // La bande est un pur rendu du payload déjà chargé : elle ne doit RIEN
  // déclencher de plus que les 2 GET des bannières LW18.
  it('n’émet AUCUN appel réseau supplémentaire', async () => {
    const state = makeState({
      devis: DEVIS, canal: 'meta_ads',
      chatter_recent: [{ id: 3, kind: 'appel', body: 'rappel', created_at: '2026-07-28T12:00:00Z' }],
    })
    render(<IdentityRail state={state} onAction={onAction} users={[]} />)
    await screen.findByText('Montant estimé')
    expect(crmApi.getLeadDuplicates).toHaveBeenCalledTimes(1)
    expect(crmApi.getLeadClientMatch).toHaveBeenCalledTimes(1)
    // `points-contact/` (l'autre source « dernier échange ») reste l'affaire de
    // l'onglet Historique : le rail ne peut structurellement pas l'appeler.
    expect(crmApi.getLeadPointsContact).toBeUndefined()
  })
})

describe('PUB53 — badge « Vient de la pub » (traçabilité retour lead Meta → ad)', () => {
  let onAction
  beforeEach(() => {
    onAction = vi.fn()
    isAdminOrResponsableMock.mockReturnValue(true)
  })

  it('affiche le badge + lien vers /publicite/ad/:id pour un lead Meta, rôle autorisé', () => {
    render(<IdentityRail
      state={makeState({ meta_ad_id: '120210000000001' })}
      onAction={onAction}
      users={[]}
    />)
    const link = screen.getByRole('link', { name: /Vient de la pub/ })
    expect(link).toHaveAttribute('href', '/publicite/ad/120210000000001')
    expect(link).toHaveAttribute('target', '_blank')
  })

  it('masque le badge quand le lead n\'a pas de meta_ad_id (lead non-Meta)', () => {
    render(<IdentityRail state={makeState()} onAction={onAction} users={[]} />)
    expect(screen.queryByRole('link', { name: /Vient de la pub/ })).toBeNull()
  })

  it('masque le badge pour un rôle qui ne voit pas /publicite, même sur un lead Meta', () => {
    isAdminOrResponsableMock.mockReturnValue(false)
    render(<IdentityRail
      state={makeState({ meta_ad_id: '120210000000001' })}
      onAction={onAction}
      users={[]}
    />)
    expect(screen.queryByRole('link', { name: /Vient de la pub/ })).toBeNull()
  })
})
