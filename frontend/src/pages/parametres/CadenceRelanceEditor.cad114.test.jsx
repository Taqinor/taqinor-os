import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, act, cleanup } from '@testing-library/react'

/* CAD114 — le canal « Visite » n'est plus PROPOSÉ à la configuration.

   `RelanceEtapeRow` ne teste `etape.canal` que pour `appel` et pour les
   canaux de message, jamais pour `visite` : une touche de canal « Visite »
   affichait un badge et proposait Appeler/WhatsApp comme les autres — un
   canal qui ne déclenche rien.

   Garde-fou décisif du round 2, verrouillé ici : on n'y câble SURTOUT PAS la
   modale de planification de visite. Le seul barreau de canal visite est le
   J+35 générique, porté par des leads legacy souvent SANS devis : l'ouvrir
   institutionnaliserait la visite AVANT le devis, contre la doctrine du
   15/09.

   Le barreau qui porte DÉJÀ `visite` continue d'afficher sa valeur — on ne
   réécrit rien en base depuis un écran de configuration. */

vi.mock('../../api/parametresApi', () => ({
  default: {
    getMessages: vi.fn(async () => ({ data: [] })),
    getCadenceRelance: vi.fn(),
    updateCadenceRelanceEtape: vi.fn(async () => ({ data: {} })),
    createCadenceRelanceEtape: vi.fn(async () => ({ data: {} })),
    deleteCadenceRelanceEtape: vi.fn(async () => ({ data: {} })),
  },
}))

import parametresApi from '../../api/parametresApi'
import { ThemeProvider } from '../../design/ThemeProvider'
import CadenceRelanceEditor from './CadenceRelanceEditor'

const BARREAU_APPEL = {
  id: 61, cadence: 'contact', ordre: 1, delai_jours: 0, delai_minutes: 0,
  heure_cible: null, canal: 'appel', libelle: "Appel d'ouverture",
  template_cle: '', dimanche_ok: false, actif: true,
}
const BARREAU_VISITE_LEGACY = {
  id: 62, cadence: 'contact', ordre: 2, delai_jours: 35, delai_minutes: 0,
  heure_cible: null, canal: 'visite', libelle: 'Visite J+35',
  template_cle: '', dimanche_ok: false, actif: true,
}

let listeCourante = [BARREAU_APPEL]

beforeEach(() => {
  listeCourante = [BARREAU_APPEL]
  parametresApi.getCadenceRelance.mockReset()
  parametresApi.getCadenceRelance.mockImplementation(async (cadence) => ({
    data: cadence === 'contact' ? listeCourante : [],
  }))
})
afterEach(() => cleanup())

const renderEditor = async () => {
  await act(async () => {
    render(
      <ThemeProvider>
        <CadenceRelanceEditor />
      </ThemeProvider>,
    )
  })
}

const user = async () => {
  const { default: userEvent } = await import('@testing-library/user-event')
  return userEvent.setup()
}

describe('CAD114 — « Visite » n’est plus un canal proposé', () => {
  it('n’offre que Appel, WhatsApp et E-mail sur un barreau ordinaire', async () => {
    await renderEditor()
    await screen.findByDisplayValue("Appel d'ouverture")
    const u = await user()
    await u.click(screen.getByLabelText('Canal'))
    const options = await screen.findAllByRole('option')
    expect(options.map(o => o.textContent)).toEqual(
      ['Appel', 'WhatsApp', 'E-mail'])
  })

  it('laisse le barreau legacy afficher sa valeur, désactivée et étiquetée', async () => {
    listeCourante = [BARREAU_VISITE_LEGACY]
    await renderEditor()
    await screen.findByDisplayValue('Visite J+35')
    const u = await user()
    await u.click(screen.getByLabelText('Canal'))
    const options = await screen.findAllByRole('option')
    const visite = options.find(o => /Visite \(héritée/.test(o.textContent))
    expect(visite).toBeTruthy()
    // Proposé à AUCUNE nouvelle configuration : l'option n'est pas choisissable.
    expect(visite).toHaveAttribute('aria-disabled', 'true')
  })

  it('n’ouvre aucune modale de planification de visite', async () => {
    listeCourante = [BARREAU_VISITE_LEGACY]
    await renderEditor()
    await screen.findByDisplayValue('Visite J+35')
    // Garde-fou du round 2 : rien, dans cet écran, ne propose de planifier
    // une visite — ni bouton, ni dialogue.
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(screen.queryByText(/planifier la visite/i)).toBeNull()
  })
})
