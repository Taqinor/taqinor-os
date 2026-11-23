import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { exempleContrat } from '../../../test/fixtures/contractSamples'

/* ============================================================================
   H3 (tour 3) — « Prêt à envoyer ? » : lent n'est pas échoué, l'ordre des listes, `?etape=`.
   Nouveau fichier car : aucun module de test n'existait pour `commun/PretAEnvoyer.jsx` (ses cas
   d'origine vivent dans les tests des écrans qui le montent, d'autres lanes).
   Les charges utiles viennent du contrat committé `calepinage_pret_a_envoyer.json` (PACT13).
   ========================================================================== */

vi.mock('../../../api/calepinageApi', () => ({
  default: {
    calepinages: {
      pretAEnvoyer: vi.fn(),
      explications: vi.fn(() => Promise.resolve({ data: { entrees: [] } })),
    },
  },
}))

import calepinageApi from '../../../api/calepinageApi'
import PretAEnvoyer from './PretAEnvoyer'
import { ongletParCle } from '../atelier/onglets'
import { ETAPE_DU_CODE, MESSAGE_ECHEC, MESSAGE_LENT, rangerControles } from './PretAEnvoyer.helpers'

const pret = exempleContrat('calepinage', 'calepinage_pret_a_envoyer', 'exemple')
const etapeDuCode = exempleContrat('calepinage', 'calepinage_pret_a_envoyer', 'etape_du_code')
const [modeleBloquant, modeleARegler, modeleInfo, modeleOk] = pret.controles
const ligne = (modele, code) => ({ ...modele, code, libelle: `Contrôle ${code}` })
// Électrique : ok, info, à régler, bloquant (l'ordre où le serveur les mettrait sans tri d'écran).
const ELECTRIQUES = [
  ligne(modeleOk, 'tension_froid'), ligne(modeleInfo, 'ratio_dc_ac'),
  ligne(modeleARegler, 'chutes_tension'), ligne(modeleBloquant, 'terre_protections'),
  ligne(modeleOk, 'orientation_mppt'),
]
const servi = (controles) => ({
  data: {
    ...pret, controles, pret: false,
    nombre_bloquants: controles.filter((c) => c.etat === 'bloquant').length,
    nombre_a_regler: controles.filter((c) => c.etat === 'a_regler').length,
  },
})
const delai = () => Object.assign(new Error('timeout of 20000ms exceeded'), { code: 'ECONNABORTED' })
const codesAffiches = (racine) => [...racine.querySelectorAll('[data-testid^="cal-pret-ligne-"]')]
  .map((n) => n.dataset.testid.replace('cal-pret-ligne-', ''))
const monter = (props) => render(<MemoryRouter><PretAEnvoyer testIdCompte="compte" {...props} /></MemoryRouter>)

