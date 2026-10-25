import { describe, it, expect, vi, afterEach, beforeEach, beforeAll } from 'vitest'
import { renderHook, act, render, screen, fireEvent, cleanup } from '@testing-library/react'
import { useCallEndedNudge } from './CallLogPopover'
import LeadCard from '../../pages/crm/leads/views/LeadCard'
import ListView from '../../pages/crm/leads/views/ListView'
import { polyfillResizeObserver } from '../../test/selectNatif'
import { renderAvecAuth } from '../../test/renderAvecAuth'

// VX87/EZ2 — seul le réseau est simulé : le hook, la carte, la liste et le
// popover de journal sont les VRAIS composants.
vi.mock('../../api/crmApi', () => ({
  default: {
    logInteraction: vi.fn(() => Promise.resolve({ data: {} })),
    updateLead: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))
vi.mock('../../lib/toast', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toastSuccess: vi.fn(), toastError: vi.fn() }
})
import crmApi from '../../api/crmApi'

beforeAll(polyfillResizeObserver)

/* EZ2 — Le nudge « noter l'appel » marche AUSSI au bureau.
   ---------------------------------------------------------------------------
   État vérifié : le nudge ne dépendait que de `visibilitychange`. Exact sur
   téléphone (l'OS bascule sur l'app Téléphone puis revient) ; sur POSTE FIXE
   un tap `tel:` ne masque rien — l'événement ne part jamais, le nudge
   n'apparaît JAMAIS, et noter l'appel repasse par la fiche (7 clics).

   Trois déclencheurs, LE PREMIER GAGNE. Ces tests couvrent les DEUX chemins
   demandés (temporisation + retour de focus) et prouvent qu'ils ne se
   déclenchent jamais deux fois. */

const visible = (etat) => {
  Object.defineProperty(document, 'visibilityState', { value: etat, configurable: true })
  document.dispatchEvent(new Event('visibilitychange'))
}

beforeEach(() => { vi.useFakeTimers() })
afterEach(() => { cleanup(); vi.useRealTimers(); vi.clearAllMocks() })

