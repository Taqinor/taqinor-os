/* Panneau devis INLINE de la fiche lead (style Odoo : slide-over plein écran
   au-dessus de la fiche). Tout se passe sans quitter le lead : créer (auto ou
   modifiable), voir l'aperçu PDF et le télécharger. On RÉUTILISE le générateur
   existant (DevisGenerator embarqué) et le calcul auto partagé (autoQuote.js) —
   aucune logique de prix ni de PDF dupliquée. Le PDF vient du chemin canonique
   /proposal (CLAUDE.md règle #4). */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Download, ExternalLink, Pencil, Send, Zap,
} from 'lucide-react'
import ventesApi from '../../../api/ventesApi'
import { createAutoQuote, libelleSuccesDevisAuto } from '../../../features/ventes/autoQuote'
import { proposalParams, pdfBlob } from '../../../features/ventes/previewPdf'
import { usePdfPreview } from '../../../features/ventes/usePdfPreview'
import PdfPreviewBody from '../../../features/ventes/PdfPreviewBody'
import DevisGenerator from '../../ventes/DevisGenerator'
import {
  peutEditerDevis, peutReviserDevis, libelleStatutDevis,
} from '../../../features/ventes/devisStatuts'
import { reviserEtOuvrir } from '../../../features/ventes/reviserDevis'
// QJR589 — la bannière de dérive lead → devis (mêmes gestes que l'Édition complète).
import BandeauDeriveLead from '../../../features/ventes/quote/BandeauDeriveLead'
import { downloadBlobInGesture, filenameFromResponse } from '../../../utils/downloadBlob'
import { openPdfInGesture } from '../../../utils/pdfBlob'
import { toast, useConfirmDialog } from '../../../ui/confirm'
// EDC6 (suite) — un « pointeur hors panneau » de Radix est-il un vrai geste de sortie ?
import { estGesteHorsPanneau } from './gesteHorsPanneau'
import { jumpToField } from '../../../features/crm/workspace/jumpToField'
// ALEA52 — la MÊME boîte « Envoyer au client » que la carte devis de l'onglet Devis.
import EnvoiDevisDialog from '../../../features/crm/workspace/EnvoiDevisDialog'
import { useEnvoiDevis } from '../../../features/crm/workspace/useEnvoiDevis'
import { missingFieldTarget } from '../../../features/crm/workspace/missingFields'
import fieldLabels from '../../../features/crm/workspace/fieldLabels'
// AGQ25 — le journal du devis automatique, même rendu que le générateur.
import AlertesDevisAuto from './AlertesDevisAuto'
import {
  Button, Input, Spinner, Segmented, Checkbox, Sheet, SheetContent, StatusPill,
} from '../../../ui'

// L'aperçu PDF vient de usePdfPreview + PdfPreviewBody (le même moteur que
// PdfPreviewSheet) : octets en BLOB via axios — MÊME chemin que « Télécharger »
// —, dessinés par PDF.js sur canvas (jamais un cadre embarqué bloquable), refresh
// silencieux du token rejoué, annulation réelle des rendus longs.

// ALEA55 — la création automatique dure ~30 s (étude, composition, PDF) : au lieu
// d'un cercle muet, trois étapes dont la courante est mise en avant. Le serveur
// ne renvoie qu'UNE réponse : l'avancement est indicatif (minuteur), la dernière
// étape reste active jusqu'au retour.
const ETAPES_CREATION = ['Étude', 'Composition', 'PDF']
const DELAIS_ETAPES_MS = [0, 5000, 14000]

function EtapesCreationDevis() {
  const [courante, setCourante] = useState(0)
  useEffect(() => {
    const minuteurs = DELAIS_ETAPES_MS.map((delai, i) => (
      i === 0 ? null : setTimeout(() => setCourante(i), delai)))
    return () => minuteurs.forEach((m) => m && clearTimeout(m))
  }, [])
  return (
    <div role="status" aria-live="polite" data-testid="ldp-etapes-creation">
      <p className="gen-hint"><Spinner /> Création du devis automatique…</p>
      <ol className="ldp-etapes flex gap-2 text-sm" aria-label="Étapes de la création">
        {ETAPES_CREATION.map((nom, i) => (
          <li key={nom} data-etape={nom} aria-current={i === courante ? 'step' : undefined}
              className={i === courante ? 'font-semibold' : (i < courante ? 'text-muted-foreground' : 'opacity-50')}>
            {i < courante ? '✓ ' : ''}{nom}{i < ETAPES_CREATION.length - 1 ? ' →' : ''}
          </li>
        ))}
      </ol>
    </div>
  )
}

