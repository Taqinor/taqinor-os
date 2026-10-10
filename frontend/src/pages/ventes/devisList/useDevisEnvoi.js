// SPL205 — parcours d'envoi de la liste des devis (email, copie des liens,
// WhatsApp + relance, deep-link EZ3 ?envoyer=1 / ?apercu=1, « Contacter mon
// supérieur »), déplacé VERBATIM de DevisList.jsx (move only). Les statuts ne
// sont JAMAIS écrits ici : le marquage « envoyé » est fait par le serveur
// (garde T17, règle #4).
import { useEffect, useMemo, useRef, useState } from 'react'
import { rafraichirDevis } from '../../../features/ventes/store/ventesSlice.js'
import ventesApi from '../../../api/ventesApi.js'
import { toast } from '../../../ui/index.js'
import { formatMAD } from '../../../lib/format.js'
// VX156 — le devis envoyé porte la voix Taqinor (moment « devis envoyé »).
import { voice } from '../../../lib/voice.js'
// VX155 — jalon « devis envoyé » : un cran au-dessus du toast succès plat.
import { toastMilestone } from '../../../lib/toast.js'
import { clientProposalUrl } from '../../../features/ventes/clientProposalLink.js'
import useVisibilityAwarePolling from '../../../hooks/useVisibilityAwarePolling.js'
import { frenchError, buildRelanceWaUrl } from './devisListHelpers.js'

