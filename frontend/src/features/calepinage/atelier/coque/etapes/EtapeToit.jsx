import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { PARAM_CHAMP } from '../../ouvrirChamp'
import SaisiePente from '../../../SaisiePente'
import { panParDefaut, sourceDePente, zonesDuDocument } from '../../../SaisiePente.helpers'
import useDocumentCalepinage from '../../../useDocumentCalepinage'
import { PiedEtape, SurCarte } from '../emplacements'
import { BoutonMarine, BoutonOr, CarteFlottante, Icone, Indicateur, SectionEtape, Segmente } from '../primitives'
import {
  GESTES, ajoutTermine, annulerAjoutPan, appliquerCotes, commencerAjoutPan, confirmerPenteVivante, degres, enregistrerPentePan, estObjet, nomFace,
  selectionnerObstacle, texteBesoin, useEtatToit,
} from './EtapeToit.helpers'
import { jourMois } from './panneaux/formats'
import { useCibleFactures } from './panneaux/lectures'
import ValeurUnite from './panneaux/ValeurUnite'

/* ============================================================================
   COQUE — L'ÉTAPE « TOIT » (maquette Main du 22/11 ; ToitSombre = même écran,
   thème sombre par les jetons seuls).
   ----------------------------------------------------------------------------
   Panneau de droite, dans l'ordre de la maquette : Forme (les tuiles SONT les
   puces du script `#rp9-formes-toit`, placées sous ce titre par la feuille
   51-etape-toit.css — jamais déplacées ni re-rendues), Dimensions, Pente et
   orientation, Obstacles. Sur la carte (`SurCarte`) : la puce « Surface du
   toit | Pans | Besoin d'après la facture », la bulle « Contour tracé » et la
   barre d'outils flottante. Chaque chiffre est LU dans le DOM du constructeur
   (EtapeToit.helpers.js) ; chaque geste CLIQUE le vrai contrôle du script.
   Les anciens contrôles restent montés : masqués en guidé, visibles en Avancé.
   ========================================================================== */

// T4-X7-018 — au doigt (`pointer: coarse`), le geste se dit « Touchez deux fois », jamais « Double-cliquez ».
const auDoigt = () => typeof window !== 'undefined' && typeof window.matchMedia === 'function'
  && !!window.matchMedia('(pointer: coarse)')?.matches
const astuceContour = () => `Glissez un coin pour le déplacer. ${auDoigt() ? 'Touchez deux fois' : 'Double-cliquez'} un bord pour ajouter un point.`
const MOTIF_ECHELLE = 'Retracez d’abord le toit à la bonne échelle : le tracé actuel n’est pas utilisable.'
const ALERTE_ECHELLE = 'Le tracé semble à la mauvaise échelle : une surface si grande ne tient aucune rangée. Effacez-le et retracez le toit de près.'
const ASTUCE_AJOUT = 'Cliquez sur la carte pour poser chaque coin du pan, double-cliquez pour le fermer. Échap annule l’ajout.'
const DUREE_BULLE_MS = 8000

function Champ({ id, libelle, valeur, onChange, onBlur, desactive }) {
  return (
    <div className="cal-toit-champ">
      <label htmlFor={id}>{libelle}</label>
      <div className="cal-toit-saisie">
        <input id={id} type="text" inputMode="decimal" autoComplete="off" value={valeur}
          onChange={onChange} onBlur={onBlur} disabled={desactive} />
        <span aria-hidden="true">m</span>
      </div>
    </div>
  )
}

/** Longueur / largeur : les champs de « Créer le toit » avant tout contour, les cotes du pan actif ensuite.
    La saisie en cours n'est jamais réécrite sous le curseur ; Entrée (ou la sortie du champ, contour fermé)
    la pose dans le vrai contrôle du script, qui la valide. */
