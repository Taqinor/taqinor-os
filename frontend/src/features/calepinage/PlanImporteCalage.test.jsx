/* CALX39 — l'écran de calage, branché sur la porte d'import de plan.

   Tout ce qui est affirmé ici vient de l'échantillon COMMITTÉ
   `apps/calepinage/contract_samples/calepinage_import_plan.json` (PACT10/13) —
   le test backend `test_calx39_import_plan.py` affirme le MÊME fichier, en
   appelant la porte sur un vrai DXF : les deux moitiés ne peuvent pas diverger.

   Ce qui est prouvé :
   1. sans plan rattaché, l'écran offre le DÉPÔT (avant CALX39, il disait
      seulement qu'il n'avait rien à caler) et l'analyse passe le fichier au
      serveur ;
   2. les calques SERVIS sont proposés, et le motif d'échelle du serveur est
      affiché — aucune échelle n'est estimée à l'écran ;
   3. le contour du calque choisi devient celui qu'on cale ;
   4. un refus atterrit SOUS le champ fautif, avec le bandeau qui le NOMME
      (`fichier` ou `calque`), et le motif vient du serveur ;
   5. l'import n'enregistre RIEN : `enregistrerLayoutCalepinage` n'est pas
      appelé. */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

vi.mock('../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      layout: vi.fn(),
      enregistrerLayoutCalepinage: vi.fn(),
      importerPlan: vi.fn(),
    },
  },
}))

import calepinageApi from '../../api/calepinageApi'
import PlanImporteCalage from './PlanImporteCalage'

const contrat = (variante) => exempleContrat(
  'calepinage', 'calepinage_import_plan', variante,
)

const reponse = (variante) => reponseContrat(
  'calepinage', 'calepinage_import_plan', variante,
)

const PLAN = () => new File(['0\nSECTION\n'], 'plan-toiture.dxf',
  { type: 'application/dxf' })

const rendre = () => render(
  <MemoryRouter><PlanImporteCalage calepinageId={7} /></MemoryRouter>,
)

const deposer = async (utilisateur) => {
  await utilisateur.upload(screen.getByTestId('cal-calage-fichier'), PLAN())
  await utilisateur.click(screen.getByTestId('cal-calage-analyser'))
}

