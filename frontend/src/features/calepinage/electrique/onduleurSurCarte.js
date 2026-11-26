import { useEffect, useRef, useState } from 'react'

/* ============================================================================
   ACAL1317 (D-ACAL-70) — POSER, DÉPLACER, RETIRER L'ONDULEUR DEPUIS L'ÉTAPE ÉLECTRIQUE.
   ----------------------------------------------------------------------------
   La position de l'onduleur EXISTE déjà : c'est `roof_layout.electrical.equipements[]` (type « onduleur »,
   contrat `electrique_equipements.json`), écrite par la couche électrique de la scène (`electrique3d.ts`,
   `builderApi.electrique`) et enregistrée avec le calepinage. Ce crochet n'ajoute AUCUNE valeur stockée : il
   arme les gestes de la couche (le clic sur la carte pose ou déplace), relit le document après chaque geste
   (`ecouter`) et dit d'où vient le tracé du câble. La longueur est celle que le serveur MESURE sur ce tracé.
   CE QU'UN DÉPLACEMENT CHANGE, À L'ENREGISTREMENT SUIVANT (c'est le sens de « en déduire la longueur de câble ») :
   `services/troncons.py` mesure chaque tronçon tracé, en dimensionne la SECTION et en calcule la CHUTE de tension,
   puis prononce un verdict DC et AC sur les cumuls (CALX224-226, `resultat.troncons`, pastille « Câble côté
   panneaux ») ; `services/bordereau_calepinage.py` prend son métré de câble sur les mêmes tronçons (CALX227). Ces
   verdicts et ce métré bougent donc avec l'onduleur. CE QU'IL NE CHANGE PAS (décision du 26/11, option 2) : `dc_m`
   de l'entrée électrique, la perte câbles de la SIMULATION (`cables_du_calepinage`, qui lit le cheminement saisi —
   son alignement est l'affaire d'une autre tâche), et rien de ce que lit `apps/ventes` (le devis ne lit que `dc_m`
   SAISI, `selectors.entree_electrique_du_devis`). L'empreinte du document porte `electrical` : enregistrer un
   déplacement rend la simulation « à refaire », comme tout geste sur le toit — l'écran le dit après le geste.
   ========================================================================== */

export const PROVENANCE_TRACE_PROPOSE = 'tracé proposé le long des rangées (position de l’onduleur)'
// L'écran ne sait PAS qui a tracé un tracé non reconnu (point par point, saisi, ou proposé sur un toit qui a changé) :
// il ne dit que ce qu'il sait.
export const PHRASE_TRACE_DECALE = 'Le tracé enregistré n’aboutit plus à l’onduleur ; il n’a pas été remplacé.'
// Le document porte `electrical` dans son empreinte : enregistrer un geste sur l'onduleur périme la simulation, comme
// tout geste sur le toit. Mêmes mots que le bandeau de l'atelier (« Simulation à refaire : le toit … a changé … »).
export const PHRASE_SIMULATION_A_REFAIRE = 'Après l’enregistrement : Simulation à refaire, le toit a changé depuis le dernier calcul.'

/** Les gestes dont l'écran a besoin : sans eux (constructeur absent ou ancien), rien n'est proposé. */
const GESTES = ['documentElectrique', 'armerPose', 'armerDeplacement', 'deplacementArme', 'typeArme', 'pousser',
  'retirerAvecTraces', 'etatTraces', 'ecouter', 'definirLectureSeule', 'annuler', 'retablir', 'profondeurHistorique']

/** Désarme ce que la couche attend d'un toucher de la carte : la scène route le clic de carte vers `clicCarte` à
    TOUTES les étapes, un armement oublié poserait un onduleur à l'étape Toit. */
function desarmer(couche) {
  couche.armerDeplacement(null)
  if (couche.typeArme() !== null) couche.armerPose(null)
}

function coucheUtilisable(builderApi) {
  const couche = builderApi?.electrique ?? null
  return couche && GESTES.every((g) => typeof couche[g] === 'function')
    && Number.isFinite(couche.pasDeplacementM) && couche.pasDeplacementM > 0 ? couche : null
}

/** Ctrl+Z / Ctrl+Y (⌘ sur Mac) pressés dans la barre : c'est l'historique ÉLECTRIQUE de la couche qui répond, et la
    touche s'arrête là — sans cela l'atelier (`annulerAtelier.ts`, à l'écoute du document) annulait une action du PLAN,
    sans rapport, en silence. Rend vrai quand la touche est prise. */
