// CIQ135 — la carte INDUSTRIELLE : équipes, registres MT, cos φ, courbe mesurée.
// Tests EXÉCUTÉS : un harnais tient l'état comme l'écran (`poserProfilCi`), le
// corps envoyé au moteur est lu par `corpsCiDepuisProfil`, la réponse vient du
// contrat `etude_ci_preview.json` (jamais une charge utile tapée à la main).
//
// Run : npx vitest run src/pages/ventes/generator/PanneauIndustriel.test.jsx
import { describe, it, expect } from 'vitest'
import { useState } from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

import { CarteIndustrielleMt } from './PanneauIndustriel'
import {
  profilCiVide, poserProfilCi, corpsCiDepuisProfil, entreesCiV2, profilDepuisEtude,
} from '../../../features/ventes/quote/profilCi'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

const EXEMPLE_MT = exempleContrat('ventes', 'etude_ci_preview', 'exemple_industriel_mt')

function Harnais({ onProfil, initial, apercuCi = null }) {
  const [profil, setProfil] = useState(initial || profilCiVide())
  onProfil(profil)
  return (
    <CarteIndustrielleMt profilCi={profil} apercuCi={apercuCi}
                         setChampCi={(c, v) => setProfil((p) => poserProfilCi(p, c, v))} />
  )
}

const CTX = { mode: 'industriel' }

