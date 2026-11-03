import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, cleanup, screen, fireEvent, waitFor } from '@testing-library/react'
import LeadCard from './LeadCard'
import KanbanView from './KanbanView'
import { PIPELINE_STAGES, NEW_STAGE, COLD_STAGE } from '../../../../features/crm/stages'
import { refusEtape } from '../../../../features/crm/raisonsFroid'

// ERR-ACVI9-KANBAN-FROID — le vrai DndContext, dont on capte `onDragEnd` : un
// glisser au pointeur n'est pas jouable dans jsdom.
const dnd = vi.hoisted(() => ({ onDragEnd: null }))
vi.mock('@dnd-kit/core', async (original) => {
  const reel = await original()
  return {
    ...reel,
    DndContext: (props) => {
      dnd.onDragEnd = props.onDragEnd
      return <reel.DndContext {...props} />
    },
  }
})

describe('KanbanView · StageMover — SUPPRIMÉ (ordre fondateur 2026-08-02)', () => {
  // « Ne la cache pas, supprime-la complètement. » Le sélecteur d'étape par
  // carte (J140/L151/LB3/LB4) n'existe plus — ni exporté, ni rendu, ni stylé.
  // Chemins restants : glisser-déposer (garde LB4 + recul confirmé round 4)
  // et la pilule d'étape de la fenêtre du lead.
  // La moitié SOURCE du contrat (aucune balise <StageMover>, aucun export,
  // aucun câblage inlineSaveAvecUndo, aucune classe kb-stage-mover) vit dans
  // RenderCap.apx9.test.mjs — un test node:test peut lire le source, pas un
  // test vitest (URL de transformeur non-file).
  it("n'est plus exporté par le module", async () => {
    const mod = await import('./KanbanView')
    expect(mod.StageMover).toBeUndefined()
    // Le module garde ses exports légitimes.
    // AANA67 — la table locale de probabilités n'existe plus (table SERVIE).
    expect(mod.STAGE_PROBABILITY).toBeUndefined()
    expect(mod.default).toBeTypeOf('function')
  })
})

// ENF15 — montage réel de LeadCard (remplace les lectures de source
// LeadCardRotting/VX45Emojis/FirstTouchTimer/TouchPII, partie DOM).
afterEach(() => { cleanup() })

const QUOTE_SENT = PIPELINE_STAGES.find((s) => s === 'QUOTE_SENT')
const lead = (over = {}) => ({
  id: 1, nom: 'Test', stage: QUOTE_SENT, stage_since_days: 3, devis: [], ...over,
})
const monter = (l) => render(<LeadCard lead={l} users={[]} />)

describe('LeadCard — data-rot posé sur article.kb-card (LB14)', () => {
  const rotDe = (l) => monter(l).container.querySelector('article.kb-card').getAttribute('data-rot')

  it('QUOTE_SENT à 16 j = danger, 9 j = warning, 3 j = ok', () => {
    expect(rotDe(lead({ stage_since_days: 16 }))).toBe('danger')
    cleanup()
    expect(rotDe(lead({ stage_since_days: 9 }))).toBe('warning')
    cleanup()
    expect(rotDe(lead({ stage_since_days: 3 }))).toBe('ok')
  })

  it("un lead perdu n'est JAMAIS teinté", () => {
    expect(rotDe(lead({ stage_since_days: 30, statut: 'perdu', perdu: true, motif_perte: 'prix' }))).toBe('ok')
  })
})

describe("LeadCard — icônes lucide Zap, pas d'emoji ⚡ (VX45)", () => {
  it('le bouton devis auto rend un <svg> et aucun emoji ⚡', () => {
    const { container } = monter(lead({ devis_auto: { pret: true } }))
    const bouton = container.querySelector('button.kb-flash')
    expect(bouton).not.toBeNull()
    expect(bouton.querySelector('svg')).not.toBeNull()
    expect(bouton.textContent).not.toContain('⚡')
  })

  it("aucun emoji ⚡ nulle part sur la carte (micro-icône « prêt à deviser » comprise)", () => {
    const { container } = monter(lead({ devis_auto: { pret: true } }))
    const icone = container.querySelector('.kb-readi-devis')
    if (icone) expect(icone.querySelector('svg')).not.toBeNull()
    expect(container.textContent).not.toContain('⚡')
  })
})

