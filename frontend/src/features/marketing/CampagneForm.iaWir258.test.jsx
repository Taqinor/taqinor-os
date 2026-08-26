import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* WIR258/XMKT34 — l'assistant « Générer avec l'IA » vivait dans
   `CampagnesScreen.jsx`, un DOUBLON d'écran plus routé nulle part : la
   fonctionnalité était morte. Elle vit désormais dans `CampagneForm`, le seul
   formulaire de campagne réellement monté. Couvre les DEUX cas :
   (1) sans clé LLM → AUCUNE trace UI (le gating est la sonde, pas un try) ;
   (2) avec clé → le bouton remplit objet/corps comme SUGGESTION éditable,
       sans rien sauvegarder. */

const mocks = vi.hoisted(() => ({
  listesList: vi.fn(),
  blocsList: vi.fn(),
  heatmap: vi.fn(),
  apercuFusion: vi.fn(),
  genererIaDisponible: vi.fn(),
  genererIa: vi.fn(),
}))

vi.mock('../../api/marketingApi', () => ({
  default: {
    unwrapList: (res) => {
      const data = res?.data
      return Array.isArray(data) ? data : (data?.results || [])
    },
    listes: { list: mocks.listesList },
    blocsContenu: { list: mocks.blocsList },
    heatmapEngagement: mocks.heatmap,
    campagnes: {
      apercuFusion: mocks.apercuFusion,
      genererIaDisponible: mocks.genererIaDisponible,
      genererIa: mocks.genererIa,
    },
  },
}))

import CampagneForm, { emptyForm } from './CampagneForm'

beforeEach(() => {
  mocks.listesList.mockResolvedValue({ data: [] })
  mocks.blocsList.mockResolvedValue({ data: [] })
  mocks.heatmap.mockResolvedValue({
    data: { cellules: [], meilleur: null, total_envois: 0 },
  })
  mocks.genererIa.mockResolvedValue({
    data: { ok: true, objet: 'Offre solaire -20%', corps: 'Bonjour {{prenom}}…' },
  })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderForm() {
  return render(
    <CampagneForm initial={emptyForm()} onSave={vi.fn()} onCancel={vi.fn()} />,
  )
}

describe('CampagneForm — WIR258 assistant IA (XMKT34)', () => {
  it('sans clé LLM : AUCUNE trace UI, et aucun appel de génération', async () => {
    mocks.genererIaDisponible.mockResolvedValue({ data: { configured: false } })
    renderForm()
    await waitFor(() => expect(mocks.genererIaDisponible).toHaveBeenCalled())

    expect(screen.queryByTestId('campagne-ia-panel')).toBeNull()
    expect(screen.queryByTestId('campagne-ia-generer')).toBeNull()
    expect(mocks.genererIa).not.toHaveBeenCalled()
  })

  it('sonde en échec : dégrade en silence, aucun panneau IA', async () => {
    mocks.genererIaDisponible.mockRejectedValue(new Error('réseau'))
    renderForm()
    await waitFor(() => expect(mocks.genererIaDisponible).toHaveBeenCalled())
    expect(screen.queryByTestId('campagne-ia-panel')).toBeNull()
  })

  it('avec clé : le bouton remplit objet et corps (suggestion éditable)', async () => {
    const user = userEvent.setup()
    mocks.genererIaDisponible.mockResolvedValue({ data: { configured: true } })
    renderForm()

    const panneau = await screen.findByTestId('campagne-ia-panel')
    expect(panneau).toBeInTheDocument()

    await user.type(screen.getByTestId('campagne-ia-segment'), 'leads froids')
    await user.type(screen.getByTestId('campagne-ia-offre'), '-20% panneaux')
    await user.click(screen.getByTestId('campagne-ia-generer'))

    await waitFor(() => expect(mocks.genererIa).toHaveBeenCalledWith({
      segment_label: 'leads froids', offre: '-20% panneaux',
      instruction: '', langue: 'fr',
    }))
    await waitFor(() => expect(screen.getByTestId('campagne-objet'))
      .toHaveValue('Offre solaire -20%'))
    expect(screen.getByTestId('campagne-corps')).toHaveValue('Bonjour {{prenom}}…')

    // SUGGESTION : le texte reste éditable à la main.
    await user.clear(screen.getByTestId('campagne-objet'))
    await user.type(screen.getByTestId('campagne-objet'), 'Mon objet')
    expect(screen.getByTestId('campagne-objet')).toHaveValue('Mon objet')
  })
})

describe('WIR258 — CampagnesScreen supprimé', () => {
  it("l'écran doublon n'existe plus dans le module", async () => {
    const modules = import.meta.glob('./*.jsx')
    expect(Object.keys(modules)).not.toContain('./CampagnesScreen.jsx')
  })
})
