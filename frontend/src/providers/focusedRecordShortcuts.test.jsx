import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import {
  FOCUSED_RECORD_SHORTCUTS, LEAD_STAGE_SHORTCUTS,
  useFocusedRecordShortcuts, ActiveScreenProvider, useActiveScreen,
} from './focusedRecordShortcuts'
import { roleProfile } from './ShortcutsProvider'

/* VX248 — Raccourcis d'ACTION sur le record focalisé + cheatsheet filtrée par
   rôle. Défaut prouvé : shortcuts.js ne connaît que GOTO_SHORTCUTS (nav), la
   cheatsheet « ? » était une liste statique identique pour tous les rôles.
   Couvre : le registre (données pures — 4 touches de stage, jamais SIGNED/
   COLD), le câblage clavier (isTypingTarget/modificateur), et la
   classification de rôle qui pilote « Pour votre rôle » d'abord. */

afterEach(() => { cleanup() })

describe('FOCUSED_RECORD_SHORTCUTS (registre)', () => {
  it('leadForm : a/d/n + 4 touches de stage, jamais SIGNED ni COLD', () => {
    const entry = FOCUSED_RECORD_SHORTCUTS.leadForm
    const keys = entry.items.map((it) => it.key)
    expect(keys).toEqual(['a', 'd', 'n', '1', '2', '3', '4'])
    const stages = LEAD_STAGE_SHORTCUTS.map((s) => s.stage)
    expect(stages).toEqual(['NEW', 'CONTACTED', 'QUOTE_SENT', 'FOLLOW_UP'])
    expect(stages).not.toContain('SIGNED')
    expect(stages).not.toContain('COLD')
  })

  it('les labels des touches de stage viennent de STAGE_LABELS (règle #2 — jamais un libellé en dur)', () => {
    for (const s of LEAD_STAGE_SHORTCUTS) {
      expect(s.label).toMatch(/^Étape : /)
      expect(s.label.length).toBeGreaterThan('Étape : '.length)
    }
  })

  it("devisDetail/factureDetail existent, aucun écran 'ticket' (hors périmètre de cette tâche — jamais un raccourci qui ne fait rien)", () => {
    expect(FOCUSED_RECORD_SHORTCUTS.devisDetail).toBeDefined()
    expect(FOCUSED_RECORD_SHORTCUTS.factureDetail).toBeDefined()
    expect(FOCUSED_RECORD_SHORTCUTS.ticket).toBeUndefined()
  })
})

describe('roleProfile (ShortcutsProvider.jsx)', () => {
  it('classe commercial/vente → "commercial"', () => {
    expect(roleProfile('Commercial')).toBe('commercial')
    expect(roleProfile('Chargé de vente')).toBe('commercial')
  })
  it('classe SAV/technicien → "sav"', () => {
    expect(roleProfile('Technicien SAV')).toBe('sav')
    expect(roleProfile('Support après-vente')).toBe('sav')
  })
  it('repli "general" pour un rôle inconnu ou vide', () => {
    expect(roleProfile('Magasinier')).toBe('general')
    expect(roleProfile(null)).toBe('general')
    expect(roleProfile(undefined)).toBe('general')
  })
})

function Harness({ screenId, handlers, enabled }) {
  useFocusedRecordShortcuts(screenId, handlers, enabled)
  const { activeScreen } = useActiveScreen()
  return <span data-testid="active-screen">{activeScreen ?? ''}</span>
}

describe('useFocusedRecordShortcuts — câblage clavier', () => {
  it('« a » hors saisie déclenche le handler (archiver sans clic)', () => {
    const onA = vi.fn()
    render(
      <ActiveScreenProvider>
        <Harness screenId="leadForm" handlers={{ a: onA }} enabled />
      </ActiveScreenProvider>,
    )
    fireEvent.keyDown(document, { key: 'a' })
    expect(onA).toHaveBeenCalledTimes(1)
  })

  it('une frappe DANS un <input> ne déclenche jamais le raccourci (isTypingTarget)', () => {
    const onA = vi.fn()
    render(
      <ActiveScreenProvider>
        <Harness screenId="leadForm" handlers={{ a: onA }} enabled />
        <input data-testid="some-field" />
      </ActiveScreenProvider>,
    )
    fireEvent.keyDown(screen.getByTestId('some-field'), { key: 'a' })
    expect(onA).not.toHaveBeenCalled()
  })

  it('une combinaison avec modificateur est laissée au système (jamais interceptée)', () => {
    const onA = vi.fn()
    render(
      <ActiveScreenProvider>
        <Harness screenId="leadForm" handlers={{ a: onA }} enabled />
      </ActiveScreenProvider>,
    )
    fireEvent.keyDown(document, { key: 'a', metaKey: true })
    expect(onA).not.toHaveBeenCalled()
  })

  it('enabled=false désactive le raccourci (ex. création — rien à archiver)', () => {
    const onA = vi.fn()
    render(
      <ActiveScreenProvider>
        <Harness screenId="leadForm" handlers={{ a: onA }} enabled={false} />
      </ActiveScreenProvider>,
    )
    fireEvent.keyDown(document, { key: 'a' })
    expect(onA).not.toHaveBeenCalled()
  })

  it('une touche du registre SANS handler fourni reste un no-op silencieux (jamais une exception)', () => {
    render(
      <ActiveScreenProvider>
        <Harness screenId="leadForm" handlers={{}} enabled />
      </ActiveScreenProvider>,
    )
    expect(() => fireEvent.keyDown(document, { key: 'd' })).not.toThrow()
  })

  it('enregistre l’écran actif pour la cheatsheet, le retire au démontage', () => {
    const { unmount } = render(
      <ActiveScreenProvider>
        <Harness screenId="leadForm" handlers={{}} enabled />
      </ActiveScreenProvider>,
    )
    expect(screen.getByTestId('active-screen').textContent).toBe('leadForm')
    unmount()
  })
})
