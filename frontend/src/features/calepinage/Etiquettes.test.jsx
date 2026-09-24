import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ============================================================================
   CALX344 — les étiquettes libres, prouvées SUR LE CONTRAT.
   ----------------------------------------------------------------------------
   AUCUN MOCK ÉCRIT À LA MAIN (PACT13) : les réponses du serveur sont l'exemple
   committé `apps/calepinage/contract_samples/calepinage_etiquettes.json`
   (CALX332), le même fichier que `tests/test_calx343_etiquettes.py` affirme
   côté serveur. Les invariants durs du « Done » :
     1. filtre vide ⇒ liste inchangée (AUCUN paramètre `etiquette`) ;
     2. étiquette retirée ⇒ elle disparaît SANS rechargement complet ;
     3. le drapeau « modèle » n'apparaît JAMAIS comme étiquette libre.
   ========================================================================== */

const mocks = vi.hoisted(() => ({
  etiquettes: vi.fn(), poserEtiquette: vi.fn(), retirerEtiquette: vi.fn(),
  list: vi.fn(), getTags: vi.fn(), getLeads: vi.fn(), searchClients: vi.fn(),
  navigate: vi.fn(),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mocks.navigate }
})

vi.mock('../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      etiquettes: mocks.etiquettes,
      poserEtiquette: mocks.poserEtiquette,
      retirerEtiquette: mocks.retirerEtiquette,
      list: mocks.list,
    },
  },
}))

vi.mock('../../api/recordsApi', () => ({ default: { getTags: mocks.getTags } }))

vi.mock('../../api/crmApi', () => ({
  default: { getLeads: mocks.getLeads, searchClients: mocks.searchClients },
}))

import Etiquettes from './Etiquettes'
import CalepinageList from './CalepinageList'
import { documentContrat, exempleContrat } from '../../test/fixtures/contractSamples'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

const DOCUMENT = documentContrat('calepinage', 'calepinage_etiquettes')
const CONTRAT = exempleContrat('calepinage', 'calepinage_etiquettes')
const CONTRAT_VIDE = exempleContrat('calepinage', 'calepinage_etiquettes', 'exemple_vide')
const [PREMIERE, SECONDE] = CONTRAT.etiquettes
const SYSTEME = DOCUMENT.exclu_de_la_liste

// Le vocabulaire de la société, tel que `records` le sert : il CONTIENT le tag
// système (la bibliothèque l'y crée) — c'est à l'écran de ne jamais l'offrir.
const VOCABULAIRE = [
  ...CONTRAT.etiquettes,
  { id: 90, nom: SYSTEME, couleur: '' },
  { id: 91, nom: 'Chantier prioritaire', couleur: '' },
]

const LIGNES = [
  exempleContrat('calepinage', 'calepinage_detail'),
  exempleContrat('calepinage', 'calepinage_detail', 'exemple_vide'),
]

beforeEach(() => {
  vi.clearAllMocks()
  mocks.etiquettes.mockResolvedValue({ data: CONTRAT })
  mocks.getTags.mockResolvedValue({ data: VOCABULAIRE })
  mocks.list.mockResolvedValue({
    data: { count: 2, next: null, previous: null, results: LIGNES },
  })
  mocks.getLeads.mockResolvedValue({ data: [] })
  mocks.searchClients.mockResolvedValue({ data: [] })
})

const rendreFiche = (props = {}) => render(
  <Etiquettes calepinageId={7} peutGerer {...props} />,
)

