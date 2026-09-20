import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* CAL40 — le bloc « calepinage de ce devis » : TROIS états de badge servis par
   le serveur (CAL28 `calepinage_du_devis`), et la discipline du null.

   Le badge n'est JAMAIS recalculé ici : `a_jour` est une comparaison des deux
   empreintes faite côté serveur. `null` veut dire INCONNU (une empreinte
   manque), pas « à rejouer » — afficher une alerte là-dessus serait inventé. */

vi.mock('../../api/ventesApi', () => ({
  default: { getDevisById: vi.fn() },
}))

import ventesApi from '../../api/ventesApi'
import BlocCalepinageDevis from './BlocCalepinageDevis'

const rendre = (devisId = 7) => render(
  <MemoryRouter><BlocCalepinageDevis devisId={devisId} /></MemoryRouter>,
)

const avecCalepinage = (calepinage) => {
  ventesApi.getDevisById.mockResolvedValue({ data: { id: 7, calepinage } })
}

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('BlocCalepinageDevis (CAL40)', () => {
  it('a_jour = true : badge « à jour » et lien vers /calepinage/<id>', async () => {
    avecCalepinage({
      id: 12, titre: 'Toiture — bâtiment principal',
      layout_hash: 'abab', a_jour: true,
    })

    rendre()

    expect(await screen.findByTestId('cal-badge-a-jour')).toHaveTextContent('à jour')
    expect(screen.getByText('Toiture — bâtiment principal')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ouvrir le calepinage' }))
      .toHaveAttribute('href', '/calepinage/12')
    expect(screen.queryByTestId('cal-badge-a-rejouer')).toBeNull()
  })

  it('a_jour = false : badge « à rejouer », valeur SERVEUR telle quelle', async () => {
    avecCalepinage({ id: 12, titre: 'Toiture', layout_hash: 'cdcd', a_jour: false })

    rendre()

    expect(await screen.findByTestId('cal-badge-a-rejouer'))
      .toHaveTextContent('à rejouer')
    expect(screen.queryByTestId('cal-badge-a-jour')).toBeNull()
  })

  it('a_jour = null (inconnu) : le bloc s’affiche SANS badge — aucune alerte inventée', async () => {
    avecCalepinage({ id: 12, titre: 'Toiture', layout_hash: null, a_jour: null })

    rendre()

    expect(await screen.findByTestId('cal-bloc-calepinage-devis')).toBeInTheDocument()
    expect(screen.queryByTestId('cal-badge-a-jour')).toBeNull()
    expect(screen.queryByTestId('cal-badge-a-rejouer')).toBeNull()
  })

  it('devis SANS calepinage : AUCUN bloc (pas un bloc vide)', async () => {
    avecCalepinage(null)

    rendre()

    await waitFor(() => expect(ventesApi.getDevisById).toHaveBeenCalledWith(7))
    expect(screen.queryByTestId('cal-bloc-calepinage-devis')).toBeNull()
  })

  it('clé absente du détail (serveur qui ne la publie pas) : aucun bloc, aucune erreur', async () => {
    ventesApi.getDevisById.mockResolvedValue({ data: { id: 7 } })

    rendre()

    await waitFor(() => expect(ventesApi.getDevisById).toHaveBeenCalled())
    expect(screen.queryByTestId('cal-bloc-calepinage-devis')).toBeNull()
  })

  it('lecture du détail en échec : aucun bloc, jamais un badge deviné', async () => {
    ventesApi.getDevisById.mockRejectedValue(new Error('réseau'))

    rendre()

    await waitFor(() => expect(ventesApi.getDevisById).toHaveBeenCalled())
    expect(screen.queryByTestId('cal-bloc-calepinage-devis')).toBeNull()
  })
})
