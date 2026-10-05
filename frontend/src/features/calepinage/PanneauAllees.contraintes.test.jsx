// CIQ138 — « Contraintes du site » de l'atelier (assureur, dégagements, îlots,
// source). Les valeurs viennent du contrat COMMITTÉ `calepinage_detail.json`
// (PACT10) : l'exemple FM (`exemple.contraintes_site`) et l'exemple vide.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { documentContrat } from '../../test/fixtures/contractSamples'

const getParametres = vi.fn()
const updateCalepinage = vi.fn()
vi.mock('../../api/calepinageApi', () => ({
  default: {
    parametres: { get: (...a) => getParametres(...a), update: vi.fn() },
    moteur: { calculer: vi.fn() },
    calepinages: { update: (...a) => updateCalepinage(...a) },
  },
}))

const { default: PanneauAllees, PRESET_FM_DS_1_15, MESSAGE_SANS_SOURCE } = await import('./PanneauAllees')

const CONTRAT = documentContrat('calepinage', 'calepinage_detail')
const FM = CONTRAT.exemple.contraintes_site
const VIDE = CONTRAT.exemple_vide.contraintes_site

beforeEach(() => {
  vi.clearAllMocks()
  getParametres.mockResolvedValue({ data: { degagements: {} } })
})
afterEach(() => { cleanup() })

const rendre = (contraintes, props = {}) => render(
  <PanneauAllees entree={null} calepinageId={5} contraintesSite={contraintes} {...props} />,
)
const val = (id) => document.getElementById(id).value

describe('CIQ138 — préréglage FM Global', () => {
  it('le préréglage du front est celui du contrat committé (serveur)', () => {
    expect(PRESET_FM_DS_1_15).toEqual(FM)
  })

  it('FM puis « Charger » ⇒ valeurs du préréglage avec la source citée', async () => {
    rendre(VIDE)
    expect(screen.queryByTestId('ciq138-preset-fm')).not.toBeInTheDocument()
    fireEvent.change(document.getElementById('ciq138-assureur'), { target: { value: 'fm_global' } })
    // Rien n'est chargé tant qu'on n'a pas cliqué.
    expect(val('ciq138-deg-lanterneau')).toBe('')
    fireEvent.click(screen.getByTestId('ciq138-preset-fm'))
    expect(val('ciq138-deg-lanterneau')).toBe('1.8')
    expect(val('ciq138-deg-joint_dilatation')).toBe('1.2')
    expect(val('ciq138-ilot-longueur')).toBe('46')
    expect(val('ciq138-allee-ilot')).toBe('1.2')
    expect(val('ciq138-source-document')).toBe(FM.source.document)
    expect(val('ciq138-source-reference')).toBe(FM.source.reference)
    // La règle appliquée s'affiche à côté de l'obstacle.
    expect(screen.getByTestId('ciq138-regle-ciq138-deg-lanterneau'))
      .toHaveTextContent(FM.regles.lanterneau)
  })

  it('le bouton n’existe que pour FM', () => {
    rendre(VIDE)
    for (const a of ['aucun', 'apsad', 'autre']) {
      fireEvent.change(document.getElementById('ciq138-assureur'), { target: { value: a } })
      expect(screen.queryByTestId('ciq138-preset-fm')).not.toBeInTheDocument()
    }
  })
})

describe('CIQ138 — source obligatoire et identité à la ré-enregistrement', () => {
  it('valeur sans source ⇒ erreur sous le champ, rien n’est envoyé', () => {
    rendre(VIDE)
    fireEvent.change(document.getElementById('ciq138-assureur'), { target: { value: 'apsad' } })
    fireEvent.change(document.getElementById('ciq138-deg-lanterneau'), { target: { value: '2.5' } })
    fireEvent.click(screen.getByTestId('ciq138-enregistrer'))
    expect(screen.getByTestId('ciq138-erreur-source')).toHaveTextContent(MESSAGE_SANS_SOURCE)
    expect(updateCalepinage).not.toHaveBeenCalled()
  })

  it('saisie libre : un nombre tapé n’est ni arrondi ni refusé (step="any")', async () => {
    updateCalepinage.mockResolvedValue({ data: { contraintes_site: {} } })
    rendre(VIDE)
    expect(document.getElementById('ciq138-deg-lanterneau')).toHaveAttribute('step', 'any')
    fireEvent.change(document.getElementById('ciq138-assureur'), { target: { value: 'apsad' } })
    fireEvent.change(document.getElementById('ciq138-deg-rive'), { target: { value: '0.375' } })
    fireEvent.change(document.getElementById('ciq138-source-document'), { target: { value: 'Règle APSAD R81' } })
    fireEvent.click(screen.getByTestId('ciq138-enregistrer'))
    await waitFor(() => expect(updateCalepinage).toHaveBeenCalled())
    const [id, corps] = updateCalepinage.mock.calls[0]
    expect(id).toBe(5)
    expect(corps.contraintes_site.assureur).toBe('apsad')
    expect(corps.contraintes_site.degagements_m).toEqual({ rive: 0.375 })
    expect(corps.contraintes_site.source.document).toBe('Règle APSAD R81')
  })

  it('enregistrer sans rien toucher = objet serveur identique (FM, puis vide)', async () => {
    updateCalepinage.mockImplementation((_id, c) => Promise.resolve({ data: c }))
    for (const serveur of [FM, VIDE]) {
      rendre(serveur)
      fireEvent.click(screen.getByTestId('ciq138-enregistrer'))
      await waitFor(() => expect(updateCalepinage).toHaveBeenCalled())
      expect(updateCalepinage.mock.calls.at(-1)[1]).toEqual({ contraintes_site: serveur })
      cleanup()
      vi.clearAllMocks()
    }
  })

  it('enregistrer le préréglage chargé envoie l’objet du contrat', async () => {
    updateCalepinage.mockImplementation((_id, c) => Promise.resolve({ data: c }))
    rendre(VIDE)
    fireEvent.change(document.getElementById('ciq138-assureur'), { target: { value: 'fm_global' } })
    fireEvent.click(screen.getByTestId('ciq138-preset-fm'))
    fireEvent.click(screen.getByTestId('ciq138-enregistrer'))
    await waitFor(() => expect(updateCalepinage).toHaveBeenCalled())
    expect(updateCalepinage.mock.calls[0][1].contraintes_site).toEqual(FM)
  })

  it('refus serveur sur la source : message FR sous le champ', async () => {
    updateCalepinage.mockRejectedValue({
      response: { status: 400, data: { contraintes_site: [MESSAGE_SANS_SOURCE] } },
    })
    rendre(FM)
    fireEvent.change(document.getElementById('ciq138-deg-rive'), { target: { value: '1' } })
    fireEvent.click(screen.getByTestId('ciq138-enregistrer'))
    expect(await screen.findByTestId('ciq138-erreur-source')).toHaveTextContent('source')
  })

  it('sans calepinageId, la section n’est pas montée', () => {
    render(<PanneauAllees entree={null} />)
    expect(screen.queryByTestId('ciq138-contraintes-site')).not.toBeInTheDocument()
  })
})
