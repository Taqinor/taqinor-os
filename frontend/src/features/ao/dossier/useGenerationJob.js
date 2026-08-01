import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import aoApi from '../../../api/aoApi'
import useVisibilityAwarePolling from '../../../hooks/useVisibilityAwarePolling'

/* ============================================================================
   AOF177 — Suivi de la génération asynchrone du pack et du ZIP.
   ----------------------------------------------------------------------------
   AOF153 produit le pack en tâche Celery (`core.jobs.submit`, clé
   d'idempotence = empreinte du contexte) avec avancement PIÈCE PAR PIÈCE et un
   endpoint de statut ; sans consommateur, rien de tout cela n'est visible. Ce
   hook est ce consommateur, calqué sur le patron de sondage des exports
   asynchrones du dépôt (`BackgroundJobsBell` / SCA41) : **le hook partagé
   `useVisibilityAwarePolling` (VX56)**, jamais un `setInterval` maison, jamais
   un sondage d'onglet masqué.

   Trois garanties tenues ici :
     • **Rien ne bloque.** `lancer()` rend la main immédiatement ; l'écran reste
       utilisable pendant toute la génération.
     • **Reprise après départ/retour.** L'identifiant du job est mémorisé par
       dossier (`localStorage`) : revenir sur l'écran REPREND le suivi au lieu
       de relancer une seconde génération.
     • **Le 409 du verrou de dossier (AOF155) est NOMMÉ.** Un refus de verrou
       n'est pas « une erreur » : le porteur et l'heure sont exposés tels que le
       serveur les renvoie.

   ANNULATION : le serveur n'expose pas (encore) d'endpoint d'annulation dans
   `api/aoApi.js` (AOF11, lane `frontend/ao-socle`, jamais retouché ici). Le
   hook accepte donc `onAnnulerServeur(jobId)` — quand il est fourni, il est
   appelé ; dans tous les cas l'utilisateur cesse de suivre le job et l'écran
   redevient disponible. Aucun endpoint n'est inventé.
   ========================================================================== */

// Statuts « le job tourne encore » — tolère les deux vocabulaires rencontrés
// (`core.jobs.BackgroundJob` en anglais, fabrique AO en français).
const ACTIFS = new Set(['queued', 'running', 'en_file', 'en_cours'])
const SUCCES = new Set(['done', 'succes', 'termine'])
const ECHECS = new Set(['failed', 'echec', 'erreur'])

export const cleStockage = (dossierId) => `ao.dossier.${dossierId}.job-pack`

function lire(cle) {
  try { return globalThis.localStorage?.getItem(cle) ?? null } catch { return null }
}
function ecrire(cle, valeur) {
  try {
    if (valeur == null) globalThis.localStorage?.removeItem(cle)
    else globalThis.localStorage?.setItem(cle, String(valeur))
  } catch { /* stockage indisponible : on dégrade sans casser l'écran */ }
}

/** Verrou de dossier renvoyé par un 409 (AOF155) : le serveur NOMME le porteur
    et l'heure. On ne fabrique aucun message à sa place. */
export function lireVerrou(err) {
  if (err?.response?.status !== 409) return null
  const data = err.response.data || {}
  return {
    porteur: data.verrou?.porteur ?? data.porteur ?? null,
    depuis: data.verrou?.depuis ?? data.depuis ?? null,
    detail: data.detail ?? null,
  }
}

export function etatDeJob(job) {
  const s = job?.statut ?? job?.status
  if (!s) return 'idle'
  if (SUCCES.has(s)) return 'succes'
  if (ECHECS.has(s)) return 'echec'
  if (ACTIFS.has(s)) return 'en_cours'
  return 'en_cours'
}

