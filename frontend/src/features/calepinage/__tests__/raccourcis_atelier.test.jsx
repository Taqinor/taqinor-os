import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import RaccourcisAtelier, { RACCOURCIS, estSaisieEnCours } from '../RaccourcisAtelier'

/* ============================================================================
   CAL101 — CHAQUE RACCOURCI EST LISTÉ *ET* TESTÉ, ET AUCUN NE VOLE UNE FRAPPE.
   ----------------------------------------------------------------------------
   Le test PARCOURT la table `RACCOURCIS` : impossible d'ajouter un raccourci
   sans qu'il soit documenté dans l'aide, ni d'en documenter un qui ne fasse
   rien. La garde la plus importante — « aucun raccourci ne capture une frappe
   pendant la saisie d'un champ » — est exercée sur les quatre sortes de
   champs, pas seulement sur `<input>`.
   ========================================================================== */

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

/** Tous les gestionnaires, espionnés. */
function actionsEspionnees() {
  return Object.fromEntries(RACCOURCIS.map((r) => [r.action, vi.fn()]))
}

const rendre = (actions) => render(<RaccourcisAtelier actions={actions} />)

describe('CAL101 — l’aide-mémoire liste TOUS les raccourcis', () => {
  it('s’ouvre par « ? » et se referme par « ? »', () => {
    rendre(actionsEspionnees())
    expect(screen.queryByTestId('cal-raccourcis-aide')).toBeNull()
    fireEvent.keyDown(window, { key: '?' })
    expect(screen.getByTestId('cal-raccourcis-aide')).toBeInTheDocument()
    fireEvent.keyDown(window, { key: '?' })
    expect(screen.queryByTestId('cal-raccourcis-aide')).toBeNull()
  })

  it.each(RACCOURCIS)('documente « $libelle » ($affichage)', (raccourci) => {
    rendre(actionsEspionnees())
    fireEvent.keyDown(window, { key: '?' })
    const ligne = screen.getByTestId(`cal-raccourci-${raccourci.action}`)
    expect(ligne).toHaveTextContent(raccourci.affichage)
    expect(ligne).toHaveTextContent(raccourci.libelle)
  })

  it('documente aussi la touche qui ouvre l’aide elle-même', () => {
    rendre(actionsEspionnees())
    fireEvent.keyDown(window, { key: '?' })
    expect(screen.getByTestId('cal-raccourci-aide')).toBeInTheDocument()
  })

  it('l’aide est en français, du premier au dernier libellé', () => {
    for (const raccourci of RACCOURCIS) {
      expect(raccourci.libelle).not.toMatch(/[A-Za-z]+ (tool|mode|zone tool)$/)
      expect(raccourci.libelle.length).toBeGreaterThan(2)
    }
    rendre(actionsEspionnees())
    fireEvent.keyDown(window, { key: '?' })
    expect(screen.getByTestId('cal-raccourcis-aide'))
      .toHaveTextContent('inactifs pendant la saisie d’un champ')
  })
})

describe('CAL101 — chaque raccourci déclenche SON geste, et lui seul', () => {
  it.each(RACCOURCIS)('« $affichage » appelle $action', (raccourci) => {
    const actions = actionsEspionnees()
    rendre(actions)
    fireEvent.keyDown(window, {
      key: raccourci.touche, ctrlKey: Boolean(raccourci.ctrl),
    })
    expect(actions[raccourci.action]).toHaveBeenCalledTimes(1)
    for (const autre of RACCOURCIS) {
      if (autre.action === raccourci.action) continue
      expect(actions[autre.action], `${autre.action} a été déclenché à tort`)
        .not.toHaveBeenCalled()
    }
  })

  it('Ctrl + D et D nu sont DEUX frappes différentes', () => {
    const actions = actionsEspionnees()
    rendre(actions)
    fireEvent.keyDown(window, { key: 'd' })     // sans Ctrl : aucun raccourci
    expect(actions.dupliquer).not.toHaveBeenCalled()
    fireEvent.keyDown(window, { key: 'd', ctrlKey: true })
    expect(actions.dupliquer).toHaveBeenCalledTimes(1)
  })

  it('un raccourci sans gestionnaire ne mange pas la frappe', () => {
    rendre({})     // l'atelier n'offre aucun de ces outils
    const evenement = new KeyboardEvent('keydown', { key: 't', cancelable: true })
    window.dispatchEvent(evenement)
    expect(evenement.defaultPrevented).toBe(false)
  })
})