beforeEach(() => { vi.clearAllMocks() })
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('PretAEnvoyer — ordre des listes (H3)', () => {
  it('rangerControles : bloquant, à régler, bon, info — stable à état égal', () => {
    const ranges = rangerControles([
      { code: 'a', etat: 'info' }, { code: 'b', etat: 'ok' }, { code: 'c', etat: 'a_regler' },
      { code: 'd', etat: 'ok' }, { code: 'e', etat: 'bloquant' }, { code: 'f', etat: 'a_regler' },
    ])
    expect(ranges.map((c) => c.code)).toEqual(['e', 'c', 'f', 'b', 'd', 'a'])
  })

  it('liste courte (Électrique) : les points à régler EN TÊTE, compte inchangé, `?etape=electrique` demandé', async () => {
    calepinageApi.calepinages.pretAEnvoyer.mockResolvedValue(servi(ELECTRIQUES))
    monter({ calepinageId: 101, filtre: 'electrique', court: true })
    expect(await screen.findByTestId('compte')).toHaveTextContent('2 points à régler')
    expect(codesAffiches(screen.getByTestId('cal-pret-a-envoyer')))
      .toEqual(['terre_protections', 'chutes_tension', 'tension_froid', 'orientation_mppt', 'ratio_dc_ac'])
    expect(calepinageApi.calepinages.pretAEnvoyer).toHaveBeenCalledWith(101, { etape: 'electrique' })
  })

  it('ACAL1543 : liste courte, une seule ligne « Régler » dorée (la première), les autres discrètes', async () => {
    const avecCible = (modele, code) => ({ ...ligne(modele, code), cible: { onglet: 'electrique', ...modele.cible } })
    calepinageApi.calepinages.pretAEnvoyer.mockResolvedValue(servi([
      avecCible(modeleARegler, 'chutes_tension'), avecCible(modeleBloquant, 'terre_protections'),
      avecCible(modeleARegler, 'ratio_dc_ac'),
    ]))
    monter({ calepinageId: 105, filtre: 'electrique', court: true })
    await screen.findByTestId('compte')
    const boutons = [...screen.getByTestId('cal-pret-a-envoyer').querySelectorAll('[data-testid^="cal-pret-regler-"]')]
    expect(boutons.length).toBeGreaterThan(1)
    expect(boutons.filter((b) => b.dataset.recommande === 'oui')).toHaveLength(1)
    expect(boutons[0].dataset.recommande).toBe('oui')
  })

  it('par étape (Documents) : le groupe qui porte un point à régler passe en tête, ses points à régler d’abord', async () => {
    const controles = [
      ligne(modeleOk, 'visite_validee'), ligne(modeleOk, 'pentes_confirmees'),
      ligne(modeleInfo, 'ecart_pvgis'), ligne(modeleARegler, 'simulation_fraiche'), ligne(modeleOk, 'dossier_pieces'),
    ]
    calepinageApi.calepinages.pretAEnvoyer.mockResolvedValue(servi(controles))
    monter({ calepinageId: 102, groupes: true })
    await screen.findByTestId('cal-pret-groupe-resultats')
    const groupes = [...document.querySelectorAll('[data-testid^="cal-pret-groupe-"]')].map((n) => n.dataset.testid)
    expect(groupes).toEqual(['cal-pret-groupe-resultats', 'cal-pret-groupe-toit'])
    expect(codesAffiches(screen.getByTestId('cal-pret-groupe-resultats')))
      .toEqual(['simulation_fraiche', 'dossier_pieces', 'ecart_pvgis'])
    expect(calepinageApi.calepinages.pretAEnvoyer).toHaveBeenCalledWith(102, undefined)
  })
})