function Dimensions({ cotes, relire, pans = null }) {
  const [brouillon, setBrouillon] = useState(null)
  const valeurs = brouillon ?? cotes
  const desactive = cotes.mode === 'aucun' || cotes.desactive
  const changer = (cle) => (e) => setBrouillon({ longueur: valeurs.longueur, largeur: valeurs.largeur, [cle]: e.target.value })
  const appliquer = (e) => {
    e?.preventDefault?.()
    if (!brouillon) return
    appliquerCotes(document, brouillon.longueur, brouillon.largeur)
    setBrouillon(null)
    relire()
  }
  const surSortie = cotes.mode === 'pan' ? appliquer : undefined
  return (
    <div className="cal-toit-bloc cal-toit-bloc-dimensions">
      <SectionEtape titre="Dimensions">
        <form noValidate onSubmit={appliquer} className="cal-toit-dimensions" data-testid="cal-toit-dimensions">
          <Champ id="cal-toit-longueur" libelle="Longueur" valeur={valeurs.longueur} onChange={changer('longueur')}
            onBlur={surSortie} desactive={desactive} />
          <Champ id="cal-toit-largeur" libelle="Largeur" valeur={valeurs.largeur} onChange={changer('largeur')}
            onBlur={surSortie} desactive={desactive} />
          {cotes.mode === 'creer' && <button type="submit" className="cal-bouton-contour cal-toit-creer">Créer le toit</button>}
        </form>
        {/* R5B-N7 (rejeu 26/11) — toit 10 × 8 créé en 2 pans : « Largeur » relisait 4 (la largeur du PAN sélectionné) sans
            le dire. Les champs gardent leurs libellés (maquette) ; la ligne dit de quoi ils sont les cotes. */}
        {cotes.mode === 'pan' && pans > 1 && (
          <p className="cal-pan-note" data-zone="cotes-du-pan">{`Cotes du pan sélectionné — le toit en compte ${pans}.`}</p>
        )}
      </SectionEtape>
    </div>
  )
}

/** La pente du pan ACTIF : celle du document servi quand le pan y est, sinon celle que le script affiche. */
function penteAffichee(zone, pente, ferme) {
  if (zone) {
    return {
      plat: zone.roofType ? zone.roofType === 'flat' : pente.plat,
      deg: Number.isFinite(Number(zone.pitchDeg)) ? Number(zone.pitchDeg) : null,
      face: nomFace(zone.facingAzimuthDeg),
      azimut: zone.facingAzimuthDeg != null && Number.isFinite(Number(zone.facingAzimuthDeg)) ? Number(zone.facingAzimuthDeg) : null,
      aConfirmer: !estObjet(zone.pitchSource),
    }
  }
  return ferme ? pente : null
}

