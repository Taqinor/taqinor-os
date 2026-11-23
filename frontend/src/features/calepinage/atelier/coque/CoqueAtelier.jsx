import { Suspense, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useSearchParams } from 'react-router-dom'
import calepinageApi from '../../../../api/calepinageApi'
import { ErrorBoundary, SkeletonCard, SkeletonText } from '../../../../ui'
import BarreEnregistrement from '../BarreEnregistrement'
import { formaterHeureBrouillon } from '../contexteAtelier'
import { PARAM_MODE, useModeExpert } from '../modeExpert'
import { PARAM_ONGLET, resoudreOnglet } from '../onglets'
import { cadrerToitAtelier } from '../useAtelierBoot'
import {
  CADRES, ETAPES, ecranCoque, premierOngletEtape, useParcours, vueParcours,
} from '../parcoursGuide'
import { BandeauAlertes } from './BandeauxCoque'
import BarreProjet from './BarreProjet'
import { ETAPES_POSE, sousTitrePose } from './projet'
import { ContexteCoque, ContextePresentation } from './contexteCoque'
import PanneauEtape from './PanneauEtape'
import { BoutonOr } from './primitives'
import RailEtapes from './RailEtapes'

/* ============================================================================
   COQUE (maquettes 22/11) — L'ATELIER PLEIN ÉCRAN DU MODULE CALEPINAGE.
   ----------------------------------------------------------------------------
   Bandeau du projet en haut ; rail des étapes à gauche ; au centre la carte
   (`#rp9-studio-scene`) OU l'écran d'une étape « pleine » ; à droite le panneau
   d'étape (`#rp9-studio-inspecteur`). Route sans la mise en page de l'ERP
   (`plein: true`, `WithAtelier`). Le mode lead (CRM) n'y passe jamais.

   L'ÉTAPE EST DANS L'URL (`?onglet=`), lue par la MÊME fonction que le rail
   d'onglets (`vueParcours`) : aucun second état. Le niveau expert et le parcours
   sont tenus ICI et descendent au rail d'onglets (`AtelierPanneaux` › `Rail`).

   RIEN N'EST DÉMONTÉ : la carte et les groupes du constructeur (`groupes`) sont
   montés pour toute la session ; une étape ne fait que les masquer (`hidden`).
   Quand la carte réapparaît, la coque émet `resize` (la carte suit aussi sa
   boîte par ResizeObserver — MapLibre 6) pour qu'elle se redessine.

   Guidé : l'écran de l'étape (`ECRANS_ETAPE`, champs `cadre` / `titre`) ; Expert
   et « Avancé » : l'ancien inspecteur entier (`avance`), rail d'onglets compris.

   TABLETTE / TÉLÉPHONE (< 1 280 px, maquette Tablette) : le panneau d'étape devient le
   TIROIR du bas (`tiroir`, poignée pour l'agrandir) ; le rail se replie en pictogrammes
   (en barre du bas au téléphone). Mise en page : 56-coque-responsive.css.

   PRÉSENTATION (« Montrer au client », `ContextePresentation` posé par client/VueClient) :
   le MÊME atelier, sa carte 3D seule visible ; bandeau, rail, panneau et calques d'étape
   sont MASQUÉS (`hidden`, jamais démontés : les contrôles du constructeur restent là, le
   soleil leur est renvoyé) ; l'habillage client (`presentation.rendu`) est rendu autour.
   ========================================================================== */

const REQUETE_TIROIR = '(max-width: 1279px)'

/** Vrai quand la largeur range le panneau d'étape en tiroir du bas (même seuil que la feuille 56). */
function useTiroir() {
  const lire = () => (typeof window !== 'undefined' && typeof window.matchMedia === 'function'
    ? !!window.matchMedia(REQUETE_TIROIR)?.matches : false)
  const [tiroir, setTiroir] = useState(lire)
  useEffect(() => {
    const mq = typeof window.matchMedia === 'function' ? window.matchMedia(REQUETE_TIROIR) : null
    if (!mq?.addEventListener) return undefined
    const suivre = () => setTiroir(!!mq.matches)
    mq.addEventListener('change', suivre)
    return () => mq.removeEventListener('change', suivre)
  }, [])
  return tiroir
}

