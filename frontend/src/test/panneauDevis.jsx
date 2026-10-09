import { act, render, screen } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'

import authReducer from '../features/auth/store/authSlice'
import ConfirmProvider from '../providers/ConfirmProvider'
import LeadDevisPanel from '../pages/crm/leads/LeadDevisPanel'
import { exempleContrat } from './fixtures/contractSamples'
import { generateur } from './mocksApiDevis.js'

/* EDC (gardes CI) — banc PARTAGÉ des tests du panneau devis du cockpit lead
   (`LeadDevisPanel`, générateur simulé).

   Les tests EDC6/EDC8/EDC11 recopiaient lead, devis envoyé, `rendre()`,
   `ouvrirEdition()` et le `beforeEach` : `scripts/check_duplicats_litteraux.py`
   (ACAL345) refuse tout bloc de ≥ 6 lignes significatives copié dans deux
   fichiers. Chaque test garde SES `vi.mock(...)` (hissés, chemins relatifs à
   lui) — leurs fabriques viennent de `./mocksApiDevis.js` (ventesApiPanneauMock,
   stockApiMock, generateurSimule), le seul module sans import d'API ni du panneau.
   Le porteur des props du générateur (`generateur`) s'importe de ce même module,
   pas d'ici : une ré-exportation arrivait `undefined` côté test sous Vitest. */

export const LEAD = { id: 77, nom: 'Khalid' }

/** Réponse de `getDevisById` pour l'exemple COMMITTÉ « envoyé » (PACT10). */
export const envoye = () => ({
  data: exempleContrat('ventes', 'devis_modifiabilite', 'exemple_envoye'),
})

/** Corps commun des `beforeEach` : remise à zéro + devis envoyé lisible. */
export function preparerApisPanneau({ ventesApi }) {
  vi.clearAllMocks()
  generateur.props = null
  ventesApi.getProposalPdf.mockImplementation(() => new Promise(() => {}))
  ventesApi.getDevisById.mockResolvedValue(envoye())
}

/** Panneau en édition du devis 413 avec le VRAI `ConfirmProvider`.
 *  `auth` monte un Magasinier dans le store (sinon un store sans `auth`). */
export function rendrePanneau(props = {}, { auth = false } = {}) {
  const onClose = vi.fn()
  const onDevisChanged = vi.fn()
  const store = auth
    ? configureStore({
      reducer: { auth: authReducer },
      preloadedState: {
        auth: {
          user: { id: 1 }, role: 'normal', role_nom: 'Magasinier', permissions: [],
          isAuthenticated: true, loading: false,
        },
      },
    })
    : configureStore({ reducer: { r: (s = {}) => s } })
  render(
    <Provider store={store}>
      <MemoryRouter>
        <ConfirmProvider>
          <LeadDevisPanel lead={LEAD} mode="edit" existingDevisId={413}
                          onClose={onClose} onDevisChanged={onDevisChanged} {...props} />
        </ConfirmProvider>
      </MemoryRouter>
    </Provider>,
  )
  return { onClose, onDevisChanged }
}

/** Ouvre l'éditeur ; `dirty` = ce que le générateur annonce via onDirtyChange. */
export async function ouvrirEdition({ dirty = false, auth = false, ...props } = {}) {
  const rendu = rendrePanneau(props, { auth })
  await screen.findByTestId('generateur-monte')
  // Radix n'écoute `pointerdown` sur le document qu'après un tour de timer.
  await act(async () => { await new Promise((r) => setTimeout(r, 5)) })
  if (dirty) await act(async () => { generateur.props.onDirtyChange(true) })
  return rendu
}
