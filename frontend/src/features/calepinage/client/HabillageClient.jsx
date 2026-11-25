import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Icone, Segmente } from '../atelier/coque/primitives'
import { gestes, useConstructeur } from '../atelier/coque/etapes/panneaux/constructeur'
import { jourMois } from '../atelier/coque/etapes/panneaux/formats'
import { AttenteScene, AvisEchec3D, PastilleAttente, PiedClient, PlanDessus, PuceProjet, TuilesClient, IconeTourner } from './partiesClient'
import { instantSoleilChoisi, useBureau } from './vueClient.helpers'
import { useHorsVueClientInerte } from './inerteHorsClient'

/* ============================================================================
   « MONTRER AU CLIENT » — L'HABILLAGE DE L'ATELIER EN MODE PRÉSENTATION
   (maquette TelephoneClient, 390 × 844). Rendu PAR la coque (`ContextePresentation`)
   autour de la VRAIE 3D du constructeur, jamais un second constructeur.
   - Sur la scène : la puce du projet ; tant que la 3D n'est pas prête, le toit
     enregistré dessiné de dessus (repli 2D) et « La vue 3D se prépare… ».
   - J1 — LA VUE DE TROIS QUARTS TENUE : `builderApi.modePresentation(true, { vue: 'trois-quarts', … })`
     (roofPro11/presentationCarte.ts) la pose et la REPOSE après tout mouvement de caméra qui n'est pas
     un geste de l'utilisateur (atterrissage du boot, hydratation, cadrage tardif), jusqu'à ce qu'il
     tourne la maison ; `surPrete` dit quand elle est posée et le toit cadré : la 3D est alors montrée.
   - Le soleil : RE-PRÉSENTÉ, renvoyé aux vrais contrôles (`#rp9-sun-hour`,
     `[data-sun-season]`, `#rp9-sun-play-day`). J1 — la vue s'ouvre en été à midi (maquette), sauf
     si la scène enregistrée porte un instant CHOISI par le commercial (gardé).
   - Les DONNÉES (tuiles, puce) sont tenues par la vue client hors de l'atelier (`donnees`) : elles ne
     dépendent pas du démarrage de la 3D, et « Réessayer » ne les efface pas.
   Aucune écriture : des lectures (GET) et des gestes d'affichage.
   ========================================================================== */

/** ACAL1839 — la zone de la carte que les pièces flottantes laissent LIBRE : la puce en haut ; au bureau la carte de chiffres
    à droite et la barre du soleil en bas ; au téléphone le corps en bas. Relue à chaque cadrage (la mise en page s'installe
    après l'ouverture), pour que la maison entière tienne dans cette zone, avec de l'air, jamais sous une carte. */
const PIECES_CLIENT = '[data-testid="client-projet"], [data-testid="client-soleil"], [data-testid="client-tuiles"], [data-testid="cal-vue-client"], [data-testid="client-envoyer-lien"]'
function margesClient(doc = document) {
  const carte = doc.getElementById('rp9-map')?.getBoundingClientRect()
  const m = { haut: 0, gauche: 0, droite: 0, bas: 0 }
  if (!carte?.width || !carte.height) return m
  for (const el of doc.querySelectorAll(PIECES_CLIENT)) {
    const r = el.getBoundingClientRect()
    if (!r.width || !r.height) continue
    if (r.top > carte.top + 0.4 * carte.height && r.width > 0.6 * carte.width) m.bas = Math.max(m.bas, carte.bottom - r.top)
    else if (r.left > carte.left + 0.5 * carte.width && r.top < carte.top + 0.7 * carte.height) m.droite = Math.max(m.droite, carte.right - r.left)
    else if (r.bottom < carte.top + 0.35 * carte.height) m.haut = Math.max(m.haut, r.bottom - carte.top)
  }
  return m
}

/** H6 — la maison remplit la scène comme sur la maquette ; J1 — posée plus bas (le ciel gardé en haut).
    ACAL1839 — en vue inclinée, le constructeur cadre le VOLUME (murs compris) dans la zone libre ; au téléphone, sous la
    puce et l'aide « Glissez un doigt » (150 px), sur 80 % de la scène qui reste. Caméra seule. */