const TOTAL = ETAPES.length

// Les gestes qui CHOISISSENT une vue (segment Plan/3D de la carte, vues de la feuille « Avancé », boussole) : après
// l'un d'eux, la coque ne repose plus « Plan » d'office pour la séance. Le cadrage reste reposé à chaque étape.
const CHOIX_VUE = '.cal-barre-outils-carte [role="group"] button, [data-testid^="cal-vue-"], '
  + '[data-testid="cal-onglet-3d"], [data-testid="cal-onglet-2d"], .maplibregl-ctrl-compass'
// La carte et le constructeur se posent tard sur un poste chargé : la vue est reposée à ces instants après l'entrée.
const ESSAIS_PLAN_MS = [0, 1500, 4000, 8000]

/** Plan + cadrage à l'entrée d'une étape à carte (caméra seule : rien n'est sérialisé, aucun brouillon). */
function usePlanALEntreeDEtape({ builderRef, actif, cle, builderApiCoque }) {
  const vueChoisie = useRef(false)
  useEffect(() => {
    const noter = (e) => { if (e.target?.closest?.(CHOIX_VUE)) vueChoisie.current = true }
    document.addEventListener('click', noter, true)
    return () => document.removeEventListener('click', noter, true)
  }, [])
  useEffect(() => {
    if (!actif || !builderApiCoque) return undefined
    let touchee = false
    const carte = document.getElementById('rp9-map')
    const toucher = () => { touchee = true }
    carte?.addEventListener('pointerdown', toucher, true)
    carte?.addEventListener('wheel', toucher, { capture: true, passive: true })
    const poser = () => {
      const b = builderRef.current
      if (!b || touchee) return
      if (!vueChoisie.current) b.appliquerVue?.('dessus')
      cadrerToitAtelier(b)
    }
    const minuteurs = ESSAIS_PLAN_MS.map((ms) => window.setTimeout(() => window.requestAnimationFrame(poser), ms))
    return () => {
      minuteurs.forEach((m) => window.clearTimeout(m))
      carte?.removeEventListener('pointerdown', toucher, true)
      carte?.removeEventListener('wheel', toucher, { capture: true })
    }
  }, [actif, cle, builderApiCoque, builderRef])
}

// H7 — la feuille « Avancé » ne reste jamais par-dessus ce qu'elle n'a pas ouvert. Elle se referme : sur Échap, sur un
// changement d'adresse (lien ou onglet suivi depuis elle — CAL221 : « Comparer les variantes » laissait la feuille sur
// « Retenir »), sur un clic hors d'elle, et quand un geste fait DEPUIS elle ouvre un autre dialogue (posé hors d'elle).
const GARDE_FEUILLE = '.cal-coque-avance, [data-testid="cal-rail-avance"], [role="dialog"], [role="alertdialog"], '
  + '[role="listbox"], [role="menu"], [data-radix-popper-content-wrapper], [data-sonner-toaster]'
const AUTRE_DIALOGUE = '[role="dialog"]:not(.cal-coque-avance), [role="alertdialog"], [aria-modal="true"]'
const ESSAIS_DIALOGUE_MS = [50, 400, 1500]

