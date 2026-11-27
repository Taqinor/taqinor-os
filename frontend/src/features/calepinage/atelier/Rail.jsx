import { estAtelierPompage } from './contexteAtelier'
import { Suspense, useCallback, useEffect, useRef } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import api from '../../../api/axios'
import {
  ErrorBoundary, SkeletonCard, SkeletonText, Tabs, TabsContent, TabsList, TabsTrigger,
} from '../../../ui'
import { HelpTip } from '../../../ui/HelpTip'
import { GLOSSAIRE_ONGLETS } from '../commun/glossaireOnglets'
import { PARAM_ONGLET, ongletParCle, resoudreOnglet } from './onglets'
// Le bandeau des étapes du mode guidé n'est PAS un onglet : il vit hors d'atelier/ (CALX383).
// Le bandeau d'étapes du mode guidé n'est pas un onglet : il vit hors d'atelier/ (CALX383).
import RailGuide from '../commun/RailGuide'
import OutilPosePompage from '../commun/OutilPosePompage'
import { PARAM_MODE, useModeExpert } from './modeExpert'
import { PARAM_CHAMP, useOuvrirChamp } from './ouvrirChamp'
import {
  ECRANS_ETAPE, ongletsVisibles, premierOngletEtape, useParcours, vueParcours,
} from './parcoursGuide'

/* ============================================================================
   CALX1 — LE RAIL D'ONGLETS DE L'ATELIER.
   ----------------------------------------------------------------------------
   Il lit `atelier/onglets.js` (le registre, seule surface qu'une tâche rouvre
   pour ajouter un panneau) et monte le composant de l'onglet actif. Il ne
   connaît AUCUN panneau par son nom : ajouter un onglet ne rouvre jamais ce
   fichier.

   L'ONGLET ACTIF EST DANS L'URL (`?onglet=<cle>`), jamais dans un `useState`
   caché : le lien est partageable, le bouton « précédent » du navigateur
   fonctionne, et un rechargement rouvre le même panneau. Les treize routes
   profondes historiques (`/calepinage/:id/<cle>`) restent servies telles
   quelles par `module.config.jsx` : elles sont les liens profonds qui ouvrent
   le même écran, avec la MÊME clé.

   PARITÉ (Aurora) — la conception d'un projet se parcourt par onglets d'un seul
   écran (Site / System / Simulate) plutôt que par des URL qu'il faut connaître :
   https://help.aurorasolar.com/hc/en-us/articles/21240604594963

   SANS `?onglet=`, AUCUN PANNEAU N'EST OUVERT : l'atelier rend exactement ce
   qu'il rendait hier, plus le rail. On n'impose pas un panneau — et un onglet
   ouvert d'office chargerait des données que personne n'a demandées.

   JAMAIS D'ÉCRAN BLANC, DEUX FOIS :
     - une clé inconnue retombe sur le PREMIER onglet (`resoudreOnglet`) ;
     - un panneau qui échoue au rendu est rattrapé par un `ErrorBoundary` qui
       NOMME l'onglet fautif — jamais un « une erreur est survenue » anonyme
       (règle fondateur : l'erreur désigne ce qui a échoué).

   CALX222 — `builderApi` DESCEND JUSQU'AUX PANNEAUX. L'atelier possède déjà
   l'API du constructeur 3D (`AtelierPanneaux.jsx`, qui la tient de l'écran de
   conception, CALX8) ; le rail la relayait à personne, si bien qu'un panneau
   qui pilote la scène — « Armer la pose » d'`EquipementsElectriques.jsx` —
   n'avait aucun moyen de l'atteindre et répondait « outil 3D non prêt » même
   quand il l'était. Elle est donc passée à CHAQUE panneau : ceux qui ne la
   DÉCLARENT pas dans leurs props l'ignorent, et le rail ne connaît toujours
   aucun panneau par son nom. Absente (le rail monté hors de la scène 3D),
   elle vaut `null` : le panneau le DIT au lieu d'échouer en silence — jamais
   une pose armée dans le vide.

   CALX392 — PILOTABLE AU CLAVIER, SELON LE PATRON ARIA DES ONGLETS
   (https://www.w3.org/WAI/ARIA/apg/patterns/tabs/). Radix pose déjà la
   sémantique : `role="tablist"` + `aria-orientation`, un `role="tab"` par
   onglet avec `aria-selected`/`aria-controls`, le panneau en `role="tabpanel"`
   avec `aria-labelledby`, un SEUL onglet tabulable à la fois (tabindex
   mobile), Flèches qui BOUCLENT, Début/Fin. Deux décisions sont prises ICI :
     - activation MANUELLE : les flèches déplacent le focus sans ouvrir de
       panneau (chaque onglet charge ses données — les ouvrir tous en
       parcourant le rail serait une rafale de requêtes que personne n'a
       demandées) ; Entrée ou Espace OUVRE l'onglet focalisé ;
     - à l'ouverture par l'utilisateur, le focus PART SUR LE PANNEAU, pour que
       la touche Tab suivante entre dans son contenu ; Maj+Tab revient à
       l'onglet ouvert. Un `?onglet=` présent au chargement n'arrache JAMAIS
       le focus (seule une ouverture demandée le déplace).
   Les intertitres de groupe restent hors du chemin du clavier
   (`aria-hidden`), et leur conteneur n'a aucun rôle (`role="none"`).
   ========================================================================== */

