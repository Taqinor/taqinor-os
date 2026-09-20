import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

/* ============================================================================
   CAL159 — L'ÉCRAN POMPAGE NE CALCULE RIEN, IL REND CE QUE LE SERVEUR SERT.
   ----------------------------------------------------------------------------
   La charge utile vient du contrat COMMITTÉ `calepinage_pompage.json`
   (PACT10) — le MÊME fichier que la vue CAL159 (moitié serveur) affirme.
   Aucun objet n'est écrit à la main ici : un mock maison serait une seconde
   source de vérité, exactement l'incident du 03/08/2026.

   CE QUE CE TEST TIENT :
     * la courbe et le point de fonctionnement sont ceux du serveur — l'écran
       n'interpole rien (aucun point n'est calculé côté navigateur) ;
     * un champ fautif porte SON message SOUS LUI, et le bandeau le NOMME
       (règle fondateur « jamais un refus générique ») ;
     * un volume non calculable rend « non calculé — pompe sans courbe »,
       jamais un 0 ;
     * la saisie n'est jamais snappée : `noValidate` + `step="any"`.
   ========================================================================== */

const RESULTAT = exempleContrat('calepinage', 'calepinage_pompage')
const RESULTAT_VIDE = exempleContrat('calepinage', 'calepinage_pompage',
  'exemple_vide')

const pompage = vi.fn()
vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: { pompage: (...a) => pompage(...a) } },
}))

const { default: PompagePanel } = await import('./PompagePanel')

const rendre = () => render(
  <MemoryRouter><PompagePanel calepinageId={1} /></MemoryRouter>,
)

const calculer = () => fireEvent.submit(screen.getByTestId('cal-pompage-form'))

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

describe('CAL159 — la saisie du puits, du besoin et du réservoir', () => {
  it('monte les trois groupes de champs, tous libres de saisie', () => {
    rendre()
    for (const groupe of ['puits', 'besoin', 'reservoir']) {
      expect(screen.getByTestId(`cal-pompage-groupe-${groupe}`)).toBeInTheDocument()
    }
    // Règle fondateur : l'écran ne refuse ni n'arrondit jamais une frappe.
    expect(screen.getByTestId('cal-pompage-form')).toHaveAttribute('noValidate')
    const champ = screen.getByLabelText(/Débit souhaité/)
    expect(champ).toHaveAttribute('step', 'any')
  })

  it('envoie au serveur EXACTEMENT ce qui a été tapé, sans conversion', () => {
    pompage.mockResolvedValue({ data: RESULTAT })
    rendre()
    fireEvent.change(screen.getByLabelText(/Débit souhaité/), { target: { value: '8.25' } })
    fireEvent.change(screen.getByLabelText(/Niveau statique/), { target: { value: '40' } })
    calculer()
    expect(pompage).toHaveBeenCalledWith(1, expect.objectContaining({
      debit_souhaite_m3h: '8.25', niveau_statique_m: '40',
    }))
  })
})

describe('CAL159 — le rendu d’un dimensionnement SERVI', () => {
  it('affiche HMT, pompe, variateur et autonomie tels que servis', async () => {
    pompage.mockResolvedValue({ data: RESULTAT })
    rendre()
    calculer()

    expect(await screen.findByTestId('cal-pompage-hmt'))
      .toHaveTextContent(String(RESULTAT.hmt.hmt_m))
    expect(screen.getByTestId('cal-pompage-hmt'))
      .toHaveTextContent(RESULTAT.hmt.source)
    expect(screen.getByTestId('cal-pompage-pompe'))
      .toHaveTextContent(RESULTAT.pompe.nom)
    expect(screen.getByTestId('cal-pompage-variateur'))
      .toHaveTextContent(RESULTAT.variateur.nom)
    expect(screen.getByTestId('cal-pompage-autonomie'))
      .toHaveTextContent(String(RESULTAT.besoin.autonomie_jours))
    expect(screen.getByTestId('cal-pompage-irradiation'))
      .toHaveTextContent(RESULTAT.volumes.source_irradiation)
  })

  it('trace la courbe SERVIE et le point de fonctionnement SERVI', async () => {
    pompage.mockResolvedValue({ data: RESULTAT })
    rendre()
    calculer()

    const svg = await screen.findByTestId('cal-pompage-courbe')
    const polyline = svg.querySelector('polyline')
    // Autant de points tracés que le serveur en a publié — ni plus (pas
    // d'interpolation), ni moins.
    expect(polyline.getAttribute('points').trim().split(/\s+/))
      .toHaveLength(RESULTAT.pompe.courbe.debits_m3h.length)
    expect(screen.getByTestId('cal-pompage-point')).toBeInTheDocument()
  })

  it('rend les DOUZE volumes mensuels, plat et PVGIS', async () => {
    pompage.mockResolvedValue({ data: RESULTAT })
    rendre()
    calculer()

    const table = await screen.findByTestId('cal-pompage-volumes')
    expect(table).toBeInTheDocument()
    for (let i = 0; i < 12; i += 1) {
      const ligne = screen.getByTestId(`cal-pompage-mois-${i}`)
      expect(ligne).toHaveTextContent(String(RESULTAT.volumes.m3_mois_plat[i]))
      expect(ligne).toHaveTextContent(String(RESULTAT.volumes.m3_mois_pvgis[i]))
    }
  })
})

