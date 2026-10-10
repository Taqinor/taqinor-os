// AGNR18 (C-AGNR-007) — après un modèle appliqué (10 × « Panneau Jinko 550W »)
// sur un devis rouvert dont le `panelW` d'état vient d'un panneau 715 W, le
// kWc FACTURÉ par les lignes est 5,5 (watt LU de chaque ligne), jamais
// 10 × 715 = 7,15 : le corps de l'aperçu horaire porte `kwc: 5.5`.
//
// Harnais du golden (seules les quatre API sont mockées, jamais l'écran).
import { describe, it, expect, vi } from 'vitest'
import { cycleEcran } from '../../test/cycleEcran'
import { act, waitFor, fireEvent } from '@testing-library/react'

import {
  monter, attendreStable, CATALOGUE, DEVIS_ETUDE_HORAIRE,
} from './DevisGeneratorGoldenHarnais'
import { exempleContrat } from '../../test/fixtures/contractSamples'

vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).apiAutoMock())

const JINKO = {
  id: 108, nom: 'Panneau Jinko 550W', prix_vente: 1000, tva: 10, is_archived: false, prix_achat: 700,
}
const MODELE = {
  id: 9, nom: 'Modèle 5,5 kWc', mode_installation: 'residentiel', taux_tva: '20.00', remise_globale: '0.00',
  etude_params_snapshot: {},
  lignes_snapshot: [
    { produit_id: 108, designation: 'Panneau Jinko 550W', quantite: '10', prix_unitaire: '1000',
      remise: '0', taux_tva: '10', ordre: 0, variante: '', type_ligne: 'produit', optionnelle: false },
    { produit_id: 102, designation: 'Onduleur réseau 5kW Monophasé', quantite: '1', prix_unitaire: '9000',
      remise: '0', taux_tva: '20', ordre: 1, variante: '', type_ligne: 'produit', optionnelle: false },
  ],
}

cycleEcran()

const bouton = (container, re) => [...container.querySelectorAll('button')].find((b) => re.test(b.textContent))

describe('AGNR18 — kWc des lignes au watt de chaque ligne panneau', () => {
  it('modèle 10 × Jinko 550W appliqué ⇒ corps de l’aperçu horaire `kwc: 5.5`', async () => {
    const vue = await monter(`/ventes/devis/nouveau?edit=${DEVIS_ETUDE_HORAIRE.id}`, {
      devis: DEVIS_ETUDE_HORAIRE,
      etudeHoraire: exempleContrat('ventes', 'etude_horaire'),
      avant: (apis) => {
        apis.stockApi.getProduits.mockResolvedValue({ data: [...CATALOGUE, JINKO] })
        apis.ventesApi.getPresets.mockResolvedValue({ data: [MODELE] })
      },
    })
    const { container } = vue
    await waitFor(() => expect(vue.ventesApi.postEtudeHorairePreview).toHaveBeenCalled(), { timeout: 5000 })
    await attendreStable(container, act, { stables: 10 })

    await act(async () => { fireEvent.click(bouton(container, /Modèles de devis/)) })
    await waitFor(() => expect(bouton(container, /^Appliquer$/)).toBeTruthy(), { timeout: 5000 })
    await act(async () => { fireEvent.click(bouton(container, /^Appliquer$/)) })
    await waitFor(() => {
      const corps = vue.ventesApi.postEtudeHorairePreview.mock.calls.at(-1)[0]
      expect(corps.kwc).toBe(5.5)
    }, { timeout: 5000 })
  }, 60000)
})
