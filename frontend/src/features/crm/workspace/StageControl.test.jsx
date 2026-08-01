import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { initState } from './draftCore'
import StageControl from './StageControl'
import { PIPELINE_STAGES, STAGE_LABELS, CONVERSION_STAGE } from '../stages'

/* LW16 — StageControl : étape, rotting, SIGNED gardé.
   LWC1 — la forme a changé (UNE pilule + menu ▾ au lieu des 6 pastilles en
   rangée) ; le CONTRAT ne change pas : onChangeStage(key) / onSigne(). On lit
   les clés/labels depuis stages.js (règle #2), jamais de littéral local. */

afterEach(() => cleanup())

const CONTACTED = PIPELINE_STAGES[1]
const QUOTE_SENT = PIPELINE_STAGES[2]

const makeState = (over = {}) => initState({
  lead: { id: 3, stage: CONTACTED, stage_since_days: 8, ...over },
  mode: 'edit',
})

// Le déclencheur est la pilule entière (cible tactile ≥44 px). Radix ouvre le
// menu au clavier (Entrée) comme au pointeur — le clavier est le chemin stable
// en jsdom.
const ouvrirMenu = (container) => {
  const trigger = container.querySelector('.lw-stagepill')
  fireEvent.keyDown(trigger, { key: 'Enter' })
  return trigger
}

describe('LW16 — StageControl', () => {
  it('CONTACTED à 8 j affiche l\'ancienneté en classe/rotting warning', () => {
    // LW33 — le compteur de jours vit dans un <span className="num"> (échelle
    // numérique dédiée) : le texte « depuis 8 j » est désormais scindé sur
    // plusieurs nœuds, hors de portée du matcher texte par défaut de RTL
    // (qui ne concatène pas le texte de plusieurs éléments). On requête le
    // conteneur par classe puis on vérifie son textContent complet.
    const { container } = render(<StageControl state={makeState()} onChangeStage={vi.fn()} onSigne={vi.fn()} />)
    const since = container.querySelector('.lw-stage-since')
    expect(since).toHaveTextContent('depuis 8 j')
    expect(since).toHaveAttribute('data-rotting', 'warning')
    expect(since.className).toMatch(/lw-stage-since--warning/)
  })

  it('à 2 j sur NEW, aucune teinte d\'alerte (rotting ok)', () => {
    const NEW = PIPELINE_STAGES[0]
    const { container } = render(<StageControl
      state={makeState({ stage: NEW, stage_since_days: 2 })}
      onChangeStage={vi.fn()}
      onSigne={vi.fn()}
    />)
    const since = container.querySelector('.lw-stage-since')
    expect(since).toHaveTextContent('depuis 2 j')
    expect(since).toHaveAttribute('data-rotting', 'ok')
  })

  // LWC1 — compactage : au repos, UNE seule pilule (l'étape courante), jamais
  // les 6. Les autres étapes ne coûtent plus une ligne de rail.
  it('au repos, seule l\'étape COURANTE est rendue (menu fermé)', () => {
    const { container } = render(<StageControl state={makeState()} onChangeStage={vi.fn()} onSigne={vi.fn()} />)
    expect(container.querySelectorAll('.lw-stagepill')).toHaveLength(1)
    expect(screen.getByText(STAGE_LABELS[CONTACTED])).toBeInTheDocument()
    expect(screen.queryByText(STAGE_LABELS[QUOTE_SENT])).toBeNull()
    expect(screen.queryByRole('menuitem')).toBeNull()
  })

  it('le groupe garde son étiquette aria « Étape du lead »', () => {
    render(<StageControl state={makeState()} onChangeStage={vi.fn()} onSigne={vi.fn()} />)
    expect(screen.getByRole('group', { name: 'Étape du lead' })).toBeInTheDocument()
  })

  it('le menu liste les AUTRES étapes, jamais l\'étape courante', async () => {
    const { container } = render(<StageControl state={makeState()} onChangeStage={vi.fn()} onSigne={vi.fn()} />)
    ouvrirMenu(container)
    const items = await screen.findAllByRole('menuitem')
    expect(items).toHaveLength(PIPELINE_STAGES.length - 1)
    const noms = items.map((i) => i.textContent)
    expect(noms).not.toContain(STAGE_LABELS[CONTACTED])
    expect(noms).toContain(STAGE_LABELS[QUOTE_SENT])
    expect(noms).toContain(STAGE_LABELS[CONVERSION_STAGE])
  })

  it('choisir l\'étape signée ouvre la signature (onSigne), jamais un PATCH direct', async () => {
    const onChangeStage = vi.fn()
    const onSigne = vi.fn()
    const { container } = render(<StageControl state={makeState()} onChangeStage={onChangeStage} onSigne={onSigne} />)
    ouvrirMenu(container)
    fireEvent.click(await screen.findByRole('menuitem', { name: STAGE_LABELS[CONVERSION_STAGE] }))
    expect(onSigne).toHaveBeenCalledTimes(1)
    expect(onChangeStage).not.toHaveBeenCalled()
  })

  it('choisir une autre étape appelle onChangeStage(key)', async () => {
    const onChangeStage = vi.fn()
    const { container } = render(<StageControl state={makeState()} onChangeStage={onChangeStage} onSigne={vi.fn()} />)
    ouvrirMenu(container)
    fireEvent.click(await screen.findByRole('menuitem', { name: STAGE_LABELS[QUOTE_SENT] }))
    expect(onChangeStage).toHaveBeenCalledWith(QUOTE_SENT)
  })

  it('n\'utilise aucun <select> d\'étape (StatusPill uniquement)', () => {
    const { container } = render(<StageControl state={makeState()} onChangeStage={vi.fn()} onSigne={vi.fn()} />)
    expect(container.querySelector('select')).toBeNull()
  })
})
