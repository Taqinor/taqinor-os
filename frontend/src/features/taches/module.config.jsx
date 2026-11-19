import { Suspense, createElement, lazy, useEffect } from 'react'
import { Navigate } from 'react-router-dom'
import { Calendar, Folder, Inbox, ListTodo, Sun } from 'lucide-react'
import { appGlyph } from '../../lib/apps/appGlyph'
/* ============================================================================
   TCH43 — Module frontend « Tâches » (apps.taches) : routes déclarées.
   ----------------------------------------------------------------------------
   Clé `taches` IDENTIQUE au manifeste backend (`apps/taches/apps.py`, vérifiée par
   `scripts/check_modules.py`). TCH131 — activation : `nav` à 4 onglets (spec-7 §2,
   maquette `coque.js`), chacun gardé par `taches_voir` comme les routes — le lanceur,
   la barre latérale, la barre d'onglets et les épinglés ne montrent le module qu'à un
   compte qui porte le droit (l'Administrateur seul en F2, donnees.md inv. 28). Les
   autres écrans s'ouvrent depuis ces onglets (menu « Plus » de la coquille, liens).

   Table des routes : docs/taches/reference/api.md §7 (13 routes). `/taches/projets/archive`
   et `/taches/projets/modeles` sont statiques : elles passent avant `/taches/projets/:id`.
   Gating STRICT : palier ET `taches_voir` (activation par étapes, donnees.md inv. 28) —
   jamais le repli WIR171 des comptes sans rôle fin, que le serveur refuse aussi.
   ========================================================================== */

/* R4-41 — pas de page blanche au premier passage sur un écran. Chaque écran est un morceau chargé à la demande ; tant
   qu'il n'est pas arrivé, le repli du routeur de l'ERP (hors du module) remplaçait TOUT : la coque du module (`.tch`)
   disparaissait, la barre de l'ERP revenait, l'onglet actif repassait à l'or (mesuré : ≈ 280 ms sur 4G). Ici chaque écran
   porte SA frontière de chargement, DANS le module : le repli est la coquille (en-tête, titre, squelette), sous la même
   enveloppe `.route-fade > .tch` — les règles de l'enveloppe (base.css) tiennent donc pendant le chargement. Et dès
   l'entrée dans le module, les écrans des onglets se chargent à l'inactivité, un à un : le premier toucher d'un onglet
   n'attend plus le réseau. Le repli est volontairement minuscule : il vit dans le morceau commun du module. */
export const CHARGEURS = {
  aujourdhui: () => import('../../pages/taches/Aujourdhui'),
  atrier: () => import('../../pages/taches/ATrier'),
  projets: () => import('../../pages/taches/Projets'),
  projet: () => import('../../pages/taches/Projet'),
  archive: () => import('../../pages/taches/ProjetsArchive'),
  modeles: () => import('../../pages/taches/ProjetsModeles'),
  agenda: () => import('../../pages/taches/Agenda'),
  revue: () => import('../../pages/taches/Revue'),
  rythme: () => import('../../pages/taches/Rythme'),
  recherche: () => import('../../pages/taches/Recherche'),
  supprimees: () => import('../../pages/taches/Supprimees'),
  reglages: () => import('../../pages/taches/Reglages'),
}

/** Les écrans préchargés à l'entrée dans le module, dans l'ordre où l'on y va : les onglets, puis la page d'un projet. */
const A_PRECHARGER = ['atrier', 'projets', 'agenda', 'aujourdhui', 'projet']

let prechargement = null
/** Pour les tests : remet le préchargement à zéro (une session ne le fait qu'une fois). */
export function reinitialiserPrechargement() { prechargement = null }

/** Charge les écrans des onglets, UN par UN, chaque fois à l'inactivité du navigateur : ni le premier rendu ni le réseau
 *  du premier écran n'attendent après eux. Une seule fois par session ; hors économie de données ; un échec (réseau) se
 *  retente au prochain écran monté. */