describe('CAL101 — AUCUNE frappe n’est volée pendant la saisie d’un champ', () => {
  it.each([
    ['input', () => document.createElement('input')],
    ['textarea', () => document.createElement('textarea')],
    ['select', () => document.createElement('select')],
    ['contenteditable', () => {
      const div = document.createElement('div')
      div.setAttribute('contenteditable', 'true')
      return div
    }],
  ])('une frappe dans un %s ne déclenche rien', (_nom, fabriquer) => {
    const actions = actionsEspionnees()
    rendre(actions)
    const champ = fabriquer()
    document.body.appendChild(champ)
    champ.focus()

    fireEvent.keyDown(champ, { key: 't' })
    fireEvent.keyDown(champ, { key: 'd', ctrlKey: true })
    fireEvent.keyDown(champ, { key: '?' })

    for (const raccourci of RACCOURCIS) {
      expect(actions[raccourci.action], `${raccourci.action} a volé la frappe`)
        .not.toHaveBeenCalled()
    }
    // Et l'aide ne s'ouvre pas non plus derrière le champ.
    expect(screen.queryByTestId('cal-raccourcis-aide')).toBeNull()
    champ.remove()
  })

  it('`estSaisieEnCours` reconnaît les champs, et laisse passer le reste', () => {
    const div = document.createElement('div')
    expect(estSaisieEnCours(div)).toBe(false)
    expect(estSaisieEnCours(null)).toBe(false)
    expect(estSaisieEnCours(document.createElement('input'))).toBe(true)
  })
})

describe('CAL101 — le bouton d’aide, pour qui ne connaît pas encore « ? »', () => {
  it('ouvre la même aide, et annonce son état', () => {
    rendre(actionsEspionnees())
    const bouton = screen.getByTestId('cal-raccourcis-bouton')
    expect(bouton).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(bouton)
    expect(bouton).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByTestId('cal-raccourcis-aide')).toBeInTheDocument()
  })

  it('Échap referme l’aide', () => {
    rendre(actionsEspionnees())
    fireEvent.keyDown(window, { key: '?' })
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.queryByTestId('cal-raccourcis-aide')).toBeNull()
  })
})

describe('CAL101 — le panneau de l’atelier le monte', () => {
  it('AtelierPanneaux affiche l’entrée des raccourcis', async () => {
    vi.resetModules()
    vi.doMock('../../../api/calepinageApi', () => ({
      default: {
        calepinages: {
          get: vi.fn().mockResolvedValue({ data: null }),
          genererDevis: vi.fn(), syncDevis: vi.fn(), importerContourAo: vi.fn(),
        },
        // CAL70 — PanneauAllees (monté par AtelierPanneaux) lit les réglages
        // société au montage.
        parametres: { get: vi.fn().mockResolvedValue({ data: { degagements: {} } }) },
        moteur: { calculer: vi.fn() },
      },
    }))
    vi.doMock('../../../api/aoApi', () => ({
      default: { toitures: { reprendreContour3d: vi.fn() } },
    }))
    vi.doMock('../../../api/ventesApi', () => ({ default: { reviserDevis: vi.fn() } }))
    const { MemoryRouter } = await import('react-router-dom')
    const { default: AtelierPanneaux } = await import('../AtelierPanneaux')

    render(
      <MemoryRouter>
        <AtelierPanneaux calepinageId={1} contexte={null} />
      </MemoryRouter>,
    )
    expect(await screen.findByTestId('cal-raccourcis-bouton')).toBeInTheDocument()
    vi.doUnmock('../../../api/calepinageApi')
  })
})