const cadrageClient = (bureau) => ({
  zoomMax: 22, part: bureau ? 0.62 : 0.8, cielPx: bureau ? 190 : 150, get margesPx() { return margesClient() },
})

/** ACAL1839 — le ciel de la scène : dégradé de la maquette (bleu clair vers transparent), aux jetons du module, sans geste. */
const CIEL_CLIENT = {
  position: 'absolute', insetInline: 0, top: 0, height: '34%', pointerEvents: 'none',
  background: 'linear-gradient(to bottom, color-mix(in srgb, var(--cal-lien) 30%, var(--cal-surface)), color-mix(in srgb, var(--cal-lien) 10%, transparent) 60%, transparent)',
}

const SAISONS = [{ valeur: 'winter', libelle: 'Hiver' }, { valeur: 'summer', libelle: 'Été' }]

/** La vue de trois-quarts TENUE par le constructeur ; `pret` quand elle est posée et le toit cadré. Un constructeur
 *  sans mode présentation : la vue et le cadrage une fois, `pret` aussitôt (rien de plus à attendre). */
function useVueTroisQuarts(builderApi, essai, bureau) {
  // `pret` vaut pour UN essai et UNE instance du constructeur (« Réessayer » repart de zéro).
  const [pretPour, setPretPour] = useState(null)
  const disponible = typeof builderApi?.appliquerVue === 'function'
  const tenue = disponible && typeof builderApi.modePresentation === 'function'
  useEffect(() => {
    if (!disponible) return undefined
    if (!tenue) {
      builderApi.appliquerVue('trois-quarts')
      builderApi.cadrerToit?.(cadrageClient(bureau))
      return undefined
    }
    let vivant = true
    builderApi.modePresentation(true, {
      vue: 'trois-quarts', cadrage: cadrageClient(bureau), surPrete: () => { if (vivant) setPretPour({ builderApi, essai }) },
    })
    return () => { vivant = false; builderApi.modePresentation(false) }
  }, [builderApi, essai, disponible, tenue, bureau])
  const pret = disponible && (!tenue || (pretPour?.builderApi === builderApi && pretPour?.essai === essai))
  return { pret, tourne: tenue }
}

/** J1 — la saison montrée suit l'état RÉEL : celle que le constructeur dit pressée, sinon (lecture de la journée :
 *  il ne presse plus rien, la date reste) celle dont il a montré cette même date. */
function useSaisonReelle(saison, date) {
  const [vue, setVue] = useState({ date: null, saison: null })
  if (saison && date && (vue.date !== date || vue.saison !== saison)) setVue({ date, saison })
  return saison ?? (date && vue.date === date ? vue.saison : null)
}

/** J1 — l'ouverture : été à midi, sauf instant choisi par le commercial (gardé), une fois, la 3D prête. */
function useEteAMidi(pret, doc) {
  const fait = useRef(false)
  useEffect(() => {
    if (!pret || fait.current || doc.etat !== 'ok') return
    fait.current = true
    if (instantSoleilChoisi(doc.document)) return
    gestes.saison('summer')
    gestes.heure(12)
  }, [pret, doc])
}

/** ACAL1838 — les repères de la barre du soleil du bureau : de la borne basse à la borne haute SERVIES par le curseur du constructeur. */
const reperes = (min, max) => [0, 1, 2, 3, 4].map((i) => Math.round(min + ((max - min) * i) / 4))

function LecteurSoleil({ bureau = false }) {
  const [etat, rafraichir] = useConstructeur()
  const { heure, date, saison, lecture, min, max } = etat.soleil
  const saisonReelle = useSaisonReelle(saison, date)
  if (heure == null) return null
  const g = (geste) => (...a) => { geste(...a); rafraichir() }
  const quand = [jourMois(date), `${heure} h`].filter(Boolean).join(' · ')
  const rempli = max > min ? ((Number(heure) - min) / (max - min)) * 100 : 0
  return (
    <div className="cal-client-soleil" data-testid="client-soleil">
      <button type="button" className="cal-client-soleil-lecture" aria-label="Faire passer la journée"
        aria-pressed={!!lecture?.active} disabled={!lecture} onClick={g(gestes.lecture)}>
        <Icone nom="lecture" taille={18} epaisseur={2} />
      </button>
      <div className="cal-client-soleil-curseur">
        {bureau && <span className="cal-client-soleil-etiquette">Soleil</span>}
        <span className="cal-client-soleil-quand">{quand}</span>
      </div>
      <div className="cal-client-soleil-piste">
        <input type="range" min={min} max={max} step="1" value={heure} aria-label="Heure du soleil"
          className="cal-pan-heure" style={{ '--cal-pan-rempli': `${rempli}%` }}
          onChange={(e) => g(gestes.heure)(e.target.value)} />
        {bureau && (
          <div className="cal-client-soleil-reperes" aria-hidden="true">
            {reperes(min, max).map((h) => <span key={h} data-courant={h === Number(heure) ? '' : undefined}>{`${h} h`}</span>)}
          </div>
        )}
      </div>
      <Segmente libelle="Saison" options={SAISONS} valeur={saisonReelle} onChange={g(gestes.saison)} />
    </div>
  )
}

