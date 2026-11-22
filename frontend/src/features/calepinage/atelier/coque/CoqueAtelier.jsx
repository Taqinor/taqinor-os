import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import calepinageApi from '../../../../api/calepinageApi'
import { ErrorBoundary, SkeletonCard, SkeletonText } from '../../../../ui'
import '../../../../styles/calepinage/50-coque-atelier.css'
import BarreEnregistrement from '../BarreEnregistrement'
import { formaterHeureBrouillon } from '../contexteAtelier'
import { PARAM_MODE, useModeExpert } from '../modeExpert'
import { PARAM_ONGLET, resoudreOnglet } from '../onglets'
import {
  CADRES, ETAPES, ecranCoque, premierOngletEtape, useParcours, vueParcours,
} from '../parcoursGuide'
import BarreProjet from './BarreProjet'
import { ContexteCoque } from './contexteCoque'
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
   ========================================================================== */

const TOTAL = ETAPES.length

const etatSimulation = (data) => (data?.calcule_le && data?.simulation_perimee === false
  ? `Simulation à jour · ${formaterHeureBrouillon(data.calcule_le)}` : null)

/** « Simulation à jour · HH:MM » à l'étape Résultats, seulement quand `resultat/` le sert. */
function useEtatSimulation(calepinageId, actif, relecture) {
  const [etat, setEtat] = useState(null)
  useEffect(() => {
    if (!actif || !calepinageId) return undefined
    let vivant = true
    Promise.resolve()
      .then(() => calepinageApi.calepinages.resultat(calepinageId))
      .then((rep) => { if (vivant) setEtat(etatSimulation(rep?.data)) })
      .catch(() => { if (vivant) setEtat(null) })
    return () => { vivant = false }
  }, [calepinageId, actif, relecture])
  return actif ? etat : null
}

/** Met le focus sur le vrai bouton de devis dès qu'il est monté (étape Documents). */
function focaliserBoutonDevis(essais = 30) {
  const bouton = document.querySelector('[data-testid="cal-generer-devis"], [data-testid="cal-resynchroniser-devis"]')
  if (bouton && bouton.offsetParent !== null) { bouton.focus(); return }
  if (essais > 0) window.setTimeout(() => focaliserBoutonDevis(essais - 1), 100)
}

