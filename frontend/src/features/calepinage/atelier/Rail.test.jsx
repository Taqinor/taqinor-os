import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'

/* ============================================================================
   CALX1 — LE RAIL D'ONGLETS, ET LA PREUVE QU'AUCUNE ROUTE NE RESTE ORPHELINE.
   ----------------------------------------------------------------------------
   Ce que ce fichier empêche de revenir :
     1. les treize écrans servis par le routeur et visés par AUCUN lien — un
        écran qu'on ne peut pas ouvrir n'existe pas (incident du 03/08/2026) ;
     2. un onglet inscrit au registre qui ne monterait pas son composant ;
     3. un `?onglet=` fautif qui rendrait un écran blanc ;
     4. une route AJOUTÉE plus tard à `module.config.jsx` sans être rendue
        atteignable : le test ITÈRE sur `config.routes` et n'en compte JAMAIS
        le nombre — une quatorzième route ne le périme pas, elle le fait
        rougir tant qu'elle n'est ni un item de nav, ni un onglet du rail, ni
        un lien rendu par l'atelier.

   L'API DU MODULE EST DOUBLÉE PAR UN PROXY PERMISSIF : ce fichier juge le RAIL
   (il monte le bon panneau pour la bonne clé), pas le contenu de chacun des
   treize panneaux — chacun a, ou aura, son propre test. Le proxy rend une
   promesse résolue pour n'importe quel appel, donc aucun panneau ne tombe sur
   une méthode absente : un rouge ici désigne le rail, jamais une doublure
   oubliée.
   ========================================================================== */

vi.mock('../../../api/calepinageApi', async () => (await import('../../../test/fixtures/proxyPermissif')).moduleApiPermissif({
  calepinages: new Proxy({}, { get: (_c, prop) => (prop === 'parcours' ? (...a) => mocks.parcours(...a)
    : prop === 'modulesDisponibles' ? (...a) => mocks.modulesDisponibles(...a)
      : prop === 'simuler' ? (...a) => mocks.simuler(...a)
        : prop === 'pretAEnvoyer' ? (...a) => mocks.pretAEnvoyer(...a)
          : prop === 'entreeElectrique' ? (...a) => mocks.entreeElectrique(...a) : () => Promise.resolve({ data: {} })) }),
}))
vi.mock('../../../api/ventesApi', () => ({ default: { reviserDevis: vi.fn() } }))

/* CALX349 — l'onglet « Approbation » lit `useHasPermission`, qui va chercher
   le store redux : aucun rendu de ce fichier n'en monte un (même double que
   `AtelierPanneaux.test.jsx`). Sans lui, le panneau lève et le rail affiche
   son bandeau d'échec au lieu du contenu. */
const mocks = vi.hoisted(() => ({
  hasPermission: vi.fn(() => false), parcours: vi.fn(), modulesDisponibles: vi.fn(), simuler: vi.fn(),
  pretAEnvoyer: vi.fn(() => Promise.resolve({ data: {} })), entreeElectrique: vi.fn(() => Promise.resolve({ data: {} })),
}))
vi.mock('../../../hooks/useHasPermission', () => ({
  useHasPermission: (code) => mocks.hasPermission(code),
}))

import AtelierPanneaux from '../AtelierPanneaux'
import config from '../module.config.jsx'
import Rail from './Rail'
import RailGuide from '../commun/RailGuide'
import { BoutonCalculer } from '../production/PanneauProduction'
import { BoutonOr, BoutonMarine, Segmente, Tuile, Indicateur, SectionEtape } from './coque/primitives'
import { GLOSSAIRE_ONGLETS } from '../commun/glossaireOnglets'
import { exempleContrat, reponseContrat } from '../../../test/fixtures/contractSamples'
import { ETAPES, ESSENTIELS, ecranGuideDeOnglet, ongletDansLaFeuille, ongletsVisibles } from './parcoursGuide'
import { ONGLETS, PARAM_ONGLET, ongletParCle, ongletsTries, resoudreOnglet } from './onglets'

const ID = '7'

const rendreRail = (recherche = '') => render(
  <MemoryRouter initialEntries={[`/calepinage/${ID}${recherche}`]}>
    <Routes>
      <Route path="/calepinage/:id" element={<Rail />} />
    </Routes>
  </MemoryRouter>,
)

/* Le panneau ouvert, une fois le module paresseux chargé ET son premier rendu
   utile passé. Les deux attentes sont RÉELLES : le composant arrive par
   `import()` (un tick), puis la plupart des panneaux traversent un état de
   chargement muet (une roue sans texte) avant d'écrire quoi que ce soit — d'où
   un délai large, et une attente sur le CONTENU plutôt que sur un simple
   montage. Un écran blanc durable fait donc rougir ce helper. */
const DELAI_PANNEAU = 15_000

