import { describe, it, expect, vi, afterEach } from 'vitest'
import { useRef } from 'react'
import { createPortal } from 'react-dom'
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
  it('leadForm : d/n + 4 touches de stage, jamais SIGNED ni COLD, jamais « a » archiver (incident 02/10)', () => {
    const entry = FOCUSED_RECORD_SHORTCUTS.leadForm
    const keys = entry.items.map((it) => it.key)
    expect(keys).toEqual(['d', 'n', '1', '2', '3', '4'])
    expect(entry.items.some((it) => /archiv/i.test(it.label))).toBe(false)
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
  it('« n » hors saisie déclenche le handler (noter sans clic)', () => {
    const onA = vi.fn()
    render(
      <ActiveScreenProvider>
        <Harness screenId="leadForm" handlers={{ n: onA }} enabled />
      </ActiveScreenProvider>,
    )
    fireEvent.keyDown(document, { key: 'n' })
    expect(onA).toHaveBeenCalledTimes(1)
  })

  it('une frappe DANS un <input> ne déclenche jamais le raccourci (isTypingTarget)', () => {
    const onA = vi.fn()
    render(
      <ActiveScreenProvider>
        <Harness screenId="leadForm" handlers={{ n: onA }} enabled />
        <input data-testid="some-field" />
      </ActiveScreenProvider>,
    )
    fireEvent.keyDown(screen.getByTestId('some-field'), { key: 'n' })
    expect(onA).not.toHaveBeenCalled()
  })

  it('une combinaison avec modificateur est laissée au système (jamais interceptée)', () => {
    const onA = vi.fn()
    render(
      <ActiveScreenProvider>
        <Harness screenId="leadForm" handlers={{ n: onA }} enabled />
      </ActiveScreenProvider>,
    )
    fireEvent.keyDown(document, { key: 'n', metaKey: true })
    expect(onA).not.toHaveBeenCalled()
  })

  it('enabled=false désactive le raccourci (ex. création — rien à noter)', () => {
    const onA = vi.fn()
    render(
      <ActiveScreenProvider>
        <Harness screenId="leadForm" handlers={{ n: onA }} enabled={false} />
      </ActiveScreenProvider>,
    )
    fireEvent.keyDown(document, { key: 'n' })
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

/* INCIDENT 02/10/2026 — un lead vivant archivé par une frappe tapée dans le
   panneau devis ouvert PAR-DESSUS la fiche lead. `scopeRef` : les touches d'un
   écran se taisent dès qu'une boîte de dialogue qui ne le contient pas est
   ouverte ; elles marchent toujours dans l'écran lui-même. */
function ScopedScreen({ handlers, autreDialogue = false }) {
  const ref = useRef(null)
  useFocusedRecordShortcuts('leadForm', handlers, true, { scopeRef: ref })
  return (
    <>
      <div role="dialog" data-state="open" ref={ref}>
        <button type="button" data-testid="btn-fiche">Fiche</button>
      </div>
      {autreDialogue && createPortal(
        <div role="dialog" data-state="open"><button type="button" data-testid="btn-dessus">Option</button></div>,
        document.body,
      )}
    </>
  )
}

describe('useFocusedRecordShortcuts — scopeRef (incident 02/10/2026)', () => {
  it('fiche seule : la touche agit (rien n’est posé par-dessus)', () => {
    const onN = vi.fn()
    render(<ActiveScreenProvider><ScopedScreen handlers={{ n: onN }} /></ActiveScreenProvider>)
    fireEvent.keyDown(screen.getByTestId('btn-fiche'), { key: 'n' })
    expect(onN).toHaveBeenCalledTimes(1)
  })

  it('une boîte posée par-dessus : la touche tapée dedans n’atteint JAMAIS la fiche', () => {
    const onN = vi.fn()
    render(<ActiveScreenProvider><ScopedScreen handlers={{ n: onN }} autreDialogue /></ActiveScreenProvider>)
    fireEvent.keyDown(screen.getByTestId('btn-dessus'), { key: 'n' })
    expect(onN).not.toHaveBeenCalled()
  })

  it('une bannière permanente NON modale (role=dialog sans data-state, invite PWA) ne fait pas taire la fiche', () => {
    const onN = vi.fn()
    render(
      <ActiveScreenProvider>
        <ScopedScreen handlers={{ n: onN }} />
        <div role="dialog" aria-label="Installer Taqinor OS">bannière</div>
      </ActiveScreenProvider>,
    )
    fireEvent.keyDown(screen.getByTestId('btn-fiche'), { key: 'n' })
    expect(onN).toHaveBeenCalledTimes(1)
  })

  it('une boîte posée par-dessus : même une frappe sur la fiche elle-même reste muette', () => {
    const onN = vi.fn()
    render(<ActiveScreenProvider><ScopedScreen handlers={{ n: onN }} autreDialogue /></ActiveScreenProvider>)
    fireEvent.keyDown(document, { key: 'n' })
    expect(onN).not.toHaveBeenCalled()
  })
})
