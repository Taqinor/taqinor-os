// ENF15 — remplace deux tests « regex sur code source » (LeadCardRotting,
// LeadCardVX45Emojis) par un MONTAGE réel de la carte : on lit le DOM rendu.
import { describe, it, expect, afterEach } from 'vitest'
import { render, cleanup } from '@testing-library/react'
import LeadCard from './LeadCard'
import { PIPELINE_STAGES } from '../../../../features/crm/stages'

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