function useFermetureFeuille(feuille, fermer, cleLieu) {
  const fermerRef = useRef(fermer)
  useEffect(() => { fermerRef.current = fermer })
  // L'adresse au moment où la feuille s'ouvre : tenue à jour tant qu'elle est fermée (aucun état posé au montage).
  const lieuOuvert = useRef(cleLieu)
  useEffect(() => {
    if (feuille && lieuOuvert.current !== cleLieu) fermerRef.current()
  }, [feuille, cleLieu])
  useEffect(() => { if (!feuille) lieuOuvert.current = cleLieu })
  useEffect(() => {
    if (!feuille) return undefined
    const dialoguesHors = () => [...document.querySelectorAll(AUTRE_DIALOGUE)]
      .filter((d) => !d.closest('.cal-coque-avance')).length
    const minuteurs = []
    const echap = (e) => { if (e.key === 'Escape') fermerRef.current() }
    const dehors = (e) => { if (!e.target?.closest?.(GARDE_FEUILLE)) fermerRef.current() }
    const dedans = (e) => {
      if (!e.target?.closest?.('.cal-coque-avance')) return
      const avant = dialoguesHors()
      ESSAIS_DIALOGUE_MS.forEach((ms) => minuteurs.push(window.setTimeout(() => {
        if (dialoguesHors() > avant) fermerRef.current()
      }, ms)))
    }
    window.addEventListener('keydown', echap)
    document.addEventListener('pointerdown', dehors, true)
    document.addEventListener('click', dedans, true)
    return () => {
      window.removeEventListener('keydown', echap)
      document.removeEventListener('pointerdown', dehors, true)
      document.removeEventListener('click', dedans, true)
      minuteurs.forEach((m) => window.clearTimeout(m))
    }
  }, [feuille])
}

const etatSimulation = (data) => (data?.calcule_le && data?.simulation_perimee === false
  ? `Simulation à jour · ${formaterHeureBrouillon(data.calcule_le)}` : null)

/** Le résultat SERVI (`resultat/`) aux étapes Électrique, Résultats et Documents : « Simulation à jour · HH:MM » à
    Résultats, et la ligne « N panneaux · x kWc (· onduleur) » du bandeau (maquettes). `null` tant qu'il n'est pas lu. */
function useResultatServi(calepinageId, actif, relecture) {
  const [data, setData] = useState(null)
  useEffect(() => {
    if (!actif || !calepinageId) return undefined
    let vivant = true
    Promise.resolve()
      .then(() => calepinageApi.calepinages.resultat(calepinageId))
      .then((rep) => { if (vivant) setData(rep?.data ?? null) })
      .catch(() => { if (vivant) setData(null) })
    return () => { vivant = false }
  }, [calepinageId, actif, relecture])
  return actif ? data : null
}

/** L'heure de la dernière version enregistrée, servie par le détail (`versions.derniere_le`). */
function useDerniereVersion(calepinageId, relecture) {
  const [le, setLe] = useState(null)
  useEffect(() => {
    if (!calepinageId) return undefined
    let vivant = true
    Promise.resolve()
      .then(() => calepinageApi.calepinages.get(calepinageId))
      .then((rep) => { if (vivant) setLe(rep?.data?.versions?.derniere_le ?? null) })
      .catch(() => { if (vivant) setLe(null) })
    return () => { vivant = false }
  }, [calepinageId, relecture])
  return le
}

/** Le vrai bouton de devis du bloc, quand il est monté et à l'écran (hors `hidden`). */
function boutonDevisVisible() {
  const bouton = document.querySelector('[data-testid="cal-generer-devis"], [data-testid="cal-resynchroniser-devis"]')
  return bouton && !bouton.closest('[hidden]') ? bouton : null
}

/** Met le focus sur le vrai bouton de devis dès qu'il est monté (étape Documents). */
function focaliserBoutonDevis(essais = 30) {
  const bouton = boutonDevisVisible()
  if (bouton) { bouton.focus(); return }
  if (essais > 0) window.setTimeout(() => focaliserBoutonDevis(essais - 1), 100)
}