describe('CAL159 — ce que le serveur ne sert PAS n’est jamais inventé', () => {
  it('sans pompe retenue : « non calculé — pompe sans courbe », jamais 0', async () => {
    pompage.mockResolvedValue({ data: RESULTAT_VIDE })
    rendre()
    calculer()

    expect(RESULTAT_VIDE.volumes).toBeNull()
    const absent = await screen.findByTestId('cal-pompage-volumes-absents')
    expect(absent).toHaveTextContent('non calculé — pompe sans courbe')
    expect(screen.queryByTestId('cal-pompage-volumes')).toBeNull()
    expect(screen.queryByTestId('cal-pompage-courbe')).toBeNull()
    // La pompe et le variateur valent `null` au contrat : « — », pas « 0 ».
    expect(screen.getByTestId('cal-pompage-pompe')).toHaveTextContent('—')
    expect(screen.getByTestId('cal-pompage-variateur')).toHaveTextContent('—')
  })

  it('chaque champ fautif porte SON message, et le bandeau le nomme', async () => {
    pompage.mockResolvedValue({ data: RESULTAT_VIDE })
    rendre()
    calculer()

    for (const [cle, message] of Object.entries(RESULTAT_VIDE.erreurs)) {
      const sousChamp = await screen.findByTestId(`cal-pompage-erreur-${cle}`)
      expect(sousChamp).toHaveTextContent(message.slice(0, 30))
      // Le message est posé DANS le champ, pas ailleurs sur l'écran.
      expect(screen.getByTestId(`cal-pompage-champ-${cle}`)).toContainElement(sousChamp)
      expect(document.getElementById(`cal-pompage-${cle}`))
        .toHaveAttribute('aria-invalid', 'true')
    }
    // Le bandeau NOMME les champs et y emmène — jamais « Non enregistré ».
    const bandeau = screen.getByTestId('cal-pompage-bandeau')
    expect(bandeau).toHaveTextContent('Débit souhaité')
    expect(bandeau.querySelector('a[href="#cal-pompage-debit_souhaite_m3h"]'))
      .toBeTruthy()
  })

  it('les avertissements du serveur sont répétés tels quels', async () => {
    pompage.mockResolvedValue({ data: RESULTAT_VIDE })
    rendre()
    calculer()
    expect(await screen.findByTestId('cal-pompage-avertissements'))
      .toHaveTextContent('pompe sans courbe')
  })

  it('refus du serveur : son message, sous une alerte', async () => {
    pompage.mockRejectedValue({ response: { data: { detail: 'Calepinage introuvable.' } } })
    rendre()
    calculer()
    expect(await screen.findByTestId('cal-pompage-refus'))
      .toHaveTextContent('Calepinage introuvable.')
  })
})

describe('CAL159 — l’écran est ATTEIGNABLE', () => {
  it('le module déclare la route `/calepinage/:id/pompage` avec ses rôles', async () => {
    const { default: config } = await import('../module.config.jsx')
    const route = config.routes.find((r) => r.path === '/calepinage/:id/pompage')
    expect(route, 'route de pompage absente du module').toBeTruthy()
    expect(Array.isArray(route.roles) && route.roles.length > 0).toBe(true)
  })
})