/* ============================================================================
   CALX397 — SAVOIR QUELS ONGLETS SONT RÉELLEMENT OUVERTS.
   ----------------------------------------------------------------------------
   `uxviews.EcranRecent` (UNE ligne par société + utilisateur + écran, jamais
   un journal qui grossit) n'a qu'un chemin d'écriture : la lecture
   `GET saved-views/?ecran=` (`SavedViewViewSet.list`). Un onglet n'étant pas
   une route d'écran, aucune ligne n'était jamais écrite pour lui. Le rail
   emprunte donc CE chemin existant — aucun modèle, aucune migration, aucun
   endpoint neuf — avec la seule CLÉ du registre (`calepinage:<cle>`, jamais
   un libellé traduit, jamais une donnée du calepinage).
     - au plus UNE fois par onglet et par session du navigateur
       (`sessionStorage` ; à défaut, la mémoire de la page) ;
     - jamais bloquant : l'appel part après le rendu, et son échec est avalé —
       l'onglet s'affiche exactement pareil, SANS le toast d'erreur global
       (`suppressErrorToast`, cf. `api/axios.js`) : une mesure d'usage qui
       échoue n'a rien à dire à l'utilisateur. Même URL et même paramètre que
       `uxviewsApi.listSavedViews` — c'est l'instance axios partagée qui porte
       l'option, que ce raccourci ne transmet pas.
   ========================================================================== */

/** Le chemin EXISTANT qui écrit `EcranRecent` (NTUX39). */
const URL_VUES_SAUVEGARDEES = '/uxviews/saved-views/'

const CLE_SESSION_ONGLETS = 'calepinage:onglets-signales'
const ongletsSignalesEnMemoire = new Set()

/** Vrai la PREMIÈRE fois que `cle` est vue dans la session — et la retient. */
function premiereOuvertureDeLaSession(cle) {
  try {
    const brut = window.sessionStorage.getItem(CLE_SESSION_ONGLETS)
    const vus = brut ? JSON.parse(brut) : []
    const liste = Array.isArray(vus) ? vus : []
    if (liste.includes(cle)) return false
    window.sessionStorage.setItem(CLE_SESSION_ONGLETS, JSON.stringify([...liste, cle]))
    return true
  } catch {
    // Stockage indisponible (navigation privée, quota) : la mémoire de la
    // page tient lieu de session — jamais une rafale d'appels.
    if (ongletsSignalesEnMemoire.has(cle)) return false
    ongletsSignalesEnMemoire.add(cle)
    return true
  }
}

/** Signale l'ouverture de l'onglet `cle` — best-effort, jamais bloquant. */
function signalerOuverture(cle) {
  if (!cle || !premiereOuvertureDeLaSession(cle)) return
  Promise.resolve()
    .then(() => api.get(URL_VUES_SAUVEGARDEES, {
      params: { ecran: `calepinage:${cle}` },
      suppressErrorToast: true,
    }))
    .catch(() => {})
}

/** Le bandeau d'erreur d'un panneau : il NOMME l'onglet qui n'a pas pu s'ouvrir. */
function EchecOnglet({ libelle }) {
  return (
    <p
      role="alert"
      data-testid="cal-onglet-erreur"
      className="mt-3 border border-destructive/50 bg-destructive/5 px-4 py-3 text-sm text-destructive"
    >
      {`L'onglet « ${libelle} » n'a pas pu s'afficher. Les autres onglets restent ouvrables ; rechargez la page si le problème persiste.`}
    </p>
  )
}

/* ACAL23 — LE RAIL RELAIE AUSSI `onRecharger`, `lectureSeule` ET `documentVivant`.
   Un onglet qui change le document SERVEUR (restauration de version, import de
   conception) doit faire relire la scène — sinon « Enregistrer le calepinage »
   republierait la copie d'avant et annulerait son geste. `onRecharger` est
   l'UNIQUE rechargement de l'atelier (posé par l'écran de conception) ;
   `documentVivant = {empreinte, appliquerSection(cle, valeur, empreinteApres)}`
   porte le jeton d'écriture courant (empreinte « document », contrat
   `calepinage_layout_section.json`) et la façon d'appliquer UNE section écrite
   par l'onglet à la scène vivante. Comme `builderApi`, un panneau qui ne les
   déclare pas les ignore. */