export function toucheAnnulation(e, onduleur) {
  if (!onduleur?.disponible || !(e.ctrlKey || e.metaKey)) return false
  const k = String(e.key).toLowerCase()
  const retablir = k === 'y' || (k === 'z' && e.shiftKey)
  if (k !== 'z' && !retablir) return false
  e.preventDefault()
  e.stopPropagation()
  if (retablir) onduleur.retablir(); else onduleur.annuler()
  return true
}

/** La provenance affichée sous la longueur du câble : `null` quand le tracé n'est pas (seulement) celui que la barre
    a proposé. Un pan à modules sans tracé vers l'onduleur rend la longueur PARTIELLE, et c'est dit. */
export function provenanceCable(etat) {
  if (!etat) return null
  if (etat.decales?.length) return 'tracé enregistré — n’aboutit plus à l’onduleur'
  if (!etat.proposes?.length || etat.autres?.length) return null
  const n = etat.pansSansTrace?.length ?? 0
  if (n) return `tracé partiel : ${n} pan${n > 1 ? 's' : ''} sans tracé vers l’onduleur`
  return PROVENANCE_TRACE_PROPOSE
}

function phraseApresGeste(couche, id, verbe) {
  const refus = couche.dernierRefus?.()
  if (refus) return `Onduleur ${verbe}, mais ${refus.message.charAt(0).toLowerCase()}${refus.message.slice(1)} ${PHRASE_SIMULATION_A_REFAIRE}`
  const etat = id ? couche.etatTraces(id) : null
  if (etat?.decales?.length) return `${PHRASE_TRACE_DECALE} ${PHRASE_SIMULATION_A_REFAIRE}`
  return `Onduleur ${verbe} : le tracé du câble a suivi. Enregistrez le calepinage pour mesurer sa longueur. ${PHRASE_SIMULATION_A_REFAIRE}`
}

/**
 * L'état de l'onduleur sur la carte et ses gestes. `nombreAttendu` = les onduleurs de l'entrée électrique
 * (`nombre_onduleurs`, 1 par défaut) : la barre n'en pose jamais plus. Plusieurs onduleurs au document : les gestes
 * visent celui CHOISI (`choisir`), le premier par défaut.
 */
