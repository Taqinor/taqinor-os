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
  MENTION_REVENTE_BT, LIBELLE_REVENTE_MT, CarteTarifFacture,
} from './BlocEtudeReseau'
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
