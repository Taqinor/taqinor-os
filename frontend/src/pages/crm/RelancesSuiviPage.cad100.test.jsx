import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* CAD100 (moitié écran de CAD87) — les deux tableaux de `mesure_cadence`
   (taux de joint par touche × heure × jour × canal, signatures par nombre
   de touches consommées) rendus TELS QUELS sur « Suivi des relances »,
   en LECTURE SEULE. Charge utile = l'exemple COMMITTÉ
   (`apps/crm/contract_samples/mesure_cadence.json`, PACT10). */
import { exempleContrat, reponseContrat } from '../../test/fixtures/contractSamples'

const MESURE = exempleContrat('crm', 'mesure_cadence')

const isAdminOrResponsableMock = vi.fn(() => false)
vi.mock('../../hooks/useHasPermission', () => ({
  useIsAdminOrResponsable: () => isAdminOrResponsableMock(),
}))
vi.mock('react-redux', () => ({
  useSelector: (sel) => sel({ auth: { user: { id: 42 } } }),
}))

vi.mock('../../api/crmApi', () => ({
  default: {
    getRelanceEtapesSuivi: vi.fn(() => Promise.resolve({
      data: { results: [], resume: { a_faire: 0, en_retard: 0, fait: 0, sautee: 0, annulee: 0 } },
    })),
    getAssignableUsers: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    marquerRelanceEtapeFait: vi.fn(),
    marquerRelanceEtapeSautee: vi.fn(),
    reporterRelanceEtape: vi.fn(),
    getRelanceEtapeMessage: vi.fn(),
    whatsappRelanceEtape: vi.fn(),
    getMesureCadence: vi.fn(),
  },
}))

import crmApi from '../../api/crmApi'
import RelancesSuiviPage from './RelancesSuiviPage'