beforeEach(() => {
  vi.clearAllMocks()
  calepinageApi.calepinages.layout.mockResolvedValue({ data: { roof_layout: null } })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('PlanImporteCalage (CALX39) — le dépôt d’un plan', () => {
  it('offre le dépôt même sans plan rattaché, et envoie le fichier au serveur', async () => {
    const utilisateur = userEvent.setup()
    calepinageApi.calepinages.importerPlan
      .mockResolvedValue(reponse('exemple_sans_calque'))
    rendre()

    await screen.findByTestId('cal-calage-sans-plan')
    expect(screen.getByTestId('cal-calage-import')).toBeInTheDocument()

    await deposer(utilisateur)

    await waitFor(() => expect(calepinageApi.calepinages.importerPlan)
      .toHaveBeenCalledTimes(1))
    const [id, corps] = calepinageApi.calepinages.importerPlan.mock.calls[0]
    expect(id).toBe(7)
    expect(corps).toBeInstanceOf(FormData)
    expect(corps.get('fichier')).toBeTruthy()
    // Première analyse : aucun calque n'est choisi à la place de l'utilisateur.
    expect(corps.get('calque')).toBeNull()
  })

  it('propose les calques SERVIS et affiche le motif d’échelle du serveur', async () => {
    const utilisateur = userEvent.setup()
    calepinageApi.calepinages.importerPlan
      .mockResolvedValue(reponse('exemple_sans_calque'))
    rendre()
    await screen.findByTestId('cal-calage-sans-plan')
    await deposer(utilisateur)

    const servi = contrat('exemple_sans_calque')
    await screen.findByTestId('cal-calage-analyse')
    const selecteur = screen.getByTestId('cal-calage-calque')
    servi.calques.forEach((calque) => {
      expect(selecteur).toHaveTextContent(calque.nom)
    })
    expect(screen.getByTestId('cal-calage-motif-echelle'))
      .toHaveTextContent(servi.motif_echelle)
    expect(screen.getByTestId('cal-calage-unite')).toHaveTextContent(servi.unite)
    // Aucune échelle n'est servie : elle ne peut donc pas être affichée.
    expect(servi.echelle).toBeNull()
  })

  it('cale le contour du calque choisi, et n’enregistre rien au passage', async () => {
    const utilisateur = userEvent.setup()
    calepinageApi.calepinages.importerPlan
      .mockResolvedValueOnce(reponse('exemple_sans_calque'))
      .mockResolvedValueOnce(reponse('exemple'))
    rendre()
    await screen.findByTestId('cal-calage-sans-plan')
    await deposer(utilisateur)
    await screen.findByTestId('cal-calage-analyse')

    const avecCalque = contrat('exemple')
    await utilisateur.selectOptions(screen.getByTestId('cal-calage-calque'),
      avecCalque.calque)
    await utilisateur.click(screen.getByTestId('cal-calage-proposer'))

    await waitFor(() => expect(calepinageApi.calepinages.importerPlan)
      .toHaveBeenCalledTimes(2))
    const [, corps] = calepinageApi.calepinages.importerPlan.mock.calls[1]
    expect(corps.get('calque')).toBe(avecCalque.calque)

    // Le contour SERVI devient celui qu'on cale.
    await waitFor(() => expect(screen.getByTestId('cal-calage-sommets'))
      .toHaveTextContent(String(avecCalque.contour.length)))
    // … et rien n'a été enregistré : l'écriture reste le geste de l'utilisateur.
    expect(avecCalque.enregistre).toBe(false)
    expect(calepinageApi.calepinages.enregistrerLayoutCalepinage)
      .not.toHaveBeenCalled()
  })
})

describe('PlanImporteCalage (CALX39) — les refus nomment leur champ', () => {
  it('un calque inconnu : message SOUS le champ et bandeau qui le nomme', async () => {
    const utilisateur = userEvent.setup()
    const refus = contrat('refus_calque')
    calepinageApi.calepinages.importerPlan
      .mockResolvedValueOnce(reponse('exemple_sans_calque'))
      .mockRejectedValueOnce({ response: { data: refus } })
    rendre()
    await screen.findByTestId('cal-calage-sans-plan')
    await deposer(utilisateur)
    await screen.findByTestId('cal-calage-analyse')

    await utilisateur.selectOptions(screen.getByTestId('cal-calage-calque'),
      contrat('exemple').calque)
    await utilisateur.click(screen.getByTestId('cal-calage-proposer'))

    const sousLeChamp = await screen.findByTestId('cal-calage-erreur-calque')
    expect(sousLeChamp).toHaveTextContent(refus.calque)
    expect(screen.getByTestId('cal-calage-bandeau-import'))
      .toHaveTextContent('calque')
    expect(screen.getByTestId('cal-calage-calque'))
      .toHaveAttribute('aria-invalid', 'true')
  })

  it('un fichier non vectoriel : le motif du serveur, sous « fichier »', async () => {
    const utilisateur = userEvent.setup()
    const refus = contrat('refus_fichier_image')
    calepinageApi.calepinages.importerPlan
      .mockRejectedValue({ response: { data: refus } })
    rendre()
    await screen.findByTestId('cal-calage-sans-plan')
    await deposer(utilisateur)

    const sousLeChamp = await screen.findByTestId('cal-calage-erreur-fichier')
    expect(sousLeChamp).toHaveTextContent(refus.fichier)
    expect(screen.getByTestId('cal-calage-bandeau-import'))
      .toHaveTextContent('fichier')
    expect(screen.getByTestId('cal-calage-fichier'))
      .toHaveAttribute('aria-invalid', 'true')
  })

  it('cliquer « Analyser » sans fichier nomme le champ, sans appeler le serveur', async () => {
    const utilisateur = userEvent.setup()
    rendre()
    await screen.findByTestId('cal-calage-sans-plan')

    await utilisateur.click(screen.getByTestId('cal-calage-analyser'))

    expect(screen.getByTestId('cal-calage-erreur-fichier')).toBeInTheDocument()
    expect(calepinageApi.calepinages.importerPlan).not.toHaveBeenCalled()
  })
})
