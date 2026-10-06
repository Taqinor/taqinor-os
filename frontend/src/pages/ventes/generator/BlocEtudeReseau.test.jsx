// CIQ125 — le bloc « profil déclaré » C&I (BlocEtudeReseau), monté UNE fois
// par les panneaux industriel et commercial (QJR637). Tests EXÉCUTÉS : un
// harnais tient l'état comme l'écran (`poserProfilCi`) et le corps envoyé au
// moteur est lu par `corpsCiDepuisProfil` — aucun calcul simulé.
//
// Run : npx vitest run src/pages/ventes/generator/BlocEtudeReseau.test.jsx
import { describe, it, expect, vi } from 'vitest'
import { useState } from 'react'
import { render, screen, fireEvent } from '@testing-library/react'

import BlocEtudeReseau, { MENTION_REVENTE_BT } from './BlocEtudeReseau'
import PanneauIndustriel from './PanneauIndustriel'
import PanneauCommercial from './PanneauCommercial'
import {
  profilCiVide, poserProfilCi, corpsCiDepuisProfil,
} from '../../../features/ventes/quote/profilCi'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

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
