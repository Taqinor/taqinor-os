// CIQ223 — la carte « Économies » C&I est servie par le serveur : seule la
// réponse HTTP est simulée, À LA FORME du contrat `economie_ci.json` ; jamais
// le moteur. Run : npx vitest run src/pages/ventes/generator/CarteEconomieCi.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useState } from 'react'
import { render, screen, waitFor, act } from '@testing-library/react'

const api = vi.hoisted(() => ({ economieCiPreview: vi.fn() }))
vi.mock('../../../api/ventesApi', () => ({ default: api }))

import CarteEconomieCi from './CarteEconomieCi'
import { useApercuEconomieCi } from '../../../features/ventes/quote/hooks/useApercuEconomieCi'
import { saisiesEconomieCi, ECO_CI_VIDE } from '../../../features/ventes/quote/etudeMarcheBloc'
import { ecoCiDepuisSaisies } from '../../../features/ventes/quote/reouverture'
import { documentContrat, exempleContrat } from '../../../test/fixtures/contractSamples'

const CONTRAT = documentContrat('ventes', 'economie_ci')
const apercu = (variante) => ({ donnees: exempleContrat('ventes', 'economie_ci', variante) })

beforeEach(() => { vi.clearAllMocks() })

describe('CIQ223 — CarteEconomieCi', () => {
  it('statut omis ⇒ motif affiché et aucun nombre', () => {
    render(<CarteEconomieCi apercu={apercu('exemple_omis')} />)
    expect(screen.getByTestId('eco-ci-omis'))
      .toHaveTextContent(CONTRAT.exemple_omis.motifs_omission[0])
    expect(screen.queryByTestId('eco-ci-resultat')).toBeNull()
    expect(screen.queryByText(/MAD/)).toBeNull()
  })

  it('base « deux » ⇒ deux colonnes HT et TTC ; VAN omise avec son motif', () => {
    render(<CarteEconomieCi apercu={apercu('exemple')} />)
    expect(CONTRAT.exemple.base).toBe('deux')
    expect(screen.getByText('Économie HT')).toBeInTheDocument()
    expect(screen.getByText('Économie TTC')).toBeInTheDocument()
    const jalons = screen.getByTestId('eco-ci-jalons')
    expect(jalons).toHaveTextContent('HT')
    expect(jalons).toHaveTextContent('TTC')
    expect(screen.getByTestId('eco-ci-van-motif')).toHaveTextContent(CONTRAT.exemple.indicateurs.van_motif)
    expect(screen.getByTestId('eco-ci-indicateurs'))
      .toHaveTextContent(`sur ${CONTRAT.exemple.indicateurs.tri_horizon_ans} ans`)
  })

  it('BT ⇒ mention, aucun montant de revente ; MT ⇒ la revente servie', () => {
    const { unmount } = render(<CarteEconomieCi apercu={apercu('exemple')} />)
    expect(CONTRAT.exemple.revente.statut).toBe('absente_bt')
    expect(screen.getByTestId('eco-ci-revente')).toHaveTextContent(CONTRAT.exemple.revente.mentions[0])
    expect(screen.queryByText(/Revente MT/)).toBeNull()
    unmount()
    render(<CarteEconomieCi apercu={apercu('exemple_industriel_mt')} />)
    expect(screen.getByText(/Revente MT/)).toBeInTheDocument()
  })

  it('saisie rapide ⇒ seule la DERNIÈRE réponse s’affiche (jamais une réponse périmée)', async () => {
    const attentes = []
    api.economieCiPreview.mockImplementation(() => new Promise((ok) => attentes.push(ok)))
    function Harnais() {
      const [n, setN] = useState(1)
      const ap = useApercuEconomieCi({ saisies: { n } }, { delai: 0 })
      return (
        <>
          <button type="button" onClick={() => setN(2)}>suivant</button>
          <CarteEconomieCi apercu={ap} />
        </>
      )
    }
    render(<Harnais />)
    await waitFor(() => expect(attentes).toHaveLength(1))
    act(() => { screen.getByText('suivant').click() })
    await waitFor(() => expect(attentes).toHaveLength(2))
    // la réponse de la saisie DÉPASSÉE arrive après : jetée
    await act(async () => { attentes[0]({ data: exempleContrat('ventes', 'economie_ci', 'exemple_omis') }) })
    expect(screen.queryByTestId('eco-ci-omis')).toBeNull()
    await act(async () => { attentes[1]({ data: exempleContrat('ventes', 'economie_ci', 'exemple') }) })
    expect(await screen.findByTestId('eco-ci-resultat')).toBeInTheDocument()
  })

  it('enregistrer → rouvrir → enregistrer sans toucher = saisies_economie_ci identiques', () => {
    const stocke = CONTRAT.saisies_economie_ci.exemple_industriel_mt
    const ecran = ecoCiDepuisSaisies(stocke)
    expect(saisiesEconomieCi(ecran, { aujourdhui: '2030-01-01' })).toEqual(stocke)
    expect(saisiesEconomieCi(ECO_CI_VIDE)).toBeNull()
  })
})

// ══ CIQ224 — volet INTERNE : offre de financement et offre CSE ══════════════
describe('CIQ224 — VoletInterneEconomieCi', () => {
  it('offre sans source ⇒ le 400 du serveur s’affiche sous le champ nommé', async () => {
    const detail = 'offre_financement.source : le financement se construit seulement depuis une offre ÉCRITE.'
    api.economieCiPreview.mockRejectedValue({ response: { status: 400, data: { detail, champ: 'offre_financement.source' } } })
    function Harnais() {
      const [eco, setEco] = useState({ ...ECO_CI_VIDE })
      const ap = useApercuEconomieCi({ saisies: eco }, { delai: 0 })
      return <CarteEconomieCi apercu={ap} eco={eco} setEcoChamp={(c, v) => setEco((e) => ({ ...e, [c]: v }))} />
    }
    render(<Harnais />)
    expect(await screen.findByTestId('erreur-offre_financement.source')).toHaveTextContent('offre ÉCRITE')
  })

  it('taux vide ⇒ aucun taux affiché ; le volet lit la réponse INTERNE, jamais economie_ci_publique', () => {
    const interne = exempleContrat('ventes', 'economie_ci', 'exemple_industriel_mt')
    expect(interne.financement.taux_annuel_pct ?? null).toBeNull()
    const donnees = { ...interne, economie_ci_publique: { financement: { echeance_mad: 999999 } } }
    render(<CarteEconomieCi apercu={{ donnees }} eco={ECO_CI_VIDE} setEcoChamp={() => {}} />)
    const f = screen.getByTestId('eco-ci-financement')
    expect(f).toHaveTextContent(interne.financement.libelle_client)
    expect(f).not.toHaveTextContent(/Taux écrit/)
    expect(f).not.toHaveTextContent('999')
  })

  it('hors du générateur (aucune saisie possible) : le volet n’est pas rendu', () => {
    render(<CarteEconomieCi apercu={apercu('exemple_industriel_mt')} />)
    expect(screen.queryByTestId('eco-ci-volet-interne')).toBeNull()
  })

  it('enregistrer → rouvrir → enregistrer : offres de financement et CSE identiques', () => {
    const stocke = {
      ...CONTRAT.saisies_economie_ci.exemple_industriel_mt,
      offre_cse_concurrente: { tarif_kwh_ht: 0.95, duree_ans: 20, indexation_pct_an: null, source: 'offre écrite du 01/09/2026' },
    }
    expect(saisiesEconomieCi(ecoCiDepuisSaisies(stocke), { aujourdhui: '2030-01-01' })).toEqual(stocke)
  })
})