export default function CoqueAtelier({
  calepinageId, retour, titre, sousTitre, enregistrement = null, libelleDevis, devisPossible = true,
  carte, statut = null, groupes = {}, alertes = null, avance: contenuAvance = null,
  ecranProps = {}, enregistreLe = null, onEtape = null, renderAtelierPanneaux = null,
}) {
  const [parametres, setParametres] = useSearchParams()
  const [expert, basculerExpert] = useModeExpert(parametres.get(PARAM_MODE) === 'expert')
  const parcours = useParcours(calepinageId)
  const cleActive = resoudreOnglet(parametres.get(PARAM_ONGLET))?.cle ?? null
  const { cleEtape } = vueParcours(cleActive, parcours.etats, expert)
  const ecran = ecranCoque(cleActive, resoudreOnglet(cleActive), parcours.etats, expert)
  const cadre = expert ? CADRES.CARTE : (ecran?.cadre ?? CADRES.CARTE)
  const [avanceOuvert, setAvanceOuvert] = useState(false)
  const avance = expert || avanceOuvert
  const carteVisible = cadre === CADRES.CARTE

  const choisirEtape = (cle) => {
    const premier = premierOngletEtape(cle, expert)
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
  const [piedsPris, setPiedsPris] = useState(0)
  const prendrePied = useCallback(() => {
    setPiedsPris((n) => n + 1)
    return () => setPiedsPris((n) => n - 1)
  }, [])
  const pleine = cadre === CADRES.PLEIN
  const valeurCoque = useMemo(() => ({
    noeuds: { surCarte: noeudSurCarte, panneau: noeudPanneau, pied: pleine ? noeudPiedPlein : noeudPiedPanneau },
    prendrePied,
  }), [noeudSurCarte, noeudPanneau, noeudPiedPanneau, noeudPiedPlein, pleine, prendrePied])

  // La carte réapparaît (retour d'une étape pleine) : elle se recale sur sa boîte.
  const carteAvant = useRef(carteVisible)
  useEffect(() => {
    if (carteVisible && !carteAvant.current) {
      window.requestAnimationFrame(() => window.dispatchEvent(new Event('resize')))
    }
    carteAvant.current = carteVisible
  }, [carteVisible])

  const etatPropre = useEtatSimulation(calepinageId, cleEtape === 'resultats' && !expert, enregistreLe)

  const onDevis = () => {
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
        <Ecran {...ecranProps} calepinageId={calepinageId} parcours={parcours} ouvert={cleActive}
          action={action} enregistreLe={enregistreLe}
          actionDevis={<span ref={setNoeudDevis} className="contents" />} />
      </Suspense>
    </ErrorBoundary>
  )
  const piedParDefaut = action && piedsPris === 0 && !pleine ? (
    <BoutonOr plein fleche onClick={action.onClick} data-testid="cal-action-etape-suivante">{action.libelle}</BoutonOr>
  ) : null

  return (
    <ContexteCoque.Provider value={valeurCoque}>
      <div className="rp9-host cal-coque" data-testid="cal-coque" data-etape={cleEtape} data-cadre={cadre}
        data-avance={avance ? '1' : '0'} data-expert={expert ? '1' : '0'}>
        <BarreProjet retour={retour} titre={titre} sousTitre={sousTitre} expert={expert} onExpert={basculerExpert}
          libelleDevis={libelleDevis} onDevis={devisPossible ? onDevis : null}
          enregistrement={enregistrement && <BarreEnregistrement {...enregistrement} etatPropre={etatPropre} />} />
        <div id="rp9-studio" className="cal-coque-corps">
          <RailEtapes etapeActive={cleEtape} parcours={parcours} onChoisir={allerA}
            avance={avance} onAvance={setAvanceOuvert} />
          <main className="cal-coque-centre">
            <div id="rp9-studio-scene" className="cal-coque-scene" hidden={!carteVisible}>
              {carte}
              <div ref={setNoeudSurCarte} className="cal-coque-sur-carte" />
              {statut}
            </div>
            {!carteVisible && (
              <div className="cal-coque-plein">
                {ecranMonte}
                <div ref={setNoeudPiedPlein} className="cal-coque-plein-pied" />
              </div>
            )}
          </main>
          <PanneauEtape numero={rang >= 0 ? rang + 1 : null} total={TOTAL} titre={ecran?.titre ?? null}
            cache={pleine && !avance} refCorps={setNoeudPanneau} refPied={setNoeudPiedPanneau} pied={piedParDefaut}>
            {alertes}
            {carteVisible && ecranMonte}
            <div className="cal-coque-groupe" data-groupe="toit" hidden={!(avance || cleEtape === 'toit')}>
              {groupes.outils}
              {groupes.toit}
            </div>
            <div className="cal-coque-groupe" data-groupe="pose" hidden={!(avance || cleEtape === 'panneaux')}>
              {groupes.pose}
            </div>
            <div className="cal-coque-avance" hidden={!avance}>
              {calepinageId && (
                <nav aria-label="Autres écrans du calepinage" className="cal-coque-liens">
                  <Link to={`/calepinage/${calepinageId}/releve`}>Relevé de visite</Link>
                  <Link to={`/calepinage/${calepinageId}/client`}>Montrer au client</Link>
                  <Link to="/calepinage/reglages/demarrage-rapide">Démarrage rapide des réglages</Link>
                </nav>
              )}
              {contenuAvance}
              {renderAtelierPanneaux?.({
                expert, onBasculerExpert: basculerExpert, parcours, portailDevis: noeudDevis,
              })}
            </div>
          </PanneauEtape>
        </div>
      </div>
    </ContexteCoque.Provider>
  )
}
