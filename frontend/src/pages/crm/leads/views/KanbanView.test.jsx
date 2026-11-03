import { describe, it, expect, afterEach } from 'vitest'
import { render, cleanup } from '@testing-library/react'
import LeadCard from './LeadCard'
import { PIPELINE_STAGES, NEW_STAGE } from '../../../../features/crm/stages'

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

describe('LeadCard — Devis auto (ALEA63)', () => {
  it('désactivé quand catalogue_ci.pret est faux, motif nommé', () => {
    const { container } = monter(lead({ devis_auto: {
      pret: true, catalogue_ci: { pret: false, manquants: ['a', 'b', 'c'] } } }))
    const bouton = container.querySelector('button.kb-flash')
    expect(bouton).toBeDisabled()
    expect(bouton.getAttribute('title')).toContain('3 postes sans prix')
  })

  it('actif quand le catalogue est prêt ou non servi', () => {
    const { container } = monter(lead({ devis_auto: { pret: true, catalogue_ci: { pret: true, manquants: [] } } }))
    expect(container.querySelector('button.kb-flash')).not.toBeDisabled()
  })
})