export default function CoqueAtelier({
  calepinageId, retour, titre, sousTitre, enregistrement = null, libelleDevis, devisPossible = true,
  carte, statut = null, groupes = {}, alertes = null, avance: contenuAvance = null,
  ecranProps = {}, enregistreLe = null, onEtape = null, renderAtelierPanneaux = null,
}) {
  const presentation = useContext(ContextePresentation)
  const tiroir = useTiroir() && !presentation
  const [deplie, setDeplie] = useState(false)
  const [parametres, setParametres] = useSearchParams()
  const [expert, basculerExpert] = useModeExpert(parametres.get(PARAM_MODE) === 'expert')
  const parcours = useParcours(calepinageId)
  const cleActive = resoudreOnglet(parametres.get(PARAM_ONGLET))?.cle ?? null
  const { cleEtape } = vueParcours(cleActive, parcours.etats, expert)
  const ecran = ecranCoque(cleActive, resoudreOnglet(cleActive), parcours.etats, expert)
  // J1 — présentation : la carte, toujours (la 3D est la scène du client, quelle que soit l'étape du parcours).
  const cadre = expert || presentation ? CADRES.CARTE : (ecran?.cadre ?? CADRES.CARTE)
  // « Avancé » (guidé) : une FEUILLE à part, posée par-dessus l'écran (l'écran guidé reste intact dessous) ;
  // Expert : l'ancienne disposition entière (contrôles du constructeur, rangées sous la carte, recherche).
  const [avanceOuvert, setAvanceOuvert] = useState(false)
  const avance = expert || avanceOuvert
  const feuille = !expert && avanceOuvert
  const lieu = useLocation()
  useFermetureFeuille(feuille, () => setAvanceOuvert(false), `${lieu.pathname}${lieu.search}`)
  const carteVisible = cadre === CADRES.CARTE

  const choisirEtape = (cle) => {
    const premier = premierOngletEtape(cle, expert)
    setAvanceOuvert(false) // une étape choisie referme la feuille « Avancé »
    if (!premier || premier === cleActive) return
    const suivants = new URLSearchParams(parametres)
    suivants.set(PARAM_ONGLET, premier)
    setParametres(suivants)
  }
  const choisirRef = useRef(choisirEtape)
  useEffect(() => { choisirRef.current = choisirEtape })
  const allerA = useCallback((cle) => choisirRef.current(cle), [])
  useEffect(() => { onEtape?.({ etape: cleEtape, expert, allerA }) }, [onEtape, cleEtape, expert, allerA])

  const rang = ETAPES.findIndex((e) => e.cle === cleEtape)
  const suivante = rang >= 0 ? ETAPES[rang + 1] : null
  const action = !expert && suivante && ETAPES[rang].action
    ? { libelle: ETAPES[rang].action, onClick: () => choisirEtape(suivante.cle) } : null

  // Emplacements ouverts aux écrans (coque/emplacements.jsx) : nœuds DOM + pied « pris ».
  const [noeudSurCarte, setNoeudSurCarte] = useState(null)
  const [noeudPanneau, setNoeudPanneau] = useState(null)
  const [noeudPiedPanneau, setNoeudPiedPanneau] = useState(null)
  const [noeudPiedPlein, setNoeudPiedPlein] = useState(null)
  const [noeudDevis, setNoeudDevis] = useState(null)
  const [noeudControle, setNoeudControle] = useState(null)
  const [noeudPresentation, setNoeudPresentation] = useState(null)
  const [piedsPris, setPiedsPris] = useState(0)
  const prendrePied = useCallback(() => {
    setPiedsPris((n) => n + 1)
    return () => setPiedsPris((n) => n - 1)
  }, [])
  const pleine = cadre === CADRES.PLEIN
  const valeurCoque = useMemo(() => ({
    noeuds: {
      surCarte: noeudSurCarte, panneau: noeudPanneau, pied: pleine ? noeudPiedPlein : noeudPiedPanneau,
      controle: noeudControle,
    },
    prendrePied,
    tiroir,
  }), [noeudSurCarte, noeudPanneau, noeudPiedPanneau, noeudPiedPlein, noeudControle, pleine, prendrePied, tiroir])

  // La carte réapparaît (retour d'une étape pleine) : elle se recale sur sa boîte (resize).
  const builderApiCoque = ecranProps.builderApi ?? null
  const builderRef = useRef(builderApiCoque)
  useEffect(() => { builderRef.current = builderApiCoque })
  const carteAvant = useRef(carteVisible)
  useEffect(() => {
    if (carteVisible && !carteAvant.current) window.requestAnimationFrame(() => window.dispatchEvent(new Event('resize')))
    carteAvant.current = carteVisible
  }, [carteVisible])
  // H1 (tour 3) — RÈGLE DE LA COQUE : chaque étape à carte s'ouvre en « Plan », le toit cadré et centré (au-dessus
  // du tiroir sur tablette), sauf si l'utilisateur a choisi une vue dans la séance ou touche la carte entre-temps.
  usePlanALEntreeDEtape({ builderRef, actif: carteVisible && !presentation, cle: `${cleEtape}:${tiroir}`, builderApiCoque })

  // J1 — présentation : ni résultat ni détail pour le bandeau (masqué) — aucune lecture de plus devant le client.
  const resultatServi = useResultatServi(calepinageId, ETAPES_POSE.includes(cleEtape) && !presentation, enregistreLe)
  const etatPropre = cleEtape === 'resultats' && !expert ? etatSimulation(resultatServi) : null
  const derniereVersionLe = useDerniereVersion(presentation ? null : calepinageId, enregistreLe)

  // ACAL1437 — un bouton qui dit « Générer » génère quand son bloc est à l'écran (Documents, ou Expert), même route.
  const onDevis = () => {
    const bouton = boutonDevisVisible()
    if (bouton && !bouton.disabled) { bouton.click(); return }
    if (cleEtape !== 'documents') allerA('documents')
    focaliserBoutonDevis()
  }

  const Ecran = ecran?.composant ?? null
  const ecranMonte = Ecran && (
    <ErrorBoundary key={`${cleEtape}:${cleActive ?? ''}`} fallback={(
      <p role="alert" className="text-sm text-destructive">
        {`L'étape « ${ecran.titre ?? cleEtape} » n'a pas pu s'afficher. Rechargez la page si le problème persiste.`}
      </p>
    )}>
      <Suspense fallback={(
        <div role="status" aria-label="Chargement…" className="space-y-3">
          <SkeletonCard />
          <SkeletonText lines={2} />
        </div>
      )}>
        {/* Un onglet ouvert par l'URL (`?onglet=`) : l'écran monté EST son panneau (`cal-onglet-panneau`,
            le hook du rail d'onglets, qui ne monte pas de panneau en guidé dans la coque). */}
        <div className="cal-coque-ecran-hote" data-testid={cleActive ? 'cal-onglet-panneau' : undefined}>
          <Ecran {...ecranProps} calepinageId={calepinageId} parcours={parcours} ouvert={cleActive}
            action={action} enregistreLe={enregistreLe || derniereVersionLe}
            actionDevis={<span ref={setNoeudDevis} className="contents" />} />
        </div>
      </Suspense>
    </ErrorBoundary>
  )
  const piedParDefaut = action && piedsPris === 0 && !pleine ? (
    <BoutonOr plein fleche onClick={action.onClick} data-testid="cal-action-etape-suivante">{action.libelle}</BoutonOr>
  ) : null

  return (
    <ContexteCoque.Provider value={valeurCoque}>
      <div className="rp9-host cal-coque" data-testid="cal-coque" data-etape={cleEtape} data-cadre={cadre}
        data-avance={expert ? '1' : '0'} data-expert={expert ? '1' : '0'} data-feuille={feuille ? '1' : undefined}
        data-presentation={presentation ? '1' : undefined}>
        <BarreProjet cache={!!presentation} retour={retour} titre={titre} expert={expert} onExpert={basculerExpert}
          sousTitre={sousTitrePose(resultatServi, cleEtape) || sousTitre}
          libelleDevis={libelleDevis} onDevis={devisPossible ? onDevis : null}
          enregistrement={enregistrement && <BarreEnregistrement {...enregistrement} etatPropre={etatPropre}
            derniereVersionLe={derniereVersionLe} />} />
        <BandeauAlertes cache={!!presentation}>{alertes}</BandeauAlertes>
        <div id="rp9-studio" className="cal-coque-corps">
          <RailEtapes cache={!!presentation} etapeActive={cleEtape} parcours={parcours} onChoisir={allerA}
            avance={avance} onAvance={setAvanceOuvert} />
          <main className="cal-coque-centre">
            <div id="rp9-studio-scene" className="cal-coque-scene" hidden={!carteVisible}>
              {carte}
              <div ref={setNoeudSurCarte} className="cal-coque-sur-carte" hidden={presentation ? true : undefined} />
              {statut}
              {presentation && <div ref={setNoeudPresentation} className="cal-coque-sur-carte-client" />}
            </div>
            {!carteVisible && (
              <div className="cal-coque-plein">
                {/* ACAL1727 — la même tête que le panneau d'étape : « Étape N sur 5 » + titre (cadre plein seulement ;
                    le Schéma garde son panneau à droite). */}
                {pleine && rang >= 0 && ecran?.titre && (
                  <div className="cal-plein-etape-tete" data-testid="cal-plein-etape-tete">
                    <p className="cal-panneau-etape-rang">{`Étape ${rang + 1} sur ${TOTAL}`}</p>
                    <h2 className="cal-panneau-etape-titre">{ecran.titre}</h2>
                  </div>
                )}
                {ecranMonte}
                <div ref={setNoeudPiedPlein} className="cal-coque-plein-pied" />
              </div>
            )}
          </main>
          <PanneauEtape numero={rang >= 0 ? rang + 1 : null} total={TOTAL} titre={ecran?.titre ?? null}
            cache={(pleine && !avance) || !!presentation} refCorps={setNoeudPanneau} refPied={setNoeudPiedPanneau}
            pied={piedParDefaut} tiroir={tiroir} deplie={deplie} onDeplier={setDeplie} refControle={setNoeudControle}>
            {/* J1 — présentation : l'écran d'étape n'est pas monté (il ne tient aucun nœud `rp9-*`, il les LIT) — sa
                caméra d'entrée (« Plan » à l'étape Toit) ne remet jamais la vue client de dessus. */}
            {carteVisible && !presentation && ecranMonte}
            <div className="cal-coque-groupe" data-groupe="toit" hidden={!(expert || cleEtape === 'toit')}>
              {groupes.outils}
              {groupes.toit}
            </div>
            <div className="cal-coque-groupe" data-groupe="pose" hidden={!(expert || cleEtape === 'panneaux')}>
              {groupes.pose}
            </div>
            <div className="cal-coque-avance" hidden={!avance} role={feuille ? 'dialog' : undefined}
              aria-label={feuille ? 'Avancé' : undefined}>
              {feuille && (
                <div className="cal-coque-feuille-tete">
                  <h2>Avancé</h2>
                  <button type="button" className="cal-coque-feuille-fermer" onClick={() => setAvanceOuvert(false)}>Fermer</button>
                </div>
              )}
              {contenuAvance}
              {renderAtelierPanneaux?.({
                expert, onBasculerExpert: basculerExpert, parcours, portailDevis: noeudDevis,
              })}
            </div>
          </PanneauEtape>
        </div>
        {presentation?.rendu?.({
          calepinageId, builderApi: ecranProps.builderApi ?? null, noeudScene: noeudPresentation,
          // H1 (demande H2) — le contexte déjà servi à l'atelier : la vue client ne relit pas design-context.
          contexte: ecranProps.contexte ?? null, onRecharger: ecranProps.onRecharger ?? null,
        })}
      </div>
    </ContexteCoque.Provider>
  )
}
