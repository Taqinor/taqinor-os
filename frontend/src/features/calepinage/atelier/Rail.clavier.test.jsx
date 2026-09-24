import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

/* ============================================================================
   CALX392 — LE RAIL D'ONGLETS SE PILOTE ENTIÈREMENT AU CLAVIER.
   ----------------------------------------------------------------------------
   Patron ARIA des onglets (https://www.w3.org/WAI/ARIA/apg/patterns/tabs/) :
     * `role="tablist"` + `aria-orientation`, un `role="tab"` par onglet avec
       `aria-selected` et `aria-controls`, le panneau en `role="tabpanel"` avec
       `aria-labelledby` ;
     * UN SEUL onglet tabulable à la fois (tabindex mobile) ;
     * Flèches qui bouclent, Début/Fin ; Entrée ou Espace OUVRE l'onglet
       focalisé (activation manuelle) et le focus part sur le panneau.

   LE TEST LIT LE RAIL RENDU (`getAllByRole('tab')`), jamais une liste écrite
   ici : un onglet ajouté au registre `atelier/onglets.js` est couvert sans
   rouvrir ce fichier. Il OUVRE chaque onglet, d'un bout à l'autre du rail,
   uniquement au clavier.

   L'API du module est doublée par le même proxy permissif que
   `Rail.test.jsx` : ce fichier juge le CLAVIER, pas le contenu des panneaux.
   ========================================================================== */

vi.mock('../../../api/calepinageApi', () => {
  const reponse = () => Promise.resolve({ data: {} })
  const doublure = () => new Proxy(function appel() { return reponse() }, {
    // `then` DOIT rester absent : un proxy « thenable » serait attendu comme
    // une promesse par `await` et bloquerait le test.
    get: (_cible, prop) => (typeof prop === 'symbol' || prop === 'then'
      ? undefined
      : doublure()),
    apply: () => reponse(),
  })
  return { default: doublure() }
})
vi.mock('../../../api/ventesApi', () => ({ default: { reviserDevis: vi.fn() } }))

import Rail from './Rail'

const rendreRail = () => render(
  <MemoryRouter initialEntries={['/calepinage/7']}>
    <Routes>
      <Route path="/calepinage/:id" element={<Rail />} />
    </Routes>
  </MemoryRouter>,
)

const onglets = () => screen.getAllByRole('tab')

/** Le tabindex mobile : UN seul onglet tabulable, et c'est `attendu`. */
function seulTabulable(attendu) {
  const tabulables = onglets().filter((onglet) => onglet.tabIndex === 0)
  expect(tabulables, 'plus d’un onglet (ou aucun) sur le chemin de la touche Tab')
    .toEqual([attendu])
}

/** `attendu` est le SEUL onglet sélectionné du rail. */
function seulSelectionne(attendu) {
  const selectionnes = onglets()
    .filter((onglet) => onglet.getAttribute('aria-selected') === 'true')
  expect(selectionnes).toEqual(attendu ? [attendu] : [])
}

afterEach(() => { cleanup() })

describe('CALX392 — le rail d’onglets au clavier', () => {
  it('porte la sémantique ARIA des onglets, sans aucun panneau ouvert d’office', () => {
    rendreRail()
    const liste = screen.getByRole('tablist', { name: 'Onglets du calepinage' })
    expect(liste).toHaveAttribute('aria-orientation', 'horizontal')
    expect(onglets().length).toBeGreaterThan(0)
    for (const onglet of onglets()) {
      expect(onglet).toHaveAttribute('aria-selected', 'false')
      expect(onglet).toHaveAttribute('aria-controls')
    }
    expect(screen.queryByRole('tabpanel')).toBeNull()
    // Aucun data-testid historique n'a disparu.
    expect(screen.getByTestId('cal-rail-onglets')).toBeTruthy()
  })

  it('ouvre CHAQUE onglet au clavier, d’un bout à l’autre du rail', async () => {
    const utilisateur = userEvent.setup()
    rendreRail()
    const tous = onglets()

    // La touche Tab entre dans le rail sur le PREMIER onglet.
    await utilisateur.tab()
    expect(document.activeElement).toBe(tous[0])

    for (let rang = 0; rang < tous.length; rang += 1) {
      const onglet = onglets()[rang]
      expect(document.activeElement, `rang ${rang} : focus perdu`).toBe(onglet)
      seulTabulable(onglet)

      // Entrée (ou Espace, un rang sur deux) OUVRE l'onglet focalisé.
      await utilisateur.keyboard(rang % 2 === 0 ? '{Enter}' : ' ')
      await waitFor(() => expect(onglet).toHaveAttribute('aria-selected', 'true'))
      seulSelectionne(onglet)

      // Le focus part sur le panneau, relié à SON onglet.
      const panneau = screen.getByRole('tabpanel')
      await waitFor(() => expect(document.activeElement).toBe(panneau))
      expect(panneau).toHaveAttribute('aria-labelledby', onglet.id)
      expect(onglet).toHaveAttribute('aria-controls', panneau.id)

      // Maj+Tab ramène sur l'onglet ouvert — seul tabulable du rail.
      await utilisateur.tab({ shift: true })
      expect(document.activeElement).toBe(onglet)
      seulTabulable(onglet)

      if (rang < tous.length - 1) {
        // La flèche DÉPLACE le focus sans rien ouvrir (activation manuelle).
        await utilisateur.keyboard('{ArrowRight}')
        const suivant = onglets()[rang + 1]
        expect(document.activeElement).toBe(suivant)
        seulTabulable(suivant)
        seulSelectionne(onglet)
      }
    }

    // Au bout du rail, la flèche BOUCLE sur le premier onglet.
    await utilisateur.keyboard('{ArrowRight}')
    expect(document.activeElement).toBe(onglets()[0])
    seulTabulable(onglets()[0])
  }, 120_000)

  it('Début, Fin et la flèche gauche qui boucle', async () => {
    const utilisateur = userEvent.setup()
    rendreRail()
    const tous = onglets()
    await utilisateur.tab()
    expect(document.activeElement).toBe(tous[0])

    await utilisateur.keyboard('{End}')
    expect(document.activeElement).toBe(tous[tous.length - 1])
    seulTabulable(tous[tous.length - 1])

    await utilisateur.keyboard('{Home}')
    expect(document.activeElement).toBe(tous[0])
    seulTabulable(tous[0])

    await utilisateur.keyboard('{ArrowLeft}')
    expect(document.activeElement).toBe(tous[tous.length - 1])

    // Rien n'a été ouvert en parcourant le rail.
    seulSelectionne(null)
    expect(screen.queryByRole('tabpanel')).toBeNull()
  })
})
