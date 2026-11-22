import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { Icone, Segmente } from '../atelier/coque/primitives'
import { gestes, useConstructeur } from '../atelier/coque/etapes/panneaux/constructeur'
import { jourMois } from '../atelier/coque/etapes/panneaux/formats'
import { PiedClient, PlanDessus, PuceProjet, TuilesClient } from './partiesClient'
import { useDonneesClient } from './vueClient.helpers'
import '../../../styles/calepinage/58-telephone.css'

/* ============================================================================
   « MONTRER AU CLIENT » — L'HABILLAGE DE L'ATELIER EN MODE PRÉSENTATION
   (maquette TelephoneClient, 390 × 844). Rendu PAR la coque (`ContextePresentation`)
   autour de la VRAIE 3D du constructeur, jamais un second constructeur.
   - Sur la scène : la puce du projet ; tant que la 3D n'est pas prête, le toit
     enregistré dessiné de dessus (repli 2D) le temps du démarrage.
   - La vue de trois-quarts : `builderApi.appliquerVue('trois-quarts')` (la caméra
     « 3/4 » de l'atelier), redemandée le temps que l'hydratation finisse de recentrer.
   - Le soleil : RE-PRÉSENTÉ, renvoyé aux vrais contrôles (`#rp9-sun-hour`,
     `[data-sun-season]`, `#rp9-sun-play-day`) — lus et pilotés par les gestes de
     l'étape Panneaux (`constructeur.js`). Sans ces contrôles : la barre est omise.
   - Trois tuiles + mention + pied : pièces partagées (`partiesClient`).
   Aucune écriture : ce sont des lectures (GET) et des gestes d'affichage.
   ========================================================================== */

const ESSAIS_VUE_MS = [0, 1500, 4000]

const SAISONS = [{ valeur: 'winter', libelle: 'Hiver' }, { valeur: 'summer', libelle: 'Été' }]

/** La caméra de trois-quarts, posée dès que l'API du constructeur est là ; `pret` ensuite. */
function useVueTroisQuarts(builderApi) {
  const [pret, setPret] = useState(false)
  useEffect(() => {
    if (typeof builderApi?.appliquerVue !== 'function') return undefined
    const minuteurs = ESSAIS_VUE_MS.map((delai) => window.setTimeout(() => {
      builderApi.appliquerVue('trois-quarts')
      setPret(true)
    }, delai))
    return () => minuteurs.forEach((m) => window.clearTimeout(m))
  }, [builderApi])
  return pret
}

function LecteurSoleil() {
  const [etat, rafraichir] = useConstructeur()
  const { heure, date, saison, lecture } = etat.soleil
  if (heure == null) return null
  const g = (geste) => (...a) => { geste(...a); rafraichir() }
  const quand = [jourMois(date), `${heure} h`].filter(Boolean).join(' · ')
  return (
    <div className="cal-client-soleil" data-testid="client-soleil">
      <button type="button" className="cal-client-soleil-lecture" aria-label="Faire passer la journée"
        aria-pressed={!!lecture?.active} disabled={!lecture} onClick={g(gestes.lecture)}>
        <Icone nom="lecture" taille={18} epaisseur={2} />
      </button>
      <div className="cal-client-soleil-curseur">
        <span className="cal-client-soleil-quand">{quand}</span>
        <input type="range" min="6" max="18" step="1" value={heure} aria-label="Heure du soleil"
          onChange={(e) => g(gestes.heure)(e.target.value)} />
      </div>
      <Segmente libelle="Saison" options={SAISONS} valeur={saison} onChange={g(gestes.saison)} />
    </div>
  )
}

export default function HabillageClient({ calepinageId, builderApi = null, noeudScene = null }) {
  const donnees = useDonneesClient(calepinageId)
  const pret = useVueTroisQuarts(builderApi)
  return (
    <>
      {noeudScene && createPortal(
        <>
          {!pret && (
            <div className="cal-client-repli" data-testid="client-repli-2d">
              {donnees.plan && <PlanDessus plan={donnees.plan} />}
            </div>
          )}
          <PuceProjet titre={donnees.titre} sousTitre={donnees.sousTitre} />
        </>,
        noeudScene,
      )}
      <div className="cal-client-corps" data-testid="cal-vue-client">
        <LecteurSoleil />
        <TuilesClient tuiles={donnees.tuiles} ville={donnees.ville} />
      </div>
      <PiedClient id={calepinageId} />
    </>
  )
}
