import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* AGR613 — recette POMPAGE : chantier agricole → dialogue pompage ;
   résidentiel → fiche IEC 62446-1 inchangée. La charge utile vient du contrat
   partagé `recette_pompage.json` (jamais un mock écrit à la main). */

const api = vi.hoisted(() => ({
  getRecettePompage: vi.fn(),
  ouvrirRecettePompage: vi.fn(),
  updateRecettePompage: vi.fn(),
  getRecette: vi.fn(),
  getEtapesChantier: vi.fn(),
  getPackRemise: vi.fn(),
}))

vi.mock('../../api/installationsApi', () => ({ default: api }))

import ChantierGateTimeline from './ChantierGateTimeline'
import RecettePompageDialog from './RecettePompageDialog'
import { exempleContrat } from '../../test/fixtures/contractSamples'

const EXEMPLE = exempleContrat('installations', 'recette_pompage')
const VIDE = exempleContrat('installations', 'recette_pompage', 'exemple_vide')
const SANS_COURBE = exempleContrat('installations', 'recette_pompage', 'exemple_sans_courbe')

const ETAPES = {
  installation: 214,
  reference: 'CH-214',
  etape_courante: 'montage_mecanique',
  etapes: [{
    cle: 'montage_mecanique', libelle: 'Montage mécanique', ordre: 1,
    bloquant: true, satisfait: true, raisons: [], id: 2,
    statut_legacy: 'installe', courante: true,
  }],
}

beforeEach(() => {
  api.getEtapesChantier.mockResolvedValue({ data: ETAPES })
  api.getRecette.mockResolvedValue({ data: { installation: 1, record: null } })
  api.getRecettePompage.mockResolvedValue({ data: VIDE })
  api.getPackRemise.mockResolvedValue({
    data: { installation: 214, pieces: [], complet: false, persiste: false },
  })
  api.ouvrirRecettePompage.mockResolvedValue({ data: EXEMPLE })
  api.updateRecettePompage.mockResolvedValue({ data: EXEMPLE })
})

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('ChantierGateTimeline — AGR613 aiguillage pompage / IEC', () => {
  it('chantier agricole → dialogue de recette pompage, pas la fiche IEC', async () => {
    const user = userEvent.setup()
    render(<ChantierGateTimeline installationId={214}
                                 installation={{ id: 214, type_installation: 'agricole' }} />)
    await waitFor(() => expect(api.getRecettePompage).toHaveBeenCalledWith(214))
    expect(api.getRecette).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: /Ouvrir la fiche de recette/ }))
    expect(await screen.findByText('Recette de pompage (IEC 62253)', { selector: '[role="dialog"] *' }))
      .toBeInTheDocument()
    expect(screen.queryByText('Fiche de recette (IEC 62446-1)')).not.toBeInTheDocument()
  })

  it('chantier résidentiel → fiche IEC 62446-1 inchangée', async () => {
    const user = userEvent.setup()
    render(<ChantierGateTimeline installationId={1}
                                 installation={{ id: 1, type_installation: 'residentiel' }} />)
    await waitFor(() => expect(api.getRecette).toHaveBeenCalledWith(1))
    expect(api.getRecettePompage).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: /Ouvrir la fiche de recette/ }))
    expect(await screen.findByText('Fiche de recette (IEC 62446-1)')).toBeInTheDocument()
  })
})

