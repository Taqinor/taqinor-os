import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

/* ============================================================================
   CAL121 — LE PANNEAU DIT LE CHAMP FAUTIF *ET* LE CALCUL QU'IL DÉBLOQUE.
   ----------------------------------------------------------------------------
   LA CHARGE UTILE VIENT DU CONTRAT COMMITTÉ (PACT10/PACT13), jamais d'un objet
   écrit à la main : `calepinage_equipements.json` est le MÊME fichier que la
   vue CAL243 affirme et que `scripts/check_api_shapes.py` compare au
   dictionnaire réellement renvoyé. Si le serveur change de forme, ce test
   casse tout seul.

   LA GARDE CENTRALE : chaque champ listé dans les `champs_manquants` du
   contrat DOIT porter une phrase d'impact. C'est ce qui rend « zéro message
   générique » vérifiable plutôt que promis — le jour où le serveur publie un
   champ de plus, ce test réclame sa phrase.
   ========================================================================== */

const AGREGAT = exempleContrat('calepinage', 'calepinage_equipements')
const AGREGAT_VIDE = exempleContrat('calepinage', 'calepinage_equipements',
  'exemple_vide')

const equipements = vi.fn()
vi.mock('../../../api/calepinageApi', () => ({
  default: { calepinages: { equipements: (...a) => equipements(...a) } },
}))

const { default: FichesIncompletes, impactChamp } = await import('./FichesIncompletes')

const rendre = () => render(
  <MemoryRouter><FichesIncompletes calepinageId={1} /></MemoryRouter>,
)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup() })

const FAMILLES = ['panneau', 'onduleur', 'batterie', 'optimiseur']

describe('CAL121 — chaque champ manquant du contrat porte son impact', () => {
  it.each(FAMILLES)('famille « %s » : tout champ manquant servi a une phrase', (famille) => {
    const equipement = AGREGAT[famille]
    if (!equipement) return // famille `null` au contrat : rien à documenter.
    const champs = equipement.champs_manquants ?? []
    expect(champs.length, `le contrat ne liste aucun manquant pour ${famille}`)
      .toBeGreaterThan(0)
    for (const champ of champs) {
      expect(impactChamp(famille, champ),
        `champ « ${champ} » (${famille}) sans phrase d’impact — un message `
        + 'générique serait exactement ce que CAL121 interdit').toBeTruthy()
    }
  })

  it('les champs RENSEIGNÉS ont eux aussi leur impact documenté', () => {
    // Ils deviendront des « manquants » dès qu'une fiche partielle arrivera :
    // la table doit déjà les couvrir, sinon la première fiche trouée affiche
    // une ligne sans calcul nommé.
    for (const famille of FAMILLES) {
      for (const champ of AGREGAT[famille]?.champs_renseignes ?? []) {
        expect(impactChamp(famille, champ), `${famille}.${champ}`).toBeTruthy()
      }
    }
  })
})

describe('CAL121 — rendu sur une fiche TROUÉE', () => {
  it('nomme chaque champ manquant servi et le calcul qu’il débloque', async () => {
    equipements.mockResolvedValue({ data: AGREGAT })
    rendre()

    expect(await screen.findByTestId('cal-fiches-incompletes')).toBeInTheDocument()
    expect(equipements).toHaveBeenCalledWith(1)

    for (const famille of ['panneau', 'onduleur']) {
      for (const champ of AGREGAT[famille].champs_manquants) {
        const ligne = screen.getByTestId(`cal-fiche-manquant-${famille}-${champ}`)
        expect(ligne).toHaveTextContent(champ)
        expect(ligne).toHaveTextContent(impactChamp(famille, champ))
      }
    }
  })

  it('marque « requis » les champs que le STOCK déclare requis (règle non recopiée)', async () => {
    equipements.mockResolvedValue({ data: AGREGAT })
    rendre()
    await screen.findByTestId('cal-fiches-incompletes')

    // `temp_coeff_pmax_pct_c` est dans `CHAMPS_REQUIS_PAR_TYPE.module` et
    // manque au contrat : il doit porter la mention « requis ».
    expect(AGREGAT.panneau.champs_manquants).toContain('temp_coeff_pmax_pct_c')
    expect(screen.getByTestId('cal-fiche-requis-panneau-temp_coeff_pmax_pct_c'))
      .toHaveTextContent('requis')
    // `noct_c` manque aussi mais n'est PAS requis au catalogue : pas de mention.
    expect(screen.queryByTestId('cal-fiche-requis-panneau-noct_c')).toBeNull()
  })

  it('une famille non retenue est dite telle — jamais « fiche complète »', async () => {
    equipements.mockResolvedValue({ data: AGREGAT })
    rendre()
    await screen.findByTestId('cal-fiches-incompletes')

    expect(AGREGAT.batterie).toBeNull()
    const bloc = screen.getByTestId('cal-fiches-batterie')
    expect(bloc).toHaveTextContent('Aucune batterie retenue')
    expect(bloc).not.toHaveTextContent('Fiche complète')
    expect(screen.queryByTestId('cal-fiches-complet-batterie')).toBeNull()
  })

  it('renvoie vers le catalogue pour compléter la fiche', async () => {
    equipements.mockResolvedValue({ data: AGREGAT })
    rendre()
    await screen.findByTestId('cal-fiches-incompletes')
    expect(screen.getByTestId('cal-fiches-lien-panneau'))
      .toHaveAttribute('href', '/stock')
  })
})

describe('CAL121 — rendu sur un calepinage SANS devis lié (contrat vide)', () => {
  it('dit qu’il n’y a rien à vérifier, sans inventer de fiche complète', async () => {
    equipements.mockResolvedValue({ data: AGREGAT_VIDE })
    rendre()

    expect(await screen.findByTestId('cal-fiches-sans-devis')).toBeInTheDocument()
    expect(AGREGAT_VIDE.devis).toBeNull()
    for (const famille of FAMILLES) {
      expect(screen.getByTestId(`cal-fiches-${famille}`))
        .toHaveTextContent('sur le devis lié')
    }
    expect(screen.queryByText(/Fiche complète/)).toBeNull()
  })
})

describe('CAL121 — états non rendus', () => {
  it('agrégat pas encore lu : rien du tout, jamais un panneau rassurant', () => {
    equipements.mockReturnValue(new Promise(() => {}))
    rendre()
    expect(screen.queryByTestId('cal-fiches-incompletes')).toBeNull()
  })

  it('refus du serveur : le message du serveur, sous une alerte', async () => {
    equipements.mockRejectedValue({ response: { data: { detail: 'Calepinage introuvable.' } } })
    rendre()
    expect(await screen.findByTestId('cal-fiches-erreur'))
      .toHaveTextContent('Calepinage introuvable.')
  })
})

describe('CAL121 — l’écran est ATTEIGNABLE', () => {
  it('le module déclare la route `/calepinage/:id/fiches` avec ses rôles', async () => {
    const { default: config } = await import('../module.config.jsx')
    const route = config.routes.find((r) => r.path === '/calepinage/:id/fiches')
    expect(route, 'route des fiches incomplètes absente du module').toBeTruthy()
    expect(Array.isArray(route.roles) && route.roles.length > 0).toBe(true)
  })
})