const TITLES = {
  auto: 'Devis automatique',
  remise: 'Devis automatique avec remise',
  onepage: 'Devis 1 page',
  premium: 'Devis premium',
  edit: 'Édition complète du devis',
  view: 'Devis',
}

// EDC1 — largeur du panneau : l'Édition complète prend jusqu'à 1 800 px (la
// table des lignes tient sans défilement horizontal), les autres phases gardent
// 1 500 px. Classes écrites EN ENTIER (Tailwind ne devine pas une chaîne
// recomposée).
const LARGEUR_STANDARD = 'w-[min(1500px,100%)]'
const LARGEUR_EDITION = 'w-[min(1800px,100%)]'

// EZ5 — `targetKwc` : puissance cible (kWc) demandée pour CE devis depuis la
// fiche lead (« Devis automatique »). Optionnelle ; vide = comportement
// historique (taille souhaitée du lead, sinon facture d'hiver). Elle n'écrit
// RIEN sur le lead — c'est un paramètre de dimensionnement ponctuel.
export default function LeadDevisPanel({ lead, mode, onClose, onDevisChanged, existingDevisId = null, targetKwc = null, pdfInitial = null }) {
  const navigate = useNavigate()

  // phase: 'remise-input' | 'creating' | 'chargement' | 'edit' | 'preview' | 'error'
  // EDC8 — un devis EXISTANT demandé en édition ne monte PAS le générateur tout
  // de suite : phase `chargement` (spinner) jusqu'à la lecture du devis, qui
  // décide (modifiable → `edit`, sinon toast + `preview`). Avant, l'éditeur
  // s'ouvrait puis se refermait d'un coup sur un devis figé (flash « ouvre puis
  // referme ») : la garde du générateur n'est plus qu'un second rideau.
  const [phase, setPhase] = useState(
    existingDevisId ? (mode === 'edit' ? 'chargement' : 'preview')
      : mode === 'remise' ? 'remise-input'
        : mode === 'edit' ? 'edit'
          : 'creating')
  // Vrai tant que la lecture qui doit trancher entre `edit` et `preview` n'est
  // pas revenue (une seule décision, jamais rejouée par une relecture).
  const ouvertureEnAttenteRef = useRef(!!existingDevisId && mode === 'edit')
  // EDC11 — l'éditeur a-t-il des modifications NON enregistrées ? Poussé par le
  // générateur (`onDirtyChange`), remis à false à chaque sortie de l'édition et
  // à chaque enregistrement réussi.
  const [dirty, setDirty] = useState(false)
  // EDC11 — enregistrer ne quitte plus l'éditeur : on relit le devis (statut,
  // référence, droits, dérive lead) pour que l'en-tête et l'aperçu ne montrent
  // jamais un `devisRecord` périmé.
  const [rechargeTick, setRechargeTick] = useState(0)
  const { confirm } = useConfirmDialog()
  // Une seule confirmation à la fois (double clic, Échap martelé).
  const confirmationEnCoursRef = useRef(false)
  // EDC6 (suite) — le nœud du panneau, pour distinguer un clic sur le voile
  // d'un clic dans une AUTRE couche Radix (confirmation, dialogue, popover).
  const contenuRef = useRef(null)
  const [discount, setDiscount] = useState('0')
  const [errorMsg, setErrorMsg] = useState(null)
  // ALEA48 — champ du lead nommé par le 409 du devis auto (bouton « Compléter »).
  const [errorField, setErrorField] = useState(null)
  // AGR126 — alertes renvoyées par le serveur avec le devis automatique
  // (agricole : étude pompage, articles « prix à renseigner » omis).
  const [alertes, setAlertes] = useState([])
  // ALEA51 — le retour du serveur après le devis automatique (réf., kWc, TTC,
  // économie, retour, postes à chiffrer) : bannière de SUCCÈS, pas d'erreur.
  const [resume, setResume] = useState(null)
  const [devisId, setDevisId] = useState(existingDevisId || null)
  const [devisRef, setDevisRef] = useState('')
  // QJR534 — le devis CHARGÉ (droits `modifiable` / `revision_possible` lus du
  // serveur, QJR516) : « Édition complète » seulement si modifiable, sinon
  // « Réviser ».
  const [devisRecord, setDevisRecord] = useState(null)
  // EDC8 — plus de `true` par défaut avant la lecture : sur un devis EXISTANT,
  // « Édition complète » n'est rendu qu'une fois `devisRecord` chargé ET
  // modifiable. Seul cas sans devis (échec de la création automatique) :
  // ouvrir l'éditeur = CRÉER un devis à la main, toujours permis.
  const editable = devisId ? peutEditerDevis(devisRecord) : true
  const revisable = !editable && peutReviserDevis(devisRecord)
  const reviser = () => reviserEtOuvrir({
    devis: { ...devisRecord, id: devisId },
    navigate,
    onApres: () => onDevisChanged?.(),
  })

  // ALEA52 — « Envoyer au client » depuis l'aperçu : la même boîte que la carte
  // devis (canaux WhatsApp / e-mail / copier le lien, réglages sous « Avancé »).
  // Un envoi relit la fiche (le devis passe « envoyé », le funnel avance).
  const envoi = useEnvoiDevis({
    leadPhone: (lead.whatsapp || lead.telephone || '').trim(),
    leadEmail: (lead.email || '').trim(),
    leadNom: `${lead.nom ?? ''} ${lead.prenom ?? ''}`.trim(),
    onRefresh: () => onDevisChanged?.(),
    leadId: lead.id,
    relanceActuelle: lead.relance_date ?? null,
  })
  const [envoiOuvert, setEnvoiOuvert] = useState(false)
  // Marché du devis : hors résidentiel, ni options 1/2/3 (boîte d'envoi) ni
  // « Inclure l'étude » (sans effet en commercial / industriel / agricole).
  const marcheDevis = devisRecord?.mode_installation ?? lead.type_installation ?? null
  const marcheHorsResidentiel = !!marcheDevis && marcheDevis !== 'residentiel'
  const devisPourEnvoi = {
    id: devisId,
    reference: devisRef || devisRecord?.reference || `Devis_${devisId}`,
    share_link: (lead.devis || []).find((d) => d.id === devisId)?.share_link ?? null,
  }

  // QJR602 suivi (D-QJR5-13) — une taille explicite est respectée telle
  // quelle : plus d'arrondi au palier de 5 kWc, donc plus d'avis de palier.

  // Format d'aperçu PDF
  // ALEA55 — « 1 page » / « Premium » sont des FORMATS du PDF d'un devis existant
  // (`pdfInitial` : choix fait sur la carte), jamais un second devis.
  const [pdfMode, setPdfMode] = useState(
    mode === 'onepage' || pdfInitial === 'onepage' ? 'onepage' : 'full')
  const [includeEtude, setIncludeEtude] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const startedRef = useRef(false)
  const cleIdempotenceRef = useRef(null) // AGQ23 — une clé par ouverture

  // Octets du PDF : récupérés par usePdfPreview (MÊME source que le
  // téléchargement) ; changer de format ou fermer le panneau avorte le rendu
  // en vol (APXTMO : les rendus à froid ~26 s ne s'empilent pas sur gunicorn).
  const fetchPreviewBlob = useCallback(
    (signal) => ventesApi.getProposalPdf(
      devisId, proposalParams(pdfMode, includeEtude), { signal })
      .then((res) => pdfBlob(res.data)),
    [devisId, pdfMode, includeEtude])
  const preview = usePdfPreview(fetchPreviewBlob, {
    enabled: phase === 'preview' && !!devisId,
  })
  const previewBlob = preview.blob

  // « Réessayer l'aperçu » : on relance fetch + rendu depuis zéro.
  const reloadPreview = () => {
    setErrorMsg(null)
    preview.reload()
  }

  // ALEA48 — même geste que les puces « manquants » de DevisTab : on ferme le
  // panneau (modal) puis `jumpToField` déplie, scrolle et focalise le champ.
  const completerChamp = (champ) => {
    const cible = missingFieldTarget(champ)
    if (!cible) return
    onClose?.()
    setTimeout(() => jumpToField(cible), 0)
  }

  // ── Création auto (auto / onepage / premium : pas de saisie préalable) ──
  const doCreateAuto = async (discountStr) => {
    setPhase('creating')
    setErrorMsg(null)
    setErrorField(null)
    try {
      // ALEA55 — AUCUN préchargement du catalogue ni des gammes avant l'appel :
      // le serveur lit lui-même le catalogue, les marques épinglées (PVMRQ) et
      // l'ordre des lignes de la société (`createAutoQuote` ignorait déjà ces
      // données) — ces deux lectures ne faisaient qu'ajouter des secondes
      // d'attente avant le premier octet du devis.
      setAlertes([])
      setResume(null)
      // AGQ23 (C-AGQ-022) — UNE clé d'idempotence par ouverture du panneau :
      // un 2ᵉ clic (après un délai dépassé) rejoue le 1ᵉʳ devis au serveur.
      if (!cleIdempotenceRef.current) {
        cleIdempotenceRef.current = globalThis.crypto?.randomUUID?.()
          || `auto-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`
      }
      const id = await createAutoQuote({
        lead, discountStr, targetKwc, onAlertes: setAlertes, onResultat: setResume,
        idempotencyKey: cleIdempotenceRef.current,
      })
      setDevisId(id)
      onDevisChanged?.()
      setPhase('preview')
    } catch (err) {
      setErrorMsg(typeof err?.detail === 'string'
        ? err.detail
        : "Le devis automatique a échoué — vérifiez la fiche du lead et réessayez.")
      // AGQ23 — délai dépassé : le devis a pu être créé ; la liste du lead
      // se recharge (le parent relit ses devis).
      if (err?.delaiDepasse) onDevisChanged?.()
      // ALEA48 / AGQ22 — un refus qui NOMME un champ de la fiche (`field` du
      // 409) : le panneau le dit et propose « Compléter : <champ> » (un seul
      // message : le toast global est coupé pour cet appel, `suppressErrorToast`).
      setErrorField(typeof err?.field === 'string' ? err.field : null)
      setPhase('error')
    }
  }

  useEffect(() => {
    if (startedRef.current) return
    // ALEA55 — jamais de création quand le panneau s'ouvre sur un devis EXISTANT.
    if (!existingDevisId && (mode === 'auto' || mode === 'onepage' || mode === 'premium')) {
      startedRef.current = true
      // eslint-disable-next-line react-hooks/set-state-in-effect -- création automatique au montage, une seule fois (startedRef) (D-ENF22)
      doCreateAuto('0')
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps -- création automatique au montage, une seule fois (startedRef); mode/doCreateAuto relancés créeraient un 2e devis (D-ENF22)
  }, [])

  // Référence (pour le nom du fichier) une fois le devis connu. EDC8 — c'est
  // AUSSI cette lecture qui décide d'ouvrir l'éditeur d'un devis existant : le
  // générateur n'est monté qu'ensuite (phase `chargement` d'ici là).
  useEffect(() => {
    if (!devisId) return undefined
    let annule = false
    ventesApi.getDevisById(devisId)
      .then(({ data }) => {
        if (annule) return
        setDevisRef(data.reference || `Devis_${devisId}`)
        setDevisRecord(data)
        if (!ouvertureEnAttenteRef.current) return
        ouvertureEnAttenteRef.current = false
        if (peutEditerDevis(data)) {
          setPhase('edit')
          return
        }
        // Devis figé : on le DIT (la raison vient du serveur) et on montre
        // l'aperçu ; « Réviser » y est offert si le serveur le permet.
        toast.error(data.raison_non_modifiable
          || 'Ce devis ne peut plus être modifié — révisez-le pour créer une nouvelle version.')
        setPhase('preview')
      })
      .catch(() => {
        if (annule) return
        setDevisRef(`Devis_${devisId}`)
        if (!ouvertureEnAttenteRef.current) return
        ouvertureEnAttenteRef.current = false
        setErrorMsg("Ce devis n'a pas pu être ouvert. Vérifiez votre connexion puis réessayez.")
        setPhase('error')
      })
    return () => { annule = true }
  }, [devisId, rechargeTick])

  // EDC11 — UNE confirmation à la fois ; renvoie true si l'ouvrier confirme.
  const demanderConfirmation = async (options) => {
    if (confirmationEnCoursRef.current) return false
    confirmationEnCoursRef.current = true
    try {
      return (await confirm(options)) === true
    } finally {
      confirmationEnCoursRef.current = false
    }
  }

  // CRÉATION embarquée terminée (`onDone`) : le devis existe désormais, on
  // passe à l'aperçu comme avant.
  const onEditDone = (id) => {
    if (id) setDevisId(id)
    setDirty(false)
    onDevisChanged?.()
    setPhase('preview')
  }

  // EDC11 — enregistrement d'un devis EXISTANT (`onEnregistre`) : l'ouvrier
  // RESTE dans l'éditeur. Avant, chaque enregistrement le renvoyait à l'aperçu
  // PDF (réentrer = tout recharger) : le « retour d'un coup au devis ».
  const onEnregistre = (id) => {
    if (id) setDevisId(id)
    // Le drapeau « non enregistré » reste celui du générateur (`onDirtyChange`) :
    // s'il passe à faux après l'écriture, il le dit lui-même ; une frappe faite
    // PENDANT l'enregistrement le laisse à vrai — on ne l'écrase pas ici.
    setRechargeTick((t) => t + 1)
    onDevisChanged?.()
  }

  // EDC11 — « Voir le PDF » est un geste EXPLICITE (bouton de la barre
  // d'actions du générateur). L'aperçu remplace l'éditeur : avec des
  // modifications non enregistrées, on le dit avant de les abandonner.
  const onVoirPdf = async () => {
    if (dirty) {
      const ok = await demanderConfirmation({
        title: 'Voir le PDF sans enregistrer ?',
        description: 'Le PDF montre la dernière version enregistrée du devis : '
          + 'vos modifications en cours seront abandonnées.',
        confirmLabel: 'Voir sans enregistrer',
        cancelLabel: 'Rester',
        destructive: false,
      })
      if (!ok) return
    }
    setDirty(false)
    setPhase('preview')
  }

  // EDC6 — SORTIES PROTÉGÉES de l'édition. Échap, clic sur le voile et ✕
  // fermaient tout le panneau SANS prévenir : une frappe de trop et le devis
  // en cours était perdu. Maintenant, avec des modifications non enregistrées,
  // chaque geste passe par « Quitter sans enregistrer ? » (Rester / Quitter) ;
  // sans modification, il sort directement. La destination dépend du GESTE,
  // pas de l'état : Échap et le voile « reviennent » (aperçu si le devis
  // existe, sinon fermeture), ✕ ferme le panneau.
  const sortirDeLEdition = async (destination) => {
    const quitter = () => {
      setDirty(false)
      if (destination === 'retour' && devisId) setPhase('preview')
      else onClose()
    }
    if (!dirty) {
      quitter()
      return
    }
    const ok = await demanderConfirmation({
      title: 'Quitter sans enregistrer ?',
      description: "Les modifications de ce devis n'ont pas été enregistrées : "
        + 'elles seront perdues si vous quittez.',
      confirmLabel: 'Quitter',
      cancelLabel: 'Rester',
    })
    if (ok) quitter()
  }

  // Rappels de Radix DismissableLayer (préventables). Phase `edit` SEULEMENT :
  // `preview`/`creating`/`error`/`remise-input` gardent la fermeture Radix
  // d'origine (Échap / clic sur le voile ferment le panneau).
  const onEscapeKeyDown = (e) => {
    if (phase !== 'edit') return
    // Déjà pris : Radix empile les couches, donc Échap dans un popover ouvert
    // (ProduitPicker) ne remonte pas jusqu'ici ; ce garde couvre le reste (un
    // écouteur en amont qui a déjà fait preventDefault()).
    if (e.defaultPrevented) return
    e.preventDefault()
    sortirDeLEdition('retour')
  }
  const onInteractOutside = (e) => {
    if (phase !== 'edit') return
    // Geste déjà pris : le Dialog modal annule lui-même le clic droit ET la
    // prise de focus hors du panneau (ex. la boîte de confirmation qui
    // s'ouvre) AVANT de nous appeler — sans ce garde, la confirmation
    // rappellerait la confirmation.
    if (e.defaultPrevented) return
    // En édition, JAMAIS de fermeture directe par Radix.
    e.preventDefault()
    // Un toast (« Modifications enregistrées. ») vit hors du panneau : cliquer
    // dessus pour le fermer ne doit pas renvoyer l'ouvrier à l'aperçu.
    if (e.target?.closest?.('[data-sonner-toaster], [data-sonner-toast]')) return
    // EDC6 (suite, mesuré en direct le 09/10/2026) — Radix DIFFÈRE le rappel
    // « pointeur hors panneau » (setTimeout 0, `deferPointerDownOutside`). Un
    // clic sur « Rester » DANS la boîte de confirmation la ferme d'abord ; le
    // rappel différé arrive ensuite, alors que cette couche a disparu et que le
    // panneau est redevenu la plus haute : il prenait ce clic pour un clic sur
    // le voile et REDEMANDAIT la confirmation — le dialogue ne se fermait
    // jamais. Une cible déjà décrochée du document, ou qui vit dans une autre
    // couche (confirmation, dialogue, popover), n'est jamais un geste de sortie.
    if (!estGesteHorsPanneau(e.detail?.originalEvent?.target ?? e.target, contenuRef.current)) return
    sortirDeLEdition('retour')
  }
  // Fermeture demandée par Radix par une autre voie : en édition, elle passe
  // aussi par la garde (filet de sécurité, ces voies sont déjà interceptées).
  const onOpenChange = (ouvert) => {
    if (ouvert) return
    if (phase === 'edit') sortirDeLEdition('fermer')
    else onClose()
  }
  const onCloseClick = () => {
    if (phase === 'edit') sortirDeLEdition('fermer')
    else onClose()
  }

  // Téléchargement : MÊME source que l'aperçu (/proposal), récupérée en blob
  // via axios (cookie httpOnly) — aperçu et téléchargement concordent.
  const handleDownload = async () => {
    if (!devisId) return
    setDownloading(true)
    // QJR652 — fenêtre ouverte dans le geste, avant le premier await (iOS / PWA).
    const pending = downloadBlobInGesture()
    try {
      const res = await ventesApi.getProposalPdf(
        devisId, proposalParams(pdfMode, includeEtude))
      // QD2 — nom cohérent posé par le serveur (repli sur la référence).
      pending.deliver(res.data, filenameFromResponse(res, `${devisRef || 'Devis'}.pdf`))
    } catch {
      try { pending.win?.close() } catch { /* fenêtre déjà fermée */ }
      setErrorMsg('Téléchargement du PDF indisponible. Réessayez.')
    } finally {
      setDownloading(false)
    }
  }

  // « Ouvrir dans un nouvel onglet » : on ouvre le MÊME PDF authentifié via une
  // URL blob (donc indépendante d'un bloqueur sur l'embed inline). On réutilise
  // le blob déjà récupéré ; sinon on le récupère d'abord.
  // VX48 — onglet pré-ouvert SYNCHRONE dans le geste de tap, avant tout await
  // (Safari iOS bloque silencieusement un window.open() post-await).
  const handleOpenNewTab = async () => {
    if (!devisId) return
    const pending = openPdfInGesture()
    try {
      let blob = previewBlob
      if (!blob) {
        const res = await ventesApi.getProposalPdf(
          devisId, proposalParams(pdfMode, includeEtude))
        blob = pdfBlob(res.data)
      }
      if (!pending.deliver(blob, `${devisRef || 'Devis'}.pdf`)) {
        setErrorMsg('Ouverture bloquée par le navigateur. Téléchargez le PDF.')
      }
    } catch {
      setErrorMsg('Ouverture impossible. Réessayez ou téléchargez le PDF.')
    }
  }

  return (
    // VX133 — migré du `.ldp-overlay`/`.ldp-panel` bespoke (pop centré) vers
    // Sheet side="right" : le panneau glisse depuis son bord réel au lieu de
    // « pop » du centre de l'écran. Le bouton ✕ reste celui du header
    // ldp-* existant (showClose désactivé pour ne pas en dupliquer un).
    <Sheet open onOpenChange={onOpenChange}>
      <SheetContent side="right" showClose={false} ref={contenuRef}
                    onEscapeKeyDown={onEscapeKeyDown}
                    onInteractOutside={onInteractOutside}
                    className={`${phase === 'edit' ? LARGEUR_EDITION : LARGEUR_STANDARD} gap-0 p-0 sm:max-w-none`}>
        <div className="ldp-header">
          <h3 className="ldp-title">
            {TITLES[mode] || 'Devis'} — {lead.nom} {lead.prenom || ''}
            {devisRef && <span className="ldp-ref">{devisRef}</span>}
            {/* EDC1 — le statut du devis CHARGÉ (libellés de devisStatuts.js,
                jamais une clé de STAGES.py) : l'ouvrier sait sur quelle
                version il travaille sans quitter l'éditeur. */}
            {devisRecord?.statut && (
              <StatusPill status={devisRecord.statut}
                          label={libelleStatutDevis(devisRecord.statut)}
                          data-testid="ldp-statut" />
            )}
          </h3>
          <button type="button" className="modal-close" onClick={onCloseClick}>✕</button>
        </div>

        <div className="ldp-body">
          {phase === 'remise-input' && (
            <div className="ldp-center">
              <p className="gen-hint">
                Entrez la remise à appliquer, puis le devis sera dimensionné
                automatiquement depuis les données du lead.
              </p>
              <div className="form-group" style={{ maxWidth: 220 }}>
                <label className="form-label">Remise (%)</label>
                <Input type="number" min="0" max="100" step="any"
                       value={discount} autoFocus
                       onChange={e => setDiscount(e.target.value)} />
              </div>
              <div className="ldp-actions">
                <Button type="button" variant="outline" onClick={onClose}>
                  Annuler
                </Button>
                <Button type="button"
                        onClick={() => { startedRef.current = true; doCreateAuto(discount || '0') }}>
                  <Zap /> Créer le devis
                </Button>
              </div>
            </div>
          )}

          {phase === 'creating' && (
            <div className="ldp-center">
              <EtapesCreationDevis />
            </div>
          )}

          {/* EDC8 — lecture du devis avant de monter l'éditeur. */}
          {phase === 'chargement' && (
            <div className="ldp-center" data-testid="ldp-chargement">
              <p className="gen-hint" role="status"><Spinner /> Ouverture du devis…</p>
            </div>
          )}

          {phase === 'error' && (
            <div className="ldp-center">
              <div className="form-error-box" role="alert">{errorMsg}</div>
              {errorField && missingFieldTarget(errorField) && (
                <Button type="button" variant="outline" data-testid="ldp-completer"
                        onClick={() => completerChamp(errorField)}>
                  Compléter : {fieldLabels[errorField].label}
                </Button>
              )}
              <div className="ldp-actions">
                <Button type="button" variant="outline" onClick={onClose}>Fermer</Button>
                {editable && (
                  <Button type="button" onClick={() => setPhase('edit')}>
                    Ouvrir l'édition complète
                  </Button>
                )}
                {revisable && (
                  <Button type="button" onClick={reviser}>
                    Réviser (nouvelle version)
                  </Button>
                )}
              </div>
            </div>
          )}

          {phase === 'edit' && (
            <div className="ldp-edit">
              {/* EDC1 — le défileur `.ldp-edit` n'a PLUS de padding (sinon tout
                  `top: 0` collant du générateur se décale de 16 px) : le
                  retrait vit sur ce conteneur intérieur. */}
              <div className="ldp-edit-inner">
                <DevisGenerator
                  embedded
                  leadId={lead.id}
                  editId={devisId || null}
                  onDone={onEditDone}
                  onEnregistre={onEnregistre}
                  onVoirPdf={onVoirPdf}
                  onDirtyChange={setDirty}
                  onCancel={() => { setDirty(false); if (devisId) setPhase('preview'); else onClose() }}
                />
              </div>
            </div>
          )}

          {phase === 'preview' && (
            <div className="ldp-preview">
              {/* ALEA51 — SUCCÈS : une phrase qui dit ce qui vient d'être créé
                  (référence · kWc · TTC · économie · retour · postes à chiffrer
                  après la visite), jamais la boîte rouge des erreurs. */}
              {resume && (
                <div className="rounded-lg border border-success/40 bg-success/10 p-3 text-sm"
                     role="status" data-testid="ldp-succes-auto">
                  <strong>Devis créé :</strong> {libelleSuccesDevisAuto(resume)}
                </div>
              )}
              {/* AGR126 — ce que le devis automatique serveur signale (jamais
                  un chiffre inventé : le message du serveur, tel quel), en
                  AVERTISSEMENT sous le succès (ALEA51). AGQ25 — rendu UNIQUE,
                  partagé avec le générateur. */}
              <AlertesDevisAuto alertes={alertes} />
              {/* QJR589 — dérive lead → devis : reprendre / garder, sur place
                  (envoyé : le client verra la version corrigée) ; figé →
                  « Réviser ». Le détail est déjà lu (getDevisById). */}
              {devisRecord && (
                <BandeauDeriveLead
                  devisId={devisId}
                  statut={devisRecord.statut}
                  champs={devisRecord.lead_valeurs_modifiees}
                  onResolu={(data) => {
                    if (data?.devis) setDevisRecord(data.devis)
                    onDevisChanged?.()
                  }}
                  onReviser={revisable ? reviser : undefined}
                />
              )}
              <div className="ldp-toolbar">
                <div className="ldp-format">
                  <Segmented
                    size="sm"
                    value={pdfMode}
                    onChange={setPdfMode}
                    options={[
                      { value: 'full', label: 'Premium' },
                      { value: 'onepage', label: '1 page' },
                    ]}
                  />
                  {pdfMode === 'full' && !marcheHorsResidentiel && (
                    <label className="ldp-etude-toggle">
                      <Checkbox
                        checked={includeEtude}
                        onCheckedChange={v => setIncludeEtude(v === true)}
                      />
                      <span>Inclure l'étude</span>
                    </label>
                  )}
                </div>
                <div className="ldp-toolbar-actions">
                  {editable && (
                    <Button type="button" variant="outline" size="sm"
                            onClick={() => setPhase('edit')}>
                      <Pencil /> Édition complète
                    </Button>
                  )}
                  {revisable && (
                    <Button type="button" variant="outline" size="sm" onClick={reviser}>
                      <Pencil /> Réviser (nouvelle version)
                    </Button>
                  )}
                  {devisRecord && devisRecord.is_active !== false && (
                    <Button type="button" size="sm" data-testid="ldp-envoyer"
                            onClick={() => setEnvoiOuvert(true)}>
                      <Send /> Envoyer au client
                    </Button>
                  )}
                  <Button type="button" size="sm" variant="outline"
                          onClick={handleDownload} loading={downloading} disabled={downloading}>
                    {!downloading && <Download />}
                    {downloading ? '…' : 'Télécharger le PDF'}
                  </Button>
                </div>
              </div>
              <div className="ldp-pdf-area">
                {errorMsg && (
                  <div className="form-error-box ldp-pdf-loading" role="alert">{errorMsg}</div>
                )}

                <PdfPreviewBody
                  blob={preview.blob}
                  loading={preview.loading}
                  errorKind={preview.errorKind}
                  errorMessage={preview.errorMessage}
                  renderFailed={preview.renderFailed}
                  onRenderError={preview.onRenderError}
                  onReload={reloadPreview}
                  reloadKey={preview.reloadKey}
                  loadingText="Chargement de l'aperçu… La première génération d'un devis peut prendre ~30 secondes."
                  serverMessage={"Le serveur n'a pas pu générer ce PDF. Ouvrez l'édition complète "
                    + 'pour vérifier le devis, puis réessayez.'}
                  serverActions={(
                    <>
                      {editable && (
                        <Button type="button" size="sm" onClick={() => setPhase('edit')}>
                          Ouvrir l'édition complète
                        </Button>
                      )}
                      {revisable && (
                        <Button type="button" size="sm" onClick={reviser}>
                          Réviser (nouvelle version)
                        </Button>
                      )}
                    </>
                  )}
                  fallbackDescription="Vérifiez votre connexion. Vous pouvez réessayer ou télécharger le devis directement."
                  fallbackActions={(
                    <>
                      <Button type="button" size="sm"
                              onClick={handleDownload} loading={downloading} disabled={downloading}>
                        {!downloading && <Download />}
                        {downloading ? '…' : 'Télécharger le PDF'}
                      </Button>
                      <Button type="button" variant="outline" size="sm" onClick={handleOpenNewTab}>
                        <ExternalLink /> Ouvrir dans un nouvel onglet
                      </Button>
                    </>
                  )}
                />
              </div>
            </div>
          )}
        </div>
        {devisId && (
          <EnvoiDevisDialog
            devis={devisPourEnvoi}
            envoi={envoi}
            ouvert={envoiOuvert}
            onOuvertChange={setEnvoiOuvert}
            modeDevis={marcheDevis}
          />
        )}
      </SheetContent>
    </Sheet>
  )
}