// L'effet EZ3 lit d'autres hooks : `setPreviewDevis` vient de useDevisPdf
// (appelé AVANT), `setStatutActionId` reste un état du composant principal,
// `highlightId` / `highlightedDevis` / `loading` / `searchParams` aussi.
export function useDevisEnvoi({
  dispatch, setPreviewDevis, setStatutActionId,
  highlightId, highlightedDevis, loading, searchParams, setSearchParams,
}) {
  // QJ14 — Modale « Envoyer par email » (PDF premium + lien tokenisé → client).
  const [emailTarget, setEmailTarget]   = useState(null)
  const [emailAddress, setEmailAddress] = useState('')
  const [emailBusy, setEmailBusy]       = useState(false)

  const openEmailModal = (d) => {
    setEmailTarget(d)
    setEmailAddress(d.client_email || '')
  }
  const closeEmailModal = () => { setEmailTarget(null); setEmailAddress('') }
  const submitEmail = async () => {
    if (!emailTarget) return
    setEmailBusy(true)
    try {
      const payload = emailAddress ? { to_email: emailAddress } : {}
      await ventesApi.envoyerEmailDevis(emailTarget.id, payload)
      closeEmailModal()
      dispatch(rafraichirDevis(emailTarget.id))
      // VX156/VX155 — moment « devis envoyé » : un jalon (toastMilestone), pas
      // un succès plat — réf/client/montant + la voix Taqinor en description.
      toastMilestone(`Devis ${emailTarget.reference} envoyé par email.`, {
        description: [emailTarget.client_nom, formatMAD(emailTarget.total_affiche ?? emailTarget.total_ttc), voice.devisSent]
          .filter(Boolean).join(' · '),
      })
    } catch (err) {
      toast.error(frenchError(err, 'Envoi email impossible.'))
    } finally {
      setEmailBusy(false)
    }
  }

  // VX79 — lien INTERNE partageable d'un devis : /ventes/devis?devis=<pk> (miroir
  // du deep-link QX12 déjà supporté au montage). Distinct du lien PUBLIC de
  // proposition (règle #4 — handleCopierLienProposition, intouché) : celui-ci
  // pointe vers l'ERP, à envoyer à un collègue (« regarde CE devis »).
  const copierLienInterne = async (d) => {
    const url = `${window.location.origin}/ventes/devis?devis=${d.id}`
    try { await navigator.clipboard?.writeText(url) } catch { /* presse-papier indispo */ }
    toast.success('Lien interne du devis copié.')
  }

  const [shareBusyId, setShareBusyId] = useState(null)

  // L-INTPREV/QJ1bis — « Copier l'aperçu interne » : la MÊME page publique
  // que le client, servie par le jeton INTERNE (ShareLink.token_interne) —
  // aucune notification, aucun compteur de vues, aucune note chatter, aucune
  // avance de funnel. C'est le lien que Reda/Meryem ouvrent pour vérifier ;
  // le lien CLIENT (WR2 ci-dessous) reste le seul à envoyer.
  const handleCopierApercuInterne = async (d) => {
    setShareBusyId(d.id)
    try {
      const res = await ventesApi.shareLinkDevis(d.id)
      const path = res?.data?.path_interne
      if (path) {
        const url = clientProposalUrl(path, import.meta.env.VITE_PUBLIC_SITE_URL)
        try { await navigator.clipboard?.writeText(url) } catch { /* presse-papier indispo */ }
        toast.success('Aperçu interne copié — ne l’envoyez jamais au client (aucune notification).')
      } else {
        toast.error('Aperçu interne indisponible.')
      }
    } catch (err) {
      toast.error(frenchError(err, 'Génération de l’aperçu interne impossible.'))
    } finally {
      setShareBusyId(null)
    }
  }

  // WR2 — « Copier le lien proposition » : (re)mint le lien public tokenisé du
  // devis (DevisViewSet.share_link) et le copie au presse-papier.
  // QJR531 (D-QJR5-3) — copier le lien CLIENT = ENVOI, comme depuis la fiche
  // lead (DevisTab.copierPageClient) : `envoi: true` → mark_devis_sent côté
  // serveur (le devis passe « envoyé », le funnel avance), puis la liste est
  // rechargée. « Copier l'aperçu interne » ci-dessus reste SANS envoi.
  const handleCopierLienProposition = async (d) => {
    setShareBusyId(d.id)
    try {
      const res = await ventesApi.shareLinkDevis(d.id, { envoi: true })
      dispatch(rafraichirDevis(d.id))
      // Le backend renvoie {token, path} (path = /proposition/<slug-client>/
      // <token>, PV84 — slug cosmétique, jamais vérifié côté serveur) — on
      // reconstruit l'URL publique complète (site public, cf. VITE_PUBLIC_SITE_URL).
      // Le repli sans slug (token seul) ne sert que si le backend omettait
      // exceptionnellement `path` : il reste une route valide côté site.
      const path = res?.data?.path || (res?.data?.token ? `/proposition/${res.data.token}` : null)
      if (path) {
        const url = clientProposalUrl(path, import.meta.env.VITE_PUBLIC_SITE_URL)
        try { await navigator.clipboard?.writeText(url) } catch { /* presse-papier indispo */ }
        toast.success('Lien copié — devis marqué envoyé.')
      } else {
        toast.error('Lien de proposition indisponible.')
      }
    } catch (err) {
      toast.error(frenchError(err, 'Génération du lien impossible.'))
    } finally {
      setShareBusyId(null)
    }
  }

  // QG8/QX22 — « Envoyer » = flux WhatsApp des leads (aperçu du message + lien
  // tokenisé). La modale se peuple désormais depuis une action de PRÉVISUALISATION
  // en LECTURE SEULE (whatsappPreviewDevis) — ouvrir-puis-fermer sans cliquer ne
  // marque plus rien « Envoyé ». Le devis n'est marqué « Envoyé » que sur le clic
  // réel vers wa.me (mark_devis_sent côté serveur, appelé par openWhatsApp).
  const [waTarget, setWaTarget] = useState(null)   // devis ciblé
  const [waData, setWaData] = useState(null)        // { wa_url, message, url }
  const [waSending, setWaSending] = useState(false)
  // VX222 — la même modale WhatsApp bascule en mode « relance » (message de
  // rappel + note au chatter) au lieu de l'envoi initial. Réinitialisé à la
  // fermeture pour qu'un « Envoyer » ultérieur reparte en mode initial.
  const [relanceMode, setRelanceMode] = useState(false)
  // GAMMES — ENVOI À LA CARTE : quand le devis appartient à une paire de
  // gammes, le vendeur choisit ici d'envoyer CETTE gamme seule ou LES DEUX
  // (défaut fondateur : les deux, comme l'axe batterie). Le mode part avec
  // l'envoi et vit ensuite sur le devis. `null` = devis sans gamme → la modale
  // est exactement celle d'aujourd'hui.
  const [waGammeEnvoi, setWaGammeEnvoi] = useState('les_deux')
  const handleEnvoyer = async (d) => {
    setStatutActionId(d.id)
    try {
      const res = await ventesApi.whatsappPreviewDevis(d.id)
      setWaTarget(d)
      setWaData(res.data)
      setWaGammeEnvoi(res?.data?.gamme?.envoi || 'les_deux')
      // Aperçu seul — AUCUNE mutation de statut ici (fermer la modale sans
      // cliquer « Ouvrir WhatsApp » laisse le devis brouillon).
    } catch (err) {
      toast.error(frenchError(err, 'Préparation WhatsApp impossible.'))
    } finally {
      setStatutActionId(null)
    }
  }
  // VX222 — « Relancer » un devis envoyé : rouvre la MÊME modale d'aperçu
  // WhatsApp (whatsappPreviewDevis, lecture seule) mais en mode relance. Aucune
  // mutation tant que le vendeur n'a pas cliqué « Ouvrir WhatsApp ».
  const handleRelancer = (d) => { setRelanceMode(true); handleEnvoyer(d) }

  // EZ3 — le panneau de succès du générateur enchaîne DIRECTEMENT sur l'action
  // suivante : `?envoyer=1` ouvre l'aperçu WhatsApp du devis ciblé, `?apercu=1`
  // ouvre l'aperçu PDF inline (APX14). Ce sont les flux EXISTANTS de cet écran
  // — aucun second chemin d'envoi ni de PDF n'est créé. Ne se déclenche
  // qu'UNE fois (le paramètre est consommé). Placé APRÈS `handleEnvoyer` :
  // un effet ne doit pas référencer une liaison déclarée plus bas.
  const enchaineFait = useRef(false)
  useEffect(() => {
    if (enchaineFait.current || !highlightId || loading) return
    if (!highlightedDevis) return
    const envoyer = searchParams.get('envoyer') === '1'
    const apercu = searchParams.get('apercu') === '1'
    if (!envoyer && !apercu) return
    enchaineFait.current = true
    // eslint-disable-next-line react-hooks/set-state-in-effect -- enchaînement d'un deep-link, une seule exécution gardée par enchaineFait
    if (envoyer) handleEnvoyer(highlightedDevis)
    else setPreviewDevis(highlightedDevis)
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.delete('envoyer')
      next.delete('apercu')
      return next
    }, { replace: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- enchaînement à UNE seule exécution
  }, [highlightId, highlightedDevis, loading])

  const closeWaModal = () => {
    setWaTarget(null); setWaData(null); setWaSending(false); setRelanceMode(false)
  }
  // QX22 — clic réel sur « Ouvrir WhatsApp » : ouvre wa.me PUIS marque le devis
  // « Envoyé » côté serveur (whatsappDevis, l'action d'envoi véritable — jamais
  // au moment de l'ouverture de la modale). Le lien s'ouvre même si le marquage
  // échoue (le message a déjà été montré au vendeur ; on prévient de l'échec).
  const openWhatsApp = async () => {
    if (!waTarget) return
    // VX222 — mode relance : le lien wa.me porte un message de RAPPEL ; sinon,
    // le lien d'aperçu initial (QX22) inchangé.
    if (relanceMode) {
      const rUrl = buildRelanceWaUrl(waData, waTarget.reference)
      if (rUrl) window.open(rUrl, '_blank', 'noopener')
    } else if (waData?.wa_url) window.open(waData.wa_url, '_blank', 'noopener')
    setWaSending(true)
    try {
      // GAMMES — le mode d'envoi choisi part AVEC l'envoi (le backend l'écrit
      // sur les deux gammes). Omis quand le devis n'appartient à aucune paire.
      await ventesApi.whatsappDevis(
        waTarget.id,
        waData?.gamme ? { gamme_envoi: waGammeEnvoi } : {},
      )
      // VX222 — consigne la relance au chatter du devis (DevisActivity, VX97) ;
      // best-effort, ne bloque jamais l'ouverture WhatsApp déjà effectuée.
      if (relanceMode) {
        ventesApi.noterDevis(
          waTarget.id, `Relance du devis ${waTarget.reference} envoyée par WhatsApp.`,
        ).catch(() => {})
      }
      dispatch(rafraichirDevis(waTarget.id))
    } catch (err) {
      toast.error(frenchError(err, 'Le marquage « Envoyé » a échoué — vérifiez le devis.'))
    } finally {
      setWaSending(false)
      closeWaModal()
    }
  }

  // QJ28 — « Contacter mon supérieur » : notifie le supérieur du vendeur
  // (in-app + canaux configurés) avec un lien vers ce devis. Manuel, jamais
  // automatique — un clic = une notification.
  const [superieurBusyId, setSuperieurBusyId] = useState(null)
  // VX215 — boucle de retour « pris en charge » : { [devisId]: { requested,
  // seen, seen_by } }, sondée (VX56 useVisibilityAwarePolling) tant qu'une
  // demande reste non vue — jamais de polling une fois « vu ».
  const [superieurStatus, setSuperieurStatus] = useState({})
  const refreshSuperieurStatus = async (devisId) => {
    try {
      const res = await ventesApi.superiorContactStatus(devisId)
      setSuperieurStatus((prev) => ({ ...prev, [devisId]: res.data }))
    } catch {
      // Best-effort — un sondage manqué n'affiche simplement rien de nouveau.
    }
  }
  const pendingSuperieurIds = useMemo(
    () => Object.entries(superieurStatus)
      .filter(([, s]) => s?.requested && !s.seen)
      .map(([id]) => id),
    [superieurStatus],
  )
  useVisibilityAwarePolling(
    [{ fn: () => pendingSuperieurIds.forEach(refreshSuperieurStatus), intervalMs: 20000 }],
    { enabled: pendingSuperieurIds.length > 0 },
  )
  const handleContacterSuperieur = async (d) => {
    setSuperieurBusyId(d.id)
    try {
      await ventesApi.contacterSuperieur(d.id)
      toast.success('Votre supérieur a été notifié.')
      refreshSuperieurStatus(d.id)
    } catch (err) {
      toast.error(frenchError(err, 'Notification du supérieur impossible.'))
    } finally {
      setSuperieurBusyId(null)
    }
  }

  return {
    emailTarget,
    emailAddress,
    setEmailAddress,
    emailBusy,
    openEmailModal,
    closeEmailModal,
    submitEmail,
    copierLienInterne,
    shareBusyId,
    handleCopierApercuInterne,
    handleCopierLienProposition,
    waTarget,
    waData,
    waSending,
    relanceMode,
    waGammeEnvoi,
    setWaGammeEnvoi,
    handleEnvoyer,
    handleRelancer,
    closeWaModal,
    openWhatsApp,
    superieurBusyId,
    superieurStatus,
    handleContacterSuperieur,
  }
}
