/* ============================================================================
   ACAL345 — L'UNIQUE ÉTAT D'ÉCRAN D'UNE SURFACE DE POSE (terrain ET ombrière).
   ----------------------------------------------------------------------------
   `ModeTerrain.jsx` (CAL89) et `Ombriere.jsx` (CAL91) portaient deux copies du
   même cycle : lecture du document (ACAL24), chargement paresseux du placeur
   `@roofpro/scene3d` (CALX50/51), relecture d'une surface déjà enregistrée,
   invalidation du plan quand une entrée du moteur change (ACAL25), choix /
   nouvelle surface, appel `moteur.pose`, enregistrement et suppression PAR id
   dans `poseSurfaces`. Deux copies d'un même aller-retour finissent par
   diverger (C-ACAL-034) : ce hook est la seule. Seuls changent, par écran, le
   genre de surface, le repère par défaut, le placeur chargé et les libellés.
   ========================================================================== */
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import calepinageApi from '../../api/calepinageApi'
import useDocumentCalepinage, { ecrireSection } from './useDocumentCalepinage'
import {
  documentSurfacePose, saisieDepuisSurface, reponseDepuisSurface,
  entreeMoteurChangee, surfacesDuGenre, remplacerSurface, retirerSurface, repereLibre,
} from './surfacePose'
import { motifChampVide, motifRefus } from './ModeTerrain'

/**
 * @param {object} o
 * @param {?(number|string)} o.idPropose  id passé par l'atelier (sinon `:id` de l'URL)
 * @param {string} o.kind            genre de surface (`KIND_SOL`, `KIND_OMBRIERE`)
 * @param {string} o.repereDefaut    repère quand la saisie n'en porte aucun
 * @param {object} o.saisieVide      la saisie initiale de l'écran
 * @param {string} o.nomPlaceur      export de `@roofpro/scene3d` à charger
 * @param {object} o.libelles        { enregistre, nonEnregistre, supprime, nonSupprime, echecPose }
 */