export default function useGenerationJob(dossierId, options = {}) {
  const { intervalMs = 3000, onSucces, onEchec, onAnnulerServeur } = options

  const [jobId, setJobId] = useState(null)
  const [job, setJob] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [verrou, setVerrou] = useState(null)
  const [lancement, setLancement] = useState(false)

  // Callbacks lus par référence : le sondage ne redémarre pas quand l'écran
  // recrée ses fermetures à chaque rendu.
  const cbRef = useRef({ onSucces, onEchec })
  useEffect(() => { cbRef.current = { onSucces, onEchec } })
  // Un job n'est notifié qu'UNE fois, même si un dernier sondage repasse.
  const notifieRef = useRef(null)
  // Job réellement suivi À CET INSTANT : une réponse de sondage arrivée APRÈS
  // une annulation (ou après un relancement) est jetée, jamais appliquée.
  const jobIdRef = useRef(null)
  useEffect(() => { jobIdRef.current = jobId }, [jobId])

  const cle = useMemo(() => cleStockage(dossierId), [dossierId])

  // Reprise : l'utilisateur est parti puis revenu — on REPREND le suivi du job
  // en cours au lieu d'en lancer un second.
  useEffect(() => {
    const memorise = lire(cle)
    jobIdRef.current = memorise || null
    setJobId(memorise || null)
    setJob(null)
    setErreur(null)
    setVerrou(null)
    notifieRef.current = null
  }, [cle])

  const etat = etatDeJob(job)
  const actif = Boolean(jobId) && (job == null || etat === 'en_cours')

  const sonder = useCallback(async () => {
    if (!jobId) return
    try {
      const res = await aoApi.dossiers.statutJob(dossierId, jobId)
      // Réponse périmée (annulation ou relancement pendant le vol) : on jette.
      if (jobIdRef.current !== jobId) return
      const j = res?.data
      setJob(j)
      const e = etatDeJob(j)
      if ((e === 'succes' || e === 'echec') && notifieRef.current !== jobId) {
        notifieRef.current = jobId
        ecrire(cle, null)
        if (e === 'succes') cbRef.current.onSucces?.(j)
        else cbRef.current.onEchec?.(j)
      }
    } catch (e) {
      setErreur(e?.response?.data?.detail || 'Suivi de la génération interrompu.')
    }
  }, [cle, dossierId, jobId])

  useVisibilityAwarePolling(
    useMemo(() => [{ fn: sonder, intervalMs }], [sonder, intervalMs]),
    { enabled: actif },
  )

  const lancer = useCallback(async () => {
    setErreur(null)
    setVerrou(null)
    setJob(null)
    notifieRef.current = null
    setLancement(true)
    try {
      const res = await aoApi.dossiers.zip(dossierId)
      const id = res?.data?.job_id ?? res?.data?.id ?? null
      jobIdRef.current = id
      setJobId(id)
      ecrire(cle, id)
      return id
    } catch (e) {
      const v = lireVerrou(e)
      if (v) setVerrou(v)
      setErreur(e?.response?.data?.detail || 'Génération du pack impossible.')
      return null
    } finally {
      setLancement(false)
    }
  }, [cle, dossierId])

  const annuler = useCallback(async () => {
    const id = jobId
    jobIdRef.current = null
    setJobId(null)
    setJob(null)
    ecrire(cle, null)
    notifieRef.current = null
    if (id && onAnnulerServeur) {
      try { await onAnnulerServeur(id) } catch { /* déjà arrêté côté serveur */ }
    }
  }, [cle, jobId, onAnnulerServeur])

  // Un job vient d'être accepté mais n'a pas encore été sondé : c'est « en
  // cours », jamais « idle » (sinon le bouton se rearme et double la demande).
  let statut = 'idle'
  if (lancement) statut = 'en_cours'
  else if (!jobId) statut = 'idle'
  else if (job) statut = etat
  else statut = 'en_cours'

  return {
    statut,
    job,
    jobId,
    // Avancement PIÈCE PAR PIÈCE tel que le serveur le renvoie (aucun chiffre
    // dérivé côté front — AOF94).
    pieces: job?.pieces ?? [],
    progression: job?.progress_pct ?? job?.progression ?? 0,
    resultatUrl: job?.resultat_url ?? job?.url ?? null,
    erreur,
    verrou,
    enCours: statut === 'en_cours',
    lancer,
    annuler,
    sonder,
  }
}
