import { useEffect, useRef, useState } from 'react'

/* ============================================================================
   ACAL1317 (D-ACAL-70) — POSER, DÉPLACER, RETIRER L'ONDULEUR DEPUIS L'ÉTAPE ÉLECTRIQUE.
   ----------------------------------------------------------------------------
   La position de l'onduleur EXISTE déjà : c'est `roof_layout.electrical.equipements[]` (type « onduleur »,
   contrat `electrique_equipements.json`), écrite par la couche électrique de la scène (`electrique3d.ts`,
   `builderApi.electrique`) et enregistrée avec le calepinage. Ce crochet n'ajoute AUCUNE valeur stockée : il
   arme les gestes de la couche (le clic sur la carte pose ou déplace), relit le document après chaque geste
   (`ecouter`) et dit d'où vient le tracé du câble. La longueur reste celle que le serveur MESURE sur ce tracé
   (`troncons`, pastille « Câble côté panneaux ») — une valeur d'AFFICHAGE : elle ne nourrit ni `dc_m`, ni la
   simulation, ni rien de ce que le devis lit (décision du 26/11, option 2).
   ========================================================================== */

export const PROVENANCE_TRACE_PROPOSE = 'tracé proposé le long des rangées (position de l’onduleur)'
// L'écran ne sait PAS qui a tracé un tracé non reconnu (point par point, saisi, ou proposé sur un toit qui a changé) :
// il ne dit que ce qu'il sait.
export const PHRASE_TRACE_DECALE = 'Le tracé enregistré n’aboutit plus à l’onduleur ; il n’a pas été remplacé.'

/** Les gestes dont l'écran a besoin : sans eux (constructeur absent ou ancien), rien n'est proposé. */
const GESTES = ['documentElectrique', 'armerPose', 'armerDeplacement', 'deplacementArme', 'typeArme', 'pousser',
  'retirerAvecTraces', 'etatTraces', 'ecouter']

function coucheUtilisable(builderApi) {
  const couche = builderApi?.electrique ?? null
  return couche && GESTES.every((g) => typeof couche[g] === 'function')
    && Number.isFinite(couche.pasDeplacementM) && couche.pasDeplacementM > 0 ? couche : null
}

/** La provenance affichée sous la longueur du câble : `null` quand le tracé n'est pas (seulement) celui que la barre
    a proposé. Un pan à modules sans tracé vers l'onduleur rend la longueur PARTIELLE, et c'est dit. */
export function provenanceCable(etat, aEnregistrer) {
  if (!etat) return null
  if (etat.decales?.length) return 'tracé enregistré — n’aboutit plus à l’onduleur'
  if (!etat.proposes?.length || etat.autres?.length) return null
  const n = etat.pansSansTrace?.length ?? 0
  if (n) return `tracé partiel : ${n} pan${n > 1 ? 's' : ''} sans tracé vers l’onduleur`
  return aEnregistrer ? `${PROVENANCE_TRACE_PROPOSE} — longueur mesurée à l’enregistrement` : PROVENANCE_TRACE_PROPOSE
}

function phraseApresGeste(couche, id, verbe) {
  const refus = couche.dernierRefus?.()
  if (refus) return `Onduleur ${verbe}, mais ${refus.message.charAt(0).toLowerCase()}${refus.message.slice(1)}`
  const etat = id ? couche.etatTraces(id) : null
  if (etat?.decales?.length) return PHRASE_TRACE_DECALE
  return `Onduleur ${verbe} : le tracé du câble a suivi. Enregistrez le calepinage pour mesurer sa longueur.`
}

/**
 * L'état de l'onduleur sur la carte et ses gestes. `nombreAttendu` = les onduleurs de l'entrée électrique
 * (`nombre_onduleurs`, 1 par défaut) : la barre n'en pose jamais plus. Plusieurs onduleurs au document : les gestes
 * visent celui CHOISI (`choisir`), le premier par défaut.
 */
export function useOnduleurSurCarte({ builderApi, enregistreLe = null, nombreAttendu = 1 } = {}) {
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
    setMessage(r.refusTrace ? `Onduleur déplacé, mais ${r.refusTrace.message}` : phraseApresGeste(couche, choisi.id, 'déplacé'))
  }
  const terminer = () => {
    if (!couche) return
    attente.current = null
    couche.armerDeplacement(null)
    if (couche.typeArme() === 'onduleur') couche.armerPose(null)
    setMessage(null)
    setVersion((v) => v + 1)
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
      : 'Onduleur retiré du plan.')
  }

  return {
    disponible: !!couche,
    pas: couche?.pasDeplacementM ?? null,
    onduleurs,
    choisi,
    choisir: setChoisiId,
    peutPlacer: !!couche && onduleurs.length < Math.max(1, Number(nombreAttendu) || 1),
    enDeplacement,
    enPose,
    message,
    provenance: provenanceCable(etat, aEnregistrer),
    placer,
    deplacer,
    pousser,
    terminer,
    retirer,
  }
}
