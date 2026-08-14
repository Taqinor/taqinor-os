import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

/* PV43 — Panneau « Conception électrique » de la fiche devis.

   PACT13 : la charge utile n'est PAS tapée à la main. Elle vient de l'exemple
   COMMITTÉ dans l'app (`apps/ventes/contract_samples/conception_electrique.json`),
   comparé par `scripts/check_api_shapes.py` au dictionnaire RÉELLEMENT rendu
   par `apps.ventes.electrical_service.build_electrical_design`. Si le serveur
   change de forme, l'exemple change et ce test casse tout seul. */

vi.mock('../../api/ventesApi', () => ({
  default: {
    getConceptionElectrique: vi.fn(),
    recalculerConceptionElectrique: vi.fn(),
    getSchemaUnifilaireDevis: vi.fn(),
    getSchemaUnifilairePdf: vi.fn(),
  },
}))

import ventesApi from '../../api/ventesApi'
import ConceptionElectrique from './ConceptionElectrique'

const DESIGN = exempleContrat('ventes', 'conception_electrique')
// Planche SANS balisage dangereux (`renderTrustedSvg` la refuserait sinon).
const SVG = '<svg viewBox="0 0 10 10"><rect width="10" height="10" /></svg>'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function setupResolved() {
  ventesApi.getConceptionElectrique.mockResolvedValue(
    reponseContrat('ventes', 'conception_electrique'))
  ventesApi.getSchemaUnifilaireDevis.mockResolvedValue(
    { data: { params: {}, svg: SVG } })
}

describe('ConceptionElectrique (PV43)', () => {
  it('charge l\'étude sur UN SEUL appel GET et rend le contrat PACT10 complet', async () => {
    setupResolved()
    render(<ConceptionElectrique devisId={42} />)

    await waitFor(() => expect(ventesApi.getConceptionElectrique).toHaveBeenCalledTimes(1))
    expect(ventesApi.getConceptionElectrique).toHaveBeenCalledWith(42)

    // Conformité : la fixture est conforme, sans bloquant, avec UNE alerte.
    // `getByTestId` (pas `getByText('Conforme')`) : l'entête de colonne
    // « Conforme » du tableau des chaînes porte le MÊME texte.
    expect(await screen.findByTestId('conception-conformite-badge'))
      .toHaveTextContent('Conforme')
    expect(screen.getByText(DESIGN.conformite.alertes[0])).toBeInTheDocument()
    expect(screen.queryByText(/bloquant/i)).not.toBeInTheDocument()

    // Chaînes par MPPT : une ligne PAR ENTRÉE du contrat, dans le MÊME ordre —
    // comparée par position (deux chaînes de la fixture partagent les mêmes
    // tensions, `getByText` seul serait ambigu).
    const corps = screen.getByRole('table').querySelector('tbody')
    const lignes = within(corps).getAllByRole('row')
    expect(lignes).toHaveLength(DESIGN.chaines.length)
    DESIGN.chaines.forEach((chaine, i) => {
      const cellules = within(lignes[i]).getAllByRole('cell')
      expect(cellules[0]).toHaveTextContent(String(chaine.pan))
      expect(cellules[1]).toHaveTextContent(String(chaine.mppt))
      expect(cellules[2]).toHaveTextContent(String(chaine.nb_modules))
      expect(cellules[3]).toHaveTextContent(`${chaine.vmp_froid_v} V`)
      expect(cellules[4]).toHaveTextContent(`${chaine.voc_froid_v} V`)
      expect(cellules[5]).toHaveTextContent(`${chaine.vmp_chaud_v} V`)
    })
  })

  it('affiche l\'aperçu du schéma unifilaire et le lien de téléchargement PDF', async () => {
    setupResolved()
    render(<ConceptionElectrique devisId={7} />)

    await waitFor(() => expect(ventesApi.getSchemaUnifilaireDevis).toHaveBeenCalledWith(7))
    const bouton = await screen.findByRole('button', { name: /Télécharger le PDF/ })
    expect(bouton).toBeInTheDocument()
    expect(document.querySelector('[role="img"][aria-label="Schéma unifilaire"] svg'))
      .toBeInTheDocument()
  })

  it('« Recalculer » envoie les surcharges DC/AC/phases et rafraîchit l\'étude + le schéma', async () => {
    setupResolved()
    ventesApi.recalculerConceptionElectrique.mockResolvedValue(
      reponseContrat('ventes', 'conception_electrique'))
    const user = userEvent.setup()
    render(<ConceptionElectrique devisId={9} />)

    await screen.findByTestId('conception-conformite-badge')
    const dcInput = screen.getByLabelText('Liaison DC (m)')
    // Préremplissage : `parametres.dc_m` du contrat, jamais une valeur inventée.
    expect(dcInput).toHaveValue(DESIGN.parametres.dc_m)

    await user.clear(dcInput)
    await user.type(dcInput, '25.5')
    await user.click(screen.getByRole('button', { name: /^Recalculer$/ }))

    await waitFor(() => expect(ventesApi.recalculerConceptionElectrique)
      .toHaveBeenCalledTimes(1))
    const [id, overrides] = ventesApi.recalculerConceptionElectrique.mock.calls[0]
    expect(id).toBe(9)
    expect(overrides.dc_m).toBe(25.5)
    expect(overrides.ac_m).toBe(DESIGN.parametres.ac_m)
    expect(overrides.phases).toBe(DESIGN.parametres.phases)
    // Le schéma est rechargé après le recalcul (même endpoint que le montage).
    await waitFor(() => expect(ventesApi.getSchemaUnifilaireDevis).toHaveBeenCalledTimes(2))
  })

  it('un devis sans étude calculable affiche un état vide plutôt qu\'un plantage', async () => {
    ventesApi.getConceptionElectrique.mockResolvedValue({
      data: {
        chaines: [], conformite: { conforme: true, bloquants: [], alertes: [] },
        ratio_dc_ac: null, ratio_ac_dc: null, protections: [], cables: [], bom: [],
        note: [], parametres: { dc_m: 10, ac_m: 15, phases: 1, regime: 'TT' },
      },
    })
    ventesApi.getSchemaUnifilaireDevis.mockResolvedValue({ data: { params: {}, svg: null } })
    render(<ConceptionElectrique devisId={1} />)

    expect(await screen.findByText('Aucune chaîne calculée.')).toBeInTheDocument()
  })
})