export function prechargerEcrans() {
  if (prechargement) return prechargement
  if (globalThis.navigator?.connection?.saveData) return Promise.resolve()
  const auRepos = () => new Promise((fait) => {
    if (typeof window.requestIdleCallback === 'function') window.requestIdleCallback(() => fait(), { timeout: 3000 })
    else setTimeout(fait, 250)
  })
  prechargement = (async () => {
    for (const cle of A_PRECHARGER) {
      await auRepos()
      try {
        await CHARGEURS[cle]()
      } catch {
        prechargement = null // réseau coupé : on réessaiera à l'écran suivant ; ce n'était qu'une avance
        return
      }
    }
  })()
  return prechargement
}

/** La forme du squelette de `ui/ChargementTardif.jsx` (deux sections de lignes « os »), recopiée ici : l'importer ferait
 *  sortir un morceau de plus (préchargé par index.html) pour 0,5 Ko — le repli doit coûter le moins possible au démarrage. */
const SQUELETTE = [
  [['72%', '44%'], ['84%', '38%'], ['64%', '']],
  [['78%', '48%'], ['56%', '40%']],
]

/** Le repli d'un écran en chargement : la coquille du module, à la même place que la vraie (rangée du haut sur iPhone,
 *  sur-titre, grand titre au même pixel), puis le squelette. `titre` absent (la page d'un projet : son nom n'est pas
 *  encore connu) : une barre à la place du titre. */