describe('PretAEnvoyer — lent n’est pas échoué (H3)', () => {
  it('en lecture, par étape : le titre et des lignes grisées, le pied reste ; jamais un bloc gris muet', () => {
    calepinageApi.calepinages.pretAEnvoyer.mockReturnValue(new Promise(() => {}))
    monter({ calepinageId: 103, groupes: true, pied: <button type="button">Générer le devis</button> })
    const carte = screen.getByTestId('cal-pret-a-envoyer')
    expect(within(carte).getByRole('heading', { name: 'Prêt à envoyer ?' })).toBeTruthy()
    expect(within(carte).getByTestId('cel-pret-attente')).toBeTruthy()
    expect(within(carte).getByRole('button', { name: 'Générer le devis' })).toBeTruthy()
  })

  it('délai dépassé sans lecture précédente : « plus de temps que prévu » + Réessayer, jamais « n’a pas pu être lu »', async () => {
    calepinageApi.calepinages.pretAEnvoyer.mockRejectedValueOnce(delai()).mockResolvedValueOnce(servi(ELECTRIQUES))
    monter({ calepinageId: 104, filtre: 'electrique', court: true })
    expect(await screen.findByText(MESSAGE_LENT)).toBeTruthy()
    expect(screen.queryByText(MESSAGE_ECHEC)).toBeNull()
    expect(screen.getByRole('heading', { name: 'Prêt à envoyer ?' })).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: 'Réessayer' }))
    expect(await screen.findByTestId('compte')).toHaveTextContent('2 points à régler')
    expect(calepinageApi.calepinages.pretAEnvoyer).toHaveBeenCalledTimes(2)
    expect(screen.queryByText(MESSAGE_LENT)).toBeNull()
  })

  it('délai dépassé APRÈS une lecture servie : le dernier verdict reste, marqué « lecture de HH:MM »', async () => {
    calepinageApi.calepinages.pretAEnvoyer.mockResolvedValueOnce(servi(ELECTRIQUES))
    const premier = monter({ calepinageId: 105, groupes: true })
    await screen.findByTestId('cal-pret-ligne-chutes_tension')
    premier.unmount()
    calepinageApi.calepinages.pretAEnvoyer.mockRejectedValueOnce(delai())
    monter({ calepinageId: 105, groupes: true })
    expect(await screen.findByText(MESSAGE_LENT)).toBeTruthy()
    expect(screen.getByTestId('cal-pret-ligne-chutes_tension')).toBeTruthy()
    expect(screen.getByText(/^Dernier verdict affiché : lecture de \d{2}:\d{2}\.$/)).toBeTruthy()
    expect(screen.queryByText(MESSAGE_ECHEC)).toBeNull()
  })

  it('un vrai refus du serveur dit toujours « n’a pas pu être lu »', async () => {
    calepinageApi.calepinages.pretAEnvoyer.mockRejectedValueOnce(Object.assign(new Error('500'), { response: { status: 500 } }))
    monter({ calepinageId: 106, groupes: true })
    await waitFor(() => expect(screen.getByTestId('cal-pret-erreur')).toHaveTextContent(MESSAGE_ECHEC))
    expect(screen.queryByText(MESSAGE_LENT)).toBeNull()
  })

  it('le rangement par étape de l’écran est celui du contrat, que le serveur prend pour filtrer `?etape=`', () => {
    expect(ETAPE_DU_CODE).toEqual(etapeDuCode)
  })
})

describe('PretAEnvoyer — « Régler » mène à un écran qui existe (ACAL1703)', () => {
  const Ou = () => {
    const lieu = useLocation()
    return <output data-testid="ou">{`${lieu.pathname}${lieu.search}`}</output>
  }
  const monterRoutes = (id) => render(
    <MemoryRouter initialEntries={[`/calepinage/${id}`]}>
      <Routes>
        <Route path="/calepinage/reglages" element={<Ou />} />
        <Route path="/calepinage/:id" element={<><PretAEnvoyer calepinageId={id} testIdCompte="compte" /><Ou /></>} />
      </Routes>
    </MemoryRouter>,
  )
  const aRegler = (code, cible) => ({ ...ligne(modeleARegler, code), cible: { ...modeleARegler.cible, ...cible } })

  it('Matériel électrique : `?onglet=materiel-electrique`, une clé du registre d’onglets', async () => {
    calepinageApi.calepinages.pretAEnvoyer.mockResolvedValue(servi([
      aRegler('materiel_designe', { etape: 'electrique', onglet: 'materiel-electrique', champ: '' })]))
    monterRoutes(201)
    await userEvent.click(await screen.findByTestId('cal-pret-regler-materiel_designe'))
    expect(screen.getByTestId('ou')).toHaveTextContent('/calepinage/201?onglet=materiel-electrique')
    expect(ongletParCle('materiel-electrique')).not.toBeNull()
  })

  it('les pertes : la page des réglages, jamais `?onglet=reglages` (qui retombait sur « Plan importé »)', async () => {
    calepinageApi.calepinages.pretAEnvoyer.mockResolvedValue(servi([
      aRegler('un_seul_chiffre', { etape: 'resultats', onglet: 'reglages', champ: '' })]))
    monterRoutes(202)
    await userEvent.click(await screen.findByTestId('cal-pret-regler-un_seul_chiffre'))
    expect(screen.getByTestId('ou')).toHaveTextContent(/^\/calepinage\/reglages$/)
  })
})