describe('RecettePompageDialog — AGR613', () => {
  const ouvrir = (record, extra = {}) => render(
    <RecettePompageDialog installationId={214} record={record}
                          onClose={() => {}} {...extra} />,
  )

  it('affiche promesse figée, débit attendu, écart et « seuil non saisi »', () => {
    ouvrir(EXEMPLE.record)
    const bloc = screen.getByTestId('recette-pompage-comparaison')
    expect(within(bloc).getByTestId('cmp-promis')).toHaveTextContent('30.5 m³/h à 58.7 m')
    expect(within(bloc).getByTestId('cmp-attendu')).toHaveTextContent('29.9 m³/h')
    expect(within(bloc).getByTestId('cmp-ecart')).toHaveTextContent('-5.2 %')
    expect(within(bloc).getByTestId('cmp-seuil'))
      .toHaveTextContent('seuil non saisi en Paramètres')
    expect(within(bloc).getByTestId('cmp-omissions')).toHaveTextContent('aucun verdict')
  })

  it('pompe sans courbe : motif affiché, aucun débit attendu inventé', () => {
    ouvrir(SANS_COURBE.record)
    expect(screen.getByTestId('cmp-attendu')).toHaveTextContent('—')
    expect(screen.getByTestId('cmp-omissions'))
      .toHaveTextContent('pompe sans courbe constructeur')
  })

  it('hors seuil → commentaire signalé obligatoire sous son champ', () => {
    const record = {
      ...EXEMPLE.record,
      comparaison: {
        ...EXEMPLE.record.comparaison,
        seuil_ecart_pct: 3, hors_seuil: true, commentaire_requis: true,
      },
    }
    ouvrir(record)
    expect(screen.getByTestId('commentaire-requis')).toBeInTheDocument()
    expect(screen.getByText('(obligatoire)')).toBeInTheDocument()
  })

  it('formulaire noValidate, tous les nombres en step="any"', () => {
    ouvrir(EXEMPLE.record)
    const form = document.querySelector('form')
    expect(form).toHaveAttribute('novalidate')
    const nombres = form.querySelectorAll('input[type="number"]')
    expect(nombres.length).toBeGreaterThan(8)
    nombres.forEach((n) => expect(n).toHaveAttribute('step', 'any'))
  })

  it('enregistrer → rouvrir → enregistrer sans toucher = PATCH identique', async () => {
    const user = userEvent.setup()
    const premier = render(<RecettePompageDialog installationId={214}
                                                 record={EXEMPLE.record} onClose={() => {}} />)
    await user.click(screen.getByRole('button', { name: /Enregistrer la fiche/ }))
    await waitFor(() => expect(api.updateRecettePompage).toHaveBeenCalledTimes(1))
    premier.unmount()
    const rendu = api.updateRecettePompage.mock.results[0]
    const { data } = await rendu.value
    ouvrir(data.record)
    await user.click(screen.getByRole('button', { name: /Enregistrer la fiche/ }))
    await waitFor(() => expect(api.updateRecettePompage).toHaveBeenCalledTimes(2))
    const [id1, p1] = api.updateRecettePompage.mock.calls[0]
    const [id2, p2] = api.updateRecettePompage.mock.calls[1]
    expect(id1).toBe(37)
    expect(id2).toBe(id1)
    expect(p2).toEqual(p1)
    expect(p1.hmt_mesuree_m).toBe(60.2)
    expect(p1.debit_mesure_m3h).toBe(28.9)
  })

  it('fiche absente : créée à la première sauvegarde seulement', async () => {
    const user = userEvent.setup()
    ouvrir(null)
    expect(api.ouvrirRecettePompage).not.toHaveBeenCalled()
    await user.type(screen.getByLabelText('HMT mesurée (m)'), '61.37')
    await user.click(screen.getByRole('button', { name: /Enregistrer la fiche/ }))
    await waitFor(() => expect(api.updateRecettePompage).toHaveBeenCalled())
    expect(api.ouvrirRecettePompage).toHaveBeenCalledWith(214)
    expect(api.updateRecettePompage.mock.calls[0][1].hmt_mesuree_m).toBe('61.37')
  })

  it('erreur serveur affichée sous le champ fautif', async () => {
    const user = userEvent.setup()
    api.updateRecettePompage.mockRejectedValueOnce({
      response: { status: 400, data: {
        commentaire_ecart: ['Écart de -12 % au-delà du seuil de la société : commentaire requis'],
      } },
    })
    ouvrir(EXEMPLE.record)
    await user.click(screen.getByRole('button', { name: /Enregistrer la fiche/ }))
    const erreur = await screen.findByTestId('erreur-commentaire_ecart')
    expect(erreur).toHaveTextContent('commentaire requis')
  })

  it('verrouillée → lecture seule, pas de bouton Enregistrer', () => {
    ouvrir({ ...EXEMPLE.record, verrouillee: true })
    expect(screen.queryByRole('button', { name: /Enregistrer la fiche/ })).not.toBeInTheDocument()
    expect(screen.getByLabelText('HMT mesurée (m)')).toBeDisabled()
  })
})