function CartePente({ calepinageId, builderApi, documentVivant, lectureSeule, enregistreLe, pente, ferme }) {
  const doc = useDocumentCalepinage(calepinageId)
  const { recharger } = doc
  const [message, setMessage] = useState(null)
  const [inconnue, setInconnue] = useState(false)
  const [envoi, setEnvoi] = useState(false)
  const [modifier, setModifier] = useState(false)
  // Un enregistrement de l'atelier a pu changer les pans : la carte relit le document servi.
  useEffect(() => { if (enregistreLe) recharger() }, [enregistreLe, recharger])

  const zones = zonesDuDocument(doc.document)
  const idActif = String(builderApi?.panActifId?.() ?? '')
  const zone = idActif
    ? zones.find((z) => String(z.id) === idActif) ?? null
    : zones.find((z) => String(z.id) === panParDefaut(doc.document)) ?? null
  const vue = penteAffichee(zone, pente, ferme)

  const confirmer = async () => {
    if (lectureSeule) return
    // ACAL1428 — un toit pas encore dans la conception servie : on confirme le pan VIVANT (le moteur écrit `pitchSource`,
    // « Enregistrer » l'emporte) ; aucune écriture serveur avant « Enregistrer ».
    // Critique — un toit PLAT tracé et pas encore enregistré prend le même chemin (le geste du moteur sur le pan vivant).
    if (!zone && vue && Number.isFinite(vue.deg) && confirmerPenteVivante(document, vue.deg)) {
      setMessage(vue.plat ? 'Toit plat confirmé : il sera enregistré avec le calepinage.'
        : 'Pente confirmée : elle sera enregistrée avec le calepinage.')
      return
    }
    if (doc.etat !== 'ok') { setMessage('Conception illisible : rien n’est enregistré.'); return }
    if (!zone) { setMessage('Enregistrez d’abord le calepinage : ce pan n’est pas encore dans la conception.'); return }
    const plat = zone.roofType === 'flat'
    const deg = plat ? 0 : Number(zone.pitchDeg)
    if (!Number.isFinite(deg)) { setMessage('Ce pan n’a pas de pente : saisissez-la avec « Modifier la pente ».'); return }
    setEnvoi(true)
    const rendu = await enregistrerPentePan({
      calepinageId, doc, documentVivant, zone, zones, confirmerPlat: plat,
      champs: { pitchDeg: deg, pitchSource: sourceDePente({ degres: deg, source: 'degres' }, {}) },
    })
    setEnvoi(false)
    setMessage(rendu.message)
  }

  const titre = !vue ? null
    : vue.plat ? 'Toit plat'
      : `${degres(vue.deg) ?? '—'}°${vue.face ? ` · face ${vue.face}` : ''}`
  const aConfirmer = Boolean(vue && vue.aConfirmer) // ACAL1429 — un plat jamais confirmé l'est aussi
  return (
    <div className="cal-toit-pente" data-testid="cal-toit-pente-carte">
      {titre ? (
        <div className="cal-toit-pente-cadre">
          {!vue.plat && <Cadran azimut={vue.azimut ?? null} />}
          <div className="cal-toit-pente-corps">
            <div className="cal-toit-pente-tete">
              <span className="cal-toit-pente-valeur">{titre}</span>
              {aConfirmer && <span className="cal-toit-pente-tag">À confirmer</span>}
              {/* ACAL1922 — « Toit plat · confirmé » : le tag suit la valeur, jamais dans son texte. */}
              {!aConfirmer && vue.plat && <span className="cal-toit-pente-tag" data-testid="cal-toit-plat-confirme">· confirmé</span>}
            </div>
            {aConfirmer && !inconnue && (
              <p className="cal-toit-pente-texte">
                {vue.plat
                  ? "Toit plat pris par défaut, pas une mesure : confirmez-le ou vérifiez-le."
                  : "Valeur de départ, pas une mesure : confirmez-la ou mesurez-la."}
              </p>
            )}
            {aConfirmer && inconnue && (
              <p className="cal-toit-pente-texte" role="status">
                Valeur de départ gardée, toujours à confirmer : elle sera vérifiée à la visite. Rien n’est enregistré.
              </p>
            )}
          </div>
        </div>
      ) : (
        <p className="cal-toit-pente-texte cal-toit-pente-vide">Tracez d’abord le contour du toit : sa pente et sa face s’afficheront ici.</p>
      )}
      {aConfirmer && !inconnue && (
        <div className="cal-toit-pente-actions">
          <BoutonMarine onClick={confirmer} disabled={lectureSeule || envoi} data-testid="cal-toit-pente-confirmer">
            Confirmer
          </BoutonMarine>
          <button type="button" className="cal-bouton-contour" data-testid="cal-toit-pente-inconnue"
            onClick={() => { setInconnue(true); setMessage(null) }}>
            Je ne la connais pas
          </button>
        </div>
      )}
      {message && <p className="cal-toit-pente-message" role="status">{message}</p>}
      {/* ACAL1341 — un toit plat n'a pas de pente : sa forme change par les tuiles, jamais par ce formulaire. */}
      {!vue?.plat && (
        <details className="cal-toit-pente-modifier" onToggle={(e) => setModifier(e.currentTarget.open)}>
          <summary>Modifier la pente</summary>
          {modifier && (
            <SaisiePente calepinageId={calepinageId} documentVivant={documentVivant} lectureSeule={lectureSeule}
              zoneInitiale={zone?.id ?? ''} onEnregistre={recharger} />
          )}
        </details>
      )}
    </div>
  )
}

