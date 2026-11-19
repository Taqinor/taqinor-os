// CIQ125 — le bloc « profil déclaré » C&I (BlocEtudeReseau), monté UNE fois
// par les panneaux industriel et commercial (QJR637). Tests EXÉCUTÉS : un
// harnais tient l'état comme l'écran (`poserProfilCi`) et le corps envoyé au
// moteur est lu par `corpsCiDepuisProfil` — aucun calcul simulé.
//
// Run : npx vitest run src/pages/ventes/generator/BlocEtudeReseau.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useState } from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import BlocEtudeReseau, {
  MENTION_REVENTE_BT, LIBELLE_REVENTE_MT, CarteTarifFacture, CarteProfilCi,
} from './BlocEtudeReseau'
import CarteResultatCi from './CarteResultatCi'
import ControleBatteriesDepart from './ControleBatteriesDepart'
import { withKeys } from '../../../features/ventes/quote/ligneFabrique'
import PanneauIndustriel from './PanneauIndustriel'
import PanneauCommercial from './PanneauCommercial'
import {
  profilCiVide, poserProfilCi, corpsCiDepuisProfil,
} from '../../../features/ventes/quote/profilCi'
import { documentContrat, exempleContrat, reponseContrat } from '../../../test/fixtures/contractSamples'
import {
  TARIF_SAISIE_VIDE, tarifDeclareDepuisSaisie, erreursTarifDeclare,
} from '../../../features/ventes/quote/etudeMarcheBloc'
import { saisieDepuisTarifDeclare } from '../../../features/ventes/quote/reouverture'

const { ventesApiMock, confirmMock } = vi.hoisted(() => ({
  ventesApiMock: { recomposerBatteriesCi: vi.fn(), patchEtudeParams: vi.fn() },
  confirmMock: vi.fn(),
}))
vi.mock('../../../api/ventesApi', async (importOriginal) => {
  const m = await importOriginal()
  return { ...m, default: { ...m.default, ...ventesApiMock } }
})
vi.mock('../../../ui/confirm', async (importOriginal) => {
  const m = await importOriginal()
  return { ...m, useConfirmDialog: () => ({ confirm: confirmMock }) }
})
beforeEach(() => {
  ventesApiMock.recomposerBatteriesCi.mockReset()
  ventesApiMock.patchEtudeParams.mockReset()
  confirmMock.mockReset()
  confirmMock.mockResolvedValue(true)
})

const EXEMPLE = exempleContrat('ventes', 'etude_ci_preview')

function Harnais({ onProfil, initial, resolues = null }) {
  const [profil, setProfil] = useState(initial || profilCiVide())
  onProfil(profil)
  return (
    <BlocEtudeReseau profil={profil} resolues={resolues}
                     setChamp={(c, v) => setProfil((p) => poserProfilCi(p, c, v))} />
  )
}

const propsPanneau = (marche, extra = {}) => ({
  marche,
  fHiver: '', setFHiver: vi.fn(), fEte: '', setFEte: vi.fn(),
  syncBillEstimator: vi.fn(), onHiverPaste: vi.fn(), onEtePaste: vi.fn(),
  handleEstimerMois: vi.fn(), errors: {}, monthly: Array(12).fill(''),
  setMonth: vi.fn(), distributeur: 'onee', setDistributeur: vi.fn(),
  realBillMode: 'mad', setRealBillMode: vi.fn(),
  realBillMad: '', setRealBillMad: vi.fn(), realBillKwh: '', setRealBillKwh: vi.fn(),
  onRealBillPaste: vi.fn(), consoAnnuelleReelle: null,
  categorieCommerciale: 'non_precisee', setCategorieCommerciale: vi.fn(),
  commercialAnswers: {}, setCommercialAnswer: vi.fn(),
  profilCi: profilCiVide(), setChampCi: vi.fn(), apercuCi: { donnees: EXEMPLE },
  repartitionMt: { pointe: '', pleines: '', creuses: '' }, setPartMt: vi.fn(),
  tarifMtApplique: null,
  ...extra,
})

