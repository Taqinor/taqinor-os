import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, act } from '@testing-library/react'
import RaccourcisAtelier from '../RaccourcisAtelier'
import { RACCOURCIS, estSaisieEnCours } from '../RaccourcisAtelier.helpers'
import { lignesDePortee } from '@roofpro/raccourcisAtelier'

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

/** ACAL1027 — un `matchMedia` doublé : `tactile` dit si la requête « sans survol, pointeur grossier » est vraie. */
function doublerMatchMedia(tactile) {
  const ecouteurs = new Set()
  window.matchMedia = vi.fn((requete) => ({
    matches: requete === '(hover: none) and (pointer: coarse)' ? tactile.valeur : false,
    media: requete,
    addEventListener: (_nom, f) => ecouteurs.add(f),
    removeEventListener: (_nom, f) => ecouteurs.delete(f),
  }))
  return ecouteurs
}

describe('ACAL1027 — le lien « Raccourcis clavier (?) » sur un appareil sans clavier', () => {
  afterEach(() => { delete window.matchMedia })

  it('écran tactile principal : pas de bouton, mais « ? » ouvre toujours l’aide', () => {
    doublerMatchMedia({ valeur: true })
    rendre(actionsEspionnees())
    expect(screen.queryByTestId('cal-raccourcis-bouton')).toBeNull()
    fireEvent.keyDown(window, { key: '?' })
    expect(screen.getByTestId('cal-raccourcis-aide')).toBeInTheDocument()
  })

  it('souris, ou pas de matchMedia : le bouton est rendu comme avant', () => {
    doublerMatchMedia({ valeur: false })
    rendre(actionsEspionnees())
    expect(screen.getByTestId('cal-raccourcis-bouton')).toBeInTheDocument()
    cleanup()
    delete window.matchMedia
    rendre(actionsEspionnees())
    expect(screen.getByTestId('cal-raccourcis-bouton')).toBeInTheDocument()
  })

  it('suit un changement de mode (événement change de la requête)', () => {
    const tactile = { valeur: true }
    const ecouteurs = doublerMatchMedia(tactile)
    rendre(actionsEspionnees())
    expect(screen.queryByTestId('cal-raccourcis-bouton')).toBeNull()
    tactile.valeur = false
    act(() => { ecouteurs.forEach((f) => f()) })
    expect(screen.getByTestId('cal-raccourcis-bouton')).toBeInTheDocument()
  })
})

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

describe('AERR114 — une boîte ouverte par-dessus garde ses frappes', () => {
  it('« Suppr » sous une boîte ouverte : aucun geste', () => {
    const actions = actionsEspionnees()
    rendre(actions)
    const boite = document.createElement('div')
    boite.setAttribute('role', 'alertdialog')
    boite.setAttribute('data-state', 'open')
    document.body.appendChild(boite)
    fireEvent.keyDown(window, { key: 'Delete' })
    expect(actions.supprimer).not.toHaveBeenCalled()
    boite.remove()
    fireEvent.keyDown(window, { key: 'Delete' })
    expect(actions.supprimer).toHaveBeenCalledTimes(1)
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

describe('ACAL1435 — Guidé : l’aide s’ouvre hors du tiroir « Avancé » masqué', () => {
  it('« ? » dans un parent `hidden` : l’aide est une fenêtre (dialog) qui n’a aucun ancêtre masqué ; Échap la ferme', () => {
    render(<div hidden data-testid="tiroir"><RaccourcisAtelier actions={actionsEspionnees()} /></div>)
    fireEvent.keyDown(window, { key: '?' })
    const aide = screen.getByTestId('cal-raccourcis-aide')
    expect(aide).toHaveAttribute('role', 'dialog')
    expect(aide.closest('[hidden]')).toBeNull()
    expect(screen.getByTestId('tiroir')).not.toContainElement(aide)
    expect(aide).toHaveTextContent('Dupliquer')
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.queryByTestId('cal-raccourcis-aide')).toBeNull()
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
          genererDevis: vi.fn(), syncDevis: vi.fn(),
        },
        // CAL70 — PanneauAllees (monté par AtelierPanneaux) lit les réglages
        // société au montage.
        parametres: { get: vi.fn().mockResolvedValue({ data: { degagements: {} } }) },
        moteur: { calculer: vi.fn() },
      },
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

describe('ACAL414 — RACCOURCIS est lue dans la table unique', () => {
  it('une ligne de portée atelier = une entrée de l’aide, mêmes touches', () => {
    const lignes = lignesDePortee('atelier')
    expect(RACCOURCIS).toHaveLength(lignes.length)
    expect(RACCOURCIS.map((r) => r.affichage)).toEqual(lignes.map((l) => l.ecriture))
    expect(RACCOURCIS.map((r) => r.touche)).toEqual(['t', 'o', 'z', 'm', 'a', 'delete', 'd', 'c', 'v', 'f'])
    expect(RACCOURCIS.find((r) => r.action === 'dupliquer').ctrl).toBe(true)
  })
})

/* Acceptation ACAL490 — « ? » dans l'atelier ouvrait l'aide GLOBALE de l'ERP (écouteur
   `ShortcutsProvider` sur `window`, posé avant) et la fenêtre ne listait pas le tracé ni la
   disposition. */
describe('ACAL414 — « ? » ouvre l’aide de l’atelier, et elle liste tracé et disposition', () => {
  it('l’écouteur global (window, posé avant) ne reçoit pas « ? » ; la fenêtre de l’atelier s’ouvre', () => {
    const global = vi.fn()
    window.addEventListener('keydown', global)
    try {
      rendre(actionsEspionnees())
      fireEvent.keyDown(document.body, { key: '?' })
      expect(screen.getByTestId('cal-raccourcis-aide')).toBeInTheDocument()
      expect(global).not.toHaveBeenCalled()
      fireEvent.keyDown(document.body, { key: 'x' }) // les autres touches passent toujours
      expect(global).toHaveBeenCalledTimes(1)
    } finally {
      window.removeEventListener('keydown', global)
    }
  })

  it('la fenêtre liste les touches de l’atelier, du tracé et de la disposition (table unique)', () => {
    rendre(actionsEspionnees())
    fireEvent.keyDown(document.body, { key: '?' })
    const aide = screen.getByTestId('cal-raccourcis-aide')
    expect(aide).toHaveTextContent('Outil tracé de toit')
    for (const portee of ['trace', 'disposition']) {
      for (const l of lignesDePortee(portee).filter((x) => x.action !== 'aide')) {
        expect(screen.getByTestId(`cal-raccourcis-section-${portee}`)).toHaveTextContent(l.libelle)
      }
    }
    expect(aide).toHaveTextContent('Poser un sommet du contour')
    expect(aide).toHaveTextContent('Annuler la dernière modification de la disposition')
  })
})

describe('ACAL492 — la ligne « Dupliquer » nomme ce qu’elle duplique', () => {
  it('l’aide se lit « Dupliquer l’obstacle sélectionné » (Ctrl + D)', () => {
    const ligne = RACCOURCIS.find((r) => r.action === 'dupliquer')
    expect(ligne.libelle).toContain('obstacle')
    expect(ligne.libelle).not.toContain('la sélection')
  })
})
