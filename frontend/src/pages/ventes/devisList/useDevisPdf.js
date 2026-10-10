// SPL204 — flux PDF de la liste des devis (dialogue de format, génération +
// sondage, aperçu inline, téléchargement, partage, proforma, BC), déplacé
// VERBATIM de DevisList.jsx (move only). Règle #4 : /proposal reste le SEUL
// chemin de PDF client — ce hook ne fait que l'appeler, il n'écrit aucun statut
// (le marquage « envoyé » du partage est fait par le serveur, garde T17).
// Le nettoyage WIR217 (minuteurs de sondage annulés au démontage) vit ici, avec
// le seul effet sensible au démontage.
import { useCallback, useEffect, useRef, useState } from 'react'
import { rafraichirDevis, genererPdfDevis } from '../../../features/ventes/store/ventesSlice.js'
import ventesApi from '../../../api/ventesApi.js'
import { toast } from '../../../ui/index.js'
import { filenameFromResponse } from '../../../utils/downloadBlob.js'
import { openPdfBlob } from '../../../utils/pdfBlob.js'
import { proposalParams, pdfBlob } from '../../../features/ventes/previewPdf.js'
// QJR624 — l'acompte personnalisé du dialogue PDF s'écrit dans l'échéancier.
import parametresApi from '../../../api/parametresApi.js'
import { echeancierAvecAcompte } from '../../../features/ventes/echeancierEdition.js'
// Incident fondateur 01/09 (round 2) — le moteur premium REFUSE 'full' quand
// AUCUNE ligne du devis ne porte un onduleur classifié : mêmes prédicats que la
// garde de DevisGenerator.validate() (voir devisSansOnduleurClasse).
import { isReseauInverter, isHybridInverter, isOffgridInverter, texteClassement } from '../../../features/ventes/solar.js'
import { frenchError } from './devisListHelpers.js'

// Les options PDF envoyées à `generer-pdf` (whitelist `clean_pdf_options`)
// depuis l'état de la modale — fonction PURE (testable sans React).
export function optionsPdfDepuisModale({
  pdfMode, showMonthly, devisFinal, includeEtude, includeCalepinage,
  includeNoteCalcul,
}, d) {
  const options = {
    pdf_mode: pdfMode,
    show_monthly: showMonthly,
    devis_final: devisFinal,
    // T12/T13 — étude uniquement si premium ET données d'étude présentes.
    include_etude: pdfMode === 'full' && includeEtude
      && !(d?.mode_installation === 'commercial' || d?.mode_installation === 'industriel')
      && !!(d?.etude_params && Object.keys(d.etude_params).length > 0),
    // CAL184 — tri-état envoyé TEL QUEL à la whitelist `clean_pdf_options` :
    // `null` = auto (le serveur ajoute la planche si le devis en porte une),
    // `true`/`false` = le commercial tranche et sa valeur prime sur l'auto.
    include_calepinage: includeCalepinage === 'auto'
      ? null : includeCalepinage === 'oui',
  }
  // AMOT68 — annexe « Note de calcul » (dossier FDA, AGR319) : agricole SEUL,
  // document complet seul ; la clé n'est posée que pour un devis agricole
  // (tout autre corps reste byte-identique).
  if (d?.mode_installation === 'agricole') {
    options.include_note_calcul = pdfMode === 'full' && !!includeNoteCalcul
  }
  return options
}