describe('CIQ135 — CarteIndustrielleMt', () => {
  it('12 mois de registres + équipes ⇒ corps conforme au contrat', () => {
    let profil = null
    render(<Harnais onProfil={(p) => { profil = p }} />)
    fireEvent.change(screen.getByLabelText('Équipes de travail'), { target: { value: '2x8' } })
    fireEvent.change(screen.getByLabelText('Heure de début (h)'), { target: { value: '6' } })
    for (let i = 0; i < 12; i += 1) {
      fireEvent.change(screen.getByTestId(`gen-ci-reg-${i}-pointe`), { target: { value: `${1000 + i}.5` } })
      fireEvent.change(screen.getByTestId(`gen-ci-reg-${i}-pleines`), { target: { value: '4000' } })
      fireEvent.change(screen.getByTestId(`gen-ci-reg-${i}-creuses`), { target: { value: '2500' } })
      fireEvent.change(screen.getByTestId(`gen-ci-reg-${i}-puissance`), { target: { value: '180.25' } })
      fireEvent.change(screen.getByTestId(`gen-ci-reg-${i}-kvarh`), { target: { value: '900' } })
    }
    fireEvent.change(screen.getByLabelText('cos φ connu'), { target: { value: '0.82' } })
    const corps = corpsCiDepuisProfil(profil, CTX)
    const registres = corps.consommation.registres_mt
    expect(registres).toHaveLength(12)
    expect(Object.keys(registres[0]).sort()).toEqual(
      ['cos_phi', 'creuses_kwh', 'kvarh', 'pleines_kwh', 'pointe_kwh', 'puissance_atteinte_kw'])
    expect(registres[0]).toMatchObject({ pointe_kwh: 1000.5, puissance_atteinte_kw: 180.25, cos_phi: 0.82 })
    expect(corps.rythme.equipes).toBe('2x8')
    expect(corps.rythme.debut_equipe_h).toBe(6)
    // Les clés du corps existent toutes dans le contrat partagé.
    const contrat = exempleContrat('ventes', 'etude_ci_preview', 'corps')
    for (const cle of Object.keys(corps.rythme)) expect(Object.keys(contrat.rythme)).toContain(cle)
  })

  it('les cellules sont libres : step="any", rien n\'est arrondi', () => {
    let profil = null
    render(<Harnais onProfil={(p) => { profil = p }} />)
    const cellule = screen.getByTestId('gen-ci-reg-3-puissance')
    expect(cellule.getAttribute('step')).toBe('any')
    fireEvent.change(cellule, { target: { value: '123.456' } })
    expect(profil.registresMt[3].puissance).toBe('123.456')
  })

  it('fichier importé ⇒ `courbe_mesuree` transmis (contenu envoyé au parseur serveur)', async () => {
    let profil = null
    render(<Harnais onProfil={(p) => { profil = p }} />)
    const csv = 'date;kwh\n2025-01-01 00:00;12.5\n'
    const fichier = new File([csv], 'compteur.csv', { type: 'text/csv' })
    fireEvent.change(screen.getByTestId('gen-ci-courbe-fichier'), { target: { files: [fichier] } })
    await waitFor(() => expect(profil.courbe).not.toBeNull())
    const corps = corpsCiDepuisProfil(profil, CTX)
    expect(corps.courbe_mesuree).toEqual({ contenu: csv, source: 'compteur.csv' })
    expect(screen.getByTestId('ci-courbe-importee').textContent).toContain('compteur.csv')
  })

  it('un fichier Excel est refusé avec la consigne d\'export CSV (aucune courbe posée)', async () => {
    let profil = null
    render(<Harnais onProfil={(p) => { profil = p }} />)
    const fichier = new File(['x'], 'releve.xlsx')
    fireEvent.change(screen.getByTestId('gen-ci-courbe-fichier'), { target: { files: [fichier] } })
    await waitFor(() => expect(screen.getByTestId('ci-courbe-erreur')).toBeTruthy())
    expect(profil.courbe).toBeNull()
  })

  it('alerte interne affichée avec son badge « vendeur seulement » + méthode retenue', () => {
    const apercu = {
      donnees: {
        ...EXEMPLE_MT,
        alertes: [
          ...EXEMPLE_MT.alertes,
          { code: 'cos_phi_apres_pv', champ: 'cos_phi', niveau: 'alerte', interne: true,
            message: 'cos φ après PV sous le seuil ONEE 0,8 — estimation interne.' },
          { code: 'incoherence_equipes_registres', champ: 'rythme.equipes', niveau: 'alerte',
            interne: true, message: 'Équipes déclarées et registres incohérents.' },
        ],
      },
    }
    render(<Harnais onProfil={() => {}} apercuCi={apercu} />)
    const liste = screen.getByTestId('ci-alertes-industriel')
    expect(liste.textContent).toContain('Vendeur seulement')
    expect(liste.textContent).toContain('cos φ après PV')
    expect(liste.textContent).toContain('Équipes déclarées et registres incohérents')
    expect(screen.getByTestId('ci-methode-retenue').textContent).toContain('registres de la facture MT')
  })

  it('enregistrer → rouvrir → enregistrer sans toucher = objet serveur identique', () => {
    let profil = null
    render(<Harnais onProfil={(p) => { profil = p }} />)
    fireEvent.change(screen.getByLabelText('Équipes de travail'), { target: { value: '3x8' } })
    fireEvent.change(screen.getByLabelText('Heure de début (h)'), { target: { value: '22' } })
    for (let i = 0; i < 12; i += 1) {
      fireEvent.change(screen.getByTestId(`gen-ci-reg-${i}-pointe`), { target: { value: '1200' } })
      fireEvent.change(screen.getByTestId(`gen-ci-reg-${i}-pleines`), { target: { value: '3000.5' } })
      fireEvent.change(screen.getByTestId(`gen-ci-reg-${i}-creuses`), { target: { value: '2000' } })
    }
    fireEvent.change(screen.getByLabelText('cos φ connu'), { target: { value: '0.9' } })
    const premier = entreesCiV2(profil, CTX)
    const rouvert = profilDepuisEtude(JSON.parse(JSON.stringify(premier)))
    expect(entreesCiV2(rouvert, CTX)).toEqual(premier)
  })

  it('courbe stockée : rouverte telle quelle', () => {
    const courbe = { contenu: 'date;kwh\n2025-01-01 00:00;1\n', source: 'compteur.csv' }
    let profil = profilCiVide()
    profil = poserProfilCi(profil, 'courbe', courbe)
    const premier = entreesCiV2(profil, CTX)
    expect(premier.courbe_mesuree).toEqual(courbe)
    expect(entreesCiV2(profilDepuisEtude(JSON.parse(JSON.stringify(premier))), CTX)).toEqual(premier)
  })
})
