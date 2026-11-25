import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import CarteParametresTechniques from './CarteParametresTechniques'

vi.mock('../../../features/stock/StructureSelector', () => ({ default: () => null }))
vi.mock('../../../features/ventes/quote/BandeauDeriveLead', () => ({ default: () => null }))

afterEach(() => cleanup())

const ligne = (designation, quantite, extra = {}) => ({ designation, quantite: String(quantite), prix_unitaire: '1000', ...extra })
function rendre({ lines, deuxValeursDim, showSans = true, showAvec = true }) {
  return render(
    <CarteParametresTechniques
      kwcCible="5.5" onKwcCibleChange={() => {}} nbPanneaux="10" onNbPanneauxChange={() => {}}
      panelW="550" dispatchSizing={() => {}} kwp={5.5} panneauxLignes={10} produits={[]}
      modeInstallation="residentiel" showSans={showSans} showAvec={showAvec}
      deuxValeursDim={deuxValeursDim} dayUsage={60} errors={{}} pompageManquants={[]}
      marcheCi={false} fHiver="400" lines={lines} onduleursIncomplets={[]}
    />,
  )
}

// T4-V2-018 — « Recommandé sans batterie : 6 panneaux · 3,30 kWc » (conseil du
// moteur) et, sur le même écran, la taille « Recommandé · Devis officiel ·
// 10 panneaux » (LE devis, définition fondateur des tailles) : deux choses
// différentes sous un même mot. Chacune son nom ; l'écran dit ce que le devis
// chiffre quand il diffère du conseil, et le geste qui chiffre le conseil.
describe('CarteParametresTechniques — conseil du moteur et taille chiffrée (T4-V2-018)', () => {
  const DIM = { sans: { nbPanneaux: 6, kwc: 3.3 }, avec: { nbPanneaux: 10, kwc: 5.5 } }

  it('les lignes communes chiffrent 10 panneaux dans les deux options : l’écart sans batterie est dit', () => {
    rendre({
      deuxValeursDim: DIM,
      lines: [ligne('Panneau mono 550W', 10), ligne('Onduleur réseau Huawei 3kW', 1, { variante: 'sans' }),
        ligne('Onduleur hybride Deye 5kW', 1, { variante: 'avec' }), ligne('Batterie lithium 5kWh', 1, { variante: 'avec' })],
    })
    const bloc = screen.getByTestId('dimensionnement-deux-valeurs').textContent.replace(/\s/g, ' ')
    expect(bloc).toMatch(/Conseillé par le moteur, sans batterie : 6 panneaux · 3,30 kWc/)
    expect(bloc).toMatch(/Conseillé par le moteur, avec batterie : 10 panneaux · 5,50 kWc/)
    expect(screen.getByTestId('dimensionnement-ecart-sans').textContent.replace(/\s/g, ' '))
      .toMatch(/Ce devis chiffre 10 panneaux · 5,50 kWc dans l’option sans batterie .*« Recalculer le dimensionnement »/)
    expect(screen.queryByTestId('dimensionnement-ecart-avec')).toBeNull()
    expect(bloc).not.toMatch(/Recommandé/)
  })

  it('les lignes suivent le conseil : aucun écart affiché', () => {
    rendre({
      deuxValeursDim: DIM,
      lines: [ligne('Panneau mono 550W', 6), ligne('Panneau mono 550W', 4, { variante: 'avec' })],
    })
    expect(screen.queryByTestId('dimensionnement-ecart-sans')).toBeNull()
    expect(screen.queryByTestId('dimensionnement-ecart-avec')).toBeNull()
  })
})