describe('LeadCard — minuteur premier contact, colonne NEW seulement (QX31)', () => {
  const ilYa = (minutes) => new Date(Date.now() - minutes * 60000 - 5000).toISOString()
  const slaDe = (over, props = { slaHours: 24 }) => render(
    <LeadCard lead={lead({ stage: NEW_STAGE, ...over })} users={[]} {...props} />,
  ).container.querySelector('.kb-sla')

  it('libellé FR compact : min, h, j', () => {
    expect(slaDe({ date_creation: ilYa(12) }).textContent).toContain('À contacter — il y a 12 min, non contacté')
    cleanup()
    expect(slaDe({ date_creation: ilYa(180) }).textContent).toContain('il y a 3 h')
    cleanup()
    expect(slaDe({ date_creation: ilYa(60 * 24 * 2) }).textContent).toContain('il y a 2 j')
  })

  it('ACVI73 — ambre dans le délai servi, rouge quand sla-breach le retient', () => {
    expect(slaDe({ date_creation: ilYa(180) }).className).toContain('kb-actionline-warning')
    cleanup()
    expect(slaDe({ date_creation: ilYa(180) }, { slaHours: 24, slaEnRetard: true }).className)
      .toContain('kb-actionline-danger')
  })

  it('sla désactivé, aucun badge', () => {
    expect(slaDe({ date_creation: ilYa(120) }, { slaHours: 0 })).toBeNull()
  })

  it('premier contact posé, aucun badge', () => {
    expect(slaDe({ date_creation: ilYa(120), first_contacted_at: ilYa(60) })).toBeNull()
  })

  it("aucun minuteur hors de l'étape NEW", () => {
    const { container } = monter(lead({ stage: QUOTE_SENT, date_creation: ilYa(12) }))
    expect(container.querySelector('.kb-sla')).toBeNull()
  })
})

describe('Kanban — glisser vers Froid (ERR-ACVI9-KANBAN-FROID)', () => {
  const deposer = (l, cible) => dnd.onDragEnd({
    active: { data: { current: { lead: l } } }, over: { id: cible },
  })
  const monterBoard = (l, onChangeStage) => render(
    <KanbanView leads={[l]} users={[]} onChangeStage={onChangeStage} />,
  )

  it('demande la raison avant le PATCH, puis la transporte', async () => {
    const onChangeStage = vi.fn()
    const l = lead()
    monterBoard(l, onChangeStage)
    deposer(l, COLD_STAGE)
    const bouton = await screen.findByRole('button', { name: 'Mettre au Froid' })
    expect(bouton).toBeDisabled()
    expect(onChangeStage).not.toHaveBeenCalled()
    fireEvent.change(screen.getByLabelText('Raison de mise au Froid'), { target: { value: 'budget' } })
    fireEvent.click(bouton)
    await waitFor(() => expect(onChangeStage).toHaveBeenCalledWith(
      l, COLD_STAGE, expect.objectContaining({ parcRaison: 'budget' })))
  })

  it("annuler la question n'écrit rien", async () => {
    const onChangeStage = vi.fn()
    const l = lead()
    monterBoard(l, onChangeStage)
    deposer(l, COLD_STAGE)
    fireEvent.click(await screen.findByRole('button', { name: 'Annuler' }))
    await waitFor(() => expect(screen.queryByLabelText('Raison de mise au Froid')).toBeNull())
    expect(onChangeStage).not.toHaveBeenCalled()
  })

  it('une autre étape ne pose aucune question', async () => {
    const onChangeStage = vi.fn()
    const l = lead()
    monterBoard(l, onChangeStage)
    const cible = PIPELINE_STAGES[PIPELINE_STAGES.indexOf(QUOTE_SENT) + 1]
    await deposer(l, cible)
    expect(onChangeStage).toHaveBeenCalledWith(l, cible, { confirmeRecul: false, parcRaison: undefined })
    expect(screen.queryByLabelText('Raison de mise au Froid')).toBeNull()
  })

  it('le refus 409 est lu, quelle que soit sa forme', () => {
    expect(refusEtape({ parc_raison: ['Raison de mise au Froid obligatoire.'] }))
      .toBe('Raison de mise au Froid obligatoire.')
    expect(refusEtape({ detail: 'Refus.' })).toBe('Refus.')
    expect(refusEtape({ stage: ['On ne recule pas une étape.'] })).toBe('On ne recule pas une étape.')
    expect(refusEtape({})).toBe('')
  })
})

describe('LeadCard — état de parcage servi (ACVI74)', () => {
  it('la carte porte la date de reprise du standby, rien sans parcage', () => {
    const { container } = monter(lead({ parc_etat: 'standby', parc_raison: 'plus_tard_date', parc_jusqu_au: '2026-12-15' }))
    expect(container.textContent).toContain("En attente jusqu'au 15/12/2026")
    cleanup()
    expect(monter(lead({ parc_etat: null })).container.querySelector('[data-testid="badge-parcage"]')).toBeNull()
  })
})

describe('LeadCard — cible tactile et PII (LB17)', () => {
  it('la case de sélection est enveloppée du label .kb-check-hit, sans style inline', () => {
    const { container } = render(<LeadCard lead={lead()} users={[]} onToggleSelect={() => {}} />)
    const case_ = container.querySelector('label.kb-check-hit input.kb-card-check')
    expect(case_).not.toBeNull()
    expect(case_.getAttribute('style')).toBeNull()
  })

  it("PII masquée : cadenas tooltipé à la place des actions d'appel", () => {
    const { container } = monter(lead({ pii_masked: true, telephone: null, whatsapp: null }))
    const cadenas = container.querySelector('.kb-quick-lock')
    expect(cadenas.getAttribute('title')).toBe('Coordonnées masquées (permission PII)')
    expect(cadenas.querySelector('svg')).not.toBeNull()
  })

  it('PII non masquée : pas de cadenas', () => {
    const { container } = monter(lead({ pii_masked: false, telephone: '0600000000' }))
    expect(container.querySelector('.kb-quick-lock')).toBeNull()
  })
})