function ChargementEcran({ ecran, titre = null, pleine = false }) {
  return (
    <div className="tch tch-chargement" data-ecran={ecran} data-largeur={pleine ? 'pleine' : undefined} aria-busy="true">
      <div className="tch-page">
        <header className="entete">
          <div className="entete-barre" />
          <div className="entete-titres">
            <div className="entete-surtitre" />
            {/* ni titre de niveau 1 ni texte lu : l'écran réel pose le sien dans quelques instants (le squelette annonce « Chargement ») */}
            <p className="entete-titre" aria-hidden="true">{titre ?? <span className="os titre-os" />}</p>
          </div>
        </header>
        <div className="squelette" role="status" aria-label="Chargement">
          {SQUELETTE.map((lignes, section) => (
            <div key={section} className="squelette-section">
              <span className="os titre-section" aria-hidden="true" />
              {lignes.map(([l1, l2], rang) => (
                <div key={rang} className="ligne" aria-hidden="true">
                  <span className="case"><span className="os cercle" /></span>
                  <div className="ligne-corps">
                    <span className="os l1" style={{ width: l1 }} />
                    {l2 ? <span className="os l2" style={{ width: l2 }} /> : null}
                  </div>
                  <div className="ligne-fin" />
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

/** Un écran paresseux, sous sa propre frontière de chargement ; son montage lance le préchargement des autres. */
function ecranParesseux(cle, { ecran, titre, pleine }) {
  const Page = lazy(() => CHARGEURS[cle]())
  function EcranTaches() {
    useEffect(() => { prechargerEcrans() }, [])
    return (
      <Suspense fallback={<ChargementEcran ecran={ecran} titre={titre} pleine={pleine} />}>
        <Page />
      </Suspense>
    )
  }
  EcranTaches.displayName = `EcranTaches(${cle})`
  return EcranTaches
}

const Aujourdhui = ecranParesseux('aujourdhui', { ecran: 'aujourdhui', titre: "Aujourd'hui" })
const ATrier = ecranParesseux('atrier', { ecran: 'a-trier', titre: 'À trier' })
const Projets = ecranParesseux('projets', { ecran: 'projets', titre: 'Projets' })
const Projet = ecranParesseux('projet', { ecran: 'projet' })
const ProjetsArchive = ecranParesseux('archive', { ecran: 'projets-archive', titre: 'Archive' })
const ProjetsModeles = ecranParesseux('modeles', { ecran: 'projets-modeles', titre: 'Modèles' })
const Agenda = ecranParesseux('agenda', { ecran: 'agenda', titre: 'Agenda', pleine: true })
const Revue = ecranParesseux('revue', { ecran: 'revue', titre: 'Revue de la semaine' })
const Rythme = ecranParesseux('rythme', { ecran: 'rythme', titre: 'Mon rythme' })
const Recherche = ecranParesseux('recherche', { ecran: 'recherche', titre: 'Recherche' })
const Supprimees = ecranParesseux('supprimees', { ecran: 'supprimees', titre: 'Supprimées' })
const Reglages = ecranParesseux('reglages', { ecran: 'reglages', titre: 'Réglages' })

/** `/taches` mène à `/taches/aujourdhui` (api.md §7), en remplaçant l'entrée d'historique. */
function AllerAAujourdhui() {
  return <Navigate to="/taches/aujourdhui" replace />
}

const ROLES = ['normal', 'responsable', 'admin']
const GARDE = { roles: ROLES, perm: 'taches_voir' }

const navIcon = (Comp) => createElement(Comp, { size: 17, strokeWidth: 1.75, 'aria-hidden': 'true' })

const config = {
  key: 'taches',
  order: 60,
  nav: {
    label: 'Tâches', labelKey: 'nav.section.taches',
    // Glyphe d'APP unique (ODY34, `lib/apps/appGlyph.test.jsx`) ; les onglets gardent ceux de la maquette.
    icon: appGlyph(ListTodo),
    items: [
      { to: '/taches/aujourdhui', label: "Aujourd'hui", k: 'nav.taches_aujourdhui', icon: navIcon(Sun), ...GARDE },
      { to: '/taches/a-trier', label: 'À trier', k: 'nav.taches_a_trier', icon: navIcon(Inbox), ...GARDE },
      { to: '/taches/projets', label: 'Projets', k: 'nav.taches_projets', icon: navIcon(Folder), ...GARDE },
      { to: '/taches/agenda', label: 'Agenda', k: 'nav.taches_agenda', icon: navIcon(Calendar), ...GARDE },
    ],
  },
  titles: [
    ['/taches/reglages', 'Tâches — Réglages'],
    ['/taches/supprimees', 'Tâches — Supprimées'],
    ['/taches/recherche', 'Tâches — Recherche'],
    ['/taches/rythme', 'Tâches — Mon rythme'],
    ['/taches/revue', 'Tâches — Revue de la semaine'],
    ['/taches/agenda', 'Tâches — Agenda'],
    ['/taches/projets/archive', 'Tâches — Archive'],
    ['/taches/projets/modeles', 'Tâches — Modèles'],
    ['/taches/projets', 'Tâches — Projets'],
    ['/taches/a-trier', 'Tâches — À trier'],
    ['/taches', 'Tâches — Aujourd\'hui'],
  ],
  sectionLabels: { taches: 'Tâches' },
  routes: [
    { path: '/taches', component: AllerAAujourdhui, ...GARDE },
    { path: '/taches/aujourdhui', component: Aujourdhui, ...GARDE },
    { path: '/taches/a-trier', component: ATrier, ...GARDE },
    { path: '/taches/projets', component: Projets, ...GARDE },
    { path: '/taches/projets/archive', component: ProjetsArchive, ...GARDE },
    { path: '/taches/projets/modeles', component: ProjetsModeles, ...GARDE },
    { path: '/taches/projets/:id', component: Projet, ...GARDE },
    { path: '/taches/agenda', component: Agenda, ...GARDE },
    { path: '/taches/revue', component: Revue, ...GARDE },
    { path: '/taches/rythme', component: Rythme, ...GARDE },
    { path: '/taches/recherche', component: Recherche, ...GARDE },
    { path: '/taches/supprimees', component: Supprimees, ...GARDE },
    { path: '/taches/reglages/:rubrique?', component: Reglages, ...GARDE },
  ],
}

export default config
