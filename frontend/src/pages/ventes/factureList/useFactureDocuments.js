// VNT102 — documents de la liste des factures (génération / téléchargement du PDF,
// aperçu inline, WhatsApp, UBL, lien de paiement, export DGI, historique), déplacés
// tels quels (move only) depuis FactureList.jsx. Le PDF facture reste le PDF LEGACY
// (règle #4 : seul le PDF de devis passe par `/proposal`).
import { useCallback, useEffect, useState } from 'react'
import { fetchFactures, genererPdfFacture } from '../../../features/ventes/store/ventesSlice'
import ventesApi from '../../../api/ventesApi'
import parametresApi from '../../../api/parametresApi'
import api from '../../../api/axios'
import { frenchError } from '../../../lib/frenchError'
import { toast } from '../../../ui'
import { formatMAD } from '../../../lib/format'
import { openPdfBlob, openPdfInGesture } from '../../../utils/pdfBlob'
import { preparerApercuWhatsApp } from '../whatsappFacture'

export default function useFactureDocuments({ dispatch }) {
  const [pdfGenerating, setPdfGenerating] = useState({})
  const [pdfDownloading, setPdfDownloading] = useState({})
  // ── Envoi WhatsApp : busy par facture (L857), langue (L851), aperçu (L852) ──
  const [waBusy, setWaBusy] = useState({})
  const [waLangue, setWaLangue] = useState('fr')
  const [waPreview, setWaPreview] = useState(null) // { reference, message, url, wa_url }

  // WR2b — interrupteur société « export DGI » (lu une fois au montage) :
  // n'affiche le bouton/badge DGI que quand la société l'a activé (défaut OFF,
  // capacité invisible sinon — même garde que côté serveur).
  const [dgiActif, setDgiActif] = useState(false)
  useEffect(() => {
    parametresApi.getProfile()
      .then(res => setDgiActif(!!res.data?.dgi_export_actif))
      .catch(() => setDgiActif(false))
  }, [])
  const [dgiBusy, setDgiBusy] = useState({})
  const [payLinkBusy, setPayLinkBusy] = useState({})

  // VX97 — Panneau « Historique » repliable dans le détail facture : journal des
  // changements (FactureActivity) — qui/quand/ancien→nouveau — sur le document
  // au plus gros blast-radius financier. Feed existant monté ; migrera vers
  // ChatterTimeline (VX23). `prix_achat` jamais rendu (le journal ne le porte pas).
  const [histoOpenId, setHistoOpenId] = useState(null)
  const [histoCache, setHistoCache] = useState({})   // id → entrées
  const [histoLoadingId, setHistoLoadingId] = useState(null)
  const toggleHistorique = (id) => {
    if (histoOpenId === id) { setHistoOpenId(null); return }
    setHistoOpenId(id)
    if (histoCache[id] === undefined) {
      setHistoLoadingId(id)
      api.get(`/ventes/factures/${id}/historique/`)
        .then(res => setHistoCache(c => ({ ...c, [id]: res.data || [] })))
        .catch(() => setHistoCache(c => ({ ...c, [id]: [] })))
        .finally(() => setHistoLoadingId(l => (l === id ? null : l)))
    }
  }

  const handleGenererPdf = async (f) => {
    setPdfGenerating(prev => ({ ...prev, [f.id]: true }))
    try {
      await dispatch(genererPdfFacture(f.id)).unwrap()
      let attempts = 0
      let erreurSignalee = false
      const poll = async () => {
        if (attempts++ > 15) {
          toast.error('La génération PDF prend plus de temps que prévu. Réessayez dans quelques instants.')
          return
        }
        try {
          const res = await ventesApi.getFacture(f.id)
          if (res.data.fichier_pdf) {
            dispatch(fetchFactures())
          } else {
            setTimeout(poll, 2000)
          }
        } catch (err) {
          // Une erreur de sondage transitoire n'arrête pas la boucle, mais la
          // raison du serveur est affichée (une seule fois, pas à chaque tick).
          if (!erreurSignalee) {
            erreurSignalee = true
            toast.error(frenchError(err, 'Suivi de la génération du PDF impossible, nouvelle tentative en cours.'))
          }
          setTimeout(poll, 2000)
        }
      }
      setTimeout(poll, 2000)
    } catch (err) {
      toast.error(err?.detail ?? 'Erreur lors de la génération PDF.')
    } finally {
      setPdfGenerating(prev => ({ ...prev, [f.id]: false }))
    }
  }

  const handleTelechargerPdf = async (f) => {
    setPdfDownloading(prev => ({ ...prev, [f.id]: true }))
    try {
      const res = await ventesApi.telechargerPdfFacture(f.id)
      openPdfBlob(res.data, `${f.reference}.pdf`)
    } catch {
      toast.error('Fichier introuvable. Régénérez le PDF.')
    } finally {
      setPdfDownloading(prev => ({ ...prev, [f.id]: false }))
    }
  }

  // APX14 — aperçu INLINE de la facture : le PDF s'ouvre dans un panneau, plus
  // dans un onglet qu'il faut quitter. La source reste le PDF LEGACY propre
  // aux factures (règle #4 — seul le PDF de DEVIS passe par `/proposal` ;
  // aucun chemin nouveau n'est créé ici).
  const [previewFacture, setPreviewFacture] = useState(null)
  const openPreview = (f) => setPreviewFacture(f)

  const fetchFacturePreviewBlob = useCallback(async () => {
    const f = previewFacture
    if (!f) return null
    try {
      const res = await ventesApi.telechargerPdfFacture(f.id)
      return res.data instanceof Blob ? res.data : new Blob([res.data], { type: 'application/pdf' })
    } catch {
      throw new Error('Fichier introuvable. Régénérez le PDF.')
    }
  }, [previewFacture])

  // Envoyer par WhatsApp : construit le message côté serveur (FR/Darija) puis
  // montre un aperçu (message + lien public) avant d'ouvrir wa.me ; le
  // commercial appuie lui-même sur Envoyer. Le POST consigne aussi l'action au
  // chatter de la facture (côté serveur, L856).
  const handleWhatsApp = (f, modele = 'facture') => preparerApercuWhatsApp({
    facture: f, params: { modele, langue: waLangue },
    setWaBusy, setWaPreview, notifier: toast,
  })

  // Ouvre wa.me après confirmation de l'aperçu.
  // VX48 — exclu volontairement : ce window.open() n'est précédé d'AUCUN await
  // (il tourne synchrone dans le clic du bouton « Envoyer » de la modale), donc
  // hors du bug Safari iOS (qui ne bloque qu'un window.open post-await). Ce
  // n'est de toute façon pas un PDF (lien wa.me).
  const ouvrirWhatsApp = () => {
    if (waPreview?.wa_url) window.open(waPreview.wa_url, '_blank', 'noopener')
    setWaPreview(null)
  }

  // N38 — télécharge l'aperçu BROUILLON UBL 2.1 (XML) de la facture.
  const handleUbl = async (f) => {
    try {
      const res = await ventesApi.telechargerUbl(f.id)
      openPdfBlob(res.data, `${f.reference}-ubl.xml`)
    } catch {
      toast.error("Génération de l'aperçu UBL impossible.")
    }
  }

  // copie au presse-papier (aucun envoi automatique au client).
  // VX48 — le repli window.open (quand le presse-papier est indisponible) suit
  // un await : onglet pré-ouvert SYNCHRONE (pas un PDF, donc `.win.location`
  // direct plutôt que `openPdfInGesture().deliver()` qui attend un Blob).
  const handleLienPaiement = async (f) => {
    setPayLinkBusy(prev => ({ ...prev, [f.id]: true }))
    const pending = openPdfInGesture()
    try {
      const { data } = await ventesApi.lienPaiementFacture(f.id)
      const url = data?.pay_url ?? ''
      if (url && navigator.clipboard?.writeText) {
        pending.win?.close?.()
        await navigator.clipboard.writeText(url)
        // AFAC26 — le montant annoncé est CE QUE LE CLIENT PAIERA (reste exigible), jamais le `montant` figé.
        toast.success(`Lien de paiement copié — ${formatMAD(data.montant_a_payer ?? data.montant)}.`)
      } else if (url) {
        if (pending.win && !pending.win.closed) {
          pending.win.location = url
        } else {
          toast.error('Ouverture bloquée par le navigateur.', {
            action: { label: 'Ouvrir', onClick: () => window.open(url, '_blank', 'noopener') },
          })
        }
      } else {
        pending.win?.close?.()
        toast.error('Lien de paiement indisponible.')
      }
    } catch (err) {
      pending.win?.close?.()
      toast.error(err?.response?.data?.detail ?? 'Création du lien de paiement impossible.')
    } finally {
      setPayLinkBusy(prev => ({ ...prev, [f.id]: false }))
    }
  }

  // N105/WR2b — export DGI (UBL local) : téléchargement direct, aucune transmission.
  const handleDgiExport = async (f) => {
    setDgiBusy(prev => ({ ...prev, [f.id]: true }))
    try {
      const res = await ventesApi.dgiExportFacture(f.id)
      openPdfBlob(res.data, `${f.reference}-dgi.xml`)
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Export DGI impossible.')
    } finally {
      setDgiBusy(prev => ({ ...prev, [f.id]: false }))
    }
  }

  // N105/WR2b — contrôle de conformité DGI à la demande (aucun statut modifié).
  const handleDgiConformite = async (f) => {
    setDgiBusy(prev => ({ ...prev, [f.id]: true }))
    try {
      const { data } = await ventesApi.dgiConformiteFacture(f.id)
      if (data.conforme) {
        toast.success('Conforme DGI : aucun problème détecté.')
      } else {
        toast.error(`Non conforme DGI :\n\n- ${(data.problemes || []).join('\n- ')}`)
      }
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Contrôle de conformité DGI impossible.')
    } finally {
      setDgiBusy(prev => ({ ...prev, [f.id]: false }))
    }
  }

  return {
    pdfGenerating, pdfDownloading, handleGenererPdf, handleTelechargerPdf,
    previewFacture, setPreviewFacture, openPreview, fetchFacturePreviewBlob,
    waBusy, waLangue, setWaLangue, waPreview, setWaPreview, handleWhatsApp, ouvrirWhatsApp,
    handleUbl, payLinkBusy, handleLienPaiement,
    dgiActif, dgiBusy, handleDgiExport, handleDgiConformite,
    histoOpenId, histoCache, histoLoadingId, toggleHistorique,
  }
}
