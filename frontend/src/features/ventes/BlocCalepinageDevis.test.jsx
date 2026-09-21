import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

/* CAL40 / CALX46 — le bloc « calepinage de ce devis » : TROIS états de badge
   servis par le serveur (CAL28 `calepinage_du_devis`), et la discipline du null.

   Le badge n'est JAMAIS recalculé ici : `a_jour` est une comparaison des deux
   empreintes faite côté serveur. `null` veut dire INCONNU (une empreinte
   manque), pas « à rejouer » — afficher une alerte là-dessus serait inventé.

   PACT10/PACT13 (CALX45) — AUCUNE CHARGE UTILE RETAPÉE ICI. Les payloads
   viennent du document committé
   `backend/django_core/apps/calepinage/contract_samples/calepinage_du_devis.json`,
   le MÊME que le test backend `apps/ventes/tests/test_calx46_calepinage_du_devis.py`
   affirme. Un mock écrit à la main serait une DEUXIÈME source de vérité :
   c'est exactement ce qui a laissé passer l'écran « AO Tableau de bord » le
   03/08/2026 (test vert, écran mort). Si le serveur change de forme,
   l'exemple change et CE test casse tout seul. */

vi.mock('../../api/ventesApi', () => ({
  default: { getDevisById: vi.fn() },
}))

import ventesApi from '../../api/ventesApi'
import BlocCalepinageDevis from './BlocCalepinageDevis'

const APP = 'calepinage'
const NOM = 'calepinage_du_devis'

/** Le bloc `calepinage` d'un état du contrat committé. */
const bloc = (variante = 'exemple') => exempleContrat(APP, NOM, variante).calepinage

/** Le détail devis mocké, tel que le contrat le décrit pour cet état. */
const servirContrat = (variante = 'exemple') => {
  ventesApi.getDevisById.mockResolvedValue(reponseContrat(APP, NOM, variante))
}

const rendre = (devisId = 7) => render(
  <MemoryRouter><BlocCalepinageDevis devisId={devisId} /></MemoryRouter>,
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('BlocCalepinageDevis (CAL40 / CALX46)', () => {
  it('le contrat committé porte bien les quatre états lus ici', () => {
    expect(bloc('exemple').a_jour).toBe(true)
    expect(bloc('exemple_a_rejouer').a_jour).toBe(false)
    expect(bloc('exemple_inconnu').a_jour).toBeNull()
    expect(exempleContrat(APP, NOM, 'exemple_vide').calepinage).toBeNull()
  })

  it('a_jour = true : badge « à jour » et lien vers /calepinage/<id>', async () => {
    const attendu = bloc('exemple')
    servirContrat('exemple')

    rendre()

    expect(await screen.findByTestId('cal-badge-a-jour')).toHaveTextContent('à jour')
    expect(screen.getByText(attendu.titre)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ouvrir le calepinage' }))
      .toHaveAttribute('href', `/calepinage/${attendu.id}`)
    expect(screen.queryByTestId('cal-badge-a-rejouer')).toBeNull()
  })

  it('a_jour = false : badge « à rejouer », valeur SERVEUR telle quelle', async () => {
    servirContrat('exemple_a_rejouer')

    rendre()

    expect(await screen.findByTestId('cal-badge-a-rejouer'))
      .toHaveTextContent('à rejouer')
    expect(screen.queryByTestId('cal-badge-a-jour')).toBeNull()
  })

  it('a_jour = null (inconnu) : le bloc s’affiche SANS badge — aucune alerte inventée', async () => {
    servirContrat('exemple_inconnu')

    rendre()

    expect(await screen.findByTestId('cal-bloc-calepinage-devis')).toBeInTheDocument()
    expect(screen.queryByTestId('cal-badge-a-jour')).toBeNull()
    expect(screen.queryByTestId('cal-badge-a-rejouer')).toBeNull()
  })

  it('devis SANS calepinage : AUCUN bloc (pas un bloc vide)', async () => {
    servirContrat('exemple_vide')

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