describe('useCallEndedNudge (EZ2)', () => {
  it('ne propose RIEN tant qu’aucun appel n’a été armé', () => {
    const { result } = renderHook(() => useCallEndedNudge({ delayMs: 100 }))
    act(() => { vi.advanceTimersByTime(10_000) })
    act(() => { window.dispatchEvent(new Event('focus')) })
    expect(result.current.nudgeVisible).toBe(false)
  })

  it('BUREAU — la temporisation déclenche le nudge sans aucun changement d’onglet', () => {
    const { result } = renderHook(() => useCallEndedNudge({ delayMs: 45_000 }))
    act(() => { result.current.armCallNudge() })
    expect(result.current.nudgeVisible).toBe(false)
    act(() => { vi.advanceTimersByTime(45_000) })
    expect(result.current.nudgeVisible).toBe(true)
  })

  it('BUREAU — le retour de FOCUS fenêtre déclenche le nudge (softphone)', () => {
    const { result } = renderHook(() => useCallEndedNudge({ delayMs: 45_000 }))
    act(() => { result.current.armCallNudge() })
    act(() => { window.dispatchEvent(new Event('focus')) })
    expect(result.current.nudgeVisible).toBe(true)
  })

  it('MOBILE — le retour d’onglet reste le déclencheur d’origine (inchangé)', () => {
    const { result } = renderHook(() => useCallEndedNudge({ delayMs: 45_000 }))
    act(() => { result.current.armCallNudge() })
    act(() => { visible('visible') })
    expect(result.current.nudgeVisible).toBe(true)
  })

  it('LE PREMIER GAGNE — un focus précoce désarme la temporisation (jamais deux nudges)', () => {
    const { result } = renderHook(() => useCallEndedNudge({ delayMs: 45_000 }))
    act(() => { result.current.armCallNudge() })
    act(() => { window.dispatchEvent(new Event('focus')) })
    expect(result.current.nudgeVisible).toBe(true)

    // Le nudge est écarté ; la temporisation d'origine ne doit PAS le rouvrir.
    act(() => { result.current.dismissNudge() })
    expect(result.current.nudgeVisible).toBe(false)
    act(() => { vi.advanceTimersByTime(60_000) })
    expect(result.current.nudgeVisible).toBe(false)
  })

  it('écarter le nudge désarme tout (aucun réveil fantôme)', () => {
    const { result } = renderHook(() => useCallEndedNudge({ delayMs: 1_000 }))
    act(() => { result.current.armCallNudge() })
    act(() => { result.current.dismissNudge() })
    act(() => { vi.advanceTimersByTime(5_000) })
    act(() => { window.dispatchEvent(new Event('focus')) })
    expect(result.current.nudgeVisible).toBe(false)
  })

  it('ré-armer repart d’un délai neuf (un 2e appel ne récupère pas le 1er timer)', () => {
    const { result } = renderHook(() => useCallEndedNudge({ delayMs: 10_000 }))
    act(() => { result.current.armCallNudge() })
    act(() => { vi.advanceTimersByTime(9_000) })
    act(() => { result.current.armCallNudge() })   // 2e appel
    act(() => { vi.advanceTimersByTime(9_000) })   // 18 s depuis le 1er
    expect(result.current.nudgeVisible).toBe(false)
    act(() => { vi.advanceTimersByTime(1_000) })   // 10 s depuis le 2e
    expect(result.current.nudgeVisible).toBe(true)
  })

  it('un onglet resté en fond des heures ne surprend pas au retour (fenêtre 10 min)', () => {
    const { result } = renderHook(() => useCallEndedNudge({ delayMs: 60 * 60 * 1000 }))
    act(() => { result.current.armCallNudge() })
    act(() => { vi.advanceTimersByTime(20 * 60 * 1000) })
    act(() => { visible('visible') })
    expect(result.current.nudgeVisible).toBe(false)
  })

  it('sans réglage, le délai par défaut est de 45 s (les appelants n’ont rien à passer)', () => {
    const { result } = renderHook(() => useCallEndedNudge())
    act(() => { result.current.armCallNudge() })
    act(() => { vi.advanceTimersByTime(44_999) })
    expect(result.current.nudgeVisible).toBe(false)
    act(() => { vi.advanceTimersByTime(1) })
    expect(result.current.nudgeVisible).toBe(true)
  })

  it('le démontage retire CHAQUE écouteur posé (focus fenêtre, visibilitychange)', () => {
    const espions = {
      ajoutFenetre: vi.spyOn(window, 'addEventListener'),
      retraitFenetre: vi.spyOn(window, 'removeEventListener'),
      ajoutDocument: vi.spyOn(document, 'addEventListener'),
      retraitDocument: vi.spyOn(document, 'removeEventListener'),
    }
    const { unmount } = renderHook(() => useCallEndedNudge())
    unmount()
    const pose = (ajout, type) => ajout.mock.calls.find(([t]) => t === type)
    const posesFocus = pose(espions.ajoutFenetre, 'focus')
    const posesVisibilite = pose(espions.ajoutDocument, 'visibilitychange')
    expect(posesFocus).toBeTruthy()
    expect(posesVisibilite).toBeTruthy()
    // Le MÊME gestionnaire est retiré : plus aucun réveil possible après coup.
    expect(espions.retraitFenetre.mock.calls.some(([t, fn]) => t === 'focus' && fn === posesFocus[1])).toBe(true)
    expect(espions.retraitDocument.mock.calls.some(([t, fn]) => t === 'visibilitychange' && fn === posesVisibilite[1])).toBe(true)
    Object.values(espions).forEach((espion) => espion.mockRestore())
  })

  it('le délai est INJECTABLE (la gate e2e peut l’avancer)', () => {
    const { result } = renderHook(() => useCallEndedNudge({ delayMs: 50 }))
    act(() => { result.current.armCallNudge() })
    act(() => { vi.advanceTimersByTime(50) })
    expect(result.current.nudgeVisible).toBe(true)
  })

  it('le démontage ne laisse aucun timer réveiller un composant mort', () => {
    const { result, unmount } = renderHook(() => useCallEndedNudge({ delayMs: 1_000 }))
    act(() => { result.current.armCallNudge() })
    unmount()
    // Aucune erreur « update on unmounted component » ne doit survenir.
    expect(() => { vi.advanceTimersByTime(5_000) }).not.toThrow()
  })
})

/* VX87/EZ2 — le câblage : tout lien `tel:` rendu par la carte ou la liste ARME
   le nudge (« aucun lien tel: sans armement »), et la relance déjà posée du lead
   est TRANSMISE au popover de journal (EZ1). Composants réels, retour de focus
   simulé ; la navigation `tel:` de jsdom est neutralisée. */
const LEAD = {
  id: 5, nom: 'Benali', prenom: 'Aziz', stage: 'NEW', is_archived: false,
  telephone: '0612345678', relance_date: '2026-08-20',
  date_creation: '2026-09-01T10:00:00Z', score: 10, devis: [], tags: [],
}

const bloquerNavigationTel = (e) => {
  if (e.target.closest?.('a[href^="tel:"]')) e.preventDefault()
}
beforeEach(() => { document.addEventListener('click', bloquerNavigationTel, true) })
afterEach(() => { document.removeEventListener('click', bloquerNavigationTel, true) })

