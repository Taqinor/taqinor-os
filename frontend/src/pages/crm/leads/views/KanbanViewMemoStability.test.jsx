import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, cleanup } from '@testing-library/react'
import KanbanView from './KanbanView'

/* LB6 — sonde légère (blueprint I4, bug recon2-03 #4) : une frappe dans la
   recherche de LeadsPage recalcule `filtered` (nouvelle référence de tableau)
   mais ne mute AUCUN lead ni AUCUN callback stabilisé (useCallback côté
   LeadsPage) — donc AUCUNE carte ne doit se re-rendre. On mocke LeadCard par
   un espion qui compte ses rendus, on rend KanbanView deux fois avec des
   props RÉFÉRENTIELLEMENT stables (mêmes objets lead, mêmes callbacks) mais
   un nouveau tableau `leads`/`columns` conteneur (exactement le scénario
   d'une frappe de recherche), et on vérifie 0 rendu supplémentaire. */

const renderCounts = {}
// Le mock DOIT être memo() comme le vrai LeadCard (export memo, LeadCard.jsx:689) :
// l'enveloppe DraggableCard se re-rend légitimement quand le contexte interne de
// dnd-kit churn (useDraggable s'abonne au DndContext — un memo ne protège pas
// d'un hook) ; l'invariant LB6 est que la CARTE LOURDE, elle, ne se re-rend pas.
vi.mock('./LeadCard', async () => {
  const { memo } = await import('react')
  return {
    default: memo((props) => {
      renderCounts[props.lead.id] = (renderCounts[props.lead.id] ?? 0) + 1
      return <article className="kb-card" data-testid={`card-${props.lead.id}`}>
        <span className="kb-card-name">{props.lead.nom}</span>
      </article>
    }),
  }
})

afterEach(() => { cleanup(); vi.clearAllMocks() })

const makeLead = (id, stage) => ({ id, nom: `Lead ${id}`, stage, date_creation: '2026-07-01' })

describe('KanbanView · sonde de re-rendu (LB6, bug #4)', () => {
  it('une frappe de recherche (nouveau tableau `leads`, mêmes leads/callbacks) ne re-rend AUCUNE carte', () => {
    for (const k of Object.keys(renderCounts)) delete renderCounts[k]

    // Callbacks STABLES (comme après LB6 : useCallback côté LeadsPage) —
    // définis UNE FOIS, jamais recréés entre les deux rendus.
    const stableProps = {
      onOpenLead: vi.fn(),
      onChangeStage: vi.fn(),
      onAutoQuote: vi.fn(),
      onReassign: vi.fn(),
      onToggleSelect: vi.fn(),
      onPlanifierRelance: vi.fn(),
      onInlineSave: vi.fn(),
      onMarkPerdu: vi.fn(),
      users: [],
      busyLeadId: null,
    }

    // Les OBJETS lead eux-mêmes restent identiques (mêmes références) — seul
    // le TABLEAU conteneur change, exactement ce que produit `filtered`
    // (useMemo) de LeadsPage quand `filters.q` change mais qu'aucun lead n'a
    // réellement été modifié.
    const leadA = makeLead(1, 'NEW')
    const leadB = makeLead(2, 'CONTACTED')

    const { rerender } = render(
      <KanbanView leads={[leadA, leadB]} {...stableProps} />,
    )
    expect(renderCounts[1]).toBe(1)
    expect(renderCounts[2]).toBe(1)

    // Deuxième rendu : NOUVEAU tableau `leads` (référence différente), mêmes
    // objets lead à l'intérieur, mêmes callbacks (mêmes références) — le
    // scénario exact d'une frappe de recherche après LB6.
    rerender(<KanbanView leads={[leadA, leadB]} {...stableProps} />)

    expect(renderCounts[1]).toBe(1) // AUCUN re-rendu supplémentaire
    expect(renderCounts[2]).toBe(1)
  })

  it('un changement RÉEL (busyLeadId ciblé) ne re-rend que la carte concernée, pas les autres', () => {
    for (const k of Object.keys(renderCounts)) delete renderCounts[k]

    const stableProps = {
      onOpenLead: vi.fn(),
      onChangeStage: vi.fn(),
      onAutoQuote: vi.fn(),
      onReassign: vi.fn(),
      onToggleSelect: vi.fn(),
      onPlanifierRelance: vi.fn(),
      onInlineSave: vi.fn(),
      onMarkPerdu: vi.fn(),
      users: [],
    }
    const leadA = makeLead(1, 'NEW')
    const leadB = makeLead(2, 'CONTACTED')

    const { rerender } = render(
      <KanbanView leads={[leadA, leadB]} busyLeadId={null} {...stableProps} />,
    )
    expect(renderCounts[1]).toBe(1)
    expect(renderCounts[2]).toBe(1)

    // busyLeadId cible SEULEMENT le lead 1 : sa carte doit re-rendre (busy
    // change), la carte 2 ne doit PAS re-rendre (son `busy` reste `false`
    // aux deux rendus — même valeur primitive).
    rerender(<KanbanView leads={[leadA, leadB]} busyLeadId={1} {...stableProps} />)

    expect(renderCounts[1]).toBe(2)
    expect(renderCounts[2]).toBe(1)
  })
})