/** ACAL1827 — le cadran de la carte de pente (maquette Main) : un N, trois repères et l'aiguille tournée vers la face lue
    (azimut 0 = nord, 180 = sud). Sans azimut lu, le cadran reste nu : aucune face n'est inventée. */
function Cadran({ azimut }) {
  const connu = Number.isFinite(azimut)
  const nom = connu ? nomFace(azimut) : null
  return (
    <svg width="56" height="56" viewBox="0 0 64 64" className="cal-cadran" {...(connu
      ? { role: 'img', 'aria-label': `Face ${nom}, ${Math.round(azimut)}°` } : { 'aria-hidden': 'true' })}>
      <circle className="cal-cadran-disque" cx="32" cy="32" r="29" />
      <path className="cal-cadran-reperes" d="M32 50v5M9 32h5M50 32h5" />
      <text className="cal-cadran-n" x="32" y="25" textAnchor="middle">N</text>
      {connu && (
        <g data-aiguille="" transform={`rotate(${Math.round(azimut)} 32 32)`}>
          <path className="cal-cadran-aiguille" d="M32 32V17" />
          <path className="cal-cadran-pointe" d="M27 21l5-8 5 8z" />
        </g>
      )}
      <circle className="cal-cadran-centre" cx="32" cy="32" r="3.5" />
    </svg>
  )
}

/** Les obstacles du toit (lus dans le tableau « Objets du site » du script) ; un clic sur une ligne la
    sélectionne comme ce tableau le fait. Liste à une seule tabulation (flèches + Entrée). */
function Obstacles({ obstacles, relire }) {
  const [actif, setActif] = useState(0)
  const [choisi, setChoisi] = useState(null)
  // ACAL1971 — « Régler » sur « Obstacles dans leur pan » arrive avec `?champ=<id de l'obstacle fautif>` : l'état est
  // AMORCÉ une fois (ligne active + choisie) et le script reçoit UNE fois le même clic que sur sa ligne du tableau
  // « Objets du site » ; le paramètre est ensuite retiré (replace : « Retour » ne le rejoue pas, un remontage non plus).
  const [parametres, setParametres] = useSearchParams()
  const visee = parametres.get(PARAM_CHAMP)
  const iVisee = visee ? obstacles.findIndex((o) => o.id === visee) : -1
  // Amorçage pendant le rendu (« ajuster l'état » de React) : une seule fois par paramètre reçu, sans effet qui pose l'état.
  const [amorce, setAmorce] = useState(null)
  if (iVisee >= 0 && amorce !== visee) {
    setAmorce(visee)
    setActif(iVisee)
    setChoisi(obstacles[iVisee].id)
  }
  useEffect(() => {
    if (iVisee < 0) return
    selectionnerObstacle(document, obstacles[iVisee])
    relire()
    setParametres((precedents) => {
      const suivants = new URLSearchParams(precedents)
      suivants.delete(PARAM_CHAMP)
      return suivants
    }, { replace: true })
  }, [iVisee, obstacles, relire, setParametres])
  const choisir = (o, i) => {
    setActif(i)
    setChoisi(o.id)
    selectionnerObstacle(document, o)
    relire()
  }
  const clavier = (e) => {
    const n = obstacles.length
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      setActif((i) => (Math.min(i, n - 1) + (e.key === 'ArrowDown' ? 1 : n - 1)) % n)
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      const i = Math.min(actif, n - 1)
      choisir(obstacles[i], i)
    }
  }
  const ajouter = (
    <button type="button" className="cal-lien-action" onClick={() => { GESTES.obstacle(document); relire() }}>
      + Ajouter
    </button>
  )
  return (
    <div className="cal-toit-bloc cal-toit-bloc-obstacles" data-testid="cal-toit-obstacles">
      <SectionEtape action={ajouter} titre={obstacles.length > 0
        ? <>Obstacles{' '}<span className="cal-toit-obstacles-compte">· {obstacles.length}</span></> : 'Obstacles'}>
        {obstacles.length > 0 && (
          <ul role="listbox" aria-label="Obstacles du toit" tabIndex={0} className="cal-toit-obstacles"
            aria-activedescendant={`cal-toit-obstacle-${Math.min(actif, obstacles.length - 1)}`} onKeyDown={clavier}>
            {obstacles.map((o, i) => (
              <li key={`${o.pan}:${o.id}`} id={`cal-toit-obstacle-${i}`} role="option" aria-selected={choisi === o.id}
                data-actif={i === actif ? '1' : '0'} onClick={() => choisir(o, i)}>
                <span className="cal-toit-obstacle-pastille" aria-hidden="true" />
                <span className="cal-toit-obstacle-nom">{o.nom}</span>
                <span className="cal-toit-obstacle-cotes">{[o.cotes, o.hauteur].filter(Boolean).join(' · ')}</span>
              </li>
            ))}
          </ul>
        )}
      </SectionEtape>
    </div>
  )
}