/* ACAL600 — le niveau expert est TENU par `AtelierPanneaux` et reçu en props (un seul
   état) ; monté seul, le rail le tient lui-même — jamais les deux à la fois. */
export default function Rail(props = {}) {
  return props.onBasculerExpert ? <RailCorps {...props} /> : <RailAutonome {...props} />
}

function RailAutonome(props) {
  const [parametres] = useSearchParams()
  const [expert, basculer] = useModeExpert(parametres.get(PARAM_MODE) === 'expert')
  return <RailCorps {...props} expert={expert} onBasculerExpert={basculer} />
}

function RailCorps({
  calepinageId: idPropose = null, builderApi = null,
  onRecharger = null, lectureSeule = false, documentVivant = null,
  expert, onBasculerExpert: basculerExpert,
  onEtape = null, // ACAL868 — publie {etape, expert, allerA} à l'écran (barre fixe) ; jamais un second état d'expert
  actionDevis = null, // ACAL867 — « Générer le devis » de l'atelier, relayé tel quel à l'écran de l'étape Documents
  // Coque (22/11) — monté dans la coque plein écran : les étapes sont au rail de gauche (pas ici), et en
  // guidé l'écran de l'étape est monté par la coque (ici : les seuls onglets) ; `parcours` = celui de la coque.
  dansCoque = false, parcours: parcoursImpose = null,
  contexte = null, // ACAL1268 — le design-context : relayé aux onglets d'un lead de POMPAGE seulement (ni kWh de réseau ni économies)
}) {
  const { id: idUrl } = useParams()
  const calepinageId = idPropose ?? idUrl ?? null

  const [parametres, setParametres] = useSearchParams()
  const actif = resoudreOnglet(parametres.get(PARAM_ONGLET))
  const cleActive = actif?.cle ?? null
  // ACAL393 — rail guidé : 5 étapes ; pour l'étape active, ses seuls essentiels
  // (+ l'onglet ouvert s'il est expert). L'étape se déduit de l'URL.
  const parcoursLocal = useParcours(parcoursImpose ? null : calepinageId)
  const parcours = parcoursImpose ?? parcoursLocal
  const etats = parcours.etats
  // ACAL395 — en guidé, les panneaux d'un écran d'étape (Électrique) s'ouvrent
  // dans UNE page portée par l'onglet `ouverture` ; l'URL garde la clé demandée.
  const { ecran, cleVue, cleEtape } = vueParcours(cleActive, etats, expert, parcours.memorisee)
  const visibles = ongletsVisibles(cleEtape, cleVue, expert).map(ongletParCle).filter(Boolean)
  const libelleOnglet = (o) => (!expert
    && Object.values(ECRANS_ETAPE).find((e) => e.ouverture === o.cle)?.libelle) || o.libelle

  // ACAL397 — `?champ=` : défiler jusqu'au champ et le focaliser.
  useOuvrirChamp(parametres.get(PARAM_CHAMP), cleActive)

  // CALX392 — le panneau à focaliser, et SI une ouverture le demande.
  const panneauRef = useRef(null)
  const focusApresOuverture = useRef(false)

  useEffect(() => {
    if (!focusApresOuverture.current) return
    focusApresOuverture.current = false
    panneauRef.current?.focus()
  }, [cleActive])

  // CALX397 — l'onglet MONTÉ est signalé (une fois par session, sans bloquer).
  useEffect(() => {
    signalerOuverture(cleActive)
  }, [cleActive])

  /* Un changement d'onglet n'écrase pas les autres paramètres de l'URL : le
     calepinage peut en porter d'autres (filtre, variante) qu'on n'a pas à
     connaître ici. */
  const ouvrir = (cle) => {
    if (cle === cleVue) {
      // Rouvrir l'onglet déjà ouvert (Entrée sur lui) : rien à écrire dans
      // l'URL, le focus part simplement sur son panneau.
      panneauRef.current?.focus()
      return
    }
    focusApresOuverture.current = true
    const suivants = new URLSearchParams(parametres)
    suivants.set(PARAM_ONGLET, cle)
    setParametres(suivants)
  }

  const choisirEtape = (cle) => {
    const premier = premierOngletEtape(cle, expert)
    if (premier) ouvrir(premier)
  }

  // ACAL868 — `allerA` garde une identité stable (il lit la dernière `choisirEtape`) : l'effet ne rebondit pas.
  const choisirEtapeRef = useRef(choisirEtape)
  useEffect(() => { choisirEtapeRef.current = choisirEtape })
  const allerA = useCallback((cle) => choisirEtapeRef.current(cle), [])
  useEffect(() => { onEtape?.({ etape: cleEtape, expert, allerA }) }, [onEtape, cleEtape, expert, allerA])

  const Composant = ecran?.composant ?? actif?.composant ?? null
  // ACAL1268 (D-ACAL-66) — pompage : les onglets de résultats et d'électrique du réseau ne s'ouvrent pas (carte de renvoi).
  const pompageSansReseau = estAtelierPompage(contexte)
    && (actif?.groupe === 'Résultats' || ECRANS_ETAPE.electrique.onglets.includes(cleActive))
  const libelleActif = ecran ? ecran.libelle : actif?.libelle

  return (
    <Tabs
      value={cleVue ?? ''}
      onValueChange={ouvrir}
      activationMode="manual"
      orientation="horizontal"
      className="mt-5"
      data-testid="cal-rail-onglets"
    >
      {/* CALX396 — l'AIDE du rail : un lien vers le lexique métier (PR,
          P50/P90, GCR, TSRF, PVGIS, MPPT…), jamais une seconde définition dans
          une bulle. Placé AVANT la liste d'onglets : il reste hors du trajet
          Maj+Tab qui ramène du panneau à l'onglet ouvert (CALX392). */}
      <p className="mb-1.5 text-right text-xs text-muted-foreground">
        <Link to="/aide/lexique" className="underline underline-offset-2"
          data-testid="cal-rail-lexique">
          Lexique des termes du solaire
        </Link>
      </p>
      {!dansCoque && (
        <RailGuide etapeActive={cleEtape} etats={etats} onChoisir={choisirEtape}
          expert={expert} onBasculerExpert={basculerExpert} />
      )}
      {/* a11y (ACAL439) — un `tablist` ne doit posséder que des `tab` : les bulles d'aide
          (boutons) en sont SŒURS, pas filles. Le conteneur visuel (bordure, fond, flex-wrap) est
          ce `div` ; `TabsList` est en `display: contents` et l'`order` CSS remet chaque bulle juste
          après son onglet (onglet 2i, bulle 2i+1). */}
      <div className="flex w-full flex-wrap items-center gap-x-1 gap-y-1.5 rounded-lg border border-border bg-muted p-1">
        <TabsList aria-label="Onglets du calepinage" className="contents">
          {visibles.map((onglet, i) => (
            <TabsTrigger key={onglet.cle} value={onglet.cle} style={{ order: 2 * i }}
              data-testid={`cal-onglet-${onglet.cle}`}>
              {libelleOnglet(onglet)}
            </TabsTrigger>
          ))}
        </TabsList>
        {/* ACAL419 — la bulle est HORS de `TabsTrigger` et du tablist : hors du trajet des flèches. */}
        {visibles.map((onglet, i) => GLOSSAIRE_ONGLETS[onglet.cle] && (
          <span key={onglet.cle} className="inline-flex" style={{ order: 2 * i + 1 }}>
            <HelpTip label={`À quoi sert « ${onglet.libelle} »`} tabIndex={-1}>
              {GLOSSAIRE_ONGLETS[onglet.cle]}
            </HelpTip>
          </span>
        ))}
      </div>

      {actif && Composant && !(dansCoque && !expert) && (
        <TabsContent ref={panneauRef} value={cleVue} data-testid="cal-onglet-panneau">
          <ErrorBoundary
            key={cleVue}
            fallback={<EchecOnglet libelle={libelleActif} />}
          >
            <Suspense
              fallback={(
                <div role="status" aria-label="Chargement…" className="mt-3 space-y-3">
                  <SkeletonCard />
                  <SkeletonText lines={2} />
                </div>
              )}
            >
              {/* CALX222 — `builderApi` est relayée à TOUS les panneaux :
                  ceux qui ne la déclarent pas l'ignorent, et le rail
                  continue de ne connaître aucun panneau par son nom. */}
              {pompageSansReseau ? (
                <OutilPosePompage contexte={contexte}
                  phrase="Lead de pompage : l’atelier pose les panneaux, sans économies, énergie du réseau, onduleur ni batterie." />
              ) : (
              <Composant
                calepinageId={calepinageId}
                builderApi={builderApi}
                onRecharger={onRecharger}
                lectureSeule={lectureSeule}
                documentVivant={documentVivant}
                parcours={parcours}
                actionDevis={actionDevis}
                ouvert={cleActive}
              />
              )}
            </Suspense>
          </ErrorBoundary>
        </TabsContent>
      )}
    </Tabs>
  )
}