// `selectedIds` / `setSelectedIds` (sélection du lot) et `devis` restent dans
// le composant principal : le lot les lit ici.
export function useDevisPdf({ dispatch, devis, selectedIds, setSelectedIds }) {
  const [pdfGenerating, setPdfGenerating] = useState({}) // id → true
  // QX21 — au-delà de 30 s, la génération n'est PAS abandonnée : elle reste
  // visible comme « toujours en cours » (le job Celery continue côté serveur)
  // et le polling se poursuit à un rythme plus espacé, sans jamais relancer un
  // second job (un seul dispatch(genererPdfDevis) par appel de genererUnPdf).
  const [pdfSlowPoll, setPdfSlowPoll] = useState({}) // id → true
  // WIR217 — les minuteries de sondage PDF, et le drapeau d'annulation. Sans
  // eux, quitter l'écran pendant une génération laissait la boucle vivante :
  // elle continuait d'appeler l'API et de poser du state sur un composant
  // démonté, indéfiniment. `clearTimeout` au démontage + garde en tête de
  // boucle (une requête peut être en vol au moment du démontage).
  const pollTimers = useRef({}) // id → handle de setTimeout
  const pollAnnule = useRef(false)
  useEffect(() => {
    pollAnnule.current = false
    const timers = pollTimers.current
    return () => {
      pollAnnule.current = true
      Object.values(timers).forEach(clearTimeout)
      pollTimers.current = {}
    }
  }, [])
  const [pdfDownloading, setPdfDownloading] = useState({}) // id → true
  // APX14 — le devis dont l'aperçu inline est ouvert (null = panneau fermé).
  // `previewingId` en dérive pour que le libellé « Aperçu du PDF… » de la
  // ligne reste exactement celui d'avant.
  const [previewDevis, setPreviewDevis] = useState(null)
  const previewingId = previewDevis?.id ?? null

  const [batchPdf, setBatchPdf] = useState(false) // la modale PDF vise le lot

  // ── Choix du format PDF (parité simulateur) ──
  const [pdfTarget, setPdfTarget] = useState(null) // devis ciblé par la modale
  const [pdfMode, setPdfMode] = useState('full')
  const [showMonthly, setShowMonthly] = useState(true)
  const [devisFinal, setDevisFinal] = useState(false)
  const [paymentMode, setPaymentMode] = useState('standard')
  const [customAcompte, setCustomAcompte] = useState('')
  const [includeEtude, setIncludeEtude] = useState(false)
  // CAL184 — page « Calepinage » (planche cotée, CAL182). TRI-ÉTAT, et le
  // défaut est 'auto' : l'écran n'invente AUCUNE valeur. C'est le serveur qui
  // sait si ce devis porte un calepinage dessinable — la liste, elle, ne le
  // sait pas (la clé `calepinage` de la fiche devis n'est calculée qu'en
  // DÉTAIL, pour ne pas faire de la liste un N+1). Dire « oui » ou « non » ici
  // serait donc une supposition ; 'auto' laisse décider celui qui sait.
  const [includeCalepinage, setIncludeCalepinage] = useState('auto')
  // AMOT68 — « Joindre la note de calcul (dossier FDA) » : agricole seul.
  const [includeNoteCalcul, setIncludeNoteCalcul] = useState(false)
  // Incident fondateur 01/09 round 2 — préselection gracieuse (voir import
  // solar.js ci-dessus) : posé UNIQUEMENT quand l'ouverture de la modale a dû
  // rabattre 'full' sur 'onepage' faute d'onduleur classifié sur les lignes.
  const [pdfModeAutoOnepage, setPdfModeAutoOnepage] = useState(false)

  // T13 — la case « Inclure l'étude » n'a de sens qu'avec des données d'étude.
  const targetHasEtude = !!(pdfTarget?.etude_params
    && Object.keys(pdfTarget.etude_params).length > 0)
  // T14 — le format premium « full » n'est pas pertinent pour le pompage agricole.
  const targetIsAgricole = pdfTarget?.mode_installation === 'agricole'
  // CIQ325 — le C&I a son document (3 pages commercial, 4 pages industriel,
  // étude intégrée) : ni case « Inclure l'étude » ni « Économies mensuelles ».
  const targetMode = pdfTarget?.mode_installation
  const targetIsCi = targetMode === 'commercial' || targetMode === 'industriel'

  // Incident fondateur 01/09 round 2 — un devis « Composition libre » (ou tout
  // devis dont aucune ligne ne classe onduleur réseau/hybride/hors réseau)
  // fait REFUSER pdf_mode 'full' par le moteur (règle dure builder.py,
  // ~ligne 1176) : agricole/pompage est DÉJÀ dégradé sans erreur côté serveur
  // (aucun onduleur n'y est jamais attendu), donc seul le cas non-agricole est
  // concerné ici.
  const devisSansOnduleurClasse = (d) =>
    d?.mode_installation !== 'agricole'
    // AGNR36 — désignation + nom du produit servi sur la ligne (`produit_nom`).
    && !(d?.lignes ?? []).some((l) => {
      const t = texteClassement(l)
      return isReseauInverter(t) || isHybridInverter(t) || isOffgridInverter(t)
    })

  const openPdfModal = (d) => {
    setBatchPdf(false)
    setPdfTarget(d)
    // AGR315 — l'agricole a son document complet de 3 pages (renderer
    // agricole, AGR312) : défaut « full », jamais rabattu sur une page faute
    // d'onduleur (un kit de pompage n'en a pas). Un autre devis sans onduleur
    // classé (Composition libre) part directement sur 'onepage' — jamais le
    // refus 400 que l'utilisateur découvrirait sinon après « Générer ».
    const sansOnduleur = d?.mode_installation !== 'agricole'
      && devisSansOnduleurClasse(d)
    setPdfMode(sansOnduleur ? 'onepage' : 'full')
    setPdfModeAutoOnepage(sansOnduleur)
    setShowMonthly(true)
    setDevisFinal(false)
    setPaymentMode('standard')
    setCustomAcompte('')
    // CIQ325 — plus de pré-coche « Inclure l'étude » : cochée pour un
    // industriel, elle envoyait le rendu au moteur legacy alors que le lien du
    // client reçoit le premium. L'étude C&I est intégrée au document.
    setIncludeEtude(false)
    setIncludeCalepinage('auto')
    setIncludeNoteCalcul(false)
  }

  // Ouvre la modale PDF pour le lot sélectionné (format partagé).
  const openBatchPdfModal = () => {
    setBatchPdf(true)
    setPdfTarget(null)
    setPdfMode('full')
    setPdfModeAutoOnepage(false)
    setShowMonthly(true)
    setDevisFinal(false)
    setPaymentMode('standard')
    setCustomAcompte('')
    setIncludeEtude(false)
    setIncludeCalepinage('auto')
    setIncludeNoteCalcul(false)
  }

  // T10 — Aperçu PDF en application : récupère le blob /proposal et l'ouvre dans
  // un nouvel onglet (mêmes params que la modale d'aperçu de la fiche lead).
  // VX48 — l'onglet est pré-ouvert SYNCHRONE dans le geste (avant l'await),
  // sinon Safari iOS bloque silencieusement le window.open post-await.
  // APX14 — « Aperçu » ne QUITTE plus l'écran : il ouvre le panneau inline
  // (PdfCanvas, déjà consommé par 4 autres écrans, jamais par celui-ci).
  // La SOURCE reste le moteur vendorisé `/proposal` — aucun chemin PDF
  // nouveau, aucun changement de statut (règle #4). Télécharger et Ouvrir
  // dans un onglet restent offerts DANS le panneau, en repli.
  const handlePreview = (d) => { setPreviewDevis(d) }

  // Récupère les octets du PDF de proposition du devis en aperçu. Passée au
  // panneau, qui ne connaît aucune URL. Le message d'erreur reste celui,
  // français, que la liste sait déjà produire (T11 — moteur sans onduleur).
  const fetchDevisPreviewBlob = useCallback(async () => {
    const d = previewDevis
    if (!d) return null
    try {
      // CIQ325 — jamais d'`include_etude` : l'aperçu rend le MÊME premium que
      // le lien du client (aucun détour par le moteur legacy).
      const params = proposalParams('full', false)
      const res = await ventesApi.getProposalPdf(d.id, params)
      return pdfBlob(res.data)
    } catch (err) {
      const msg = frenchError(err, '')
      if (/onduleur|inverter/i.test(msg)) {
        throw new Error('Ce devis n\'a aucun onduleur — choisissez le format une page.')
      }
      throw new Error(msg || 'Aperçu du PDF indisponible.')
    }
  }, [previewDevis])

  // Construit les options PDF depuis l'état de la modale (partagé une page / lot).
  const buildPdfOptions = (d) => optionsPdfDepuisModale({
    pdfMode, showMonthly, devisFinal, includeEtude, includeCalepinage,
    includeNoteCalcul,
  }, d)

  // QG1 — Lance la génération d'un PDF + polling silencieux jusqu'à fichier
  // prêt. Le PDF s'ouvre/télécharge AUTOMATIQUEMENT dès qu'il est prêt (plus
  // besoin d'un second clic sur le bouton vert, qui reste disponible pour
  // re-télécharger). Renvoie une promesse résolue quand la génération est
  // acceptée (pas attendue jusqu'au fichier final), pour permettre
  // l'enchaînement par lot.
  const genererUnPdf = async (d, { autoOpen = true } = {}) => {
    setPdfGenerating(prev => ({ ...prev, [d.id]: true }))
    setPdfSlowPoll(prev => ({ ...prev, [d.id]: false }))
    try {
      // QJR624 (D-QJR5-10) — l'« acompte personnalisé » n'est plus une option
      // de rendu : il est ÉCRIT dans l'échéancier du devis AVANT le rendu
      // (facture d'acompte et PDF lisent la même valeur ; sur un envoyé, la
      // correction est tracée par le serveur). Un refus (devis figé) arrête
      // la génération avec le message du serveur.
      if (devisFinal && paymentMode === 'custom' && customAcompte !== '') {
        // CIQ225 — sans échéancier propre, le point de départ vient des jalons
        // EFFECTIFS de la société (plus de pourcentages recopiés en JS).
        let effectifs = null
        if (!(d.echeancier || []).length) {
          try {
            effectifs = (await parametresApi.getProfile())?.data?.payment_terms_effectifs || null
          } catch { /* profil indisponible : libellés seuls, valeurs vides */ }
        }
        await ventesApi.patchDevis(d.id, {
          echeancier: echeancierAvecAcompte(
            d.echeancier, customAcompte, d.total_ttc, d.mode_installation, effectifs),
        })
      }
      await dispatch(genererPdfDevis({ id: d.id, options: buildPdfOptions(d) })).unwrap()
      let attempts = 0
      // WIR217 — le drapeau « lent » était lu dans `pdfSlowPoll[d.id]`, une
      // CLÔTURE PÉRIMÉE figée à `false` à la création de la boucle : la
      // condition restait vraie et le toast « toujours en cours » repartait
      // TOUTES LES 10 s. Un booléen LOCAL à cette boucle le dit UNE fois.
      let slowAnnonce = false
      // QX21 — 15 tentatives × 2 s = 30 s au rythme rapide ; passé ce cap, le
      // job Celery n'est PAS relancé (un seul dispatch a eu lieu ci-dessus) —
      // on continue simplement à interroger, plus espacé (10 s), et on affiche
      // « toujours en cours » au lieu d'abandonner silencieusement.
      const FAST_ATTEMPTS = 15
      const poll = async () => {
        // WIR217 — plus AUCUN sondage après démontage de l'écran.
        if (pollAnnule.current) return
        const slow = attempts >= FAST_ATTEMPTS
        attempts += 1
        if (slow && !slowAnnonce) {
          slowAnnonce = true
          setPdfSlowPoll(prev => ({ ...prev, [d.id]: true }))
          if (autoOpen) {
            toast(`${d.reference} : le PDF est toujours en cours de génération — la page continue de vérifier automatiquement.`)
          }
        }
        try {
          // WIR217 — on lit l'ÉTAT du rendu (contrat
          // apps/ventes/contract_samples/devis_etat_pdf.json), pas seulement
          // `fichier_pdf` : un échec DÉFINITIF de la tâche Celery (retries
          // épuisés) était invisible et cette boucle ne s'arrêtait jamais.
          const res = await ventesApi.etatPdfDevis(d.id)
          if (res.data.statut === 'echec') {
            // État TERMINAL : on arrête le sondage et on rend l'échec
            // ACTIONNABLE (le message du serveur nomme la cause).
            setPdfSlowPoll(prev => ({ ...prev, [d.id]: false }))
            toast.error(
              `${d.reference} : la génération du PDF a échoué${res.data.erreur ? ` — ${res.data.erreur}` : '.'}`,
              { action: { label: 'Réessayer', onClick: () => genererUnPdf(d, { autoOpen }) } },
            )
            return
          }
          if (res.data.fichier_pdf) {
            dispatch(rafraichirDevis(d.id))
            setPdfSlowPoll(prev => ({ ...prev, [d.id]: false }))
            if (autoOpen) {
              // VX48 — l'auto-open existant (QG1) reste l'expérience PAR
              // DÉFAUT et se déclenche EN PREMIER ; on n'affiche le toast
              // d'action « Ouvrir » (tap = geste frais, seul geste que
              // Safari iOS honore après ce polling asynchrone) que si le
              // téléchargement/l'ouverture automatique échoue.
              try {
                const pdfRes = await ventesApi.telechargerPdfDevis(d.id)
                openPdfBlob(pdfRes.data, filenameFromResponse(pdfRes, `${d.reference}.pdf`))
              } catch {
                toast.error(`${d.reference} : PDF prêt — l'ouverture automatique a échoué.`, {
                  action: {
                    label: 'Ouvrir',
                    onClick: async () => {
                      try {
                        const pdfRes = await ventesApi.telechargerPdfDevis(d.id)
                        openPdfBlob(pdfRes.data, filenameFromResponse(pdfRes, `${d.reference}.pdf`))
                      } catch {
                        toast.error(`${d.reference} : PDF indisponible — utilisez le bouton de téléchargement.`)
                      }
                    },
                  },
                })
              }
            }
          } else {
            pollTimers.current[d.id] = setTimeout(poll, slow ? 10000 : 2000)
          }
        } catch { /* ignore poll errors — la boucle continue */ }
      }
      pollTimers.current[d.id] = setTimeout(poll, 2000)
      return true
    } catch (err) {
      // T11 — surface claire de l'absence d'onduleur (ValueError moteur premium).
      const msg = frenchError(err, '')
      if (/onduleur|inverter/i.test(msg)) {
        toast.error(`${d.reference} : ce devis n'a aucun onduleur — choisissez le format une page.`)
      } else {
        toast.error(`${d.reference} : ${msg || 'erreur lors de la génération PDF.'}`)
      }
      return false
    } finally {
      setPdfGenerating(prev => ({ ...prev, [d.id]: false }))
    }
  }

  const handleGenererPdf = async (d) => {
    setPdfTarget(null)
    await genererUnPdf(d)
  }

  // T7 — Génération PDF par lot : même format pour tous les devis sélectionnés.
  // QG1 — pas d'ouverture automatique par lot (N devis => N ouvertures serait
  // intrusif) : chacun reste téléchargeable via son bouton vert une fois prêt.
  const handleGenererPdfLot = async () => {
    const cibles = devis.filter(d => selectedIds.includes(d.id))
    setBatchPdf(false)
    let ok = 0
    for (const d of cibles) {
      if (await genererUnPdf(d, { autoOpen: false })) ok += 1
    }
    if (ok > 0) toast.success(`Génération lancée pour ${ok} devis.`)
    setSelectedIds([])
  }

  // WIR103/XFAC10 — Proforma PDF : document sans aucun impact comptable
  // (jamais une facture, jamais une écriture). Le backend était complet et
  // testé mais n'avait AUCUN appelant côté client. Le POST renvoie le PDF.
  const handleProformaPdf = async (d) => {
    try {
      const res = await ventesApi.getProformaPdf(d.id)
      openPdfBlob(res.data, `Proforma_${d.reference}.pdf`)
    } catch {
      toast.error('Proforma indisponible.')
    }
  }

  // ZSAL8 — PDF du bon de commande lié (endpoint GET .../pdf/ backend
  // complet, jamais appelé côté client).
  const handleBonCommandePdf = async (d) => {
    const bcId = d.bon_commande_etat?.id
    if (!bcId) return
    try {
      const res = await ventesApi.getBonCommandePdf(bcId)
      openPdfBlob(res.data, filenameFromResponse(res, `${d.bon_commande_etat.reference}.pdf`))
    } catch {
      toast.error('PDF du bon de commande indisponible.')
    }
  }

  const handleTelechargerPdf = async (d) => {
    setPdfDownloading(prev => ({ ...prev, [d.id]: true }))
    try {
      const res = await ventesApi.telechargerPdfDevis(d.id)
      // QD2 — nom cohérent posé par le serveur (repli sur la référence).
      openPdfBlob(res.data, filenameFromResponse(res, `${d.reference}.pdf`))
    } catch {
      toast.error('Fichier introuvable. Régénérez le PDF.')
    } finally {
      setPdfDownloading(prev => ({ ...prev, [d.id]: false }))
    }
  }

  // VX44 — « Partager le PDF » : quand la Web Share API accepte les fichiers
  // (iOS 15+, Android Chrome), le PDF du devis part directement dans la feuille
  // de partage native (WhatsApp, e-mail…) ; sinon repli propre sur le
  // téléchargement. Aucun nouveau chemin PDF — c'est le PDF existant du devis
  // (règle #4 : le rendu /proposal n'est pas touché).
  const handlePartagerPdf = async (d) => {
    setPdfDownloading(prev => ({ ...prev, [d.id]: true }))
    try {
      const res = await ventesApi.telechargerPdfDevis(d.id)
      const filename = filenameFromResponse(res, `${d.reference}.pdf`)
      const file = new File([res.data], filename, { type: 'application/pdf' })
      const shareData = { files: [file], title: `Devis ${d.reference}` }
      if (navigator.canShare?.(shareData) && navigator.share) {
        let partage = false
        try {
          await navigator.share(shareData)
          partage = true
        } catch (err) {
          // L'utilisateur a annulé la feuille de partage : ne rien signaler.
          if (err?.name !== 'AbortError') {
            openPdfBlob(res.data, filename)
          }
        }
        // QJR659 (décision fondateur 01/10) — partage RÉSOLU = envoi (comme
        // copier le lien, D-QJR5-3) ; jamais sur AbortError ni sur le repli
        // téléchargement. Le serveur passe la garde de remise T17 puis
        // mark_devis_sent (idempotent, ne régresse jamais un devis avancé).
        if (partage && d.statut === 'brouillon') {
          try {
            await ventesApi.partagePdfDevis(d.id)
            dispatch(rafraichirDevis(d.id))
            toast.success('PDF partagé — devis marqué envoyé.')
          } catch (err) {
            toast.error(frenchError(err, 'PDF partagé, mais le devis n\'a pas pu être marqué envoyé.'))
          }
        }
      } else {
        // Pas de partage natif de fichiers : repli sur le téléchargement.
        openPdfBlob(res.data, filename)
      }
    } catch {
      toast.error('Fichier introuvable. Régénérez le PDF.')
    } finally {
      setPdfDownloading(prev => ({ ...prev, [d.id]: false }))
    }
  }

  return {
    pdfGenerating,
    pdfSlowPoll,
    pdfDownloading,
    previewDevis,
    setPreviewDevis,
    previewingId,
    batchPdf,
    setBatchPdf,
    pdfTarget,
    setPdfTarget,
    pdfMode,
    setPdfMode,
    showMonthly,
    setShowMonthly,
    devisFinal,
    setDevisFinal,
    paymentMode,
    setPaymentMode,
    customAcompte,
    setCustomAcompte,
    includeEtude,
    setIncludeEtude,
    includeCalepinage,
    setIncludeCalepinage,
    includeNoteCalcul,
    setIncludeNoteCalcul,
    pdfModeAutoOnepage,
    targetHasEtude,
    targetIsCi,
    targetMode,
    targetIsAgricole,
    openPdfModal,
    openBatchPdfModal,
    handlePreview,
    fetchDevisPreviewBlob,
    genererUnPdf,
    handleGenererPdf,
    handleGenererPdfLot,
    handleProformaPdf,
    handleBonCommandePdf,
    handleTelechargerPdf,
    handlePartagerPdf,
  }
}