function Outil({ nom, libelle, presse, desactive = false, onClick, titre }) {
  return (
    <button type="button" className="cal-outil-carte" aria-label={libelle} aria-pressed={presse}
      title={titre} disabled={desactive} onClick={onClick}>
      <Icone nom={nom} taille={20} epaisseur={2} />
    </button>
  )
}

const ESSAIS_VUE_MS = [0, 1500, 4000]

/** La maquette ouvre l'étape en « Plan » : la caméra du dessus est posée à l'entrée (et reposée tant que la carte
    se charge, sauf si l'utilisateur a déjà choisi sa vue). Le segment lit ensuite la vraie caméra (`outils.vue`). */
function useVuePlanALEntree(builderApi) {
  const choisie = useRef(false)
  useEffect(() => {
    if (typeof builderApi?.appliquerVue !== 'function') return undefined
    const minuteurs = ESSAIS_VUE_MS.map((delai) => window.setTimeout(() => {
      if (!choisie.current) builderApi.appliquerVue('dessus')
    }, delai))
    return () => minuteurs.forEach((m) => window.clearTimeout(m))
  }, [builderApi])
  return choisie
}

/** La barre d'outils flottante (bas, centrée) : 4 outils | annuler · rétablir | Plan · 3D. Le 2ᵉ outil dit ce
    qu'il fait : « Tracer un contour » sans toit (le tracé au clic est actif), « Ajouter un pan » avec un toit. */
function BarreOutils({ outils, builderApi, relire, ajout, onAjout }) {
  const [vueChoisie, setVueChoisie] = useState('plan')
  const vueToucheeRef = useVuePlanALEntree(builderApi)
  const geste = (nom) => () => { GESTES[nom](document); relire() }
  const modeLibre = !outils.obstacle && !outils.mesure
  const changerVue = (v) => {
    vueToucheeRef.current = true
    setVueChoisie(v)
    builderApi?.appliquerVue?.(v === '3d' ? 'trois-quarts' : 'dessus')
  }
  const avecToit = outils.ferme || Boolean(ajout)
  return (
    <CarteFlottante role="toolbar" aria-label="Outils du plan" className="cal-barre-outils-carte"
      data-testid="cal-barre-outils-carte">
      <Outil nom="selection" libelle="Sélectionner" presse={modeLibre && outils.ferme} onClick={geste('selection')} />
      {avecToit ? (
        <Outil nom="trace" libelle="Ajouter un pan" presse={Boolean(ajout)} onClick={onAjout}
          titre={ajout ? 'Annuler l’ajout du pan (Échap)' : 'Ajouter un pan : tracer un nouveau contour'} />
      ) : (
        <Outil nom="trace" libelle="Tracer un contour" presse={modeLibre} onClick={geste('trace')} />
      )}
      <Outil nom="obstacle" libelle="Ajouter un obstacle" presse={outils.obstacle} onClick={geste('obstacle')} />
      <Outil nom="mesure" libelle="Mesurer" presse={outils.mesure} onClick={geste('mesure')} />
      <span className="cal-barre-outils-separateur" aria-hidden="true" />
      <Outil nom="annuler" libelle="Annuler" desactive={!outils.annuler} onClick={geste('annuler')} />
      <Outil nom="retablir" libelle="Rétablir" desactive={!outils.retablir} onClick={geste('retablir')} />
      <span className="cal-barre-outils-separateur" aria-hidden="true" />
      <Segmente libelle="Vue" grand valeur={outils.vue ?? vueChoisie} onChange={changerVue}
        options={[{ valeur: 'plan', libelle: 'Plan' }, { valeur: '3d', libelle: '3D' }]} />
    </CarteFlottante>
  )
}

