// QJR641 — le sélecteur « Type d'installation » disparaît : le Marché est la
// seule source, et le défaut de la part diurne en dérive. Le curseur est
// masqué en commercial et en agricole.
// Écran RÉEL rendu (jamais une lecture du source).
// Run : npx vitest run src/pages/ventes/DevisGeneratorTypeInstallation.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'


vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).crmApiMock())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).stockApiMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).parametresApiMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).ventesApiEdition())

import stockApi from '../../api/stockApi'
import parametresApi from '../../api/parametresApi'
import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'
import { bancIndustriel, devisIndustrielBrouillon, renderRouteSortie } from './devisGenerator.testHelpers.jsx'

const { makeStore } = bancIndustriel({ DevisGenerator, stockApi, ventesApi, parametresApi,
    devis: () => devisIndustrielBrouillon({ id: 528, mode: 'industriel',  etude_params: { scenario: 'Sans batterie', conso_annuelle: 60000, part_diurne_pct: 65 } }),
})

function rendre(url) {
  return renderRouteSortie(DevisGenerator, makeStore(), url, 'APRES-ENREGISTREMENT')
}

const curseur = () => screen.queryByTestId('curseur-part-diurne')

describe('QJR641 — plus de « Type d’installation » : le Marché pilote la part diurne', () => {
  it('nouveau devis : aucun sélecteur de type, pas de curseur, défaut résidentiel (60 %) affiché', async () => {
    rendre('/ventes/devis/nouveau')
    await waitFor(() =>
      expect(screen.getByRole('radio', { name: /Résidentiel/ })).toHaveAttribute('aria-checked', 'true'))
    expect(document.getElementById('gen-insttype')).toBeNull()
    expect(screen.queryByText(/Type d'Installation/)).toBeNull()
    // AGNR44 — plus de curseur : la part diurne par défaut est DITE (60 %).
    expect(curseur()).toBeNull()
    expect(screen.getByTestId('part-diurne-defaut').textContent).toMatch(/60 %/)
  })

  it('CIQ126 — Industriel, Commercial et Agricole : curseur masqué (profil déclaré au moteur C&I)', async () => {
    const user = userEvent.setup()
    rendre('/ventes/devis/nouveau')
    await user.click(await screen.findByRole('radio', { name: /Industriel/ }))
    await waitFor(() => expect(curseur()).toBeNull())
    await user.click(screen.getByRole('radio', { name: /Commercial/ }))
    await waitFor(() => expect(curseur()).toBeNull())
    await user.click(screen.getByRole('radio', { name: /Agricole/ }))
    await waitFor(() => expect(curseur()).toBeNull())
  })

  it('CIQ126 — réouverture industrielle : part_diurne_pct n’est plus relue, aucun curseur', async () => {
    rendre('/ventes/devis/nouveau?edit=528')
    await waitFor(() =>
      expect(screen.getByRole('radio', { name: /Industriel/ })).toHaveAttribute('aria-checked', 'true'))
    await screen.findByTestId('ci-profil')
    expect(curseur()).toBeNull()
  })
})
