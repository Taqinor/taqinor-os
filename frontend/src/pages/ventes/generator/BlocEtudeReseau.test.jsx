// CIQ125 — le bloc « profil déclaré » C&I (BlocEtudeReseau), monté UNE fois
// par les panneaux industriel et commercial (QJR637). Tests EXÉCUTÉS : un
// harnais tient l'état comme l'écran (`poserProfilCi`) et le corps envoyé au
// moteur est lu par `corpsCiDepuisProfil` — aucun calcul simulé.
//
// Run : npx vitest run src/pages/ventes/generator/BlocEtudeReseau.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { useState } from 'react'
import { render, screen, fireEvent } from '@testing-library/react'

import BlocEtudeReseau, {
  MENTION_REVENTE_BT, LIBELLE_REVENTE_MT, CarteTarifFacture, CarteProfilCi,
} from './BlocEtudeReseau'
import CarteResultatCi from './CarteResultatCi'
import PanneauIndustriel from './PanneauIndustriel'
import PanneauCommercial from './PanneauCommercial'
import {
  profilCiVide, poserProfilCi, corpsCiDepuisProfil,
} from '../../../features/ventes/quote/profilCi'
import { exempleContrat } from '../../../test/fixtures/contractSamples'
import {
  TARIF_SAISIE_VIDE, tarifDeclareDepuisSaisie, erreursTarifDeclare,
} from '../../../features/ventes/quote/etudeMarcheBloc'
import { saisieDepuisTarifDeclare } from '../../../features/ventes/quote/reouverture'

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