function Bulle({ titre, texte }) {
  return (
    <div className="cal-toit-bulle" role="status">
      <p className="cal-toit-bulle-titre">{titre}</p>
      <p className="cal-toit-bulle-texte">{texte}</p>
    </div>
  )
}

/** La bulle « Contour tracé » (maquette Main). Un toit ouvert avec son contour fermé la porte TANT QU'AUCUN coin n'est
    déplacé (ACAL1445) : le moteur garde un déplacement dans son historique, `touche` est le premier instant où il le
    dit — et le reste, annuler jusqu'au début ne la ramène pas. Un tracé fait dans la séance la porte quelques
    secondes. Pendant l'ajout d'un pan, la bulle dit le geste suivant et comment l'annuler. */
function BulleContour({ contourFerme, ferme, historique, ajout, horsEchelle = false }) {
  const [vue, setVue] = useState(0)
  const [touche, setTouche] = useState(false)
  if (touche && !ferme) setTouche(false)
  else if (!touche && ferme && historique) setTouche(true)
  useEffect(() => {
    if (!contourFerme) return undefined
    const minuterie = window.setTimeout(() => setVue(contourFerme), DUREE_BULLE_MS)
    return () => window.clearTimeout(minuterie)
  }, [contourFerme])
  if (horsEchelle) return <Bulle titre="Tracé à vérifier" texte={ALERTE_ECHELLE} />
  if (ajout) return <Bulle titre="Nouveau pan" texte={ASTUCE_AJOUT} />
  // Ouvert tel quel (aucun tracé de la séance) : la bulle tient jusqu'au premier coin déplacé.
  if (!contourFerme) return ferme && !touche && !historique ? <Bulle titre="Contour tracé" texte={astuceContour()} /> : null
  if (vue === contourFerme) return null
  return <Bulle titre="Contour tracé" texte={astuceContour()} />
}

/** ACAL1445 — le bloc « Soleil » (maquette Main, à droite de la barre d'outils) : le jour et l'heure du soleil que le
    constructeur utilise pour les ombres, lus sur ses champs. Un repère, pas un contrôle : l'heure se règle à l'étape
    Panneaux. Sans date ni heure lues, rien n'est affiché. */
function BlocSoleil({ soleil }) {
  if (!soleil) return null
  const quand = [jourMois(soleil.date), soleil.heure == null ? '' : `${soleil.heure} h`].filter(Boolean).join(' · ')
  if (!quand) return null
  // Le soleil sur son arc : la position vient de l'heure lue dans la plage du curseur, jamais d'une valeur de départ.
  const t = soleil.heure != null && soleil.max > soleil.min
    ? Math.min(1, Math.max(0, (soleil.heure - soleil.min) / (soleil.max - soleil.min))) : null
  const x = t == null ? null : 32 - 28 * Math.cos(Math.PI * t)
  const y = t == null ? null : 30 - 28 * Math.sin(Math.PI * t)
  return (
    <CarteFlottante role="group" aria-label={`Soleil : ${quand}`} className="cal-toit-soleil" data-testid="cal-toit-soleil"
      title="L’heure du soleil se règle à l’étape Panneaux.">
      <svg width="64" height="34" viewBox="0 0 64 34" aria-hidden="true">
        <path className="cal-soleil-arc" d="M4 30a28 28 0 0156 0" />
        {t != null && <path className="cal-soleil-trajet" d={`M4 30A28 28 0 0 1 ${x.toFixed(1)} ${y.toFixed(1)}`} />}
        {t != null && <circle className="cal-soleil-astre" cx={x.toFixed(1)} cy={y.toFixed(1)} r="6" />}
        <path className="cal-soleil-sol" d="M2 30h60" />
      </svg>
      <span className="cal-toit-soleil-texte">
        <span>Soleil</span>
        <span>{quand}</span>
      </span>
    </CarteFlottante>
  )
}