const retourDeFocus = () => { act(() => { window.dispatchEvent(new Event('focus')) }) }

// ListView n'a besoin que d'un store (useDispatch), d'un routeur et du thème.
const rendreListe = (leads) => renderAvecAuth(
  <ListView leads={leads} onRefetch={vi.fn()} />,
  { role: 'admin', permissions: [], user: { id: 1 } },
  { theme: true },
)

describe('VX87/EZ2 — LeadCard arme le nudge sur CHAQUE lien tel:', () => {
  it('cliquer un lien tel: puis revenir sur la fenêtre propose « Appel terminé »', () => {
    render(<LeadCard lead={LEAD} />)
    const liens = [...document.querySelectorAll('a[href^="tel:"]')]
    expect(liens.length).toBeGreaterThanOrEqual(1)
    for (const lien of liens) {
      expect(screen.queryByRole('status')).not.toBeInTheDocument()
      fireEvent.click(lien)
      retourDeFocus()
      expect(screen.getByRole('status')).toHaveTextContent('Appel terminé — noter le résultat ?')
      fireEvent.click(screen.getByRole('button', { name: 'Ignorer' }))
      expect(screen.queryByRole('status')).not.toBeInTheDocument()
    }
  })

  it('sans clic sur tel:, un retour de focus ne propose rien', () => {
    render(<LeadCard lead={LEAD} />)
    retourDeFocus()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('le délai par défaut (45 s) suffit au bureau : aucun changement d’onglet nécessaire', () => {
    render(<LeadCard lead={LEAD} />)
    fireEvent.click(document.querySelector('a[href^="tel:"]'))
    act(() => { vi.advanceTimersByTime(44_000) })
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    act(() => { vi.advanceTimersByTime(1_000) })
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('EZ1 — la relance déjà posée du lead est transmise au popover : elle est affichée, pas écrasée', () => {
    render(<LeadCard lead={LEAD} />)
    fireEvent.click(document.querySelector('a[href^="tel:"]'))
    retourDeFocus()
    fireEvent.click(screen.getByRole('button', { name: 'Noter' }))
    fireEvent.click(screen.getByText('Demain'))
    expect(screen.getByRole('group', { name: 'Relance déjà planifiée' }))
      .toHaveTextContent(new Date(2026, 7, 20).toLocaleDateString('fr-FR'))
  })

  it('« Noter » journalise l’appel du bon lead puis le nudge disparaît', async () => {
    render(<LeadCard lead={LEAD} />)
    fireEvent.click(document.querySelector('a[href^="tel:"]'))
    retourDeFocus()
    fireEvent.click(screen.getByRole('button', { name: 'Noter' }))
    fireEvent.click(screen.getByText('Joint'))
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Enregistrer' })) })
    expect(crmApi.logInteraction).toHaveBeenCalledWith(5, expect.objectContaining({ outcome: 'joint' }))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})

describe('VX87/EZ2 — ListView arme le nudge sur les DEUX liens tel: d’un lead', () => {
  it('icône compacte (cellule Lead) ET colonne Téléphone arment chacune le nudge', () => {
    rendreListe([LEAD])
    const liens = [...document.querySelectorAll('a[href^="tel:"]')]
    expect(liens.length).toBeGreaterThanOrEqual(2)
    for (const lien of liens) {
      expect(screen.queryByRole('status')).not.toBeInTheDocument()
      fireEvent.click(lien)
      retourDeFocus()
      expect(screen.getByRole('status')).toHaveTextContent('Appel terminé avec Benali Aziz — noter le résultat ?')
      fireEvent.click(screen.getByRole('button', { name: 'Ignorer' }))
    }
  })

  it('le clic tel: de la colonne Téléphone arme le nudge sur CE lead (le délai par défaut suffit)', () => {
    rendreListe([LEAD, { ...LEAD, id: 6, nom: 'Idrissi', prenom: 'Sara', telephone: '0698765432' }])
    fireEvent.click(screen.getByRole('link', { name: '0698765432' }))
    act(() => { vi.advanceTimersByTime(45_000) })
    expect(screen.getByRole('status')).toHaveTextContent('Appel terminé avec Idrissi Sara')
  })

  it('EZ1 — la relance déjà posée du lead appelé est transmise au popover', () => {
    rendreListe([LEAD])
    fireEvent.click(screen.getByRole('link', { name: '0612345678' }))
    retourDeFocus()
    fireEvent.click(screen.getByRole('button', { name: 'Noter' }))
    fireEvent.click(screen.getByText('Demain'))
    expect(screen.getByRole('group', { name: 'Relance déjà planifiée' }))
      .toHaveTextContent(new Date(2026, 7, 20).toLocaleDateString('fr-FR'))
  })
})
