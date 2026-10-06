// AGR128 — générateur agricole : besoin, point d'eau, HMT détaillée, cas de
// pompe ; plus de CV / distance / région / culture / énergie pré-remplis.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

import authReducer from '../../../features/auth/store/authSlice'
import ventesReducer from '../../../features/ventes/store/ventesSlice'
import PanneauAgricole from './PanneauAgricole'
import { ECO_POMPAGE_VIDE } from '../../../features/ventes/quote/etudeMarcheBloc'
import { documentContrat } from '../../../test/fixtures/contractSamples'
import {
  POMPAGE_SAISIE_VIDE, etatPompageEcran, poserSaisie,
  construireCorpsPompage, manquantsPompage,
} from '../../../features/ventes/etudePompagePreviewPur'

vi.mock('../../../api/crmApi', () => ({
  default: {
    getClients: vi.fn(() => Promise.resolve({ data: [] })),
    getLeads: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))
vi.mock('../../../api/stockApi', () => ({
  default: { getProduits: vi.fn(() => Promise.resolve({ data: [] })) },
}))
vi.mock('../../../api/parametresApi', () => ({
  default: { getProfile: vi.fn(() => Promise.resolve({ data: {} })) },
}))
vi.mock('../../../api/ventesApi', () => ({
  default: {
    getDevisById: vi.fn(() => Promise.resolve({ data: {} })),
    getParametresGammes: vi.fn(() => Promise.resolve({ data: {} })),
    getOffresTaillesDevis: vi.fn(() => Promise.resolve({ data: { editable: false } })),
    lireOverrides: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))
// L'aperçu serveur n'est jamais appelé tant que l'essentiel manque.
vi.mock('../../../api/axios', () => ({
  default: { post: vi.fn(() => Promise.resolve({ data: null })), get: vi.fn() },
}))

import api from '../../../api/axios'
import { installerCalesJsdom } from '../../../test/fixtures/calesJsdom'
import DevisGenerator from '../DevisGenerator'

beforeEach(() => {
  vi.clearAllMocks()
  installerCalesJsdom()
})

const PROPS_VIDES = {
  marche: 'agricole',
  pompeCv: '', setPompeCv: vi.fn(),
  pompeType: '', setPompeType: vi.fn(), pompeAlim: '', dispatchSizing: vi.fn(),
  pompeHmt: '', setPompeHmt: vi.fn(), pompeDebit: '', setPompeDebit: vi.fn(),
  pompeHeures: '', setPompeHeures: vi.fn(), pompeProfondeur: '',
  setPompeProfondeur: vi.fn(), pompeDistance: '', setPompeDistance: vi.fn(),
  farmSurfaceHa: '', setFarmSurfaceHa: vi.fn(), farmCrop: '', setFarmCrop: vi.fn(),
  farmRegion: '', setFarmRegion: vi.fn(), farmIrrigation: '',
  setFarmIrrigation: vi.fn(),
  ecoPompage: ECO_POMPAGE_VIDE, majEco: vi.fn(), reperesEnergie: {},
  moisCalendrier: [], coherenceAvertit: false,
  farmHmtStatic: '', setFarmHmtStatic: vi.fn(), farmHmtDrawdown: '',
  setFarmHmtDrawdown: vi.fn(),
  pompageSaisie: POMPAGE_SAISIE_VIDE, majPompage: vi.fn(), apercuPompage: null,
}

describe('panneau agricole — formulaire neuf', () => {
  it('région, culture et énergie actuelle sont VIDES (aucun défaut)', () => {
    render(<PanneauAgricole {...PROPS_VIDES} />)
    expect(document.getElementById('gen-farm-region').textContent).toContain('Non renseignée')
    expect(document.getElementById('gen-farm-crop').textContent).toContain('Non renseignée')
    expect(document.getElementById('gen-farm-fuel').textContent).toContain('Non renseignée')
    expect(document.getElementById('gen-distance').value).toBe('')
    // Mode neuve par défaut ? Non : aucun cas de pompe n'est présumé.
    expect(screen.queryByTestId('bloc-plaque')).toBeNull()
  })

  it('une saisie part TELLE QUELLE (jamais arrondie ni rejetée)', () => {
    const majPompage = vi.fn()
    render(<PanneauAgricole {...PROPS_VIDES} majPompage={majPompage}
      pompageSaisie={poserSaisie(POMPAGE_SAISIE_VIDE, 'besoin.mode', 'volume_declare')} />)
    fireEvent.change(document.getElementById('gen-besoin-volume'),
      { target: { value: '135.757' } })
    expect(majPompage).toHaveBeenCalledWith('besoin.volume_m3_jour', '135.757')
    fireEvent.change(document.getElementById('gen-source-niveau-dynamique'),
      { target: { value: '40.05' } })
    expect(majPompage).toHaveBeenCalledWith('source.niveau_dynamique_m', '40.05')
    for (const input of document.querySelectorAll('input[type="number"]')) {
      expect(input.getAttribute('step')).toBe('any')
    }
  })

  it('pompe existante : la plaque (dont le CV) est saisie', () => {
    render(<PanneauAgricole {...PROPS_VIDES}
      pompageSaisie={poserSaisie(POMPAGE_SAISIE_VIDE, 'mode_pompe', 'existante')} />)
    expect(screen.getByTestId('bloc-plaque')).toBeTruthy()
    expect(document.getElementById('gen-pompecv')).toBeTruthy()
  })

  it('pompe neuve : le CV est retiré des entrées', () => {
    render(<PanneauAgricole {...PROPS_VIDES} pompeCv="5.5"
      pompageSaisie={poserSaisie(POMPAGE_SAISIE_VIDE, 'mode_pompe', 'neuve')} />)
    expect(document.getElementById('gen-pompecv')).toBeNull()
    expect(screen.getByTestId('pompe-actuelle-info').textContent).toContain('5.5 CV')
  })
})

describe('chaque saisie apparaît dans le corps de l’aperçu (AGR127)', () => {
  it('besoin, point d’eau, HMT détaillée, distance', () => {
    let s = POMPAGE_SAISIE_VIDE
    for (const [chemin, v] of [
      ['mode_pompe', 'neuve'], ['besoin.mode', 'volume_declare'],
      ['besoin.volume_m3_jour', '135.5'], ['besoin.mois_pointe', '7'],
      ['source.debit_exploitation_m3h', '36'],
      ['source.debit_exploitation_origine', 'foreur'],
      ['source.niveau_dynamique_m', '40'], ['source.diametre_tubage_mm', '150'],
      ['hmt.detail', true], ['hmt.denivele_m', '4'],
      ['hmt.conduite.materiau', 'pehd'], ['hmt.conduite.longueur_m', '350'],
    ]) s = poserSaisie(s, chemin, v)
    const corps = construireCorpsPompage(etatPompageEcran(s, {
      pompeDistance: '25.25', farmHmtStatic: '32', pompeProfondeur: '90',
      pompeDebit: '30', pompeAlim: 'tri', pompeType: 'immergee',
    }))
    expect(corps.besoin.volume_m3_jour).toBe(135.5)
    expect(corps.besoin.mois_pointe).toBe(7)
    expect(corps.besoin.debit_souhaite_m3h).toBe(30)
    expect(corps.source.debit_exploitation_m3h).toBe(36)
    expect(corps.source.debit_exploitation_origine).toBe('foreur')
    expect(corps.source.niveau_statique_m).toBe(32)
    expect(corps.source.profondeur_forage_m).toBe(90)
    expect(corps.hmt.denivele_m).toBe(4)
    expect(corps.hmt.conduite.materiau).toBe('pehd')
    expect(corps.hmt.conduite.longueur_m).toBe(350)
    expect(corps.distance_champ_m).toBe(25.25)
    expect(corps.alim).toBe('tri')
  })

  it('formulaire vide → manquants nommés, aucun corps', () => {
    const etat = etatPompageEcran(POMPAGE_SAISIE_VIDE, {})
    expect(construireCorpsPompage(etat)).toBeNull()
    expect(manquantsPompage(etat)).toEqual([
      'le cas de pompe (neuve ou existante)', 'le besoin en eau',
      "la hauteur (HMT ou niveau d'eau)"])
  })
})

describe('générateur — formulaire agricole vide', () => {
  it('Auto-remplir est désactivé et le message nomme ce qui manque', async () => {
    render(
      <Provider store={configureStore({
        reducer: { auth: authReducer, ventes: ventesReducer },
        preloadedState: { auth: {
          user: { id: 1 }, role: 'normal', role_nom: 'Directeur',
          permissions: [], isAuthenticated: true, loading: false } },
      })}>
        <MemoryRouter initialEntries={['/ventes/devis/nouveau']}>
          <DevisGenerator />
        </MemoryRouter>
      </Provider>,
    )
    const radio = await screen.findByRole('radio', { name: /Agricole/ })
    fireEvent.click(radio)
    await waitFor(() =>
      expect(screen.getByTestId('pompage-manquants').textContent)
        .toContain('le besoin en eau'))
    expect(screen.getByTestId('pompage-manquants').textContent)
      .toContain('le cas de pompe')
    expect(screen.getByTestId('btn-auto-remplir')).toBeDisabled()
    // Aucun appel d'aperçu tant que l'essentiel manque.
    expect(api.post).not.toHaveBeenCalledWith(
      '/ventes/etude-pompage/preview/', expect.anything(), expect.anything())
  })
})

// ── AGR129 — le résultat serveur en direct ─────────────────────────────────
const ICI = path.dirname(fileURLToPath(import.meta.url))
const CONTRAT = JSON.parse(readFileSync(path.resolve(ICI,
  '../../../../../backend/django_core/apps/ventes/contract_samples/etude_pompage_preview.json'),
'utf8'))
const REPONSE = {
  ...CONTRAT.exemple,
  alertes: CONTRAT.exemple_pompe_existante.alertes,
}

describe('résultat serveur (AGR129)', () => {
  it('réponse d’exemple avec 3 alertes → 3 alertes visibles', () => {
    expect(REPONSE.alertes).toHaveLength(3)
    render(<PanneauAgricole {...PROPS_VIDES}
      apercuPompage={{ donnees: REPONSE, chargement: false, erreur: null }} />)
    const alertes = screen.getByTestId('resultat-alertes').querySelectorAll('li')
    expect(alertes).toHaveLength(3)
    expect(screen.getByTestId('resultat-pompe').textContent)
      .toContain(REPONSE.pompe.nom)
    expect(screen.getByTestId('resultat-non-inclus').textContent)
      .toContain('génie civil')
  })

  it('cocher une option → le corps suivant porte l’option', () => {
    const majPompage = vi.fn()
    render(<PanneauAgricole {...PROPS_VIDES} majPompage={majPompage}
      apercuPompage={{ donnees: REPONSE }} />)
    fireEvent.click(screen.getByTestId('option-sonde_niveau'))
    expect(majPompage).toHaveBeenCalledWith('options_cochees', ['sonde_niveau'])
    const saisie = poserSaisie(
      poserSaisie(poserSaisie(POMPAGE_SAISIE_VIDE, 'mode_pompe', 'neuve'),
        'besoin.mode', 'volume_declare'), 'besoin.volume_m3_jour', '135')
    const corps = construireCorpsPompage(etatPompageEcran(
      poserSaisie(saisie, 'options_cochees', ['sonde_niveau']), { pompeHmt: '60' }))
    expect(corps.options_cochees).toEqual(['sonde_niveau'])
  })

  it('les 3 tailles en cartes, Recommandée par défaut ; choisir → taille', () => {
    const majPompage = vi.fn()
    render(<PanneauAgricole {...PROPS_VIDES} majPompage={majPompage}
      apercuPompage={{ donnees: REPONSE }} />)
    expect(screen.getByTestId('taille-recommandee').getAttribute('aria-pressed')).toBe('true')
    fireEvent.click(screen.getByTestId('taille-superieure'))
    expect(majPompage).toHaveBeenCalledWith('taille', 'superieure')
  })

  it('pastilles de couverture : vert 95-120, orange > 120, rouge < 95', () => {
    const donnees = { ...REPONSE, couverture_pct_mois: [99, 169, 80, ...REPONSE.couverture_pct_mois.slice(3)] }
    render(<PanneauAgricole {...PROPS_VIDES} apercuPompage={{ donnees }} />)
    const pastille = (m) => screen.getByTestId(`mois-${m}`).querySelector('[data-pastille]')
      .getAttribute('data-pastille')
    expect(pastille(1)).toBe('vert')
    expect(pastille(2)).toBe('orange')
    expect(pastille(3)).toBe('rouge')
  })

  it('aucune valeur affichée sans réponse serveur', () => {
    render(<PanneauAgricole {...PROPS_VIDES} apercuPompage={null} />)
    expect(screen.queryByTestId('resultat-pompage')).toBeNull()
  })
})

// ── AGR212 — économie déclarée ─────────────────────────────────────────────
describe('économie déclarée (AGR212)', () => {
  const REPERES = { gasoil_litre: { valeur: 11.4, source: 'Relevé station (test)', releve_le: '2026-09-01' } }

  it('repère affiché à côté du champ, champ prix VIDE', () => {
    render(<PanneauAgricole {...PROPS_VIDES} reperesEnergie={REPERES}
      ecoPompage={{ ...ECO_POMPAGE_VIDE, energie: 'diesel', unite: 'litre' }} />)
    expect(screen.getByTestId('repere-energie').textContent).toContain('Relevé station (test)')
    expect(document.getElementById('gen-eco-prix').value).toBe('')
  })

  it('2 000 / mois : jamais « 24 000 » affiché (plus de × 12)', () => {
    render(<PanneauAgricole {...PROPS_VIDES}
      ecoPompage={{ ...ECO_POMPAGE_VIDE, energie: 'diesel', quantite: '2000', periode: 'mois',
        mois: [5, 6, 7, 8] }} />)
    const texte = screen.getByTestId('bloc-economie-declaree').textContent
    expect(texte.includes('24 000') || texte.includes('24000') || texte.includes('24\u202f000')).toBe(false)
  })

  it('mois pré-cochés par le calendrier ; « je confirme » seulement si la garde avertit', () => {
    const majEco = vi.fn()
    const { rerender } = render(<PanneauAgricole {...PROPS_VIDES} majEco={majEco}
      moisCalendrier={[4, 5, 6]} />)
    expect(screen.getByTestId('mois-irr-5')).toBeChecked()
    expect(screen.getByTestId('mois-irr-1')).not.toBeChecked()
    expect(screen.queryByTestId('coherence-confirmee')).toBeNull()
    fireEvent.click(screen.getByTestId('mois-irr-5'))
    expect(majEco).toHaveBeenCalledWith('mois', [4, 6])
    rerender(<PanneauAgricole {...PROPS_VIDES} coherenceAvertit />)
    expect(screen.getByTestId('coherence-confirmee')).toBeTruthy()
  })

  it('tous les champs nombre gardent step="any"', () => {
    render(<PanneauAgricole {...PROPS_VIDES}
      ecoPompage={{ ...ECO_POMPAGE_VIDE, energie: 'electrique' }} />)
    for (const input of document.querySelectorAll('input[type="number"]')) {
      expect(input.getAttribute('step')).toBe('any')
    }
  })
})

// AGR218 (contrat AGR200) — l'attestation d'usage agricole : jamais cochée
// d'office ; chaque geste remonte tel quel ; la valeur stockée se relit.
describe('attestation d’usage agricole (AGR218)', () => {
  const CASE = /atteste l’usage exclusivement agricole/

  it('formulaire neuf : case décochée, date et signataire vides', () => {
    render(<PanneauAgricole {...PROPS_VIDES} />)
    expect(screen.getByLabelText(CASE).checked).toBe(false)
    expect(screen.getByLabelText('Date de l’attestation').value).toBe('')
    expect(screen.getByLabelText('Signataire').value).toBe('')
  })

  it('cocher, dater, signer → majAttestation reçoit chaque valeur telle quelle', () => {
    const majAttestation = vi.fn()
    render(<PanneauAgricole {...PROPS_VIDES} majAttestation={majAttestation} />)
    fireEvent.click(screen.getByLabelText(CASE))
    fireEvent.change(screen.getByLabelText('Date de l’attestation'), { target: { value: '2026-10-02' } })
    fireEvent.change(screen.getByLabelText('Signataire'), { target: { value: 'M. Exploitant' } })
    expect(majAttestation.mock.calls).toEqual([
      ['attestee', true], ['le', '2026-10-02'], ['signataire', 'M. Exploitant'],
    ])
  })

  it('une attestation relue (?edit=) s’affiche cochée, datée, signée', () => {
    const a = documentContrat('ventes', 'devis_replace_lines_entete')
      .corps_agricole.etude_params.attestation_usage_agricole
    render(<PanneauAgricole {...PROPS_VIDES} attestation={a} />)
    expect(screen.getByLabelText(CASE).checked).toBe(true)
    expect(screen.getByLabelText('Date de l’attestation').value).toBe(a.le)
    expect(screen.getByLabelText('Signataire').value).toBe(a.signataire)
  })
})
