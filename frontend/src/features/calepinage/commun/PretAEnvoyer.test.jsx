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
      get: vi.fn(),
    },
  },
}))

import calepinageApi from '../../../api/calepinageApi'
import PretAEnvoyer from './PretAEnvoyer'
import { libelleEtat } from '../electrique/etatVerdict'
import RailGuide from './RailGuide'
import { ongletParCle } from '../atelier/onglets'
import { ETAPE_DU_CODE, MESSAGE_ECHEC, MESSAGE_LENT, rangerControles, valeurAffichee } from './PretAEnvoyer.helpers'

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

  // R6-N3 — « Dossier électrique — Bloquant : 2 » à côté de « 6 points à régler », « 6 à régler » (rail) et « Contrôles · 4 bons » :
  // les trois derniers comptent des CONTRÔLES (une même liste servie) ; le premier compte les POINTS DU DOSSIER — il le dit.
  it('R6-N3 — badge, rail et « Contrôles · N bons » lisent la même liste ; « Bloquant : 2 » dit qu’il compte des points du dossier', async () => {
    const dossier = { ...ligne(modeleBloquant, 'verdict_electrique'), libelle: 'Dossier électrique', valeur_texte: 'Bloquant : 2' }
    calepinageApi.calepinages.pretAEnvoyer.mockResolvedValue(servi([
      dossier,
      ligne(modeleARegler, 'chutes_tension'), ligne(modeleARegler, 'terre_protections'), ligne(modeleARegler, 'ratio_dc_ac'),
      ligne(modeleARegler, 'orientation_mppt'), ligne(modeleARegler, 'compatibilite_equipements'),
      ligne(modeleOk, 'tension_froid'), ligne(modeleOk, 'tension_chaud'), ligne(modeleOk, 'courant_entree'),
      ligne(modeleOk, 'materiel_designe'),
    ]))
    render(
      <MemoryRouter>
        <RailGuide vertical calepinageId={108} etapeActive="electrique" onChoisir={() => {}}
          etats={{}} manque={[]} />
        <PretAEnvoyer testIdCompte="compte" calepinageId={108} filtre="electrique" court />
      </MemoryRouter>,
    )
    expect(await screen.findByTestId('compte')).toHaveTextContent('6 points à régler')
    await waitFor(() => expect(screen.getByTestId('cal-etape-electrique')).toHaveTextContent('6 à régler'))
    expect(screen.getByTestId('cal-pret-bons')).toHaveTextContent('Contrôles · 4 bons sur 10')
    // 6 + 4 : les lignes de la carte sont exactement les contrôles comptés.
    expect(codesAffiches(screen.getByTestId('cal-pret-a-envoyer'))).toHaveLength(10)
    expect(screen.getByTestId('cal-pret-ligne-verdict_electrique')).toHaveTextContent('Bloquant : 2 points du dossier')
    expect(screen.getByTestId('cal-pret-ligne-chutes_tension')).not.toHaveTextContent('du dossier')
  })

  it('R6-N3 — une seule formulation : source unique, vue liste historique et vue groupée disent « points du dossier », une seule fois par ligne', async () => {
    expect(libelleEtat('bloquant', 2).libelle).toBe('Bloquant : 2 points du dossier')
    expect(libelleEtat('bloquant', 1).libelle).toBe('Bloquant : 1 point du dossier')
    const dossier = { ...ligne(modeleBloquant, 'verdict_electrique'), libelle: 'Dossier électrique', valeur_texte: 'Bloquant : 2' }
    calepinageApi.calepinages.pretAEnvoyer.mockResolvedValue(servi([dossier]))
    monter({ calepinageId: 109 })
    const ligneDossier = await screen.findByTestId('cal-pret-ligne-verdict_electrique')
    expect(ligneDossier.textContent.match(/Bloquant : 2 points du dossier/g)).toHaveLength(1)
    expect(ligneDossier).not.toHaveTextContent('Bloquant : 2 Bloquant')
  })

  it('R6-N3 — valeurAffichee : singulier, autre état ou autre contrôle laissés tels que servis', () => {
    expect(valeurAffichee({ code: 'verdict_electrique', etat: 'bloquant', valeur_texte: 'Bloquant : 1' })).toBe('Bloquant : 1 point du dossier')
    // le champ structuré `points` prime sur le chiffre du texte servi, qui n'est que le repli
    expect(valeurAffichee({ code: 'verdict_electrique', etat: 'bloquant', valeur_texte: 'Bloquant : 9', points: [{}, {}, {}] }))
      .toBe('Bloquant : 3 points du dossier')
    expect(valeurAffichee({ code: 'verdict_electrique', etat: 'a_regler', valeur_texte: 'À compléter' })).toBe('À compléter')
    expect(valeurAffichee({ code: 'tension_froid', etat: 'bloquant', valeur_texte: 'Bloquant : 2' })).toBe('Bloquant : 2')
    expect(valeurAffichee({ code: 'verdict_electrique', etat: 'bloquant', valeur_texte: 'Autre phrase' })).toBe('Autre phrase')
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

  // T4-B4-010 — Documents : la tuile Toit du rail se disait « fait » (parcours) pendant que « Prêt à envoyer » listait
  // deux points Toit à régler. Le rail lit la MÊME lecture que la liste : « 2 à régler », plus jamais « fait ».
  it('le rail des étapes lit la même liste : Toit « 2 à régler », jamais « fait » quand la liste a des points Toit', async () => {
    calepinageApi.calepinages.pretAEnvoyer.mockResolvedValue(servi([
      ligne(modeleARegler, 'pentes_confirmees'), ligne(modeleARegler, 'obstacle_hors_pan'), ligne(modeleOk, 'pans_vides'),
      ligne(modeleOk, 'kwc_coherent'),
    ]))
    render(
      <MemoryRouter>
        <RailGuide vertical calepinageId={107} etapeActive="documents" onChoisir={() => {}}
          etats={{ toit: 'fait', panneaux: 'fait' }} manque={[]} />
        <PretAEnvoyer testIdCompte="compte" calepinageId={107} groupes />
      </MemoryRouter>,
    )
    await screen.findByTestId('cal-pret-groupe-toit')
    const toit = screen.getByTestId('cal-etape-toit')
    await waitFor(() => expect(toit).toHaveTextContent('2 à régler'))
    expect(toit.dataset.etat).not.toBe('fait')
    // Panneaux : rien à régler dans la liste, l'état servi reste.
    expect(screen.getByTestId('cal-etape-panneaux').dataset.etat).toBe('fait')
    expect(screen.getByTestId('cal-etape-panneaux')).not.toHaveTextContent('à régler')
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

describe('PretAEnvoyer par étape — quinze contrôles sans défilement interne (ACAL1725)', () => {
  // Quinze contrôles : six à régler (Électrique et Résultats), neuf bons (Toit et Panneaux n'ont aucun point).
  const quinze = () => [
    ...['visite_validee', 'approbation_a_jour', 'pentes_confirmees', 'obstacle_hors_pan'].map((c) => ligne(modeleOk, c)),
    ...['kwc_coherent', 'taille_sans_facture'].map((c) => ligne(modeleOk, c)),
    ...['verdict_electrique', 'materiel_designe', 'chutes_tension', 'terre_protections'].map((c) => ligne(modeleARegler, c)),
    ...['tension_froid', 'orientation_mppt'].map((c) => ligne(modeleOk, c)),
    ligne(modeleARegler, 'simulation_fraiche'), ligne(modeleARegler, 'ecart_pvgis'), ligne(modeleOk, 'dossier_pieces'),
  ]

  it('un groupe sans point à régler se replie sur une ligne « Toit — 4 bons », ses contrôles restent lisibles', async () => {
    calepinageApi.calepinages.pretAEnvoyer.mockResolvedValue(servi(quinze()))
    monter({ calepinageId: 301, groupes: true })
    const toit = await screen.findByTestId('cal-pret-groupe-toit')
    expect(toit.tagName).toBe('DETAILS')
    expect(toit).not.toHaveAttribute('open')
    expect(within(toit).getByText('Toit — 4 bons')).toBeTruthy()
    expect(screen.getByTestId('cal-pret-groupe-panneaux')).toHaveTextContent('Panneaux — 2 bons')
    expect(codesAffiches(toit)).toHaveLength(4)
    await userEvent.click(within(toit).getByText('Toit — 4 bons'))
    expect(toit).toHaveAttribute('open')
  })

  it('les groupes qui portent un point à régler restent dépliés, en tête, avec leurs six points ; aucune hauteur fixe', async () => {
    calepinageApi.calepinages.pretAEnvoyer.mockResolvedValue(servi(quinze()))
    monter({ calepinageId: 302, groupes: true })
    await screen.findByTestId('cal-pret-groupe-electrique')
    for (const cle of ['electrique', 'resultats']) {
      expect(screen.getByTestId(`cal-pret-groupe-${cle}`).tagName).not.toBe('DETAILS')
    }
    const groupes = screen.getByTestId('cal-pret-groupes')
    expect([...groupes.children].map((n) => n.dataset.testid))
      .toEqual(['cal-pret-groupe-electrique', 'cal-pret-groupe-resultats', 'cal-pret-groupe-toit', 'cal-pret-groupe-panneaux'])
    expect(groupes.querySelectorAll('li[data-etat="a_regler"]')).toHaveLength(6)
    // plus de dix contrôles : un groupe déplié ne montre que ses points, le reste suit sur une ligne repliée
    const reste = within(screen.getByTestId('cal-pret-groupe-electrique')).getByText('Autres contrôles — 2 bons').closest('details')
    expect(reste).not.toHaveAttribute('open')
    expect(codesAffiches(reste)).toEqual(['tension_froid', 'orientation_mppt'])
    expect(within(screen.getByTestId('cal-pret-groupe-resultats')).getByText('Autres contrôles — 1 bon')).toBeTruthy()
    expect(groupes.style.height).toBe('')
    expect(groupes.style.maxHeight).toBe('')
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

  it('ACAL1704 : matériel choisi, fiche incomplète — la vraie cause est SUR la ligne, pas « non désigné »', async () => {
    calepinageApi.calepinages.pretAEnvoyer.mockResolvedValue(servi([{
      ...aRegler('materiel_designe', { etape: 'electrique', onglet: 'materiel-electrique', champ: '' }),
      valeur_texte: 'Fiche incomplète : tension au point de puissance maximale (Vmp) du module',
      cause: 'module : tension au point de puissance maximale (Vmp)',
      geste: 'Compléter la fiche du module',
    }]))
    monterRoutes(203)
    const ligneMateriel = await screen.findByTestId('cal-pret-ligne-materiel_designe')
    expect(ligneMateriel).toHaveTextContent('Fiche incomplète : tension au point de puissance maximale (Vmp) du module')
    expect(ligneMateriel).toHaveTextContent('module : tension au point de puissance maximale (Vmp)')
    expect(ligneMateriel).not.toHaveTextContent(/non désigné/i)
  })

  it('les pertes : la page des réglages, jamais `?onglet=reglages` (qui retombait sur « Plan importé »)', async () => {
    calepinageApi.calepinages.pretAEnvoyer.mockResolvedValue(servi([
      aRegler('un_seul_chiffre', { etape: 'resultats', onglet: 'reglages', champ: '' })]))
    monterRoutes(202)
    await userEvent.click(await screen.findByTestId('cal-pret-regler-un_seul_chiffre'))
    expect(screen.getByTestId('ou')).toHaveTextContent(/^\/calepinage\/reglages$/)
  })
})

/* T4-U4-014 — un calepinage SANS lead (créé depuis un client) : le « ? » de « Facture ou taille souhaitée renseignée »
   ne renvoie plus à « la facture du lead » qui n'existe pas ; le geste proposé est faisable. */
describe('PretAEnvoyer — un calepinage sans lead ne parle pas du lead (T4-U4-014)', () => {
  const taille = {
    ...ligne(modeleARegler, 'taille_sans_facture'), libelle: 'Facture ou taille souhaitée renseignée',
    valeur_texte: 'le toit est rempli : 9 kWc', cause: 'aucune facture ni taille souhaitée : le système n’est pas dimensionné sur la consommation',
    geste: 'Saisir la facture', cible: { etape: 'toit', onglet: '', champ: 'facture' },
  }
  const registreTaille = { entrees: [{ cle: 'controle.taille_sans_facture', phrase: 'Vérifie la facture du lead.', geste: 'Si ce n’est pas bon : saisissez la facture du lead.', valeurs: {} }] }

  it('sans lead : ni « facture du lead » ni « Saisir la facture » ; le geste faisable est dit', async () => {
    calepinageApi.calepinages.pretAEnvoyer.mockResolvedValue(servi([taille]))
    calepinageApi.calepinages.explications.mockResolvedValue({ data: registreTaille })
    calepinageApi.calepinages.get.mockResolvedValue({ data: { id: 205, lead: null, client: 9 } })
    monter({ calepinageId: 205, groupes: true })
    const ligneTaille = await screen.findByTestId('cal-pret-ligne-taille_sans_facture')
    await userEvent.click(within(ligneTaille).getByRole('button', { name: 'Pourquoi : Facture ou taille souhaitée renseignée' }))
    const bulle = await screen.findByTestId('cal-pret-sans-lead')
    expect(bulle).toHaveTextContent('Ce calepinage n’a pas de lead : aucune facture à lire. Choisissez le nombre de panneaux à l’étape Panneaux, ou rattachez un lead pour dimensionner sur sa facture.')
    const contenu = bulle.parentElement
    expect(contenu).not.toHaveTextContent('facture du lead')
    expect(contenu).not.toHaveTextContent('Saisir la facture')
    cleanup()
  })

  it('avec un lead : le texte servi reste tel quel', async () => {
    calepinageApi.calepinages.pretAEnvoyer.mockResolvedValue(servi([taille]))
    calepinageApi.calepinages.explications.mockResolvedValue({ data: registreTaille })
    calepinageApi.calepinages.get.mockResolvedValue({ data: { id: 206, lead: 4, client: null } })
    monter({ calepinageId: 206, groupes: true })
    const ligneTaille = await screen.findByTestId('cal-pret-ligne-taille_sans_facture')
    await userEvent.click(within(ligneTaille).getByRole('button', { name: 'Pourquoi : Facture ou taille souhaitée renseignée' }))
    expect(await screen.findByText('Saisir la facture')).toBeInTheDocument()
    expect(screen.queryByTestId('cal-pret-sans-lead')).toBeNull()
    cleanup()
  })
})

/* ACAL1983 — « Fiche incomplète » : le bouton dit « Compléter la fiche du module », pas « Régler dans … ». */
describe('PretAEnvoyer — le bouton d’une fiche incomplète (ACAL1983)', () => {
  it('le geste servi nomme le bouton ; un autre contrôle garde « Régler dans … »', async () => {
    const fiche = {
      ...ligne(modeleARegler, 'materiel_designe'), libelle: 'Matériel électrique désigné',
      valeur_texte: 'Fiche incomplète : tension au point de puissance maximale (Vmp) du module',
      geste: 'Compléter la fiche du module', cible: { etape: 'electrique', onglet: 'materiel', champ: '' },
    }
    calepinageApi.calepinages.pretAEnvoyer.mockResolvedValue(servi([fiche, ligne(modeleARegler, 'chutes_tension')]))
    monter({ calepinageId: 208, groupes: true })
    const bouton = await screen.findByTestId('cal-pret-regler-materiel_designe')
    expect(bouton).toHaveTextContent('Compléter la fiche du module')
    expect(bouton).not.toHaveTextContent('Régler dans')
    expect(screen.getByTestId('cal-pret-regler-chutes_tension')).toHaveTextContent(/^Régler/)
    cleanup()
  })
})

/* ACAL1729 — le « ? » (Pourquoi) s'ouvre à la touche Entrée comme à la touche Espace ; Échap le ferme. */
describe('PretAEnvoyer — le « ? » au clavier (ACAL1729)', () => {
  const taille = { ...ligne(modeleARegler, 'taille_clavier'), libelle: 'Pentes et faces confirmées', valeur_texte: '4 pans' }
  const registre = { entrees: [{ cle: 'controle.taille_clavier', phrase: 'Phrase servie.', geste: '', valeurs: {} }] }
  const monterClavier = async () => {
    calepinageApi.calepinages.pretAEnvoyer.mockResolvedValue(servi([taille]))
    calepinageApi.calepinages.explications.mockResolvedValue({ data: registre })
    calepinageApi.calepinages.get.mockResolvedValue({ data: { id: 207, lead: 4, client: null } })
    monter({ calepinageId: 207, groupes: true })
    const ligneTaille = await screen.findByTestId('cal-pret-ligne-taille_clavier')
    const bouton = await within(ligneTaille).findByRole('button', { name: /Pourquoi/ })
    bouton.focus()
    return bouton
  }

  it('Entrée ouvre (aria-expanded vrai), Échap ferme et rend le focus au « ? »', async () => {
    const bouton = await monterClavier()
    await userEvent.keyboard('{Enter}')
    expect(bouton).toHaveAttribute('aria-expanded', 'true')
    await userEvent.keyboard('{Escape}')
    expect(bouton).toHaveAttribute('aria-expanded', 'false')
    cleanup()
  })

  it('Espace ouvre aussi', async () => {
    const bouton = await monterClavier()
    await userEvent.keyboard(' ')
    expect(bouton).toHaveAttribute('aria-expanded', 'true')
    cleanup()
  })
})