/** Délai au-delà duquel une 3D toujours pas démarrée est DITE (le repli 2D reste), avec « Réessayer ». */
export const DELAI_3D_MS = 45000

/** Vrai quand la 3D n'a toujours pas démarré `DELAI_3D_MS` après l'ouverture (ou le dernier « Réessayer »). */
function useTroisDEnRetard(pret, essai) {
  const [retardPour, setRetardPour] = useState(null)
  useEffect(() => {
    if (pret) return undefined
    const m = window.setTimeout(() => setRetardPour(essai), DELAI_3D_MS)
    return () => window.clearTimeout(m)
  }, [pret, essai])
  return retardPour === essai && !pret
}

export default function HabillageClient({
  calepinageId, builderApi = null, noeudScene = null, contexte = null,
  donnees, onContexte = null, onRetard = null, onReessayer = null,
}) {
  const [essai, setEssai] = useState(0)
  const bureau = useBureau()
  const { pret, tourne } = useVueTroisQuarts(builderApi, essai, bureau)
  const retard = useTroisDEnRetard(pret, essai)
  useEteAMidi(pret, donnees.doc)
  useHorsVueClientInerte(noeudScene)
  // Le contexte déjà servi à l'atelier remonte à la vue client (puce) : aucune seconde lecture de design-context.
  useEffect(() => { if (contexte) onContexte?.(contexte) }, [contexte, onContexte])
  useEffect(() => { onRetard?.(retard) }, [retard, onRetard])
  // « Réessayer » : seulement ce qui a échoué — le démarrage de la 3D (relancé par la vue client) et la vue tenue ;
  // les tuiles déjà montrées restent.
  const reessayer = () => { setEssai((n) => n + 1); onReessayer?.() }
  // ACAL2023 — les chiffres sont ceux de la conception courante servie (`donnees.tuiles`) : aucune estimation lue sur l'atelier.
  const { tuiles } = donnees
  return (
    <>
      {noeudScene && createPortal(
        <>
          {/* ACAL1839 — le ciel dégradé au-dessus de la maison (la carte, en vue inclinée, n'atteint pas l'horizon). */}
          {pret && <div aria-hidden="true" data-testid="client-ciel" style={CIEL_CLIENT} />}
          {!pret && (
            <div className="cal-client-repli" data-testid="client-repli-2d">
              {/* ACAL1837 — l'attente est présentable (ciel, silhouette) ; le plan dessus ne sert qu'à l'échec de la 3D. */}
              {retard ? donnees.plan && <PlanDessus plan={donnees.plan} /> : <AttenteScene />}
            </div>
          )}
          <PuceProjet titre={donnees.titre} sousTitre={donnees.sousTitre} />
          {!pret && (retard ? <AvisEchec3D onReessayer={reessayer} /> : <PastilleAttente />)}
          {pret && tourne && (
            <span className="cal-client-pastille cal-client-geste" data-testid="client-aide-geste">
              <IconeTourner />
              {bureau ? 'Glissez pour tourner autour' : 'Glissez un doigt pour tourner autour'}
            </span>
          )}
        </>,
        noeudScene,
      )}
      <div className="cal-client-corps" data-testid="cal-vue-client" data-vue-client="">
        <LecteurSoleil bureau={bureau} />
        <TuilesClient tuiles={tuiles} ville={donnees.ville} bureau={bureau} />
      </div>
      <PiedClient id={calepinageId} />
    </>
  )
}