/** « Ajouter un pan » et son annulation (re-clic ou Échap) : la zone vide ouverte est retirée, le pan d'avant
    redevient actif. Pendant l'ajout, la puce (table des pans) et les cotes gardent le toit d'avant. */
function useAjoutPan(etat, relire) {
  const [ajout, setAjout] = useState(null)
  // L'ajout est fini dès que sa zone a un contour (ou n'existe plus) : lu à chaque relecture de l'état.
  const actif = ajout && !ajoutTermine(document, ajout) ? ajout : null
  const enCours = useRef(null)
  useEffect(() => { enCours.current = actif }, [actif])
  const annuler = useCallback(() => {
    if (enCours.current) annulerAjoutPan(document, enCours.current)
    enCours.current = null
    setAjout(null)
    relire()
  }, [relire])
  const basculer = () => {
    if (actif) { annuler(); return }
    const lance = commencerAjoutPan(document)
    if (lance) {
      enCours.current = { ...lance, cotes: etat.cotes }
      setAjout(enCours.current)
    }
    relire()
  }
  useEffect(() => {
    if (!actif) return undefined
    const surTouche = (e) => { if (e.key === 'Escape') annuler() }
    document.addEventListener('keydown', surTouche)
    return () => document.removeEventListener('keydown', surTouche)
  }, [actif, annuler])
  return [actif, basculer]
}

/** Le « Besoin d'après la facture » de la puce selon l'état de la lecture : en chargement, rien (aucune absence
    affirmée) ; en échec, « Lecture impossible — réessayer » ; lue, le chiffre servi (ou rien : pas de facture). */
function besoinAffiche(facture) {
  if (facture.etat === 'echec') {
    return (
      <button type="button" className="cal-toit-reessayer" onClick={facture.reessayer} data-zone="besoin-echec">
        Lecture impossible — réessayer
      </button>
    )
  }
  return facture.etat === 'ok' ? texteBesoin(facture.cible) : null
}

function ResumeCarte({ surface, pans, besoin }) {
  if (!surface) return null
  const blocs = [
    ['Surface du toit', surface],
    pans ? ['Pans', String(pans)] : null,
    besoin ? ['Besoin d\'après la facture', besoin] : null,
  ].filter(Boolean)
  return (
    <CarteFlottante className="cal-sur-carte-resume" data-testid="cal-sur-carte-resume">
      {blocs.map(([libelle, valeur], i) => (
        <div key={libelle} className="cal-sur-carte-resume-bloc">
          {i > 0 && <span className="cal-sur-carte-resume-filet" aria-hidden="true" />}
          <Indicateur libelle={libelle} valeur={typeof valeur === 'string' ? <ValeurUnite texte={valeur} /> : valeur} />
        </div>
      ))}
    </CarteFlottante>
  )
}

