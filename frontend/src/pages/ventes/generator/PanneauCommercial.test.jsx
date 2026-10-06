// CIQ131 — la carte commerciale transmet catégorie, réponses et HEURES au
// moteur serveur C&I ; elle affiche l'archétype retenu avec sa source et les
// réponses sans effet sur le calcul. Aucun calcul local, aucune part diurne.
// Run : npx vitest run src/pages/ventes/generator/PanneauCommercial.test.jsx
import { describe, it, expect } from 'vitest'
import { useState } from 'react'
import { render, screen, fireEvent } from '@testing-library/react'

import PanneauCommercial from './PanneauCommercial'
import { profilCiVide, poserProfilCi, corpsCiDepuisProfil } from '../../../features/ventes/quote/profilCi'
import { devisVersEtat, etatVersEcritures } from '../../../features/ventes/quote/etatDevis'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

const KWH = exempleContrat('ventes', 'etude_ci_preview').entrees_resolues.kwh_mensuels.valeur

function Harnais({ onEtat, apercu = null, initiales }) {
  const [profil, setProfil] = useState(() => KWH.reduce(
    (p, v, i) => poserProfilCi(p, `kwhMensuels.${i}`, String(v)), profilCiVide()))
  const [categorie, setCategorie] = useState('boulangerie')
  const [reponses, setReponses] = useState(initiales || {})
  onEtat({ profil, categorie, reponses })
  return (
    <PanneauCommercial
      marche="commercial" errors={{}}
      profilCi={profil} setChampCi={(c, v) => setProfil((p) => poserProfilCi(p, c, v))}
      apercuCi={apercu ? { donnees: apercu } : {}}
      categorieCommerciale={categorie} setCategorieCommerciale={setCategorie}
      commercialAnswers={reponses}
      setCommercialAnswer={(k, v) => setReponses((r) => ({ ...r, [k]: v }))}
    />
  )
}

describe('CIQ131 — PanneauCommercial', () => {
  it('Boulangerie + four électrique + cuisson nocturne 2 h-6 h ⇒ corps conforme au contrat', () => {
    let etat = null
    render(<Harnais onEtat={(e) => { etat = e }}
                    initiales={{ four: 'electrique', cuisson_nocturne: true }} />)
    fireEvent.change(screen.getByLabelText('Heures de cuisson début'), { target: { value: '2' } })
    fireEvent.change(screen.getByLabelText('Heures de cuisson fin'), { target: { value: '6' } })
    const corps = corpsCiDepuisProfil(etat.profil, {
      mode: 'commercial', categorie: etat.categorie, reponses: etat.reponses,
    })
    expect(corps.rythme.categorie_commerciale).toBe('boulangerie')
    expect(corps.rythme.reponses_categorie).toEqual({
      four: 'electrique', cuisson_nocturne: true, heures_cuisson: [[2, 6]],
    })
    // même forme de tête que l'échantillon du contrat
    expect(Object.keys(corps.rythme).sort())
      .toEqual(Object.keys(exempleContrat('ventes', 'etude_ci_preview', 'corps').rythme).sort())
  })

  it('archétype affiché avec sa source et « estimation » ; aucune part diurne', () => {
    const apercu = exempleContrat('ventes', 'etude_ci_preview', 'exemple_kwh_seulement')
    const pc = { ...apercu.profil_charge, reponses_non_consommees: ['occupation_pct'] }
    render(<Harnais onEtat={() => {}} apercu={{ ...apercu, profil_charge: pc }} />)
    const a = screen.getByTestId('ci-archetype')
    expect(a).toHaveTextContent(pc.archetype.cle)
    expect(a).toHaveTextContent(pc.archetype.source)
    if (pc.methode === 'archetype') expect(a).toHaveTextContent('estimation')
    expect(screen.getByTestId('ci-sans-effet')).toHaveTextContent('occupation_pct')
    expect(screen.queryByText(/diurne/i)).toBeNull()
  })

  it('enregistrer → rouvrir → enregistrer sans toucher = objet serveur identique (heures comprises)', () => {
    let profil = profilCiVide()
    profil = poserProfilCi(profil, 'saisieConso', 'annuel')
    profil = poserProfilCi(profil, 'kwhAnnuel', '42000')
    const etat1 = {
      mode: 'commercial', lignes: [], tauxTva: '20.00', discountPct: '0', echeancier: null,
      categorieCommerciale: 'boulangerie',
      commercialAnswers: { four: 'electrique', cuisson_nocturne: true, heures_cuisson: [['2', '6']] },
      profilCi: profil,
    }
    const ecr1 = etatVersEcritures(etat1, { entrees: {} })
    const devis = { id: 3, mode_installation: 'commercial', taux_tva: '20.00', remise_globale: '0', lignes: [], etude_params: ecr1.etude }
    const ecr2 = etatVersEcritures(devisVersEtat(devis), { entrees: {} })
    expect(ecr2.etude).toEqual(ecr1.etude)
    expect(ecr1.etude.rythme.reponses_categorie.heures_cuisson).toEqual([[2, 6]])
  })
})
