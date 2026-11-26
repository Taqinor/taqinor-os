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

  // LOT 6 — la fiche devis montre le schéma électrique du calepinage, une planche par option servie.
  const serviSchema = (enveloppe) => {
    ventesApi.getConceptionElectrique.mockResolvedValue(reponseContrat('ventes', 'conception_electrique'))
    ventesApi.getSchemaUnifilaireDevis.mockResolvedValue({ data: { params: {}, svg: SVG, schema_electrique: enveloppe } })
  }
  const ENVELOPPE = () => structuredClone(exempleContrat('ventes', 'schema_electrique').schema_electrique)

  it('deux options : l\'option avec batterie d\'abord (carte batterie), la bascule montre l\'option sans batterie', async () => {
    serviSchema(ENVELOPPE())
    const user = userEvent.setup()
    render(<ConceptionElectrique devisId={3} />)

    const planche = await screen.findByTestId('schema-electrique-devis')
    expect(within(planche).getByRole('button', { name: 'Avec batterie' })).toHaveAttribute('aria-pressed', 'true')
    expect(within(planche).getByTestId('csch-bloc-batterie')).toHaveTextContent('Dyness BX51100')
    expect(planche).toHaveTextContent('Chaîne 4 · 12 panneaux')
    // L'en-tête de la carte dit « Schéma électrique ».
    expect(screen.getByText('Schéma électrique', { selector: 'p' })).toBeInTheDocument()
    // L'esquisse historique n'est plus affichée.
    expect(document.querySelector('[role="img"][aria-label="Schéma unifilaire"]')).toBeNull()

    await user.click(within(planche).getByRole('button', { name: 'Sans batterie' }))
    expect(within(planche).getByRole('button', { name: 'Sans batterie' })).toHaveAttribute('aria-pressed', 'true')
    expect(within(planche).queryByTestId('csch-bloc-batterie')).toBeNull()
    expect(planche).toHaveTextContent('Chaîne 2 · 17 panneaux')
    expect(planche).not.toHaveTextContent('Chaîne 4')
  })

  it('une seule option servie : pas de bascule, et jamais le dessin de l\'autre option', async () => {
    const enveloppe = ENVELOPPE()
    enveloppe.options.avec_batterie = null
    serviSchema(enveloppe)
    render(<ConceptionElectrique devisId={3} />)

    const planche = await screen.findByTestId('schema-electrique-devis')
    expect(within(planche).queryByRole('group', { name: 'Option du schéma' })).toBeNull()
    expect(planche).toHaveTextContent('Chaîne 2 · 17 panneaux')
    expect(within(planche).queryByTestId('csch-bloc-batterie')).toBeNull()
  })

  it('D-ACAL-158 : l\'avis du serveur dit au vendeur quelle option le client ne voit pas', async () => {
    const enveloppe = ENVELOPPE()
    const avis = 'Le client ne voit pas le schéma de cette option : aucune conception électrique n\'a été rangée pour elle à l\'envoi.'
    enveloppe.avis_client = { sans_batterie: avis, avec_batterie: null }
    serviSchema(enveloppe)
    const user = userEvent.setup()
    render(<ConceptionElectrique devisId={3} />)

    const planche = await screen.findByTestId('schema-electrique-devis')
    expect(within(planche).queryByText(avis)).toBeNull()
    await user.click(within(planche).getByRole('button', { name: 'Sans batterie' }))
    expect(within(planche).getByText(avis)).toHaveClass('text-muted-foreground')
  })

  it('aucun montant ni prix dans la planche', async () => {
    serviSchema(ENVELOPPE())
    render(<ConceptionElectrique devisId={3} />)
    const planche = await screen.findByTestId('schema-electrique-devis')
    expect(planche.textContent).not.toMatch(/\bDH\b|\bMAD\b|€|\$|\bprix\b|\bHT\b|\bTTC\b|\bachat\b/i)
  })

  it('une enveloppe sans aucune option dessinable dit « Schéma indisponible »', async () => {
    serviSchema({ options: { sans_batterie: null, avec_batterie: null } })
    render(<ConceptionElectrique devisId={3} />)
    expect(await screen.findByText('Schéma indisponible.')).toBeInTheDocument()
  })

  it('le badge ne dit pas « tout va bien » quand des alertes sont servies : 0 alerte, 1 alerte, plusieurs', async () => {
    const rendre = async (alertes) => {
      cleanup()
      const data = structuredClone(DESIGN)
      data.conformite = { conforme: true, bloquants: [], alertes }
      ventesApi.getConceptionElectrique.mockResolvedValue({ data })
      ventesApi.getSchemaUnifilaireDevis.mockResolvedValue({ data: { params: {}, svg: SVG } })
      render(<ConceptionElectrique devisId={42} />)
      return screen.findByTestId('conception-conformite-badge')
    }
    const sans = await rendre([])
    expect(sans.textContent.trim()).toBe('Conforme')
    const une = await rendre(['entrée MPPT 1 : Isc cumulé 22,3 A > courant d’entrée admissible 20,0 A'])
    expect(une.textContent.trim()).toBe('Conforme · 1 point à regarder')
    const deux = await rendre(['a', 'b'])
    expect(deux.textContent.trim()).toBe('Conforme · 2 points à regarder')
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