describe('Etiquettes — la fiche (CALX344)', () => {
  it('le contrat nomme le tag système exclu, et l’exemple ne le porte pas', () => {
    expect(SYSTEME).toBe('calepinage:modele')
    expect(CONTRAT.etiquettes.map((e) => e.nom)).not.toContain(SYSTEME)
  })

  it('affiche les étiquettes servies, jetons colorés par `Tag.couleur`', async () => {
    rendreFiche()
    const jeton = await screen.findByTestId(`cal-etiquette-${PREMIERE.id}`)
    expect(jeton).toHaveTextContent(PREMIERE.nom)
    expect(jeton.style.borderColor).not.toBe('')
    // Couleur vide ⇒ couleur par défaut, jamais une couleur inventée.
    expect(screen.getByTestId(`cal-etiquette-${SECONDE.id}`).style.borderColor).toBe('')
    expect(mocks.etiquettes).toHaveBeenCalledWith(7)
  })

  it('retirer fait disparaître le jeton SANS rechargement (réponse du serveur)', async () => {
    mocks.retirerEtiquette.mockResolvedValue({ data: { etiquettes: [SECONDE] } })
    rendreFiche()
    await screen.findByTestId(`cal-etiquette-${PREMIERE.id}`)
    fireEvent.click(screen.getByRole('button', { name: `Retirer l’étiquette ${PREMIERE.nom}` }))
    await waitFor(() => expect(screen.queryByTestId(`cal-etiquette-${PREMIERE.id}`)).toBeNull())
    expect(mocks.retirerEtiquette).toHaveBeenCalledWith(7, PREMIERE.id)
    expect(mocks.etiquettes).toHaveBeenCalledTimes(1)
  })

  it('le drapeau « modèle » n’est JAMAIS proposé comme étiquette libre', async () => {
    rendreFiche()
    await screen.findByTestId(`cal-etiquette-${PREMIERE.id}`)
    fireEvent.click(screen.getByTestId('cal-etiquettes-ajouter'))
    const choix = await screen.findByTestId('cal-etiquettes-choix')
    await within(choix).findByText('Chantier prioritaire')
    expect(within(choix).queryByText(SYSTEME)).toBeNull()
    // Déjà posées ⇒ non reproposées.
    expect(within(choix).queryByText(PREMIERE.nom)).toBeNull()
  })

  it('poser envoie l’identifiant choisi et affiche la liste rendue', async () => {
    const nouvelle = { id: 91, nom: 'Chantier prioritaire', couleur: '' }
    mocks.poserEtiquette.mockResolvedValue({ data: { etiquettes: [...CONTRAT.etiquettes, nouvelle] } })
    rendreFiche()
    await screen.findByTestId(`cal-etiquette-${PREMIERE.id}`)
    fireEvent.click(screen.getByTestId('cal-etiquettes-ajouter'))
    fireEvent.click(await screen.findByTestId('cal-etiquettes-proposer-91'))
    expect(await screen.findByTestId('cal-etiquette-91')).toBeInTheDocument()
    expect(mocks.poserEtiquette).toHaveBeenCalledWith(7, 91)
  })

  it('un refus affiche la phrase du serveur, sous le geste', async () => {
    const motif = DOCUMENT.refus_autre_societe.tag_id
    mocks.poserEtiquette.mockRejectedValue({ response: { data: DOCUMENT.refus_autre_societe } })
    rendreFiche()
    await screen.findByTestId(`cal-etiquette-${PREMIERE.id}`)
    fireEvent.click(screen.getByTestId('cal-etiquettes-ajouter'))
    fireEvent.click(await screen.findByTestId('cal-etiquettes-proposer-91'))
    expect(await screen.findByTestId('cal-etiquettes-erreur')).toHaveTextContent(motif)
  })

  it('sans le droit de gérer : lecture seule (ni retrait, ni ajout)', async () => {
    rendreFiche({ peutGerer: false })
    await screen.findByTestId(`cal-etiquette-${PREMIERE.id}`)
    expect(screen.queryByRole('button', { name: /Retirer l’étiquette/ })).toBeNull()
    expect(screen.queryByTestId('cal-etiquettes-ajouter')).toBeNull()
  })

  it('aucune étiquette : l’état vide du contrat se lit', async () => {
    mocks.etiquettes.mockResolvedValue({ data: CONTRAT_VIDE })
    rendreFiche()
    expect(await screen.findByText('Aucune étiquette')).toBeInTheDocument()
  })
})

/* ── Le filtre de la LISTE ─────────────────────────────────────────────── */
const rendreListe = () => render(
  <MemoryRouter><ThemeProvider><CalepinageList /></ThemeProvider></MemoryRouter>,
)
const derniersParams = () => mocks.list.mock.calls.at(-1)?.[0] ?? {}

describe('CalepinageList — filtre par étiquette (CALX344)', () => {
  it('filtre vide ⇒ liste inchangée : aucun paramètre `etiquette`, aucun vocabulaire lu', async () => {
    rendreListe()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    expect(derniersParams()).toEqual({})
    expect(mocks.getTags).not.toHaveBeenCalled()
  })

  it('choisir une étiquette filtre, la retirer rend la liste entière sans rechargement', async () => {
    rendreListe()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('cal-filtre-etiquettes-ouvrir'))
    fireEvent.click(await screen.findByTestId(`cal-filtre-etiquettes-option-${PREMIERE.id}`))
    await waitFor(() => expect(derniersParams()).toEqual({ etiquette: String(PREMIERE.id) }))
    fireEvent.click(await screen.findByTestId(`cal-filtre-etiquettes-option-${SECONDE.id}`))
    await waitFor(() => expect(derniersParams())
      .toEqual({ etiquette: `${PREMIERE.id},${SECONDE.id}` }))

    const jeton = screen.getByTestId(`cal-filtre-etiquette-${PREMIERE.id}`)
    fireEvent.click(within(jeton).getByRole('button', { name: `Retirer l’étiquette ${PREMIERE.nom}` }))
    await waitFor(() => expect(derniersParams()).toEqual({ etiquette: String(SECONDE.id) }))
    expect(screen.queryByTestId(`cal-filtre-etiquette-${PREMIERE.id}`)).toBeNull()
    // La liste est RELUE par la ressource, l'écran n'est jamais démonté.
    expect(screen.getByTestId('cal-filtre-etiquettes')).toBeInTheDocument()
  })

  it('le drapeau « modèle » n’est jamais proposé dans le filtre', async () => {
    rendreListe()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    fireEvent.click(screen.getByTestId('cal-filtre-etiquettes-ouvrir'))
    const choix = await screen.findByTestId('cal-filtre-etiquettes-choix')
    await within(choix).findByText('Chantier prioritaire')
    expect(within(choix).queryByText(SYSTEME)).toBeNull()
  })
})
