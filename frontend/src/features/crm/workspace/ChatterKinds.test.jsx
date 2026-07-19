import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import ChatterTimeline from '../../../components/ChatterTimeline'

/* LW37 — sémantiques MIGRÉES de LeadFormChatterActivities.test.mjs,
   LeadFormUnifiedTimeline.test.mjs et LeadFormNTMKT11ChatterMarketing.test.jsx.
   Le rendu des GENRES de chatter (OUTCOME_LABELS appel/e-mail, cycle de vie
   devis, touche marketing + lien cliquable, pièce jointe de note VX111) vit
   désormais dans `components/ChatterTimeline` — la seule source de rendu du
   chatter, exercée par l'onglet Historique du workspace (TimelineTab). Les
   anciens tests grattaient la SOURCE de LeadForm.jsx (disparue en LW13) ; on
   teste ici le RENDU réel, plus robuste. */

const base = { user_nom: 'Karim', created_at: '2026-07-19T10:00:00Z' }

afterEach(cleanup)

describe('LW37 — genres de chatter (ChatterTimeline)', () => {
  it('appel journalisé : 📞 + libellé de résultat (OUTCOME_LABELS) + corps', () => {
    render(<ChatterTimeline entries={[{ ...base, id: 1, kind: 'appel', outcome: 'joint', body: 'RAS visite prévue' }]} />)
    const item = document.querySelector('.chatter-appel')
    expect(item.textContent).toContain('📞')
    expect(item.textContent).toContain('Joint') // OUTCOME_LABELS.joint
    expect(item.textContent).toContain('RAS visite prévue')
  })

  it('e-mail journalisé : ✉️ + libellé de résultat + corps', () => {
    render(<ChatterTimeline entries={[{ ...base, id: 2, kind: 'email', outcome: 'interesse', body: 'devis demandé' }]} />)
    const item = document.querySelector('.chatter-email')
    expect(item.textContent).toContain('✉️')
    expect(item.textContent).toContain('Intéressé') // OUTCOME_LABELS.interesse
    expect(item.textContent).toContain('devis demandé')
  })

  it('cycle de vie devis : les 5 genres portent 5 icônes distinctes', () => {
    const kinds = ['devis_sent', 'devis_opened', 'devis_signed', 'devis_refused', 'devis_engagement']
    render(<ChatterTimeline entries={kinds.map((k, i) => ({ ...base, id: 10 + i, kind: k }))} />)
    const icons = ['📤', '👁️', '✅', '❌', '📊']
    const txt = document.querySelector('.chatter-timeline').textContent
    icons.forEach((ic) => expect(txt).toContain(ic))
    expect(new Set(icons).size).toBe(5)
  })

  it('note manuelle : 📝 + corps', () => {
    render(<ChatterTimeline entries={[{ ...base, id: 3, kind: 'note', body: 'appelé, absent' }]} />)
    const item = document.querySelector('.chatter-note')
    expect(item.textContent).toContain('📝')
    expect(item.textContent).toContain('appelé, absent')
  })

  it('VX111 — une note avec pièce jointe rend le lien via le proxy Django (attachment_url)', () => {
    render(<ChatterTimeline entries={[{
      ...base, id: 6, kind: 'note', body: 'photo toiture',
      attachment_url: '/media/leads/1/toit.png', attachment_filename: 'toit.png',
    }]}
    />)
    const link = screen.getByRole('link', { name: /toit\.png/ })
    expect(link).toHaveAttribute('href', '/media/leads/1/toit.png')
  })
})

describe('LW37 — NTMKT11 : touches marketing (campagne/séquence)', () => {
  it('une touche marketing reconnue est taguée + lien cliquable quand résolue', () => {
    render(
      <ChatterTimeline
        entries={[{ ...base, id: 4, kind: 'note', body: 'Campagne « Réveil été » envoyée' }]}
        resolveMarketingLink={(type, nom) => (
          type === 'campagne' && nom === 'Réveil été' ? '/marketing/campagnes/7' : null
        )}
      />,
    )
    expect(document.querySelector('.chatter-item-marketing')).toBeTruthy()
    const link = screen.getByRole('link', { name: /Voir la campagne/ })
    expect(link).toHaveAttribute('href', '/marketing/campagnes/7')
  })

  it('touche marketing NON résolue : reste taguée mais sans lien (jamais de lien inventé)', () => {
    render(
      <ChatterTimeline
        entries={[{ ...base, id: 5, kind: 'note', body: 'Séquence « Ambiguë » cliquée' }]}
        resolveMarketingLink={() => null}
      />,
    )
    expect(document.querySelector('.chatter-item-marketing')).toBeTruthy()
    expect(screen.queryByRole('link', { name: /Voir la séquence/ })).toBeNull()
  })
})
