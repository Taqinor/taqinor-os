// CIQ223 — la carte « Économies » C&I est servie par le serveur : seule la
// réponse HTTP est simulée, À LA FORME du contrat `economie_ci.json` ; jamais
// le moteur. Run : npx vitest run src/pages/ventes/generator/CarteEconomieCi.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useState } from 'react'
import { render, screen, waitFor, act, fireEvent } from '@testing-library/react'

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

  it('deux options ⇒ économie, retour et TRI de l’option « avec batterie » à côté de l’offre réseau', () => {
    // `option_avec` de l'aperçu C&I (forme décrite dans `etude_ci_preview.json`) :
    // chiffres servis par le serveur, jamais recalculés ici.
    const avec = {
      kwc: 34.32, cout_vente_ht: 267050, economie_annuelle_mad: 63012, retour_simple_ans: 4.3,
      batterie: { nom: 'Batterie 16 kWh', quantite: 3, capacite_utile_kwh: 45.81 },
      economie_ci: { statut: 'calcule', economie_annee1: { total_mad: 63012, total_mad_ttc: 75612.62 } },
      economie_flux: {
        base: 'deux',
        indicateurs: { tri_pct: 21.7967, tri_horizon_ans: 25, retour_ans: 5, retour_dixieme_ans: 4.3 },
        jalons: [{ annee: 10, cumul_mad: 600000 }], jalons_ttc: [{ annee: 10, cumul_mad: 720000 }],
      },
    }
    const { unmount } = render(<CarteEconomieCi apercu={apercu('exemple')} optionAvec={avec} />)
    const bloc = screen.getByTestId('eco-ci-deux-options')
    expect(bloc).toHaveTextContent('Sans batterie')
    expect(bloc).toHaveTextContent('Avec batterie')
    expect(screen.getByTestId('eco-ci-deux-economie')).toHaveTextContent(/63\s?012 MAD/)
    // L'offre réseau ne sert pas le retour au dixième : années pleines des DEUX côtés.
    const sansRetour = CONTRAT.exemple.indicateurs.retour_ans
    expect(CONTRAT.exemple.indicateurs.retour_dixieme_ans).toBeUndefined()
    expect(screen.getByTestId('eco-ci-deux-retour')).toHaveTextContent(`${sansRetour} ans`)
    expect(screen.getByTestId('eco-ci-deux-retour')).toHaveTextContent('5 ans')
    expect(screen.getByTestId('eco-ci-deux-retour')).not.toHaveTextContent('4,3')
    expect(bloc).toHaveTextContent('21,8 % sur 25 ans')
    expect(screen.getByTestId('eco-ci-avec-systeme')).toHaveTextContent('3 × Batterie 16 kWh')
    expect(screen.getByTestId('eco-ci-avec-systeme')).toHaveTextContent('34,32 kWc')
    expect(screen.getByTestId('eco-ci-avec-jalons')).toHaveTextContent('TTC')
    expect(screen.getByText('Détail — option sans batterie')).toBeInTheDocument()
    unmount()
    // Offre réseau omise : l'option batterie reste dite, sans chiffre inventé en face.
    const { unmount: fin } = render(<CarteEconomieCi apercu={apercu('exemple_omis')} optionAvec={avec} />)
    expect(screen.getByTestId('eco-ci-deux-economie')).toHaveTextContent('—')
    expect(screen.getByTestId('eco-ci-deux-economie')).toHaveTextContent(/63\s?012 MAD/)
    fin()
    // Sans option batterie : rien de neuf à l'écran.
    render(<CarteEconomieCi apercu={apercu('exemple')} />)
    expect(screen.queryByTestId('eco-ci-deux-options')).toBeNull()
    expect(screen.queryByText('Détail — option sans batterie')).toBeNull()
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

  it('CEC15 — apport, frais (> 0) et retour de l’offre servis ; omis sans la clé', () => {
    const interne = exempleContrat('ventes', 'economie_ci', 'exemple_industriel_mt')
    const fin = interne.financement
    const { unmount } = render(<CarteEconomieCi apercu={{ donnees: interne }} eco={ECO_CI_VIDE} setEcoChamp={() => {}} />)
    const o = screen.getByTestId('eco-ci-financement-offre')
    expect(o).toHaveTextContent(/Apport à la signature : 180\s000 MAD/)
    expect(o).not.toHaveTextContent(/Frais de l'offre/)
    expect(o).toHaveTextContent(`Retour sur l'offre : ${String(fin.retour_offre_ans).replace('.', ',')} ans`)
    expect(screen.getByTestId('eco-ci-financement')).toHaveTextContent(/écart 8\s529 MAD/)
    unmount()
    const sans = { ...fin, apport_mad: 0, frais_mad: 0 }
    delete sans.retour_offre_ans
    render(<CarteEconomieCi apercu={{ donnees: { ...interne, financement: sans } }} eco={ECO_CI_VIDE} setEcoChamp={() => {}} />)
    expect(screen.queryByTestId('eco-ci-financement-offre')).toBeNull()
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

  it('R1-09 — « 7,5 » dans le taux d’actualisation se lit 7,5 (jamais 75)', () => {
    const setEcoChamp = vi.fn()
    render(<CarteEconomieCi apercu={{}} eco={ECO_CI_VIDE} setEcoChamp={setEcoChamp} />)
    fireEvent.change(document.getElementById('gen-eco-taux'), { target: { value: '7,5' } })
    expect(setEcoChamp).toHaveBeenLastCalledWith(
      'taux_actualisation_client', expect.objectContaining({ valeur_pct: '7.5' }))
  })
})