export default function useSurfacePose({
  idPropose, persister, documentVivant, kind, repereDefaut, saisieVide, nomPlaceur, libelles,
}) {
  // L'id vient de l'atelier (prop) ou, écran autonome, de l'URL.
  const { id: idUrl } = useParams()
  const calepinageId = idPropose ?? idUrl
  const [saisie, setSaisie] = useState(saisieVide)
  // ACAL24 — l'UNIQUE lecture du document (hook) : un échec donne `erreur`, jamais
  // un document vide ; l'écriture ne porte que la clé `poseSurfaces`.
  const doc = useDocumentCalepinage(calepinageId, { actif: persister })
  const [reponse, setReponse] = useState(null)
  const [enCours, setEnCours] = useState(false)
  const [message, setMessage] = useState(null)
  // CALX50/51 — le PLACEUR du builder, chargé à l'ouverture de l'écran
  // seulement : `scene3d` porte aussi la couche WebGL, qu'un import statique
  // ferait tomber dans le paquet de la route. Rangé dans un objet : une
  // fonction nue passée à `setState` serait lue comme une mise à jour.
  const [placeur, setPlaceur] = useState(null)
  const [placeurAbsent, setPlaceurAbsent] = useState(false)

  useEffect(() => {
    let annule = false
    import('@roofpro/scene3d')
      .then((mod) => {
        if (annule) return
        if (typeof mod?.[nomPlaceur] === 'function') {
          setPlaceur({ [nomPlaceur]: mod[nomPlaceur] })
        } else {
          setPlaceurAbsent(true)
        }
      })
      .catch(() => { if (!annule) setPlaceurAbsent(true) })
    return () => { annule = true }
  }, [nomPlaceur])

  // RELECTURE — une surface déjà enregistrée revient telle quelle (une fois par
  // lecture serveur, jamais à une application locale d'une section écrite).
  const [lectureHydratee, setLectureHydratee] = useState(null)
  if (persister && doc.etat === 'ok' && lectureHydratee !== doc.generation) {
    setLectureHydratee(doc.generation)
    const premiere = surfacesDuGenre(doc.document?.poseSurfaces, kind)[0]
    if (premiere) {
      setSaisie((s) => ({ ...s, ...saisieDepuisSurface(premiere) }))
      // Le plan RECHARGÉ est celui du moteur : on le réaffiche sans le refaire.
      setReponse(reponseDepuisSurface(premiere))
    }
  }

  const surfaces = surfacesDuGenre(doc.document?.poseSurfaces, kind)
  const repereCourant = saisie.repere || repereDefaut
  const dejaEnregistree = surfaces.some((s) => s.id === repereCourant)

  const majChamp = (cle, brut) => {
    setSaisie((s) => ({ ...s, [cle]: brut }))
    // ACAL25 — le plan calculé ne vaut que pour la saisie qui l'a produit : dès
    // qu'une entrée du moteur change, il est invalidé (jamais un document mixte
    // contour 80 m / plan moteur 40 m).
    if (reponse && entreeMoteurChangee(cle)) {
      setReponse(null)
      setMessage('Une entrée du moteur a changé : recalculez le plan avant d’enregistrer.')
    }
  }

  // Une surface déjà enregistrée est rééditée (liste) ; « Nouvelle » en ouvre
  // une autre, sous un repère libre.
  const choisirSurface = (surface) => {
    setSaisie((s) => ({ ...s, ...saisieDepuisSurface(surface) }))
    setReponse(reponseDepuisSurface(surface))
    setMessage(null)
  }
  const nouvelleSurface = () => {
    setSaisie((s) => ({
      ...s, repere: repereLibre(doc.document?.poseSurfaces, kind), label: '',
    }))
    setReponse(null)
    setMessage(null)
  }

  /** Soumet une demande DÉJÀ construite par l'écran ; `null` ⇒ `messageIncomplet`. */
  const poser = (demande, messageIncomplet) => {
    if (!demande) {
      setMessage(messageIncomplet)
      return
    }
    setMessage(null)
    setEnCours(true)
    Promise.resolve(calepinageApi.moteur.pose({ demande }))
      .then((res) => {
        setEnCours(false)
        setReponse(res?.data ?? null)
        setMessage(motifChampVide(res?.data))
      })
      .catch((e) => {
        setEnCours(false)
        setReponse(null)
        setMessage(motifRefus(e?.response?.data) || libelles.echecPose)
      })
  }

  const ecrire = async (valeur, succes, relance, echec) => {
    const res = await ecrireSection({
      calepinageId, cle: 'poseSurfaces', valeur, empreinte: doc.empreinte, documentVivant,
    })
    if (res.ok) {
      doc.appliquerSection('poseSurfaces', valeur, res.empreinte)
      setMessage(succes)
    } else if (res.conflit) {
      setMessage(`La conception a changé ailleurs : elle est relue, ${relance}.`)
      doc.recharger()
    } else {
      setMessage(res.motif || echec)
    }
  }

  const enregistrer = async () => {
    if (doc.etat !== 'ok') return
    if (!reponse) {
      setMessage('Aucun plan du moteur : il n’y a rien à enregistrer.')
      return
    }
    // ACAL25 — la surface est remplacée PAR id : les autres surfaces restent.
    const valeur = remplacerSurface(
      doc.document?.poseSurfaces, documentSurfacePose(saisie, reponse, kind),
    )
    await ecrire(valeur, libelles.enregistre, 'enregistrez de nouveau', libelles.nonEnregistre)
  }

  const supprimer = async () => {
    if (doc.etat !== 'ok' || !dejaEnregistree) return
    const valeur = retirerSurface(doc.document?.poseSurfaces, kind, repereCourant)
    await ecrire(valeur, libelles.supprime, 'recommencez', libelles.nonSupprime)
  }

  const plan = (reponse?.plans ?? [])[0] ?? null

  return {
    calepinageId, saisie, doc, reponse, enCours, message, placeur, placeurAbsent,
    surfaces, repereCourant, dejaEnregistree, plan,
    majChamp, choisirSurface, nouvelleSurface, poser, enregistrer, supprimer,
  }
}