describe('CIQ125 — BlocEtudeReseau, profil déclaré C&I', () => {
  it('saisir 12 kWh ⇒ le corps porte consommation.kwh_mensuels tels quels', () => {
    let profil = null
    const { container } = render(<Harnais onProfil={(p) => { profil = p }} />)
    const kwh = EXEMPLE.entrees_resolues.kwh_mensuels.valeur
    kwh.forEach((v, i) => {
      fireEvent.change(container.querySelector(`#gen-ci-kwh-${i}`), { target: { value: String(v) } })
    })
    const corps = corpsCiDepuisProfil(profil, { mode: 'commercial' })
    expect(corps.consommation.kwh_mensuels).toEqual(kwh)
    // aucun champ « kWh — pour l'étude » séparé
    expect(container.querySelector('#gen-conso')).toBeNull()
    expect(screen.queryByText(/pour l'étude/)).toBeNull()
  })

  it('aucun jour pré-coché (le week-end n’est jamais supposé)', () => {
    render(<Harnais onProfil={() => {}} />)
    for (let i = 0; i < 7; i += 1) expect(screen.getByTestId(`gen-ci-jour-${i}`)).not.toBeChecked()
  })

  it('tension BT ⇒ case revente désactivée avec la phrase sourcée ; MT ⇒ activable', () => {
    let profil = null
    render(<Harnais onProfil={(p) => { profil = p }} />)
    fireEvent.change(screen.getByTestId('gen-tension'), { target: { value: 'bt' } })
    expect(screen.getByTestId('gen-ci-revente')).toBeDisabled()
    expect(screen.getByTestId('ci-revente-bt')).toHaveTextContent(MENTION_REVENTE_BT)
    fireEvent.change(screen.getByTestId('gen-tension'), { target: { value: 'mt' } })
    expect(screen.getByTestId('gen-ci-revente')).not.toBeDisabled()
    expect(screen.queryByTestId('ci-revente-bt')).toBeNull()
    fireEvent.click(screen.getByTestId('gen-ci-revente'))
    expect(profil.revente).toBe(true)
  })

  it('saisie libre : chaque input number porte step="any", une décimale reste telle quelle', () => {
    let profil = null
    const { container } = render(<Harnais onProfil={(p) => { profil = p }} />)
    for (const input of container.querySelectorAll('input[type=number]')) {
      expect(input.getAttribute('step')).toBe('any')
      expect(input).not.toHaveAttribute('max')
    }
    fireEvent.change(container.querySelector('#gen-ci-puissance'), { target: { value: '72.125' } })
    expect(corpsCiDepuisProfil(poserProfilCi(profil, 'tailleExplicite', '1'), { mode: 'industriel' })
      .puissance_souscrite_kva).toBe(72.125)
  })

  it('chaque valeur retenue par le serveur s’affiche avec sa provenance', () => {
    render(<Harnais onProfil={() => {}} resolues={EXEMPLE.entrees_resolues} />)
    expect(screen.getByTestId('ci-retenu-tension')).toHaveTextContent(/fiche lead — déclaré par le client/)
    expect(screen.getByTestId('ci-retenu-type_pose')).toHaveTextContent(/saisi/)
  })

  it.each(['industriel', 'commercial'])('le panneau %s monte le bloc partagé et la carte résultat', (marche) => {
    const Panneau = marche === 'industriel' ? PanneauIndustriel : PanneauCommercial
    const { container } = render(<Panneau {...propsPanneau(marche)} />)
    expect(screen.getAllByTestId('ci-profil')).toHaveLength(1)
    expect(container.querySelector('#gen-hiver')).toBeNull()
    expect(container.querySelector('#gen-realbill')).toBeNull()
    expect(screen.getByTestId('ci-taille-retenue')).toHaveTextContent(String(EXEMPLE.taille.retenue_kwc))
  })
})

// ══ CIQ222 — le tarif de SA facture (contrat `tarifs_ci.json`) ══════════════
const TARIF_CONTRAT = exempleContrat('ventes', 'tarifs_ci').tarif_declare

function HarnaisTarif({ onTarif, erreurs = {}, tension = 'mt' }) {
  const [tarif, setTarif] = useState({ ...TARIF_SAISIE_VIDE })
  onTarif(tarif)
  return (
    <CarteTarifFacture tarif={tarif} tension={tension} erreurs={erreurs}
                       setTarifChamp={(c, v) => setTarif((t) => ({ ...t, [c]: v }))} />
  )
}

describe('CIQ222 — carte « Tarif de la facture »', () => {
  it('MT : libellé de revente sourcé ; BT : case désactivée et mention', () => {
    render(<Harnais onProfil={() => {}} />)
    fireEvent.change(screen.getByTestId('gen-tension'), { target: { value: 'mt' } })
    expect(screen.getByText(LIBELLE_REVENTE_MT)).toBeInTheDocument()
    fireEvent.change(screen.getByTestId('gen-tension'), { target: { value: 'bt' } })
    expect(screen.getByTestId('gen-ci-revente')).toBeDisabled()
    expect(screen.getByTestId('ci-revente-bt')).toHaveTextContent(MENTION_REVENTE_BT)
  })

  it('saisie MT ⇒ projection tarif_declare exacte (forme du contrat)', () => {
    let tarif = null
    render(<HarnaisTarif onTarif={(t) => { tarif = t }} />)
    expect(screen.getByTestId('ci-tarif-repli')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Contrat'), { target: { value: 'mt_general' } })
    fireEvent.change(screen.getByLabelText('Prix imprimés'), { target: { value: 'ht' } })
    fireEvent.change(screen.getByLabelText('Date de la facture'), { target: { value: '2026-08-31' } })
    const mt = TARIF_CONTRAT.mt
    fireEvent.change(screen.getByLabelText(/Heures de pointe/), { target: { value: String(mt.tarif_pointe) } })
    fireEvent.change(screen.getByLabelText(/Heures pleines/), { target: { value: String(mt.tarif_pleines) } })
    fireEvent.change(screen.getByLabelText(/Heures creuses/), { target: { value: String(mt.tarif_creuses) } })
    fireEvent.change(screen.getByLabelText(/Prime fixe/), { target: { value: String(mt.prime_fixe_kva_an) } })
    fireEvent.change(screen.getByLabelText(/Puissance souscrite/), { target: { value: String(mt.puissance_souscrite_kva) } })
    fireEvent.change(screen.getByLabelText('Source des prix'), { target: { value: 'facture' } })
    const td = tarifDeclareDepuisSaisie(tarif, { aujourdhui: TARIF_CONTRAT.saisi_le })
    expect(td).toEqual(TARIF_CONTRAT)
    expect(screen.queryByTestId('ci-tarif-repli')).toBeNull()
    // option bi-horaire : force motrice SEULEMENT
    expect(screen.queryByTestId('gen-tarif-bi-horaire')).toBeNull()
    fireEvent.change(screen.getByLabelText('Contrat'), { target: { value: 'bt_force_motrice' } })
    expect(screen.getByTestId('gen-tarif-bi-horaire')).toBeInTheDocument()
  })

  it('enregistrer → rouvrir → enregistrer sans toucher = tarif identique', () => {
    const saisie = saisieDepuisTarifDeclare(TARIF_CONTRAT)
    expect(tarifDeclareDepuisSaisie(saisie, { aujourdhui: '2030-01-01' })).toEqual(TARIF_CONTRAT)
    expect(tarifDeclareDepuisSaisie(TARIF_SAISIE_VIDE)).toBeNull()
  })

  it('400 sur tarif_declare.mt.tarif_pointe ⇒ message sous ce champ ; saisie libre step=any', () => {
    const detail = '« etude_params.tarif_declare.mt.tarif_pointe » : valeur négative refusée.'
    render(<HarnaisTarif onTarif={() => {}} erreurs={erreursTarifDeclare(detail)} />)
    fireEvent.change(screen.getByLabelText('Contrat'), { target: { value: 'mt_general' } })
    expect(screen.getByTestId('erreur-tarif-mt.tarif_pointe')).toHaveTextContent('valeur négative refusée')
    for (const input of screen.getByTestId('ci-tarif-mt').querySelectorAll('input[type=number]')) {
      expect(input.getAttribute('step')).toBe('any')
    }
  })
})

describe('ADEV100 — champs repris du lead : badge, valeur éditable, « Retenu » seulement pour le reste', () => {
  const RESOLUES = {
    surface_utile_m2: { valeur: 650, provenance: { origine: 'lead', detail: 'client', date: '2026-09-10' } },
    phases: { valeur: 'tri', provenance: { origine: 'lead', detail: 'client', date: '2026-09-10' } },
  }

  it('un champ semé montre « repris du lead » à la place de « Retenu », et reste éditable', () => {
    let profil = null
    const initial = poserProfilCi(profilCiVide(), 'surfaceUtile', '650')
    const { container } = render(
      <BlocEtudeReseauRepris initial={initial} resolues={RESOLUES} repris={['surfaceUtile']}
                             onProfil={(p) => { profil = p }} />)
    expect(screen.getByTestId('ci-repris-surfaceUtile')).toHaveTextContent('repris du lead')
    expect(screen.queryByTestId('ci-retenu-surface_utile_m2')).toBeNull()
    // un champ NON semé garde l'indication « Retenu »
    expect(screen.getByTestId('ci-retenu-phases')).toHaveTextContent('Retenu')
    expect(screen.queryByTestId('ci-repris-phases')).toBeNull()
    const champ = container.querySelector('#gen-ci-surface')
    expect(champ).not.toBeDisabled()
    expect(champ.value).toBe('650')
    fireEvent.change(champ, { target: { value: '700' } })
    expect(profil.surfaceUtile).toBe('700')
  })

  it('le contrat repris du lead porte son badge dans la carte tarif', () => {
    render(<CarteTarifFacture tarif={{ ...TARIF_SAISIE_VIDE, contrat: 'bt_patente' }} setTarifChamp={() => {}}
                              tension="bt" repris={['contrat']} />)
    expect(screen.getByTestId('ci-repris-contrat')).toHaveTextContent('repris du lead')
    expect(screen.getByLabelText(/Contrat/).value).toBe('bt_patente')
  })

  it('sans rien de semé : aucun badge, les « Retenu » du serveur comme avant', () => {
    render(<BlocEtudeReseauRepris initial={profilCiVide()} resolues={RESOLUES} repris={[]} onProfil={() => {}} />)
    expect(document.querySelector('[data-testid^="ci-repris-"]')).toBeNull()
    expect(screen.getByTestId('ci-retenu-surface_utile_m2')).toBeInTheDocument()
  })
})

function BlocEtudeReseauRepris({ initial, resolues, repris, onProfil }) {
  const [profil, setProfil] = useState(initial)
  onProfil(profil)
  return (
    <BlocEtudeReseau profil={profil} resolues={resolues} repris={repris}
                     setChamp={(c, v) => setProfil((p) => poserProfilCi(p, c, v))} />
  )
}

describe('ADEV101 — carte résultat : 4 chiffres en tête, détails du calcul repliés', () => {
  const ECO = exempleContrat('ventes', 'economie_ci')
  const donnees = (extra = {}) => ({ ...EXEMPLE, economie_ci: ECO, ...extra })

  it('kWc retenue, économie / an HT, autoconsommation et couverture en tête ; le reste replié', () => {
    render(<CarteResultatCi donnees={donnees()} />)
    const synthese = screen.getByTestId('ci-synthese')
    expect(screen.getByTestId('ci-taille-retenue')).toHaveTextContent('kWc')
    expect(screen.getByTestId('ci-economie-an')).toHaveTextContent(/MAD/)
    expect(screen.getByTestId('ci-economie-an')).toHaveTextContent('Économie estimée / an (HT)')
    expect(screen.getByTestId('ci-autoconso')).toHaveTextContent('%')
    expect(screen.getByTestId('ci-couverture')).toHaveTextContent('%')
    expect(synthese).toContainElement(screen.getByTestId('ci-couverture'))
    // le relevé d'ingénieur est sous « Détails du calcul », fermé par défaut
    const details = screen.getByTestId('ci-details-calcul')
    expect(details.open).toBe(false)
    expect(details).toHaveTextContent('Détails du calcul')
    expect(details).toContainElement(screen.getByTestId('ci-paliers'))
    expect(details).toContainElement(screen.getByTestId('ci-raison-arret'))
    expect(synthese).not.toContainElement(screen.getByTestId('ci-paliers'))
    expect(screen.queryByText(/Ratio marginal|Admis/)).toBeNull()
    expect(screen.getByTestId('ci-alertes')).toHaveTextContent('Vendeur seulement')
  })

  it('« retour » seulement quand le serveur le sert ; économie « — » quand elle est omise', () => {
    const { rerender } = render(<CarteResultatCi donnees={donnees()} />)
    const sert = ECO.indicateurs?.retour_ans != null
    expect(Boolean(screen.queryByTestId('ci-retour'))).toBe(sert)
    rerender(<CarteResultatCi donnees={donnees({ economie_ci: { statut: 'omis' } })} />)
    expect(screen.queryByTestId('ci-retour')).toBeNull()
    expect(screen.getByTestId('ci-economie-an')).toHaveTextContent('—')
    rerender(<CarteResultatCi donnees={donnees({ economie_ci: { ...ECO, indicateurs: { ...ECO.indicateurs, retour_ans: 4.2 } } })} />)
    expect(screen.getByTestId('ci-retour')).toHaveTextContent('4,2')
  })

  it('aucune clé interne brute : bornes et raison d’arrêt en français, inconnues sous « Autres »', () => {
    const taille = {
      ...EXEMPLE.taille, raison_arret: 'raison_secrete',
      paliers: [
        { kwc: 5, cout_ht: 1, economie_annuelle: 1, ratio_marginal_annees: 1, admis: true, borne: null },
        { kwc: 10, cout_ht: 1, economie_annuelle: 1, ratio_marginal_annees: 1, admis: false, borne: 'toit' },
        { kwc: 15, cout_ht: 1, economie_annuelle: 1, ratio_marginal_annees: 1, admis: false, borne: 'borne_x' },
      ],
    }
    render(<CarteResultatCi donnees={donnees({ taille })} />)
    const paliers = screen.getByTestId('ci-paliers')
    expect(paliers).toHaveTextContent('non — toit plein')
    expect(paliers).not.toHaveTextContent('(toit)')
    expect(paliers).not.toHaveTextContent('borne_x')
    expect(screen.getByTestId('ci-raison-arret')).not.toHaveTextContent('raison_secrete')
    expect(screen.getByTestId('ci-autres')).toHaveTextContent('raison_secrete, borne_x')
  })
})

describe('R1 — inclinaison retenue par le moteur et taille limitée par le toit (fondateur 28/10/2026)', () => {
  // Les clés du contrat `etude_ci_preview.json` (bloc `taille`), lues telles quelles.
  const TAILLE_RASANTE = {
    inclinaison_retenue_deg: 10,
    taille_limitee_toit: 'taille limitée par le toit : 200 m² déclarés → 35.5 kWc en pose rasante',
  }
  const carte = (taille) => (
    <CarteProfilCi profilCi={profilCiVide()} setChampCi={() => {}} errors={{}}
                   apercuCi={{ donnees: { ...EXEMPLE, taille: { ...EXEMPLE.taille, ...taille } } }} />
  )

  it('10° (pose rasante) et la phrase client, lues telles quelles sur l’aperçu, à côté du champ pente', () => {
    expect(EXEMPLE.taille).toHaveProperty('inclinaison_retenue_deg')
    expect(EXEMPLE.taille).toHaveProperty('taille_limitee_toit')
    const { container } = render(carte(TAILLE_RASANTE))
    expect(container.querySelector('#gen-ci-pente')).not.toBeNull()
    expect(screen.getByTestId('ci-inclinaison-retenue'))
      .toHaveTextContent('Inclinaison retenue par le moteur : 10° (pose rasante)')
    expect(screen.getByTestId('ci-taille-toit'))
      .toHaveTextContent('taille limitée par le toit : 200 m² déclarés → 35.5 kWc en pose rasante')
  })

  it('30° gardé : dit sans « pose rasante » ; rien d’affiché sans hypothèse du moteur', () => {
    const { rerender } = render(carte({ inclinaison_retenue_deg: 30, taille_limitee_toit: null }))
    expect(screen.getByTestId('ci-inclinaison-retenue')).toHaveTextContent('30°')
    expect(screen.getByTestId('ci-inclinaison-retenue')).not.toHaveTextContent('rasante')
    expect(screen.queryByTestId('ci-taille-toit')).toBeNull()
    rerender(carte({ inclinaison_retenue_deg: null, taille_limitee_toit: null }))
    expect(screen.queryByTestId('ci-inclinaison-retenue')).toBeNull()
    expect(screen.queryByTestId('ci-taille-toit')).toBeNull()
  })

  it('la pente saisie part telle quelle dans toit.pente_deg (elle l’emporte sur le moteur) ; vide ⇒ null', () => {
    let profil = null
    const { container } = render(<Harnais onProfil={(p) => { profil = p }} />)
    const corps = (pr) => corpsCiDepuisProfil(poserProfilCi(pr, 'tailleExplicite', '20'), { mode: 'commercial' })
    expect(corps(profil).toit.pente_deg).toBeNull()
    fireEvent.change(container.querySelector('#gen-ci-pente'), { target: { value: '12.5' } })
    expect(corps(profil).toit.pente_deg).toBe(12.5)
  })
})

describe('longueurs de câble saisies à l’écran (fondateur 17/11/2026)', () => {
  it('deux champs, aide « vide : … supposés », décimale gardée telle quelle, vide ⇒ null', () => {
    let profil = null
    const { container } = render(<Harnais onProfil={(p) => { profil = p }} />)
    const ac = container.querySelector('#gen-ci-longueur-ac')
    const dc = container.querySelector('#gen-ci-longueur-dc')
    expect(ac).not.toBeNull()
    expect(dc).not.toBeNull()
    expect(ac.getAttribute('step')).toBe('any')
    expect(screen.getByTestId('gen-ci-longueur-ac-aide')).toHaveTextContent('10 m supposés')
    expect(screen.getByTestId('gen-ci-longueur-dc-aide')).toHaveTextContent('30 m supposés')
    const corps = (pr) => corpsCiDepuisProfil(poserProfilCi(pr, 'tailleExplicite', '20'), { mode: 'commercial' })
    expect(corps(profil).contraintes.longueur_ac_m).toBeNull()
    fireEvent.change(ac, { target: { value: '12.5' } })
    fireEvent.change(dc, { target: { value: '42' } })
    expect(profil.longueurAcM).toBe('12.5')
    expect(profil.longueurDcM).toBe('42')
    expect(ac.value).toBe('12.5')
    expect(corps(profil).contraintes.longueur_ac_m).toBe(12.5)
    expect(corps(profil).contraintes.longueur_dc_m).toBe(42)
  })
})

describe('ADEV102 — les 5 questions de l’appel d’abord, l’analyse sous « Affiner l’étude »', () => {
  const rendre = (extra = {}) => render(
    <CarteProfilCi profilCi={profilCiVide()} setChampCi={() => {}} apercuCi={{}} errors={{}}
                   tarifSaisie={TARIF_SAISIE_VIDE} setTarifChamp={() => {}} {...extra}>
      <p data-testid="bloc-activite">catégorie</p>
    </CarteProfilCi>)
  const avant = (a, b) => Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING)

  it('consommation, contrat, phase, activité/horaires, surface — dans cet ordre, avec la phrase posée au client', () => {
    const { container } = rendre()
    const ordre = [
      container.querySelector('#gen-ci-kwh-0'),
      container.querySelector('#gen-tarif-contrat'),
      container.querySelector('#gen-ci-phases'),
      screen.getByTestId('bloc-activite'),
      container.querySelector('#gen-ci-surface'),
    ]
    ordre.forEach((el) => expect(el).not.toBeNull())
    for (let i = 0; i < ordre.length - 1; i += 1) expect(avant(ordre[i], ordre[i + 1])).toBe(true)
    for (const id of ['conso', 'contrat', 'phase', 'horaires', 'surface']) {
      expect(screen.getByTestId(`ci-aide-${id}`).textContent).toMatch(/^«.+»$/s)
    }
    // aucune note interne ni identifiant de tâche dans les aides
    const aides = ['conso', 'contrat', 'phase', 'horaires', 'surface']
      .map((id) => screen.getByTestId(`ci-aide-${id}`).textContent).join(' ')
    expect(aides).not.toMatch(/(^|\s)[A-Z]{2,5}\d{2,4}(\s|$)|D-[A-Z]+-\d+|\.json|\.py/)
  })

  it('prix imprimés, source des prix, talon, tension, puissance, revente : repliés sous « Affiner l’étude (facultatif) »', () => {
    const { container } = rendre()
    const affiner = screen.getByTestId('ci-affiner')
    expect(affiner.open).toBe(false)
    expect(affiner).toHaveTextContent("Affiner l'étude (facultatif)")
    for (const sel of ['#gen-tarif-base', '#gen-tarif-provenance', '#gen-tarif-date', '#gen-ci-talon',
      '#gen-ci-tension', '#gen-ci-puissance', '[data-testid="gen-ci-revente"]']) {
      const el = container.querySelector(sel)
      expect(el, sel).not.toBeNull()
      expect(affiner.contains(el), sel).toBe(true)
    }
    // les 5 questions, elles, restent hors de la section repliée
    for (const sel of ['#gen-ci-kwh-0', '#gen-tarif-contrat', '#gen-ci-phases', '#gen-ci-surface']) {
      expect(affiner.contains(container.querySelector(sel)), sel).toBe(false)
    }
  })

  it('une erreur serveur sur un détail du tarif ouvre la section (jamais une erreur cachée)', () => {
    rendre({ errors: { tarifDeclare: { base_tarifs: 'Base des prix obligatoire.' } } })
    expect(screen.getByTestId('ci-affiner').open).toBe(true)
    expect(screen.getByTestId('erreur-tarif-base_tarifs')).toBeInTheDocument()
  })
})

describe('D 17/11/2026 — carte résultat : option avec batterie + pointeur vers la fiche', () => {
  const ECO = exempleContrat('ventes', 'economie_ci')
  const donnees = (extra = {}) => ({ ...EXEMPLE, economie_ci: ECO, ...extra })
  const AVEC = {
    kwc: 12.5, cout_vente_ht: 200000, economie_annuelle_mad: 31000, retour_simple_ans: 7.3,
    batterie: { nom: 'Dyness 10', quantite: 2, capacite_utile_kwh: 18 },
  }

  it('option_avec présente : second groupe titré, chiffres, premier groupe étiqueté', () => {
    render(<CarteResultatCi donnees={donnees({ option_avec: AVEC })} />)
    const g = screen.getByTestId('ci-option-avec')
    expect(g).toHaveTextContent('Option avec batterie')
    expect(g).toHaveTextContent('2 × Dyness 10')
    expect(g).toHaveTextContent('12,50 kWc')
    expect(g).toHaveTextContent('Économie estimée / an (HT)')
    expect(g).toHaveTextContent('7,3 ans')
    expect(screen.getByText('Option sans batterie')).toBeInTheDocument()
  })

  it('valeur nulle omise ; sans option_avec aucun groupe ni étiquette', () => {
    const { rerender } = render(<CarteResultatCi donnees={donnees({
      option_avec: { ...AVEC, retour_simple_ans: null } })} />)
    expect(screen.queryByTestId('ci-avec-retour')).toBeNull()
    expect(screen.getByTestId('ci-avec-economie-an')).toBeInTheDocument()
    rerender(<CarteResultatCi donnees={donnees({ option_avec: null })} />)
    expect(screen.queryByTestId('ci-option-avec')).toBeNull()
    expect(screen.queryByText('Option sans batterie')).toBeNull()
  })

  it('alerte avec champ_lead : « À compléter sur la fiche » + libellé ; sans : rien', () => {
    const base = EXEMPLE.alertes[0]
    render(<CarteResultatCi donnees={donnees({ alertes: [
      { ...base, champ_lead: 'equipements_hors_horaires' },
      { ...base, code: 'AUTRE', message: 'Autre', champ_lead: 'colonne_inconnue' },
      { ...base, code: 'SANS', message: 'Sans pointeur', champ_lead: undefined },
    ] })} />)
    const p = screen.getAllByTestId('alerte-champ-lead')
    expect(p).toHaveLength(1)
    expect(p[0]).toHaveTextContent('À compléter sur la fiche : Équipements hors horaires')
    expect(screen.getByTestId('ci-alertes')).not.toHaveTextContent('colonne_inconnue')
  })
})

describe('Batteries au départ — ajout possible sur la carte + contrôle de quantité', () => {
  const ECO = exempleContrat('ventes', 'economie_ci')
  const AVEC = {
    kwc: 12.5, cout_vente_ht: 200000, economie_annuelle_mad: 31000, retour_simple_ans: 7.3,
    batterie: { nom: 'Dyness 10', quantite: 2, capacite_utile_kwh: 18, quantite_recommandee: 6, ajout_possible: 4 },
  }
  const avec = (batterie) => ({ ...EXEMPLE, economie_ci: ECO, option_avec: { ...AVEC, batterie } })

  it('ajout_possible > 0 : « + N batteries possibles plus tard » ; null / 0 / absent : rien', () => {
    const { rerender } = render(<CarteResultatCi donnees={avec(AVEC.batterie)} />)
    expect(screen.getByTestId('ci-avec-ajout')).toHaveTextContent('+ 4 batteries possibles plus tard')
    rerender(<CarteResultatCi donnees={avec({ ...AVEC.batterie, ajout_possible: 1 })} />)
    expect(screen.getByTestId('ci-avec-ajout')).toHaveTextContent('+ 1 batterie possible plus tard')
    for (const v of [0, null, undefined]) {
      rerender(<CarteResultatCi donnees={avec({ ...AVEC.batterie, ajout_possible: v })} />)
      expect(screen.queryByTestId('ci-avec-ajout')).toBeNull()
    }
  })

  const LIGNES = (q = 3) => withKeys([
    { produit: '1', designation: 'Panneau 550 Wc', quantite: 20, prix_unit_ttc: 1000, variante: '' },
    { produit: '7', designation: 'Batterie Dyness 10 kWh', quantite: q, prix_unit_ttc: 9000, variante: 'avec', role_devis: 'batterie' },
  ])
  const DEVIS = (extra = {}) => ({
    id: 42, modifiable: true, is_active: true,
    etude_params: { banque_recommandee: { produit: 7, nom: 'Dyness 10', quantite: 3 } }, ...extra,
  })
  const EXT = {
    retenu: { produit: 5, nom: 'Deye hybride 30 kW', kw_ac: 15, quantite: 2 },
    suffisant: { produit: 4, nom: 'Deye hybride 12 kW', kw_ac: 12, quantite: 1 },
    batteries_max: 3,
  }
  const REPONSE = { devis_id: 42, nb_batteries: 1, quantite_recommandee: 3, nb_panneaux_avec: 14, kwc_avec: 7.7, lignes_changees: true, onduleur_extension: EXT, alertes: [] }
  const ecranDe = (extra = {}) => ({ editDevis: DEVIS(), dirty: false, recharger: vi.fn(), optionAvec: null, ...extra })
  const choisir = async (nom) => {
    await userEvent.click(screen.getByTestId('gen-batteries-depart'))
    await userEvent.click(await screen.findByRole('option', { name: nom }))
  }

  it('le choix liste 1…maximum calculé ; la valeur courante est la quantité de la ligne', async () => {
    render(<ControleBatteriesDepart lines={LIGNES(2)} produits={[]} ecran={ecranDe()} />)
    expect(screen.getByTestId('gen-batteries-depart')).toHaveTextContent('2 batteries')
    expect(screen.getByTestId('gen-batteries-depart-reco')).toHaveTextContent('Recommandé : 3 — 1 à ajouter plus tard')
    await userEvent.click(screen.getByTestId('gen-batteries-depart'))
    const noms = (await screen.findAllByRole('option')).map(o => o.textContent)
    expect(noms).toEqual(['1 batterie', '2 batteries', '3 batteries (maximum calculé)'])
  })

  it('choisir 1 : appelle l’API (id du devis, 1), relit le devis, confirme sous le choix', async () => {
    ventesApiMock.recomposerBatteriesCi.mockResolvedValue({ data: REPONSE })
    const ecran = ecranDe()
    render(<ControleBatteriesDepart lines={LIGNES(3)} produits={[]} ecran={ecran} />)
    await choisir('1 batterie')
    expect(ventesApiMock.recomposerBatteriesCi).toHaveBeenCalledWith(42, 1)
    expect(ecran.recharger).toHaveBeenCalledTimes(1)
    expect(await screen.findByTestId('gen-batteries-depart-ok'))
      .toHaveTextContent('1 batterie sur 3 — panneaux de l’option batterie : 14 (7,70 kWc)')
  })

  it('refus 409 puis 400 : le message du serveur est affiché, aucune relecture, choix inchangé', async () => {
    const ecran = ecranDe()
    render(<ControleBatteriesDepart lines={LIGNES(3)} produits={[]} ecran={ecran} />)
    ventesApiMock.recomposerBatteriesCi.mockRejectedValueOnce({ response: { status: 409, data: { detail: 'Ce devis n’est plus un brouillon.' } } })
    await choisir('2 batteries')
    expect(await screen.findByTestId('gen-batteries-depart-refus')).toHaveTextContent('Ce devis n’est plus un brouillon.')
    ventesApiMock.recomposerBatteriesCi.mockRejectedValueOnce({ response: { status: 400, data: { nb_batteries: ['Au plus 3 batteries.'] } } })
    await choisir('1 batterie')
    expect(await screen.findByText('Au plus 3 batteries.')).toBeInTheDocument()
    expect(ecran.recharger).not.toHaveBeenCalled()
    expect(screen.getByTestId('gen-batteries-depart')).toHaveTextContent('3 batteries')
  })

  it('brouillon local modifié : confirmation d’abord ; refusée ⇒ aucun appel', async () => {
    ventesApiMock.recomposerBatteriesCi.mockResolvedValue({ data: REPONSE })
    confirmMock.mockResolvedValueOnce(false)
    render(<ControleBatteriesDepart lines={LIGNES(3)} produits={[]} ecran={ecranDe({ dirty: true })} />)
    await choisir('1 batterie')
    expect(confirmMock.mock.calls[0][0].description).toBe(
      "Les lignes de l'option batterie vont être recalculées pour 1 batterie. "
      + 'Les modifications non enregistrées des lignes seront perdues.')
    expect(ventesApiMock.recomposerBatteriesCi).not.toHaveBeenCalled()
    confirmMock.mockResolvedValueOnce(true)
    await choisir('2 batteries')
    expect(ventesApiMock.recomposerBatteriesCi).toHaveBeenCalledWith(42, 2)
  })

  it('désactivé avec sa raison : devis non enregistré, devis envoyé', () => {
    const { rerender } = render(<ControleBatteriesDepart lines={LIGNES()} produits={[]} ecran={ecranDe({ editDevis: null })} />)
    expect(screen.getByTestId('gen-batteries-depart')).toBeDisabled()
    expect(screen.getByTestId('gen-batteries-depart-raison')).toHaveTextContent('Enregistrez le devis pour choisir le nombre de batteries')
    rerender(<ControleBatteriesDepart lines={LIGNES()} produits={[]} ecran={ecranDe({ editDevis: DEVIS({ modifiable: false }) })} />)
    expect(screen.getByTestId('gen-batteries-depart')).toBeDisabled()
    expect(screen.getByTestId('gen-batteries-depart-raison')).toHaveTextContent('Devis envoyé : utilisez Réviser')
  })

  it('maximum inconnu : note + choix 1…quantité courante ; repli sur l’aperçu ; deux batteries ou aucune : rien', async () => {
    const sansBanque = ecranDe({ editDevis: DEVIS({ etude_params: {} }) })
    const { rerender } = render(<ControleBatteriesDepart lines={LIGNES(2)} produits={[]} ecran={sansBanque} />)
    expect(screen.getByTestId('gen-batteries-depart-inconnu')).toHaveTextContent('Maximum calculé inconnu sur ce devis — choisir un nombre le recalcule')
    expect(screen.queryByTestId('gen-batteries-depart-reco')).toBeNull()
    await userEvent.click(screen.getByTestId('gen-batteries-depart'))
    expect((await screen.findAllByRole('option')).map(o => o.textContent)).toEqual(['1 batterie', '2 batteries'])
    rerender(<ControleBatteriesDepart key="apercu" lines={LIGNES(2)} produits={[]}
      ecran={{ ...sansBanque, optionAvec: { batterie: { quantite_recommandee: 5 } } }} />)
    expect(screen.getByTestId('gen-batteries-depart-reco')).toHaveTextContent('Recommandé : 5')
    const deux = [...LIGNES(), ...withKeys([{ produit: '8', designation: 'Batterie Deye', quantite: 1, prix_unit_ttc: 1, variante: 'avec', role_devis: 'batterie' }])]
    rerender(<ControleBatteriesDepart key="deux" lines={deux} produits={[]} ecran={ecranDe()} />)
    expect(screen.queryByTestId('gen-batteries-depart')).toBeNull()
    rerender(<ControleBatteriesDepart key="aucune" lines={LIGNES().slice(0, 1)} produits={[]} ecran={ecranDe()} />)
    expect(screen.queryByTestId('gen-batteries-depart')).toBeNull()
  })

  it('onduleur d’extension : phrase « 2 × 15 kW » depuis le devis chargé ; absente si null', () => {
    const avecExt = ecranDe({ editDevis: DEVIS({ etude_params: { banque_recommandee: { produit: 7, quantite: 3 }, etude_ci: { option_avec: { onduleur_extension: EXT } } } }) })
    const { rerender } = render(<ControleBatteriesDepart lines={LIGNES(1)} produits={[]} ecran={avecExt} />)
    expect(screen.getByTestId('gen-onduleur-extension')).toHaveTextContent(
      "Onduleur hybride 2 × 15 kW retenu pour l'extension : jusqu'à 3 batteries (2 à ajouter plus tard). "
      + "Un onduleur de 12 kW suffirait pour l'installation de départ.")
    rerender(<ControleBatteriesDepart lines={LIGNES(1)} produits={[]} ecran={ecranDe({ optionAvec: { onduleur_extension: null } })} />)
    expect(screen.queryByTestId('gen-onduleur-extension')).toBeNull()
  })

  describe('fondateur 19/11/2026 — case « démarrer avec une seule batterie »', () => {
    const CONTRAT = documentContrat('ventes', 'devis_depart_une_batterie')
    const OPTIONS = { batterie_souhaitee: null, om: null, nb_batteries: 3 }
    const devisAvec = (options, etudeCi = {}) => DEVIS({
      etude_params: { banque_recommandee: { produit: 7, quantite: 3 }, options, etude_ci: etudeCi },
    })

    it('2 batteries ou plus : case décochée par défaut ; 1 batterie et case décochée : rien', () => {
      const { rerender } = render(<ControleBatteriesDepart lines={LIGNES(3)} produits={[]} ecran={ecranDe({ editDevis: devisAvec(OPTIONS) })} />)
      expect(screen.getByTestId('gen-phrase-une-batterie')).not.toBeChecked()
      expect(screen.getByText('Indiquer au client le prix pour démarrer avec une seule batterie')).toBeInTheDocument()
      rerender(<ControleBatteriesDepart lines={LIGNES(1)} produits={[]} ecran={ecranDe({ editDevis: devisAvec(OPTIONS) })} />)
      expect(screen.queryByTestId('gen-phrase-une-batterie')).toBeNull()
    })

    it('cocher : PATCH etude-params avec l’objet options COMPLET + la case, puis relecture du devis', async () => {
      ventesApiMock.patchEtudeParams.mockResolvedValue(reponseContrat('ventes', 'devis_depart_une_batterie'))
      const ecran = ecranDe({ editDevis: devisAvec(OPTIONS) })
      render(<ControleBatteriesDepart lines={LIGNES(3)} produits={[]} ecran={ecran} />)
      await userEvent.click(screen.getByTestId('gen-phrase-une-batterie'))
      await waitFor(() => expect(ecran.recharger).toHaveBeenCalledTimes(1))
      expect(ventesApiMock.patchEtudeParams).toHaveBeenCalledWith(42, { options: { ...OPTIONS, phrase_une_batterie: true } })
      expect(confirmMock).not.toHaveBeenCalled()
    })

    it('cochée + bloc du serveur : chiffres SERVIS affichés ; décocher retire la clé', async () => {
      ventesApiMock.patchEtudeParams.mockResolvedValue(reponseContrat('ventes', 'devis_depart_une_batterie'))
      const bloc = CONTRAT.etude_ci_depart_une_batterie
      const ecran = ecranDe({ editDevis: devisAvec({ ...OPTIONS, phrase_une_batterie: true }, { depart_une_batterie: bloc }) })
      render(<ControleBatteriesDepart lines={LIGNES(3)} produits={[]} ecran={ecran} />)
      expect(screen.getByTestId('gen-phrase-une-batterie')).toBeChecked()
      const apercu = screen.getByTestId('gen-phrase-une-batterie-apercu')
      expect(apercu).toHaveTextContent(/Phrase imprimée : 1 batterie, 24 panneaux \(13,20 kWc\)/)
      expect(apercu).toHaveTextContent(/182\s300 MAD TTC/)
      expect(apercu).toHaveTextContent(/151\s916,67 MAD HT/)
      await userEvent.click(screen.getByTestId('gen-phrase-une-batterie'))
      await waitFor(() => expect(ventesApiMock.patchEtudeParams).toHaveBeenCalledWith(42, { options: OPTIONS }))
    })

    it('cochée sans bloc : le refus du serveur (interne) est dit ; 409 du PATCH affiché, aucune relecture', async () => {
      const refus = CONTRAT.etude_ci_depart_une_batterie_refus
      const ecran = ecranDe({ editDevis: devisAvec({ ...OPTIONS, phrase_une_batterie: true }, { depart_une_batterie_refus: refus }) })
      render(<ControleBatteriesDepart lines={LIGNES(3)} produits={[]} ecran={ecran} />)
      expect(screen.getByTestId('gen-phrase-une-batterie-non-imprimee')).toHaveTextContent(refus.message)
      expect(screen.queryByTestId('gen-phrase-une-batterie-apercu')).toBeNull()
      ventesApiMock.patchEtudeParams.mockRejectedValueOnce({ response: { status: 409, data: { detail: 'Ne se décoche que sur un brouillon.', field: 'options.phrase_une_batterie' } } })
      await userEvent.click(screen.getByTestId('gen-phrase-une-batterie'))
      expect(await screen.findByTestId('gen-phrase-une-batterie-refus')).toHaveTextContent('Ne se décoche que sur un brouillon.')
      expect(ecran.recharger).not.toHaveBeenCalled()
    })

    it('brouillon local modifié : confirmation d’abord (refusée ⇒ aucun appel) ; devis envoyé : case désactivée', async () => {
      confirmMock.mockResolvedValueOnce(false)
      const { rerender } = render(<ControleBatteriesDepart lines={LIGNES(3)} produits={[]} ecran={ecranDe({ dirty: true, editDevis: devisAvec(OPTIONS) })} />)
      await userEvent.click(screen.getByTestId('gen-phrase-une-batterie'))
      await waitFor(() => expect(confirmMock).toHaveBeenCalledTimes(1))
      expect(ventesApiMock.patchEtudeParams).not.toHaveBeenCalled()
      rerender(<ControleBatteriesDepart lines={LIGNES(3)} produits={[]} ecran={ecranDe({ editDevis: { ...devisAvec(OPTIONS), modifiable: false } })} />)
      expect(screen.getByTestId('gen-phrase-une-batterie')).toBeDisabled()
    })
  })

  it('carte résultat : phrase sous la tuile batterie quand l’aperçu la sert (kW sans « ,0 »), sinon absente', () => {
    const { rerender } = render(<CarteResultatCi donnees={avec({ ...AVEC.batterie, quantite: 1 })} />)
    expect(screen.queryByTestId('ci-avec-onduleur-extension')).toBeNull()
    const donnees = { ...avec({ ...AVEC.batterie, quantite: 1 }) }
    donnees.option_avec = { ...donnees.option_avec, onduleur_extension: { ...EXT, retenu: { ...EXT.retenu, quantite: 1 } } }
    rerender(<CarteResultatCi donnees={donnees} />)
    expect(screen.getByTestId('ci-avec-onduleur-extension')).toHaveTextContent(
      "Onduleur hybride 15 kW retenu pour l'extension : jusqu'à 3 batteries (2 à ajouter plus tard). Un onduleur de 12 kW suffirait")
  })
})
