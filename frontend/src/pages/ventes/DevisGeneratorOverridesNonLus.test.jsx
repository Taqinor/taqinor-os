// QJR571 (D-QJR5-8) — le panneau « Surcharges (registre) » DIT quels chemins
// le moteur ne lit pas : la ligne `effectif` marquée `non_lu: true` par le
// serveur porte « — sans effet sur le document ». Depuis QJR573, la liste
// blanche ne contient plus que des chemins lus : la mention ne subsiste que
// sur une surcharge RETIRÉE déjà posée en base (ici `tarif.distributeur`).
//
// Monte réellement DevisGenerator (`?edit=7` réouvre un brouillon) — aucun
// test regex sur le source (garde QJR239).
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorOverridesNonLus.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'


// APIs mockées (aucun appel réseau réel au montage).
vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).crmApiMock())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).stockApiMock())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).parametresApiMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).ventesApiMock())

import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'
import { bancDevisVide } from './devisGenerator.testHelpers.jsx'

// Un brouillon déjà enregistré : le panneau « Surcharges (registre) »
// n'existe QUE sur un devis avec editDevis?.id (QJR215).

const { renderGenerator } = bancDevisVide({ DevisGenerator, crmApi, stockApi, ventesApi })

const REGISTRE = {
  overrides: {
    'tarif.distributeur': { valeur: 'ONEE', origine: 'manuel' },
    scenario: { valeur: 'Sans batterie', origine: 'manuel' },
  },
  effectif: {
    'tarif.distributeur': {
      auto: null, manuel: 'ONEE', effectif: 'ONEE', source: 'manuel',
      non_derivable: true, non_lu: true,
    },
    scenario: {
      auto: 'Les deux (Sans + Avec)', manuel: 'Sans batterie',
      effectif: 'Sans batterie', source: 'manuel',
    },
  },
  lignes: {},
}

describe('QJR571 — le registre dit les chemins sans effet sur le document', () => {
  it('QJR573 — le sélecteur ne propose plus que des chemins lus, sans mention', async () => {
    ventesApi.lireOverrides.mockResolvedValue({ data: REGISTRE })
    renderGenerator()
    await waitFor(() => expect(screen.getByTestId('overrides-panel')).toBeInTheDocument())
    const options = [...screen.getByTestId('overrides-chemin').querySelectorAll('option')]
    expect(options.map((o) => o.value)).toEqual([
      'taille.nb_panneaux', 'taille.panel_watt', 'taille.kwc',
      'scenario', 'recommended_option', 'etude.jour_reference',
    ])
    for (const o of options) expect(o.textContent).toBe(o.value)
  })

  it('la ligne `effectif` marquée non_lu le dit ; une ligne lue ne le dit pas', async () => {
    ventesApi.lireOverrides.mockResolvedValue({ data: REGISTRE })
    renderGenerator()
    await waitFor(() => expect(
      screen.getByTestId('overrides-non-lu-tarif.distributeur')).toBeInTheDocument())
    expect(screen.queryByTestId('overrides-non-lu-scenario')).toBeNull()
  })
})