export default function EtapeToit({
  calepinageId, builderApi = null, documentVivant = null, lectureSeule = false, enregistreLe = null, contexte: servi = null, contexteEnCours = false,
  action = null,
}) {
  const [etat, relire] = useEtatToit()
  // La taille des factures : l'accesseur PARTAGÉ avec l'étape Panneaux (trois états ; le design-context de
  // l'atelier, `ecranProps.contexte`, prime — relu ici seulement sans lui, REP-995).
  const facture = useCibleFactures(calepinageId, servi, { attendre: contexteEnCours })
  const [ajout, basculerAjout] = useAjoutPan(etat, relire)
  // ACAL1410 — tant qu'aucun contour n'est fermé, le champ d'adresse (#rp9-search) flotte au-dessus de la carte en Guidé
  // (la règle de 50-coque-atelier.css lit cet attribut de la coque) ; il disparaît dès qu'un toit est tracé.
  const sansToit = !etat.outils.ferme
  useEffect(() => {
    const coque = document.querySelector('.cal-coque')
    if (!coque || !sansToit) return undefined
    coque.dataset.sansToit = '1'
    return () => { delete coque.dataset.sansToit }
  }, [sansToit])
  // ACAL1945 — à l'étape Toit du Guidé, la carte ne montre aucun panneau posé (maquette Main) : le drapeau lu par le moteur
  // (`layoutEditor.ts::poseMasquee`) vit tant que l'étape est montée ; à la sortie il tombe et le moteur re-rend la pose.
  useEffect(() => {
    const coque = document.querySelector('.cal-coque')
    if (!coque || coque.dataset.expert === '1') return undefined
    coque.dataset.poseMasquee = '1'
    document.dispatchEvent(new CustomEvent('cal:pose-etape'))
    return () => { delete coque.dataset.poseMasquee; document.dispatchEvent(new CustomEvent('cal:pose-etape')) }
  }, [])
  // T4-X7-018 — un tracé signalé « à la mauvaise échelle » : la phrase du script qui le contredit (« Surface trop petite pour une
  // rangée ») est masquée (`data-contredit`, 50-coque-atelier.css), aucune surface absurde n'est imprimée (puce de la carte) et
  // l'action suivante est désactivée avec son motif — jamais un chiffre inventé à la place.
  const horsEchelle = etat.horsEchelle
  useEffect(() => {
    if (!horsEchelle) return undefined
    const statut = document.getElementById('rp9-status')
    statut?.setAttribute('data-contredit', '1')
    return () => statut?.removeAttribute('data-contredit')
  }, [horsEchelle])
  return (
    <div className="cal-etape-toit">
      <div className="cal-toit-bloc cal-toit-bloc-forme">
        <SectionEtape titre="Forme" />
      </div>
      <Dimensions cotes={ajout ? { ...ajout.cotes, desactive: true } : etat.cotes} relire={relire} pans={etat.pans} />
      <div className="cal-toit-bloc cal-toit-bloc-pente">
        <SectionEtape titre="Pente et orientation">
          <CartePente calepinageId={calepinageId} builderApi={builderApi} documentVivant={documentVivant}
            lectureSeule={lectureSeule} enregistreLe={enregistreLe} pente={etat.pente} ferme={etat.outils.ferme} />
        </SectionEtape>
      </div>
      <Obstacles obstacles={etat.obstacles} relire={relire} />
      {horsEchelle && action && (
        <PiedEtape>
          <BoutonOr plein fleche disabled title={MOTIF_ECHELLE} aria-describedby="cal-toit-motif-echelle" data-testid="cal-action-etape-suivante">
            {action.libelle}
          </BoutonOr>
          <span id="cal-toit-motif-echelle" className="sr-only">{MOTIF_ECHELLE}</span>
        </PiedEtape>
      )}
      <SurCarte>
        {!horsEchelle && <ResumeCarte surface={etat.surface} pans={etat.pans} besoin={besoinAffiche(facture)} />}
        <BulleContour contourFerme={etat.contourFerme} ferme={etat.outils.ferme} historique={etat.outils.annuler} ajout={ajout} horsEchelle={etat.horsEchelle} />
        <BarreOutils outils={etat.outils} builderApi={builderApi} relire={relire} ajout={ajout} onAjout={basculerAjout} />
        <BlocSoleil soleil={etat.soleil} />
      </SurCarte>
    </div>
  )
}