export function useOnduleurSurCarte({ builderApi, enregistreLe = null, nombreAttendu = 1, lectureSeule = false } = {}) {
  const couche = coucheUtilisable(builderApi)
  const [, setVersion] = useState(0)
  const [choisiId, setChoisiId] = useState(null)
  const [message, setMessage] = useState(null)
  // « à enregistrer » = un geste fait depuis le dernier enregistrement de l'atelier (`enregistreLe` relu au geste).
  const [gesteDepuis, setGesteDepuis] = useState(undefined)
  const enregistreRef = useRef(enregistreLe)
  useEffect(() => { enregistreRef.current = enregistreLe }, [enregistreLe])
  const marquerGeste = () => setGesteDepuis(enregistreRef.current)
  const aEnregistrer = gesteDepuis !== undefined && gesteDepuis === enregistreLe
  const attente = useRef(null) // le geste armé par la barre, que le clic sur la carte achèvera

  useEffect(() => {
    if (!couche) return undefined
    return couche.ecouter(() => {
      setVersion((v) => v + 1)
      const armeParBarre = attente.current
      if (armeParBarre && couche.deplacementArme() === null && couche.typeArme() === null) {
        attente.current = null
        const pose = armeParBarre.verbe === 'placé'
        const id = pose
          ? (couche.documentElectrique()?.equipements ?? []).filter((e) => e?.type === 'onduleur').at(-1)?.id
          : armeParBarre.id
        if (pose && id) setChoisiId(id)
        setGesteDepuis(enregistreRef.current)
        setMessage(phraseApresGeste(couche, id, armeParBarre.verbe))
      }
    })
  }, [couche])
  // Lecture seule : la COUCHE refuse elle-même toute écriture (et désarme) ; quitter l'étape (l'écran démonte)
  // désarme aussi, pour que le prochain toucher de la carte à une autre étape ne pose rien.
  useEffect(() => {
    if (!couche) return undefined
    couche.definirLectureSeule(!!lectureSeule)
    if (lectureSeule) attente.current = null
    return () => { attente.current = null; desarmer(couche) }
  }, [couche, lectureSeule])

  const onduleurs = couche
    ? (couche.documentElectrique()?.equipements ?? []).filter((e) => e?.type === 'onduleur')
    : []
  const choisi = onduleurs.find((e) => e.id === choisiId) ?? onduleurs[0] ?? null
  const etat = couche && choisi ? couche.etatTraces(choisi.id) : null
  const enDeplacement = !!(couche && choisi && couche.deplacementArme() === choisi.id)
  const enPose = !!(couche && couche.typeArme() === 'onduleur')

  const placer = () => {
    if (!couche) return
    couche.armerPose('onduleur', { suivreTrace: true })
    attente.current = { verbe: 'placé' }
    setMessage('Touchez la carte à l’endroit de l’onduleur.')
    setVersion((v) => v + 1)
  }
  const deplacer = () => {
    if (!couche || !choisi) return
    couche.armerDeplacement(choisi.id)
    attente.current = { verbe: 'déplacé', id: choisi.id }
    setMessage('Touchez la carte à la nouvelle place de l’onduleur, ou poussez-le avec les flèches.')
    setVersion((v) => v + 1)
  }
  const pousser = (dEstM, dNordM) => {
    if (!couche || !choisi) return
    const r = couche.pousser(choisi.id, dEstM, dNordM)
    if (!r.ok) { setMessage(r.message); return }
    marquerGeste()
    setMessage(r.refusTrace ? `Onduleur déplacé, mais ${r.refusTrace.message} ${PHRASE_SIMULATION_A_REFAIRE}` : phraseApresGeste(couche, choisi.id, 'déplacé'))
  }
  const terminer = () => {
    if (!couche) return
    attente.current = null
    couche.armerDeplacement(null)
    if (couche.typeArme() === 'onduleur') couche.armerPose(null)
    setMessage(null)
    setVersion((v) => v + 1)
  }
  const annuler = () => {
    if (!couche || lectureSeule) return
    attente.current = null
    if (!couche.annuler()) { setMessage('Rien à annuler dans le raccordement.'); return }
    marquerGeste()
    setMessage('Dernier geste du raccordement annulé.')
  }
  const retablir = () => {
    if (!couche || lectureSeule) return
    attente.current = null
    if (!couche.retablir()) { setMessage('Rien à rétablir dans le raccordement.'); return }
    marquerGeste()
    setMessage('Geste du raccordement rétabli.')
  }
  const retirer = () => {
    if (!couche || !choisi) return
    attente.current = null
    const r = couche.retirerAvecTraces(choisi.id)
    if (!r.ok) return
    marquerGeste()
    setChoisiId(null)
    const n = r.tracesGardees.length
    setMessage(n
      ? `Onduleur retiré. ${n} autre${n > 1 ? 's' : ''} tracé${n > 1 ? 's' : ''} vers lui reste${n > 1 ? 'nt' : ''} sur le plan : il${n > 1 ? 's n’ont' : ' n’a'} pas été retiré${n > 1 ? 's' : ''}.`
      : `Onduleur retiré du plan. ${PHRASE_SIMULATION_A_REFAIRE}`)
  }

  return {
    disponible: !!couche,
    pas: couche?.pasDeplacementM ?? null,
    onduleurs,
    choisi,
    choisir: (id) => {
      // Un déplacement armé pour un AUTRE onduleur ne survit pas au changement de choix.
      if (couche && couche.deplacementArme() !== null && couche.deplacementArme() !== id) {
        attente.current = null
        couche.armerDeplacement(null)
        setMessage(null)
      }
      setChoisiId(id)
    },
    peutPlacer: !!couche && onduleurs.length < Math.max(1, Number(nombreAttendu) || 1),
    enDeplacement,
    enPose,
    message,
    provenance: provenanceCable(etat),
    // Un geste depuis l'ouverture de l'étape, et s'il attend encore l'enregistrement de l'atelier.
    aGeste: gesteDepuis !== undefined,
    aEnregistrer,
    placer,
    deplacer,
    pousser,
    terminer,
    retirer,
    annuler,
    retablir,
    peutAnnuler: !!couche && !lectureSeule && (couche.profondeurHistorique()?.undo ?? 0) > 0,
  }
}