beforeEach(() => {
  isAdminOrResponsableMock.mockReturnValue(false)
  crmApi.getMesureCadence.mockResolvedValue(reponseContrat('crm', 'mesure_cadence'))
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

function mount() {
  return render(
    <MemoryRouter>
      <RelancesSuiviPage />
    </MemoryRouter>,
  )
}

describe('RelancesSuiviPage — CAD100 (KPI touche × heure × jour × canal)', () => {
  it('rend les deux tableaux à partir de la réponse serveur, telle quelle', async () => {
    mount()
    const panneau = await screen.findByTestId('mesure-cadence-panel')
    const premierCreneau = MESURE.taux_joint_par_creneau[0]
    expect(within(panneau).getByText(`${premierCreneau.taux_joint_pct} %`)).toBeInTheDocument()
    // Scopé à CE tableau (CAD178 ajoute un troisième tableau qui porte AUSSI
    // le libellé « WhatsApp », sur son geste plutôt que sur un canal — une
    // recherche non scopée sur tout le panneau serait ambiguë).
    const tableauCreneaux = within(panneau).getByTestId('mesure-taux-joint')
    expect(within(tableauCreneaux).getByText('WhatsApp')).toBeInTheDocument()
    // index 1 (touches=5, signatures=3) : « 3 » n'entre en collision avec
    // AUCUNE autre cellule exacte du panneau (contrairement à « 1 », qui est
    // aussi l'ordre de la première touche) — getByText exige l'unicité.
    const distribution = MESURE.signatures_par_touches_consommees[1]
    expect(within(panneau).getByText(String(distribution.signatures))).toBeInTheDocument()
  })

  it('rien n\'y est modifiable (lecture seule : aucun input/select dans le panneau)', async () => {
    mount()
    const panneau = await screen.findByTestId('mesure-cadence-panel')
    expect(panneau.querySelectorAll('input, select, button')).toHaveLength(0)
  })

  it('un dénominateur nul reste `null` côté écran : jamais un 0 % fabriqué', async () => {
    crmApi.getMesureCadence.mockResolvedValue({
      data: {
        ...MESURE,
        taux_joint_par_creneau: [{ ...MESURE.taux_joint_par_creneau[0], closes: 0, joints: 0, taux_joint_pct: null }],
      },
    })
    mount()
    const panneau = await screen.findByTestId('mesure-cadence-panel')
    expect(within(panneau).getByText('—')).toBeInTheDocument()
  })

  it('crmApi.getMesureCadence absente du mock (suites existantes) : repli silencieux, jamais un plantage', async () => {
    const original = crmApi.getMesureCadence
    delete crmApi.getMesureCadence
    expect(() => mount()).not.toThrow()
    await waitFor(() => expect(
      screen.getByText(/Mesure de la cadence indisponible/),
    ).toBeInTheDocument())
    crmApi.getMesureCadence = original
  })
})

describe('RelancesSuiviPage — CAD178 (gestes clés par famille d\'appareil)', () => {
  it('rend le troisième tableau, tel quel, à partir de la réponse serveur', async () => {
    mount()
    const panneau = await screen.findByTestId('mesure-cadence-panel')
    const tableau = within(panneau).getByTestId('mesure-gestes-appareil')
    const premiereLigne = MESURE.gestes_par_appareil[0]
    expect(within(tableau).getByText(String(premiereLigne.total))).toBeInTheDocument()
    // « WhatsApp » y figure aussi (comme geste, pas comme canal) — la colonne
    // « Appareil » qui manquait sur les 4 écrans de cadence (constat CAD86).
    expect(within(tableau).getAllByText('Mobile').length).toBeGreaterThan(0)
    expect(within(tableau).getByText('Tablette')).toBeInTheDocument()
  })

  it('AGR541 — tableau « Par segment » : une ligne par segment, `null` → « — », jamais 0 %', async () => {
    mount()
    const tableau = await screen.findByTestId('mesure-par-segment')
    expect(MESURE.par_segment.map((l) => l.segment)).toEqual(
      ['residentiel', 'commercial', 'industriel', 'agricole', 'non_renseigne'])
    for (const ligne of MESURE.par_segment) {
      expect(within(tableau).getByTestId(`mesure-segment-${ligne.segment}`)).toBeInTheDocument()
    }
    const residentiel = within(tableau).getByTestId('mesure-segment-residentiel')
    const res = MESURE.par_segment[0]
    expect(residentiel).toHaveTextContent('Résidentiel')
    expect(residentiel).toHaveTextContent(`${res.taux_joint_pct} %`)
    expect(residentiel).toHaveTextContent(`${res.taux_froid_pct} %`)
    // Non renseigné : délai de signature `null` côté serveur → « — ».
    const nonRenseigne = MESURE.par_segment.find((l) => l.segment === 'non_renseigne')
    expect(nonRenseigne.delai_median_signature_jours).toBeNull()
    const cellules = within(within(tableau).getByTestId('mesure-segment-non_renseigne'))
      .getAllByRole('cell').map((c) => c.textContent)
    expect(cellules).toContain('—')
    expect(cellules.join(' ')).not.toMatch(/\b0 %/)
    expect(within(tableau).getByTestId('aide-incoherents'))
      .toHaveTextContent('leads non agricoles avec un devis agricole — corriger le type sur la fiche')
    expect(tableau.querySelectorAll('input, select, button')).toHaveLength(0)
  })

  it('AGR541 — contrat vide : chaque taux `null` s’affiche « — »', async () => {
    crmApi.getMesureCadence.mockResolvedValue(reponseContrat('crm', 'mesure_cadence', 'exemple_vide'))
    mount()
    const tableau = await screen.findByTestId('mesure-par-segment')
    const agricole = within(tableau).getByTestId('mesure-segment-agricole')
    expect(agricole.textContent).not.toMatch(/%/)
    expect(within(agricole).getAllByText('—').length).toBeGreaterThanOrEqual(4)
  })

  it('aucun geste compté rend « — », jamais une ligne à zéro fabriquée', async () => {
    crmApi.getMesureCadence.mockResolvedValue({
      data: { ...MESURE, gestes_par_appareil: [] },
    })
    mount()
    const panneau = await screen.findByTestId('mesure-cadence-panel')
    expect(screen.queryByTestId('mesure-gestes-appareil')).not.toBeInTheDocument()
    expect(within(panneau).getAllByText('—').length).toBeGreaterThan(0)
  })
})

describe('RelancesSuiviPage — CIQ519 (colonnes C&I du tableau « Par segment »)', () => {
  const ligne = (segment) => MESURE.par_segment.find((l) => l.segment === segment)

  it('rend les quatre colonnes servies par le contrat, telles quelles', async () => {
    mount()
    const tableau = await screen.findByTestId('mesure-par-segment')
    for (const titre of [
      'Attentes par raison', 'Touches converties (e-mail / appel)',
      'Joints par créneau', 'Délais devis → signature (jours)',
    ]) {
      expect(within(tableau).getByText(titre)).toBeInTheDocument()
    }
    const commercial = within(tableau).getByTestId('mesure-segment-commercial')
    const servi = ligne('commercial')
    // Attentes par raison : libellés de la table du parcours, comptes du serveur.
    expect(within(commercial).getByTestId('mesure-attentes-par-raison'))
      .toHaveTextContent(`La direction / le comité : ${servi.attente_accord_par_raison.direction}`)
    expect(within(commercial).getByTestId('mesure-attentes-par-raison'))
      .toHaveTextContent(`La banque / l'organisme de financement : ${servi.attente_accord_par_raison.financement}`)
    expect(within(commercial).getByTestId('mesure-touches-converties')).toHaveTextContent(
      `e-mail : ${servi.touches_converties.email} · appel : ${servi.touches_converties.appel}`)
    expect(within(commercial).getByTestId('mesure-joints-par-creneau')).toHaveTextContent(
      `Matin : ${servi.joints_par_creneau.matin}`)
    // La liste des délais, telle quelle.
    expect(within(commercial).getByTestId('mesure-delais-signature'))
      .toHaveTextContent(servi.delais_signature_jours.join(' · '))
  })

  it('`null` s’affiche « — » : jamais un 0 ni un % fabriqué', async () => {
    mount()
    const tableau = await screen.findByTestId('mesure-par-segment')
    const industriel = within(tableau).getByTestId('mesure-segment-industriel')
    expect(ligne('industriel').joints_par_creneau).toBeNull()
    expect(within(industriel).getByTestId('mesure-joints-par-creneau')).toHaveTextContent('—')
    expect(within(industriel).getByTestId('mesure-delais-signature')).toHaveTextContent('—')
    expect(within(industriel).getByTestId('mesure-attentes-par-raison')).toHaveTextContent('—')
  })

  it('contrat vide : les nouvelles colonnes restent en lecture seule et sans pourcentage', async () => {
    crmApi.getMesureCadence.mockResolvedValue(reponseContrat('crm', 'mesure_cadence', 'exemple_vide'))
    mount()
    const tableau = await screen.findByTestId('mesure-par-segment')
    const commercial = within(tableau).getByTestId('mesure-segment-commercial')
    expect(within(commercial).getByTestId('mesure-joints-par-creneau')).toHaveTextContent('—')
    expect(within(commercial).getByTestId('mesure-delais-signature')).toHaveTextContent('—')
    expect(tableau.querySelectorAll('input, select, button')).toHaveLength(0)
  })
})
