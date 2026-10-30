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

  it('ADEV103 — Industriel et Commercial : ni panneaux, ni puissance panneau, ni structure, ni cible, ni « Recalculer » ; seule la taille explicite règle la taille', async () => {
    const user = userEvent.setup()
    rendre('/ventes/devis/nouveau')
    // résidentiel : la carte technique et « Recalculer » sont là
    await screen.findByTestId('gen-kwc-cible')
    expect(document.getElementById('gen-nbpanneaux')).not.toBeNull()
    expect(screen.getByTestId('btn-recalculer-dimensionnement')).toBeInTheDocument()
    for (const marche of [/Industriel/, /Commercial/]) {
      await user.click(screen.getByRole('radio', { name: marche }))
      await screen.findByTestId('ci-profil')
      expect(screen.queryByTestId('gen-kwc-cible')).toBeNull()
      expect(document.getElementById('gen-nbpanneaux')).toBeNull()
      expect(document.getElementById('gen-panelw')).toBeNull()
      expect(document.getElementById('gen-structure-produit')).toBeNull()
      expect(screen.queryByTestId('btn-recalculer-dimensionnement')).toBeNull()
      // la composition serveur reste lançable ; la taille se règle ici seulement
      expect(screen.getByTestId('btn-auto-remplir')).toBeInTheDocument()
      expect(document.getElementById('gen-ci-taille')).not.toBeNull()
      expect(screen.getByLabelText(/Taille explicite \(kWc\)/)).toBe(document.getElementById('gen-ci-taille'))
      expect(screen.getByTestId('ci-taille-aide'))
        .toHaveTextContent("vide = taille calculée par la règle de l'horizon marginal")
    }
  })
})