async function panneauOuvert() {
  const panneau = await screen.findByTestId('cal-onglet-panneau', {}, { timeout: DELAI_PANNEAU })
  await waitFor(() => {
    const texte = panneau.textContent.trim()
    expect(texte, 'le panneau est resté sur son écran d’attente')
      .not.toMatch(/Ouverture de l’onglet|Ouverture de l'onglet/)
    expect(texte.length, 'le panneau n’a rien affiché — écran blanc').toBeGreaterThan(0)
  }, { timeout: DELAI_PANNEAU })
  return panneau
}

beforeEach(() => vi.clearAllMocks())
afterEach(() => { cleanup(); vi.clearAllMocks() })

/* ACAL437 — ce cas DOIT rester le premier à ouvrir un panneau paresseux de ce
   fichier : `lazy()` garde le composant résolu une fois chargé, et les cas
   suivants (boucle sur tous les onglets) ne montreraient plus le repli. */
describe('ACAL437 — le repli du rail est un squelette, pas une roue seule', () => {
  it('pendant le chargement du panneau : squelette à la forme du contenu, sous role=status « Chargement… »', async () => {
    rendreRail('?onglet=production')
    const panneau = await screen.findByTestId('cal-onglet-panneau')
    const etat = within(panneau).getByRole('status', { name: 'Chargement…' })
    expect(etat.querySelector('.skeleton-shimmer'), 'la roue seule : aucun squelette').not.toBeNull()
  })
})

describe('CALX1 — le registre `atelier/onglets.js`', () => {
  it('chaque entrée porte la forme attendue, avec une clé et un ordre uniques', () => {
    expect(ONGLETS.length, 'registre vide').toBeGreaterThan(0)
    const cles = []
    const ordres = []
    for (const onglet of ONGLETS) {
      expect(typeof onglet.cle, `clé manquante : ${JSON.stringify(onglet)}`).toBe('string')
      expect(onglet.cle.length).toBeGreaterThan(0)
      expect(typeof onglet.libelle, `libellé manquant : ${onglet.cle}`).toBe('string')
      expect(onglet.libelle.trim().length, `libellé vide : ${onglet.cle}`).toBeGreaterThan(0)
      expect(typeof onglet.groupe, `groupe manquant : ${onglet.cle}`).toBe('string')
      expect(Number.isFinite(onglet.ordre), `ordre non numérique : ${onglet.cle}`).toBe(true)
      expect(onglet.composant, `composant manquant : ${onglet.cle}`).toBeTruthy()
      cles.push(onglet.cle)
      ordres.push(onglet.ordre)
    }
    expect(new Set(cles).size, `clés en double : ${cles.join(', ')}`).toBe(cles.length)
    expect(new Set(ordres).size, `ordres en double : ${ordres.join(', ')}`).toBe(ordres.length)
  })

  it('`?onglet=` absent n’ouvre rien, une clé inconnue retombe sur le PREMIER onglet', () => {
    expect(resoudreOnglet(null)).toBeNull()
    expect(resoudreOnglet('')).toBeNull()
    expect(resoudreOnglet('cle-qui-n-existe-pas')).toBe(ongletsTries()[0])
    const premier = ongletsTries()[0]
    expect(resoudreOnglet(premier.cle)).toBe(premier)
  })

  /* CALX18/CALX25 — un onglet NEUF n'a pas forcément de route profonde
     héritée : le rail est désormais le chemin normal pour l'ouvrir, et
     `module.config.jsx` n'est plus rouvert pour chaque panneau (D-CALX 13).
     L'ancien test symétrique (chaque onglet ⇔ une route de même clé) tenait
     par coïncidence pour les treize onglets fondateurs, mais AUCUNE des deux
     directions n'est une vraie invariante du module : `variantes` a une route
     profonde sans être un onglet du rail (c'est un écran à part), et un
     onglet neuf peut n'avoir aucune route héritée. La protection qui reste
     réellement utile — une route déjà servie ne devient jamais introuvable —
     est celle du test « aucune route du module ne reste orpheline » plus bas,
     qui accepte plusieurs chemins d'accès (nav, onglet, lien rendu). */
})

describe('CALX1 — le rail monte le panneau de l’onglet demandé', () => {
  it('sans `?onglet=`, le rail guidé montre 5 étapes et les seuls essentiels de l’étape active', () => {
    rendreRail()

    expect(screen.getByTestId('cal-rail-onglets')).toBeTruthy()
    for (const cle of ['toit', 'panneaux', 'electrique', 'resultats', 'documents']) {
      expect(screen.getByTestId(`cal-etape-${cle}`), `étape absente : ${cle}`).toBeTruthy()
    }
    // ACAL393 — étape active par défaut = toit : ses seuls essentiels.
    expect(screen.getByTestId('cal-etape-toit')).toHaveAttribute('aria-current', 'step')
    expect(screen.getAllByRole('tab').map((t) => t.getAttribute('data-testid')))
      .toEqual(['cal-onglet-pente'])
    expect(screen.queryByTestId('cal-onglet-panneau')).toBeNull()
  })

  // ACAL1190 — l'étape Toit guidée = le panneau de la maquette (un onglet) ; Terrain et Ombrière restent ouvrables.
  it('mode guidé, étape Toit ⇒ seul `cal-onglet-pente` ; mode expert ⇒ Terrain et Ombrière présents', async () => {
    window.localStorage.clear()
    const utilisateur = userEvent.setup()
    rendreRail()
    expect(screen.getAllByRole('tab').map((t) => t.getAttribute('data-testid'))).toEqual(['cal-onglet-pente'])
    expect(ongletsVisibles('toit')).toEqual(['pente'])
    expect(ongletsVisibles('toit', 'terrain')).toEqual(['pente', 'terrain']) // `?onglet=terrain` l'ouvre encore
    try {
      await utilisateur.click(screen.getByTestId('cal-mode-expert'))
      expect(screen.getByTestId('cal-onglet-terrain')).toBeTruthy()
      expect(screen.getByTestId('cal-onglet-ombriere')).toBeTruthy()
    } finally { window.localStorage.clear() } // le mode expert est mémorisé : ne pas le laisser aux cas suivants
  })

  // ACAL1192 — l'étape Résultats guidée = Production et Pertes ; Batterie et Économie restent ouvrables.
  it('mode guidé, étape Résultats ⇒ Production et Pertes seules ; mode expert ⇒ Batterie et Économie présentes', async () => {
    window.localStorage.clear()
    const utilisateur = userEvent.setup()
    rendreRail('?onglet=production')
    expect(screen.getAllByRole('tab').map((t) => t.getAttribute('data-testid')))
      .toEqual(['cal-onglet-production', 'cal-onglet-pertes'])
    expect(ongletsVisibles('resultats')).toEqual(['production', 'pertes'])
    expect(ongletsVisibles('resultats', 'economie')).toEqual(['production', 'pertes', 'economie']) // `?onglet=economie` l'ouvre encore
    try {
      await utilisateur.click(screen.getByTestId('cal-mode-expert'))
      expect(screen.getByTestId('cal-onglet-batterie')).toBeTruthy()
      expect(screen.getByTestId('cal-onglet-economie')).toBeTruthy()
    } finally { window.localStorage.clear() } // le mode expert est mémorisé : ne pas le laisser aux cas suivants
  })

  // ACAL1193 — l'étape Documents guidée = l'écran de fin ; Dossiers et Approbation restent ouvrables.
  it('mode guidé, étape Documents ⇒ Documents seul, `?onglet=approbation` l’ouvre ; mode expert ⇒ Dossiers et Approbation présents', async () => {
    window.localStorage.clear()
    const utilisateur = userEvent.setup()
    expect(ongletsVisibles('documents')).toEqual(['documents'])
    expect(ongletsVisibles('documents', 'approbation')).toEqual(['documents', 'approbation'])
    rendreRail('?onglet=documents')
    expect(screen.getAllByRole('tab').map((t) => t.getAttribute('data-testid'))).toEqual(['cal-onglet-documents'])
    cleanup()
    rendreRail('?onglet=approbation')
    expect(screen.getByTestId('cal-onglet-approbation')).toHaveAttribute('aria-selected', 'true')
    cleanup()
    rendreRail('?onglet=documents')
    try {
      await utilisateur.click(screen.getByTestId('cal-mode-expert'))
      expect(screen.getByTestId('cal-onglet-dossiers')).toBeTruthy()
      expect(screen.getByTestId('cal-onglet-approbation')).toBeTruthy()
    } finally { window.localStorage.clear() } // le mode expert est mémorisé : ne pas le laisser aux cas suivants
  })

  it('chaque clé de ONGLETS est dans la table du parcours, une seule fois', () => {
    const dans = ETAPES.flatMap((e) => e.onglets)
    expect([...dans].sort()).toEqual(ONGLETS.map((o) => o.cle).sort())
    for (const cle of ESSENTIELS) expect(dans, `essentiel inconnu : ${cle}`).toContain(cle)
    expect(ESSENTIELS).toHaveLength(7)
  })

  it('ACAL1731 — l’étape mémorisée sur cet appareil prime sur la première non faite ; un `?onglet=` garde la priorité ; stockage refusé ⇒ repli', async () => {
    const cle = `calepinage.etape.${ID}`
    try {
      window.localStorage.setItem(cle, 'toit')
      mocks.parcours.mockResolvedValue(reponseContrat('calepinage', 'calepinage_parcours_guide'))
      const { unmount } = rendreRail()
      // contrat : toit fait, panneaux en_cours ; la mémoire dit « toit » : l'atelier rouvre sur le Toit.
      await waitFor(() => expect(screen.getByTestId('cal-etape-toit')).toHaveAttribute('data-etat', 'fait'))
      expect(screen.getByTestId('cal-etape-toit')).toHaveAttribute('aria-current', 'step')
      unmount()
      // Un lien `?onglet=` prime sur la mémoire.
      const lien = rendreRail('?onglet=fiches')
      await waitFor(() => expect(screen.getByTestId('cal-etape-panneaux')).toHaveAttribute('aria-current', 'step'))
      lien.unmount()
      // Une valeur mémorisée qui n'est pas une étape, ou le stockage refusé : la première étape non faite.
      window.localStorage.setItem(cle, 'inconnue')
      const repli = rendreRail()
      await waitFor(() => expect(screen.getByTestId('cal-etape-panneaux')).toHaveAttribute('aria-current', 'step'))
      repli.unmount()
    } finally { window.localStorage.removeItem(cle); mocks.parcours.mockReset() }
  })

  it('la pastille d’état vient du parcours (contrat) et l’étape active est la première non faite', async () => {
    mocks.parcours.mockResolvedValueOnce(reponseContrat('calepinage', 'calepinage_parcours_guide'))
    rendreRail()
    // contrat : toit fait, panneaux en_cours => étape active « panneaux ».
    await waitFor(() => expect(screen.getByTestId('cal-etape-panneaux'))
      .toHaveAttribute('aria-current', 'step'))
    expect(screen.getByTestId('cal-etape-toit')).toHaveAttribute('data-etat', 'fait')
    expect(screen.getByTestId('cal-etape-resultats-etat')).toHaveTextContent('bloqué')
    expect(screen.getByTestId('cal-onglet-fiches')).toBeTruthy()
  })

  it('un `?onglet=` expert l’ouvre quand même, dans son étape', async () => {
    rendreRail(`?${PARAM_ONGLET}=releve`)
    expect(screen.getByTestId('cal-etape-toit')).toHaveAttribute('aria-current', 'step')
    expect(screen.getByTestId('cal-onglet-releve')).toHaveAttribute('aria-selected', 'true')
    await panneauOuvert()
  }, 30_000)

  /* ITÉRATION sur le registre : chaque entrée, sans exception, rend SON
     composant. Deux garde-fous plutôt qu'un texte attendu par onglet (qui
     figerait le contenu de treize écrans dans un test du rail) :
       - le panneau n'est NI vide NI l'écran d'attente ;
       - il ne rend pas le bandeau d'échec (un panneau qui plante est un rouge,
         pas un « une erreur est survenue » qui passerait inaperçu). */
  for (const onglet of ONGLETS) {
    it(`onglet « ${onglet.libelle} » (?onglet=${onglet.cle}) : son composant est monté`, async () => {
      rendreRail(`?${PARAM_ONGLET}=${onglet.cle}`)

      await panneauOuvert()
      expect(screen.queryByTestId('cal-onglet-erreur'),
        `le panneau « ${onglet.cle} » a échoué au rendu`).toBeNull()
      // ACAL395 : en guidé, les 7 onglets électriques sont des sections d'UNE
      // page portée par l'onglet `ouverture` ; la section demandée est dépliée
      // (sous « Réglages avancés », déplié avec elle). L'onglet d'ouverture lui-même
      // ne déplie plus rien (maquette Electrique, L3) : « Réglages avancés » reste replié.
      const ecran = ecranGuideDeOnglet(onglet.cle)
      expect(screen.getByTestId(`cal-onglet-${ecran ? ecran.ouverture : onglet.cle}`))
        .toHaveAttribute('aria-selected', 'true')
      if (ecran?.ouverture === 'verdict-electrique' && onglet.cle === ecran.ouverture) {
        expect(screen.getByTestId('cal-electrique-avances')).toHaveAttribute('data-state', 'closed')
      } else if (ecran?.ouverture === 'verdict-electrique') {
        expect(screen.getByTestId(`cal-electrique-section-${onglet.cle}`))
          .toHaveAttribute('data-state', 'open')
      }
    }, 30_000)
  }

  it('une clé inconnue ouvre le PREMIER onglet — jamais un écran blanc', async () => {
    const premier = ongletsTries()[0]
    rendreRail(`?${PARAM_ONGLET}=onglet-supprime-en-2019`)

    await panneauOuvert()
    expect(screen.queryByTestId('cal-onglet-erreur')).toBeNull()
    expect(screen.getByTestId(`cal-onglet-${premier.cle}`))
      .toHaveAttribute('aria-selected', 'true')
  }, 30_000)

  it('cliquer un onglet écrit `?onglet=` dans l’URL — le lien reste partageable', async () => {
    const utilisateur = userEvent.setup()
    const cible = ongletParCle('production')
    expect(cible, 'l’onglet « production » a disparu du registre').toBeTruthy()

    render(
      <MemoryRouter initialEntries={[`/calepinage/${ID}`]}>
        <Routes>
          <Route
            path="/calepinage/:id"
            element={(
              <>
                <Rail />
                <TemoinUrl />
              </>
            )}
          />
        </Routes>
      </MemoryRouter>,
    )

    // production est le premier essentiel de l'étape Résultats.
    await utilisateur.click(screen.getByTestId('cal-etape-resultats'))

    await waitFor(() => expect(screen.getByTestId('temoin-url'))
      .toHaveTextContent(`onglet=${cible.cle}`))
    expect(await panneauOuvert()).toBeTruthy()
  })
})

describe('ACAL394 — l’interrupteur « Mode expert »', () => {
  beforeEach(() => { try { window.localStorage.clear() } catch { /* ignoré */ } })

  it('guidé par défaut ; cocher montre tous les onglets rangés sous leur étape, et survit à un rechargement', async () => {
    const utilisateur = userEvent.setup()
    const premier = rendreRail()
    expect(screen.getAllByRole('tab')).toHaveLength(1)
    await utilisateur.click(screen.getByTestId('cal-mode-expert'))
    expect(screen.getAllByRole('tab')).toHaveLength(ETAPES[0].onglets.length)
    let total = 0
    for (const etape of ETAPES) {
      await utilisateur.click(screen.getByTestId(`cal-etape-${etape.cle}`))
      total += screen.getAllByRole('tab').length
    }
    expect(total).toBe(ONGLETS.length)

    premier.unmount()
    // rechargement : la mémoire du navigateur garde l’expert.
    rendreRail()
    expect(screen.getByTestId('cal-mode-expert')).toBeChecked()
    expect(screen.getAllByRole('tab')).toHaveLength(ETAPES[0].onglets.length)
  }, 30_000)

  it('`?mode=expert` force le mode expert', () => {
    rendreRail('?mode=expert')
    expect(screen.getByTestId('cal-mode-expert')).toBeChecked()
    expect(screen.getAllByRole('tab')).toHaveLength(ETAPES[0].onglets.length)
  })

  // ACAL600 — le niveau expert est tenu par l'atelier et descend au rail : cocher
  // « Mode expert » dans le rail fait apparaître « Comparer d'autres modules ».
  it('cocher « Mode expert » dans le rail fait apparaître le bouton', async () => {
    const DISPO = exempleContrat('calepinage', 'calepinage_modules_disponibles')
    const complet = DISPO.modules[0]
    mocks.modulesDisponibles.mockResolvedValue({ data: { ...DISPO, modules: [
      complet, { ...complet, module: { ...complet.module, id: 'produit-9001' } }] } })
    const utilisateur = userEvent.setup()
    render(
      <MemoryRouter initialEntries={[`/calepinage/${ID}`]}>
        <Routes>
          <Route path="/calepinage/:id"
            element={<AtelierPanneaux calepinageId={ID} contexte={{ cible: null, calepinage: null }} />} />
        </Routes>
      </MemoryRouter>,
    )
    expect(screen.queryByTestId('cal-comparer-modules')).toBeNull()
    await utilisateur.click(screen.getByTestId('cal-mode-expert'))
    expect(await screen.findByTestId('cal-comparer-modules')).toBeInTheDocument()
    expect(screen.getByTestId('cal-mode-expert')).toBeChecked()
  }, 30_000)
})

describe('ACAL409 — « Comparer les variantes » et « Photos du site » sont des onglets du rail', () => {
  it('le registre passe à 43 onglets (ACAL628 : +1 « controle-chaine » ; ACAL847 : +1 « consommation-mesuree » ; ACAL888 : +1 « livre-prevu »), la table du parcours couvre `variantes` (Résultats) et `photos` (Toit)', () => {
    expect(ONGLETS).toHaveLength(43)
    expect(ETAPES.find((e) => e.cle === 'resultats').onglets).toContain('variantes')
    expect(ETAPES.find((e) => e.cle === 'toit').onglets).toContain('photos')
  })

  it('`?onglet=variantes` monte VariantesCompare dans l’étape Résultats, `?onglet=photos` PhotoSiteCalage dans Toit', async () => {
    const premier = rendreRail(`?${PARAM_ONGLET}=variantes`)
    expect(screen.getByTestId('cal-etape-resultats')).toHaveAttribute('aria-current', 'step')
    expect(screen.getByTestId('cal-onglet-variantes')).toHaveAttribute('aria-selected', 'true')
    await panneauOuvert()
    premier.unmount()
    rendreRail(`?${PARAM_ONGLET}=photos`)
    expect(screen.getByTestId('cal-etape-toit')).toHaveAttribute('aria-current', 'step')
    expect(screen.getByTestId('cal-onglet-photos')).toHaveAttribute('aria-selected', 'true')
    await panneauOuvert()
  }, 30_000)

  it('les routes profondes `/variantes` et `/photos` redirigent comme les autres', () => {
    for (const segment of ['variantes', 'photos']) {
      const route = config.routes.find((r) => r.path === `/calepinage/:id/${segment}`)
      const redirection = config.routes.find((r) => r.path === '/calepinage/:id/fiches')
      expect(route?.component, segment).toBe(redirection.component)
    }
  })
})

describe('ACAL395 — l’étape Électrique en UNE page', () => {
  const SECTIONS = ['equipements-electriques', 'cheminement-cables', 'raccordement', 'verdict-electrique',
    'materiel-electrique', 'saisies-electriques', 'decisions-electriques', 'controle-chaine']
  const parcoursElectrique = (etat) => {
    const base = reponseContrat('calepinage', 'calepinage_parcours_guide')
    const ligne = (code) => ({ code, message: 'm', etape: 'electrique', cible: { onglet: 'verdict-electrique', champ: '' }, gravite: 'a_regler', nombre: 1 })
    return {
      ...base,
      data: {
        ...base.data,
        etapes: base.data.etapes.map((e) => (e.cle === 'electrique' ? { ...e, etat } : e)),
        manque: [...base.data.manque, ligne('a'), ligne('b')],
      },
    }
  }
  beforeEach(() => { try { window.localStorage.clear() } catch { /* ignoré */ } })

  /* ACAL865 — le compte de l'étape vient du panneau « Prêt à envoyer ? »
     (contrat `calepinage_pret_a_envoyer.json`), jamais de `manque[]`. */
  const pret = reponseContrat('calepinage', 'calepinage_pret_a_envoyer')
  const pretAvec = (controles) => ({
    ...pret,
    data: {
      ...pret.data,
      controles,
      nombre_bloquants: controles.filter((c) => c.etat === 'bloquant').length,
      nombre_a_regler: controles.filter((c) => c.etat === 'a_regler').length,
      pret: !controles.some((c) => ['bloquant', 'a_regler'].includes(c.etat)),
    },
  })
  const ok = pret.data.controles.find((c) => c.etat === 'ok')
  const orange = pret.data.controles.find((c) => c.etat === 'a_regler')
  const info = pret.data.controles.find((c) => c.etat === 'info')

  it('guidé : UNE page, « N point à régler » sur les seuls contrôles ÉLECTRIQUES, les 8 sections derrière « Réglages avancés » (replié)', async () => {
    mocks.parcours.mockResolvedValue(parcoursElectrique('bloque'))
    // `manque[]` (2 lignes électriques) et l'orange de l'étape Résultats (`simulation_fraiche`) ne comptent pas :
    // seul le contrôle électrique à régler (`chutes_tension`) fait le compte (maquette Electrique, `filtre`).
    mocks.pretAEnvoyer.mockResolvedValue(pretAvec([ok, orange, { ...orange, code: 'chutes_tension' }]))
    const utilisateur = userEvent.setup()
    rendreRail()
    await utilisateur.click(screen.getByTestId('cal-etape-electrique'))
    expect(await screen.findByTestId('cal-etape-electrique-ecran', {}, { timeout: DELAI_PANNEAU })).toBeTruthy()
    await waitFor(() => expect(screen.getByTestId('cal-electrique-synthese')).toHaveTextContent('1 point à régler'))
    // L3 — plus aucun déclencheur de premier niveau : « Réglages avancés » (replié) porte les 8 sections.
    expect(screen.getByTestId('cal-electrique-avances')).toHaveAttribute('data-state', 'closed')
    for (const cle of SECTIONS) expect(screen.queryByTestId(`cal-electrique-section-${cle}`), cle).toBeNull()
    await utilisateur.click(within(screen.getByTestId('cal-electrique-avances')).getAllByRole('button', { name: 'Réglages avancés' })[0])
    for (const cle of SECTIONS) expect(await screen.findByTestId(`cal-electrique-section-${cle}`), cle).toBeTruthy()
    expect(screen.getByTestId('cal-electrique-section-raccordement')).toHaveAttribute('data-state', 'closed')
    // une seule page : pas un onglet par panneau.
    expect(screen.queryByTestId('cal-onglet-raccordement')).toBeNull()
  }, 30_000)

  it('ACAL865 — tout ok ⇒ « Prêt à envoyer », même si « ce qui manque » a des lignes électriques', async () => {
    mocks.parcours.mockResolvedValue(parcoursElectrique('fait'))
    mocks.pretAEnvoyer.mockResolvedValue(pretAvec([ok]))
    rendreRail(`?${PARAM_ONGLET}=verdict-electrique`)
    await waitFor(() => expect(screen.getByTestId('cal-electrique-synthese')).toHaveTextContent('Prêt à envoyer'))
    expect(mocks.pretAEnvoyer).toHaveBeenCalledWith(ID, { etape: 'electrique' }) // H3 : `?etape=electrique`
  }, 30_000)

  it('ACAL865 — un orange électrique ⇒ UN seul « 1 point à régler », et « Régler » pousse `?onglet=…&champ=…`', async () => {
    mocks.parcours.mockResolvedValue(parcoursElectrique('bloque'))
    const cible = { etape: 'toit', onglet: 'pertes', champ: 'pente' }
    // L3 — l'orange de l'échantillon (`simulation_fraiche`) est de l'étape Résultats : filtré ici ; un code électrique compte.
    mocks.pretAEnvoyer.mockResolvedValue(pretAvec([ok, info, { ...orange, code: 'chutes_tension', cible }]))
    render(
      <MemoryRouter initialEntries={[`/calepinage/${ID}?${PARAM_ONGLET}=verdict-electrique`]}>
        <Routes>
          <Route path="/calepinage/:id" element={<><Rail /><TemoinUrl /></>} />
        </Routes>
      </MemoryRouter>,
    )
    await waitFor(() => expect(screen.getByTestId('cal-electrique-synthese')).toHaveTextContent('1 point à régler'))
    // un seul compte : `manque[]` (2 lignes électriques) n'est plus compté ici.
    expect(screen.queryAllByText(/points? à régler/)).toHaveLength(1)
    expect(screen.getByTestId(`cal-pret-ligne-${info.code}`)).toHaveTextContent(info.valeur_texte)
    await userEvent.setup().click(screen.getByTestId('cal-pret-regler-chutes_tension'))
    const recherche = new URLSearchParams(screen.getByTestId('temoin-url').textContent)
    expect(recherche.get(PARAM_ONGLET)).toBe('pertes')
    expect(recherche.get('champ')).toBe('pente')
  }, 30_000)

  it('ACAL865 / L3 — la liste COURTE de l’étape montre toutes ses lignes, les réussies comprises (maquette Electrique)', async () => {
    mocks.parcours.mockResolvedValue(parcoursElectrique('fait'))
    mocks.pretAEnvoyer.mockResolvedValue(pretAvec([ok, { ...orange, code: 'chutes_tension' }]))
    rendreRail(`?${PARAM_ONGLET}=verdict-electrique`)
    // ACAL1830 (maquette v2) : les contrôles réussis sont rangés dans la section « Contrôles · N bons » REPLIÉE,
    // la ligne y reste présente ; le repli « Voir les n contrôles réussis » de PretAEnvoyer n'existe pas ici.
    const ligne = await screen.findByTestId(`cal-pret-ligne-${ok.code}`, {}, { timeout: DELAI_PANNEAU })
    const bons = screen.getByTestId('cal-pret-bons')
    expect(bons.open).toBe(false)
    expect(within(bons).getByTestId(`cal-pret-ligne-${ok.code}`)).toBe(ligne)
    await userEvent.setup().click(bons.querySelector('summary'))
    expect(bons.open).toBe(true)
    expect(ligne).toBeVisible()
    expect(screen.queryByTestId('cal-pret-reussis')).toBeNull()
  }, 30_000)

  it('R3-10 — la ligne du dossier électrique ne répète pas la pastille qui dit la même chose', async () => {
    mocks.parcours.mockResolvedValue(parcoursElectrique('bloque'))
    const dossier = { ...orange, code: 'verdict_electrique', libelle: 'Dossier électrique', valeur_texte: 'À compléter : 3 points' }
    mocks.pretAEnvoyer.mockResolvedValue(pretAvec([dossier, info]))
    rendreRail(`?${PARAM_ONGLET}=verdict-electrique`)
    const ligne = await screen.findByTestId('cal-pret-ligne-verdict_electrique', {}, { timeout: DELAI_PANNEAU })
    expect(ligne.textContent.match(/À compléter : 3 points/g)).toHaveLength(1)
    // une valeur que la pastille ne dit pas reste affichée.
    expect(screen.getByTestId(`cal-pret-ligne-${info.code}`)).toHaveTextContent(info.valeur_texte)
  }, 30_000)

  it('ACAL1952 — en Guidé, le panneau de l’étape dit « Repris du devis <référence> » avec l’écart d’une saisie contraire', async () => {
    const entree = exempleContrat('calepinage', 'calepinage_entree_electrique')
    mocks.entreeElectrique.mockResolvedValue({ data: entree })
    mocks.parcours.mockResolvedValue(parcoursElectrique('fait'))
    mocks.pretAEnvoyer.mockResolvedValue(pretAvec([ok]))
    rendreRail(`?${PARAM_ONGLET}=verdict-electrique`)
    const bloc = await screen.findByTestId('cal-elec-devis-retenu', {}, { timeout: DELAI_PANNEAU })
    expect(bloc).toHaveTextContent(`Repris du devis ${entree.devis_retenu.reference} (option sans batterie)`)
    expect(bloc).toHaveTextContent(`Écart avec le devis — ${entree.devis_retenu.ecarts[0]}`)
    // sans devis lié : aucune mention
    cleanup()
    mocks.entreeElectrique.mockResolvedValue({ data: exempleContrat('calepinage', 'calepinage_entree_electrique', 'exemple_vide') })
    rendreRail(`?${PARAM_ONGLET}=verdict-electrique`)
    await screen.findByTestId('cal-elec-onduleur', {}, { timeout: DELAI_PANNEAU })
    expect(screen.queryByTestId('cal-elec-devis-retenu')).toBeNull()
  }, 30_000)

  it('un lien `?onglet=raccordement` déplie le Raccordement (et « Réglages avancés » avec lui)', async () => {
    rendreRail(`?${PARAM_ONGLET}=raccordement`)
    expect(await screen.findByTestId('cal-electrique-section-raccordement', {}, { timeout: DELAI_PANNEAU }))
      .toHaveAttribute('data-state', 'open')
    // ACAL1191 — le lien d'une section avancée déplie AUSSI « Réglages avancés ».
    expect(screen.getByTestId('cal-electrique-avances')).toHaveAttribute('data-state', 'open')
  }, 30_000)

  it('en mode expert, les 7 onglets restent', () => {
    rendreRail(`?${PARAM_ONGLET}=raccordement&mode=expert`)
    for (const cle of SECTIONS) expect(screen.getByTestId(`cal-onglet-${cle}`), cle).toBeTruthy()
    expect(screen.queryByTestId('cal-etape-electrique-ecran')).toBeNull()
  })
})

describe('ACAL397 — `?champ=` ouvre le champ exact', () => {
  const rendreAvecChamp = (champ) => render(
    <MemoryRouter initialEntries={[`/calepinage/${ID}?${PARAM_ONGLET}=pertes&champ=${champ}`]}>
      <Routes>
        <Route path="/calepinage/:id" element={<><input id="champ-norme" /><Rail /></>} />
      </Routes>
    </MemoryRouter>,
  )

  it('fait défiler jusqu’à l’élément d’id `champ` et lui donne le focus', async () => {
    rendreAvecChamp('champ-norme')
    await waitFor(() => expect(document.getElementById('champ-norme')).toHaveFocus())
  })

  it('un `champ` sans élément n’ouvre que le panneau, sans erreur', async () => {
    rendreAvecChamp('introuvable')
    await panneauOuvert()
    expect(screen.queryByTestId('cal-onglet-erreur')).toBeNull()
  }, 30_000)
})

describe('T4-X3-007 — un lien profond vers un panneau que l’étape ne montre pas ouvre « Avancé »', () => {
  // Les 16 clés relevées par le relecteur : quatre seulement tombent sur l'écran ordinaire de leur étape.
  const SEIZE = ['variantes', 'pompage', 'plan', 'photos', 'terrain', 'ombriere', 'schema', 'horizon',
    'course-soleil', 'dossiers', 'affectation', 'detection-toit', 'fiches', 'pente', 'production', 'pertes']

  it('exactement fiches, pente, production et pertes, et jamais en mode expert', () => {
    expect(SEIZE.filter((cle) => ongletDansLaFeuille(cle))).toEqual(['fiches', 'pente', 'production', 'pertes'])
    expect(SEIZE.filter((cle) => ongletDansLaFeuille(cle, true))).toEqual([])
    expect(ongletDansLaFeuille(null)).toBe(false)
  })
})

describe('CALX1 — aucune route du module ne reste orpheline', () => {
  /* On ITÈRE sur `config.routes`. Une route est atteignable en deux clics
     quand elle est : (a) un item de nav du module ; (b) l'atelier lui-même ;
     (c) un onglet du rail — `/calepinage/:id/<cle>` avec `<cle>` au registre ;
     (d) un lien RÉELLEMENT rendu par l'atelier (les hrefs sont relevés sur le
     rendu, pas recopiés dans une liste qui pourrait mentir). */
  it('chaque route déclarée est atteignable depuis l’atelier', async () => {
    const { container } = render(
      <MemoryRouter initialEntries={[`/calepinage/${ID}`]}>
        <Routes>
          <Route
            path="/calepinage/:id"
            element={<AtelierPanneaux calepinageId={ID} contexte={{ cible: null, calepinage: null }} />}
          />
        </Routes>
      </MemoryRouter>,
    )
    await waitFor(() => expect(screen.getByTestId('cal-atelier-panneaux')).toBeTruthy())

    const liensRendus = new Set(
      [...container.querySelectorAll('a[href]')]
        .map((a) => a.getAttribute('href').split('?')[0])
        // Le calepinage rendu porte l'identifiant `ID` : on le re-généralise
        // pour comparer au gabarit `/calepinage/:id/...` du registre de routes.
        .map((href) => href.replace(`/calepinage/${ID}`, '/calepinage/:id')),
    )
    const navItems = new Set(config.nav.items.map((i) => i.to))

    const orphelines = []
    for (const route of config.routes) {
      const segment = route.path.startsWith('/calepinage/:id/')
        ? route.path.slice('/calepinage/:id/'.length)
        : null
      const atteignable = navItems.has(route.path)
        || route.path === '/calepinage/:id'
        || (segment !== null && ongletParCle(segment) !== null)
        || liensRendus.has(route.path)
      if (!atteignable) orphelines.push(route.path)
    }

    expect(
      orphelines,
      `route(s) servie(s) mais introuvable(s) depuis l’atelier : ${orphelines.join(', ')} — `
      + 'inscrivez le panneau au registre `atelier/onglets.js`, ou posez un lien.',
    ).toEqual([])
  })
})

/* ============================================================================
   CALX222 — `builderApi` DESCEND JUSQU'AU PANNEAU.
   ----------------------------------------------------------------------------
   Le panneau « Équipements électriques » sait armer une pose dans la scène 3D
   depuis CALX222, mais personne ne lui passait l'API du constructeur : le
   bouton répondait « outil 3D non prêt » même dans l'atelier. Ces deux essais
   figent LE FIL (écran → `AtelierPanneaux` → `Rail` → panneau) et l'aveu
   honnête quand le fil n'existe pas — jamais une pose armée dans le vide.
   ========================================================================== */
describe('CALX222 — l’API du constructeur atteint les panneaux d’onglet', () => {
  const ONGLET = `?${PARAM_ONGLET}=equipements-electriques`

  it('le rail relaie `builderApi` : « Armer la pose » atteint la scène', async () => {
    const armerPose = vi.fn()
    const utilisateur = userEvent.setup()
    render(
      <MemoryRouter initialEntries={[`/calepinage/${ID}${ONGLET}`]}>
        <Routes>
          <Route
            path="/calepinage/:id"
            element={<Rail builderApi={{ electrique: { armerPose } }} />}
          />
        </Routes>
      </MemoryRouter>,
    )

    await panneauOuvert()
    await utilisateur.click(await screen.findByTestId('calx222-armer'))

    expect(armerPose).toHaveBeenCalledTimes(1)
    expect(screen.queryByTestId('calx222-armement-motif')).toBeNull()
  }, 30_000)

  it('sans `builderApi`, le panneau DIT que l’outil 3D n’est pas prêt', async () => {
    const utilisateur = userEvent.setup()
    rendreRail(ONGLET)

    await panneauOuvert()
    await utilisateur.click(await screen.findByTestId('calx222-armer'))

    expect(await screen.findByTestId('calx222-armement-motif'))
      .toHaveTextContent('Outil 3D non prêt')
  }, 30_000)

  it('l’atelier passe SON `builderApi` au rail — le fil complet', async () => {
    const armerPose = vi.fn()
    const utilisateur = userEvent.setup()
    render(
      <MemoryRouter initialEntries={[`/calepinage/${ID}${ONGLET}`]}>
        <Routes>
          <Route
            path="/calepinage/:id"
            element={(
              <AtelierPanneaux
                calepinageId={ID}
                contexte={{ cible: null, calepinage: null }}
                builderApi={{ electrique: { armerPose } }}
              />
            )}
          />
        </Routes>
      </MemoryRouter>,
    )

    await panneauOuvert()
    await utilisateur.click(await screen.findByTestId('calx222-armer'))

    expect(armerPose).toHaveBeenCalledTimes(1)
  }, 30_000)
})

/* ACAL44 — le rail relaie `lectureSeule` à l'onglet ACTIF : le bouton
   d'écriture du panneau monté est désactivé. */
describe('ACAL44 — lecture seule relayée', () => {
  it('lectureSeule est relayée à l’onglet actif', async () => {
    render(
      // Refonte 22/11 : en guidé, « Postes de pertes » est replié dans l'écran Résultats (EtapeResultats,
      // « Détail des pertes et réglages ») ; en expert l'onglet monte son panneau, où l'écriture est désactivée.
      <MemoryRouter initialEntries={[`/calepinage/${ID}?${PARAM_ONGLET}=postes-pertes&mode=expert`]}>
        <Routes>
          <Route path="/calepinage/:id" element={<Rail lectureSeule />} />
        </Routes>
      </MemoryRouter>,
    )
    const bouton = await screen.findByTestId('cal-pertes-enregistrer', {},
      { timeout: DELAI_PANNEAU })
    expect(bouton).toBeDisabled()
  }, DELAI_PANNEAU + 5_000)
})

/** Témoin minimal : il rend la recherche de l'URL du ROUTEUR (MemoryRouter ne
    touche jamais `window.location`), pour l'assertion sur `?onglet=`. */
function TemoinUrl() {
  return <span data-testid="temoin-url">{useLocation().search}</span>
}

describe('ACAL419 — une bulle d’aide par onglet', () => {
  it('chaque onglet de ONGLETS a une bulle d’aide non vide, et le glossaire n’a rien en trop', () => {
    const cles = ONGLETS.map((o) => o.cle).sort()
    expect(Object.keys(GLOSSAIRE_ONGLETS).sort()).toEqual(cles)
    for (const c of cles) expect(GLOSSAIRE_ONGLETS[c].trim().length).toBeGreaterThan(0)
  })

  it('le « ? » est rendu hors de l’onglet (hors trajet des flèches)', async () => {
    render(
      <MemoryRouter initialEntries={[`/calepinage/${ID}?onglet=series&mode=expert`]}>
        <Routes><Route path="/calepinage/:id" element={<Rail calepinageId={ID} />} /></Routes>
      </MemoryRouter>,
    )
    const aide = await screen.findByRole('button', { name: /À quoi sert « Séries »/ })
    expect(aide.closest('[role="tab"]')).toBeNull()
  })
})

describe('ACAL868 — le rail publie l’étape à la barre fixe', () => {
  const ACTIONS = { toit: 'Poser les panneaux', panneaux: 'Raccorder les panneaux', electrique: 'Voir les résultats', resultats: 'Préparer les documents' }

  it('chaque étape guidée sauf Documents porte `action` (libellé de la maquette)', () => {
    for (const e of ETAPES) {
      if (e.cle === 'documents') expect(e.action).toBeUndefined()
      else expect(e.action, `étape ${e.cle}`).toBe(ACTIONS[e.cle])
    }
  })

  it('`onEtape` reçoit l’étape et le mode ; `allerA` ouvre l’étape suivante', async () => {
    try { window.localStorage.clear() } catch { /* ignoré */ }
    const onEtape = vi.fn()
    render(
      <MemoryRouter initialEntries={[`/calepinage/${ID}`]}>
        <Routes>
          <Route path="/calepinage/:id" element={<><Rail onEtape={onEtape} /><TemoinUrl /></>} />
        </Routes>
      </MemoryRouter>,
    )
    await waitFor(() => expect(onEtape).toHaveBeenCalled())
    const publie = onEtape.mock.calls.at(-1)[0]
    expect(publie).toMatchObject({ expert: false })
    const suivante = ETAPES[ETAPES.findIndex((e) => e.cle === publie.etape) + 1].cle
    publie.allerA(suivante)
    await waitFor(() => expect(screen.getByTestId('temoin-url')).toHaveTextContent('onglet='))
    await waitFor(() => expect(onEtape.mock.calls.at(-1)[0]).toMatchObject({ etape: suivante, expert: false }))
    expect(await panneauOuvert()).toBeTruthy()
  })
})

describe('ACAL867 — l’étape Documents guidée : panneau, bouton de devis, documents', () => {
  const rendreAvecDevis = (recherche) => render(
    <MemoryRouter initialEntries={[`/calepinage/${ID}${recherche}`]}>
      <Routes>
        <Route path="/calepinage/:id" element={<Rail actionDevis={<button type="button" data-testid="cal-generer-devis">Générer le devis</button>} />} />
      </Routes>
    </MemoryRouter>,
  )

  // Refonte 22/11 (maquette Documents) : deux colonnes ; le bouton relayé est au pied de la carte « Prêt à envoyer ? ».
  it('guidé : le bouton relayé s’affiche dans l’écran, au pied de « Prêt à envoyer ? » (colonne de gauche) ; un seul bouton', async () => {
    try { window.localStorage.clear() } catch { /* ignoré */ }
    rendreAvecDevis(`?${PARAM_ONGLET}=documents`)
    const ecran = await screen.findByTestId('cal-etape-documents-ecran', {}, { timeout: DELAI_PANNEAU })
    expect(ecran.children).toHaveLength(2)
    expect(ecran.children[0]).toContainElement(screen.getByTestId('cal-generer-devis'))
    expect(screen.getAllByTestId('cal-generer-devis')).toHaveLength(1)
  }, 30_000)

  it('mode expert : l’onglet documents est inchangé (aucun écran d’étape, aucun bouton relayé)', async () => {
    rendreAvecDevis(`?${PARAM_ONGLET}=documents&mode=expert`)
    await panneauOuvert()
    expect(screen.queryByTestId('cal-etape-documents-ecran')).toBeNull()
    expect(screen.queryByTestId('cal-generer-devis')).toBeNull()
  }, 30_000)
})

/* ACAL1280 — les pièces partagées de la coque se manipulent au clavier. */
describe('ACAL1280 — pièces de la coque : clavier et rôles', () => {
  afterEach(() => cleanup())

  it('tuile de choix : atteignable par Tab, activée par Entrée et Espace, état dans aria-pressed', async () => {
    const user = userEvent.setup()
    const clic = vi.fn()
    render(<Tuile choisie onClick={clic}>Toit plat</Tuile>)
    const tuile = screen.getByRole('button', { name: 'Toit plat' })
    expect(tuile).toHaveAttribute('aria-pressed', 'true')
    await user.tab()
    expect(tuile).toHaveFocus()
    await user.keyboard('{Enter}')
    await user.keyboard(' ')
    expect(clic).toHaveBeenCalledTimes(2)
  })

  it('bascule à segments : groupe nommé, un bouton par option, aria-pressed suit la valeur, Tab + Entrée/Espace', async () => {
    const user = userEvent.setup()
    const change = vi.fn()
    render(<Segmente libelle="Vue" valeur="plan" onChange={change}
      options={[{ valeur: 'plan', libelle: 'Plan' }, { valeur: '3d', libelle: '3D' }]} />)
    expect(screen.getByRole('group', { name: 'Vue' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Plan' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: '3D' })).toHaveAttribute('aria-pressed', 'false')
    await user.tab()
    await user.tab()
    expect(screen.getByRole('button', { name: '3D' })).toHaveFocus()
    await user.keyboard('{Enter}')
    await user.keyboard(' ')
    expect(change).toHaveBeenCalledWith('3d')
    expect(change).toHaveBeenCalledTimes(2)
  })

  it('boutons or et marine : vrais <button>, activés par Entrée et Espace', async () => {
    const user = userEvent.setup()
    const or = vi.fn()
    const marine = vi.fn()
    render(<><BoutonOr plein fleche onClick={or}>Poser</BoutonOr><BoutonMarine onClick={marine}>Confirmer</BoutonMarine></>)
    await user.tab()
    expect(screen.getByRole('button', { name: 'Poser' })).toHaveFocus()
    await user.keyboard('{Enter}')
    await user.tab()
    await user.keyboard(' ')
    expect(or).toHaveBeenCalledTimes(1)
    expect(marine).toHaveBeenCalledTimes(1)
  })

  it('pastille et carte d’étape : lisibles (texte), jamais focalisables', () => {
    render(<SectionEtape titre="Pose"><Indicateur libelle="Surface" valeur="42 m²" /></SectionEtape>)
    expect(screen.getByRole('heading', { name: 'Pose' })).toBeInTheDocument()
    expect(screen.getByText('Surface')).toBeInTheDocument()
    expect(screen.getByText('42 m²')).toBeInTheDocument()
    expect(screen.queryAllByRole('button')).toHaveLength(0)
  })
})

/* T4-U1-023 (rejeu R5B, 26/11) — cheminée et voisin posés PUIS enregistrés : l'Expert les voyait, l'étape Panneaux et les
   Résultats disaient encore « aucune ombre signalée » — le parcours n'était lu qu'à l'ouverture. Relu à chaque enregistrement. */
describe('useParcours — relu à chaque enregistrement (T4-U1-023)', () => {
  it('une nouvelle heure d’enregistrement relit « ce qui manque » : la ligne des ombres posées remplace l’ancienne', async () => {
    const { renderHook } = await import('@testing-library/react')
    const { useParcours } = await import('./parcoursGuide')
    const ligne = (code) => ({ code, message: code, etape: 'resultats', gravite: 'a_regler', nombre: 1, cible: { onglet: '', champ: '' } })
    mocks.parcours.mockReset()
    mocks.parcours.mockResolvedValueOnce({ data: { etapes: [], manque: [ligne('acces_solaire_absent')] } })
    mocks.parcours.mockResolvedValueOnce({ data: { etapes: [], manque: [ligne('ombres_non_mesurees')] } })
    const { result, rerender } = renderHook(({ le }) => useParcours(ID, le), { initialProps: { le: null } })
    await waitFor(() => expect(result.current.manque.map((m) => m.code)).toEqual(['acces_solaire_absent']))
    rerender({ le: '2026-11-26T10:00:00Z' })
    await waitFor(() => expect(result.current.manque.map((m) => m.code)).toEqual(['ombres_non_mesurees']))
    expect(mocks.parcours).toHaveBeenCalledTimes(2)
    mocks.parcours.mockReset()
  })

  /* Revue de T4-U1-023 (26/11) — la relecture après un enregistrement nourrit `etapeActive` (coque : `cleEtape`, `onEtape`) :
     sans `?onglet=` ni étape mémorisée, un enregistrement qui marque le Toit « fait » faisait passer l'écran à Panneaux
     sans un clic. Le choix automatique est fait UNE fois (première réponse), puis tenu. */
  it('sans étape mémorisée : un enregistrement qui rend le Toit « fait » laisse l’étape active sur le Toit', async () => {
    const { renderHook } = await import('@testing-library/react')
    const { useParcours, etapeActive } = await import('./parcoursGuide')
    window.localStorage.removeItem(`calepinage.etape.${ID}`)
    const etapes = (toit, panneaux) => ({ data: { etapes: [{ cle: 'toit', etat: toit }, { cle: 'panneaux', etat: panneaux }], manque: [] } })
    mocks.parcours.mockReset()
    mocks.parcours.mockResolvedValueOnce(etapes('en_cours', 'a_faire'))
    mocks.parcours.mockResolvedValueOnce(etapes('fait', 'en_cours'))
    const { result, rerender } = renderHook(({ le }) => useParcours(ID, le), { initialProps: { le: null } })
    const active = () => etapeActive(null, result.current.etats, result.current.memorisee)
    await waitFor(() => expect(result.current.etats.toit).toBe('en_cours'))
    expect(active()).toBe('toit')
    rerender({ le: '2026-11-26T11:00:00Z' }) // l'enregistrement : le Toit devient « fait »
    await waitFor(() => expect(result.current.etats.toit).toBe('fait'))
    expect(result.current.etats.panneaux).toBe('en_cours') // les états, eux, sont à jour (pastilles)
    expect(active()).toBe('toit')
    mocks.parcours.mockReset()
  })
})

/* ACAL1268 (D-ACAL-66 = outil_pose) — le VRAI rail : pour un lead de pompage, les onglets de résultats et d'électrique du réseau
   (expert ET guidé) ne s'ouvrent pas ; ils disent le renvoi au devis agricole. Un autre marché : le panneau d'avant. */
describe('ACAL1268 — le rail d’un lead de pompage', () => {
  const CTX = (marche) => ({ calepinage: { lead: 5 }, chiffrage: { marche }, cible: { devis_agricole: { id: 9, reference: 'DEV-AGR-9' } } })
  const rendreAvec = (contexte, recherche) => render(
    <MemoryRouter initialEntries={[`/calepinage/${ID}${recherche}`]}>
      <Routes><Route path="/calepinage/:id" element={<Rail contexte={contexte} />} /></Routes>
    </MemoryRouter>,
  )
  const zone = () => document.querySelector('[data-zone="pompage-outil-pose"]')

  it.each([
    ['?onglet=production&mode=expert'], ['?onglet=pertes&mode=expert'], ['?onglet=economie&mode=expert'],
    ['?onglet=raccordement&mode=expert'], ['?onglet=verdict-electrique'],
  ])('%s : carte de renvoi au lieu du panneau, lien vers CE devis', async (recherche) => {
    rendreAvec(CTX('agricole'), recherche)
    const panneau = await screen.findByTestId('cal-onglet-panneau', {}, { timeout: DELAI_PANNEAU })
    expect(zone()).not.toBeNull()
    expect(within(panneau).getByRole('link', { name: 'Ouvrir le devis agricole DEV-AGR-9' })).toHaveAttribute('href', '/ventes/devis?devis=9')
  })

  it('un autre marché : aucune carte de renvoi', async () => {
    rendreAvec(CTX('residentiel'), '?onglet=production&mode=expert')
    await panneauOuvert()
    expect(zone()).toBeNull()
  })

  /* Lot 8, relecture finale (D-ACAL-106) — un lecteur sans droit sur les devis reçoit `{id: null, reference: null}` :
     la carte dit qu'un devis agricole existe, sans lien ni référence, et jamais « Créer le devis agricole ». */
  it('devis agricole non nommé : ni lien, ni référence, ni « Créer »', async () => {
    rendreAvec({ ...CTX('agricole'), cible: { devis_agricole: { id: null, reference: null } } }, '?onglet=production&mode=expert')
    const panneau = await screen.findByTestId('cal-onglet-panneau', {}, { timeout: DELAI_PANNEAU })
    expect(zone()).not.toBeNull()
    expect(within(zone()).queryByRole('link')).toBeNull()
    expect(within(panneau).getByText('Un devis agricole du lead porte ce champ (accès réservé aux rôles du module Ventes).')).toBeInTheDocument()
    expect(within(panneau).queryByText(/Créer le devis agricole/)).toBeNull()
  })
})

/* ACAL1650 — le refus 409 de la simulation (réglages météo vides) nomme LE vrai blocage : la liste « Ce qui manque
   encore » met ses lignes en tête, les autres restent dessous (« Pour un résultat complet »), et la pastille de l'étape
   Résultats du rail dit le même compte que le refus. Entrée réelle : le bouton de simulation (POST 409). */
describe('ACAL1650 — le refus météo est nommé par la liste et par le rail', () => {
  const refusMeteo = {
    response: {
      status: 409,
      data: {
        'parametres.simulation.mode_meteo': ['Choisissez le mode météo.'],
        manquants: [
          { champ: 'parametres.simulation.mode_meteo', motif: 'Choisissez le mode météo.',
            cible: { onglet: 'reglages', champ: 'calx69-mode_meteo' } },
          { champ: 'parametres.simulation.fenetre_annees', motif: 'Choisissez la fenêtre d’années météo.',
            cible: { onglet: 'reglages', champ: 'calx69-fenetre_annees' } },
        ],
      },
    },
  }
  const ligneManque = (code, message, champ) => ({
    code, message, etape: 'resultats', gravite: 'a_regler', nombre: 1, cible: { onglet: 'reglages', champ },
  })
  const manque = [
    ligneManque('norme_absente', 'La norme n’est pas choisie.', 'norme'),
    ligneManque('ombrage', 'L’ombrage n’est pas mesuré.', 'ombrage'),
    ligneManque('dossier', 'La longueur de dossier manque.', 'dossier'),
    ligneManque('temperatures', 'Les températures manquent.', 'temperatures'),
  ]
  const etats = { toit: 'fait', panneaux: 'fait', electrique: 'fait', resultats: 'a_faire' }

  it('409 météo : « 2 à régler » sur le rail, les deux lignes du refus en tête, le reste sous « Pour un résultat complet »', async () => {
    mocks.hasPermission.mockImplementation(() => true)
    mocks.simuler.mockRejectedValue(refusMeteo)
    const utilisateur = userEvent.setup()
    render(
      <MemoryRouter initialEntries={[`/calepinage/${ID}`]}>
        <RailGuide vertical calepinageId={ID} etapeActive="resultats" etats={etats} manque={manque} onChoisir={() => {}} />
        <BoutonCalculer calepinageId={ID} data={null} manque={manque} />
      </MemoryRouter>,
    )
    // avant le refus : le parcours servi (4 lignes) fait le compte
    expect(within(screen.getByTestId('cal-etape-resultats')).getByText('4 à régler')).toBeInTheDocument()
    await utilisateur.click(screen.getByTestId('calx48-lancer-bouton'))
    await waitFor(() => expect(within(screen.getByTestId('cal-etape-resultats')).getByText('2 à régler')).toBeInTheDocument())
    const liste = screen.getByTestId('calx48-manques')
    const lignes = within(liste).getAllByTestId('calx48-manque-ligne')
    expect(lignes.map((l) => l.textContent).slice(0, 2))
      .toEqual(['Choisissez le mode météo.', 'Choisissez la fenêtre d’années météo.'])
    expect(lignes).toHaveLength(6)
    expect(within(liste).getByText('Pour un résultat complet')).toBeInTheDocument()
    expect(lignes[0]).toHaveAttribute('href', '/calepinage/reglages#calx69-mode_meteo')
    // un nouveau lancement efface le refus : le rail redit le compte du parcours
    mocks.simuler.mockReturnValue(new Promise(() => {}))
    await utilisateur.click(screen.getByTestId('calx48-lancer-bouton'))
    await waitFor(() => expect(within(screen.getByTestId('cal-etape-resultats')).getByText('4 à régler')).toBeInTheDocument())
  })
})
