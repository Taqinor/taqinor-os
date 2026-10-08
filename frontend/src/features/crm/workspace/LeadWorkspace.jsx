import { createElement, useEffect, useState, useCallback, useMemo, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import api from '../../../api/axios'
import crmApi from '../../../api/crmApi'
import ventesApi from '../../../api/ventesApi'
import { toastPromise, useConfirmDialog } from '../../../ui/confirm'
import { toastWithUndo } from '../../../lib/toast'
import {
  createLead, archiveLead, restoreLead,
} from '../store/crmSlice'
import {
  Button, IconButton, Switch, FormActions,
  Dialog, DialogContent, DialogTitle,
  Sheet, SheetContent, SheetTitle,
  SkeletonAvatar, SkeletonLine, SkeletonText, SkeletonCard, FadeSwap,
} from '../../../ui'
import { useIsMobile } from '../../../ui/ResponsiveDialog'
import { useServerFieldErrors } from '../../../hooks/useServerFieldErrors'
import { useDelayedLoading } from '../../../hooks/useDelayedLoading'
import { isTypingTarget } from '../../../providers/shortcuts'
import { useFocusedRecordShortcuts, LEAD_STAGE_SHORTCUTS, dialogueParDessus } from '../../../providers/focusedRecordShortcuts'
import { pushRecentEntity } from '../../../providers/commandActions'
import { normalizePhoneE164 } from '../../../lib/format'
import { buildWaUrl } from '../../../lib/contactLinks'
import { isStageMoveBackward } from '../stages'
import { isSortieSigne } from '../stages'
// ORDRE FONDATEUR 2026-08-01 — la MÊME question que sur le board (elle nomme le
// lead et les deux étapes) : une seule formulation pour tous les gestes qui
// font reculer un lead.
import { useConfirmerRecul } from '../confirmRecul'
import { useLeadDraft, rememberVille } from './useLeadDraft'
import { schedulePrefetch } from './leadPrefetch'
import { getField } from './draftCore'
import { jumpToField } from './jumpToField'
import fieldLabels from './fieldLabels'
import IdentityRail from './IdentityRail'
import SectionsPane from './SectionsPane'
import ContextRail from './ContextRail'
// LANE Q-C — dialogue « Envoyer un questionnaire », satellite comme
// SigneDialog/PlanActiviteDialog/ConvertirClientDialog ci-dessous.
import QuestionnaireDialog from './QuestionnaireDialog'
// Satellites INCHANGÉS de place (blueprint) — importés par le shell.
import LeadDevisPanel from '../../../pages/crm/leads/LeadDevisPanel'
import SigneDialog from '../../../pages/crm/leads/SigneDialog'
import PlanActiviteDialog from '../../../pages/crm/leads/PlanActiviteDialog'
import ConvertirClientDialog from '../../../pages/crm/leads/ConvertirClientDialog'
// PV22 — les deux seuls moments où « Concevoir la toiture (3D) » a besoin d'une
// décision humaine (plusieurs brouillons / refus de dimensionnement serveur).
import ChoisirDevisPourDesign, { DevisAutoImpossibleDialog } from '../../ventes/ChoisirDevisPourDesign'

// LW10 — Le shell `LeadWorkspace` : UNE fenêtre, deux enveloppes (Dialog quasi
// plein écran depuis la liste/kanban ; pleine page à /crm/leads/:id), le scroll
// JUSTE PAR CONSTRUCTION (grille rows auto/1fr, min-height:0, chaque zone son
// propre overflow). Contrat de props identique à LeadForm — les appelants ne
// changent pas (bascule en LW13). LW12 complète le mode création.

// Validation e-mail minimale (le formulaire est noValidate) — miroir LeadForm.
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

// VX224/VX92 — « Créer un autre » : persisté par utilisateur (localStorage),
// défaut OFF. Une session de qualification en rafale = 20-40 leads/j.
const CREER_UN_AUTRE_KEY = 'taqinor.leadForm.creerUnAutre'
const lireCreerUnAutre = () => {
  try { return localStorage.getItem(CREER_UN_AUTRE_KEY) === '1' } catch { return false }
}
const ecrireCreerUnAutre = (v) => {
  try { localStorage.setItem(CREER_UN_AUTRE_KEY, v ? '1' : '0') } catch { /* best-effort */ }
}

// LW26 — registre MINIMAL « Aller à la section … » de la palette ⌘K : miroir
// des id/label STABLES du registre de SectionsPane.jsx (id/label seulement —
// SectionsPane possède la STRUCTURE, cf. « Do NOT touch » de cette lane ;
// les sections CONDITIONNELLES — pompage/origine web — n'y figurent pas,
// simplification assumée). `[data-nav-id]`/`.lw-section-head` sont des hooks
// DOM stables (même patron que `.ap-trigger` pour l'AssigneePicker).
const SECTION_JUMP_TARGETS = [
  { id: 'contact', label: 'Aller à : Contact' },
  { id: 'pipeline', label: 'Aller à : Suivi commercial' },
  { id: 'energie', label: 'Aller à : Profil énergétique' },
  { id: 'toiture', label: 'Aller à : Toiture & site' },
  { id: 'visite', label: 'Aller à : Visite technique' },
  { id: 'divers', label: 'Aller à : Compléments' },
]

function goToSection(id) {
  const el = document.querySelector(`.lw-center [data-nav-id="${id}"]`)
  if (!el) return
  // Déplie la section si elle est repliée (même logique que SectionsPane.jumpTo,
  // rejouée depuis l'extérieur via le hook DOM stable — jamais un import de
  // l'état interne de SectionsPane).
  el.querySelector('.lw-section-head[aria-expanded="false"]')?.click()
  el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

// Chip d'état de sauvegarde (autosauvegarde D2). Jamais de spinner bloquant.
// RÈGLE FONDATEUR 08/09/2026 — en erreur, le chip NOMME le champ fautif (déjà
// résolu par l'appelant via fieldLabels.js → `errorField`) et un clic dessus y
// saute (déplie + focalise, `jumpToField` — jamais de re-saisie manuelle de la
// même logique que SectionsPane/DevisTab). « Réessayer » reste TOUJOURS une
// action distincte et visible : quand aucun champ n'est résolvable (échec
// réseau/serveur générique — pas de data 400 exploitable), le chip retombe sur
// son unique bouton historique (texte + comportement inchangés, régression
// zéro pour ce cas — cf. LeadWorkspace.test.jsx « échec réseau »).
function SaveChip({ saveState, saveError, errorField, onRetry }) {
  if (saveState === 'saving') {
    return <span className="lw-savechip lw-savechip--saving" role="status" aria-live="polite">Enregistrement…</span>
  }
  if (saveState === 'saved') {
    return <span className="lw-savechip lw-savechip--saved" role="status" aria-live="polite">✓ Enregistré</span>
  }
  if (saveState === 'error') {
    if (errorField) {
      return (
        <span className="lw-savechip-group" role="alert">
          <button
            type="button"
            className="lw-savechip lw-savechip--error"
            title={saveError}
            onClick={() => jumpToField({ section: errorField.section, field: errorField.inputId })}
          >
            ⚠ {saveError}
          </button>
          <button type="button" className="lw-savechip-retry" onClick={onRetry}>
            Réessayer
          </button>
        </span>
      )
    }
    return (
      <button type="button" className="lw-savechip lw-savechip--error" onClick={onRetry}>
        ⚠ Non enregistré — Réessayer
      </button>
    )
  }
  return null
}

export default function LeadWorkspace({
  lead = null, onClose, onSaved,
  leadsQueue = null, onNavigateLead = null,
  initialDevis = null, focusSection = null,
  onOpenDuplicate = null,
  variant = 'dialog',
}) {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const isMobile = useIsMobile()
  // LW34 — 768-1023 : rail identité + centre en 2 colonnes, rail contexte
  // sorti de la grille (Sheet à la demande, bouton « Contexte » du bandeau).
  // Même famille que `isMobile` ci-dessus (useIsMobile générique, requête
  // dédiée) — le SEUL jeu de seuils du bloc .lw-* reste 768/1024.
  const isTablet = useIsMobile('(min-width: 768px) and (max-width: 1023px)')
  const [contextSheetOpen, setContextSheetOpen] = useState(false)
  // Critique Fable #8 : à 768-1023 le rail contexte n'est monté QUE dans le
  // Sheet — « n » / actions ⌘K (lw:open-*) partaient dans le vide. Le shell
  // ouvre d'abord le Sheet puis RE-DIFFUSE l'événement au frame suivant, une
  // fois ContextRail monté (son écouteur fait le focus).
  const isTabletRef = useRef(false)
  const sheetOpenRef = useRef(false)
  useEffect(() => { isTabletRef.current = isTablet }, [isTablet])
  useEffect(() => { sheetOpenRef.current = contextSheetOpen }, [contextSheetOpen])
  useEffect(() => {
    const relay = (e) => {
      if (e.detail && e.detail.relayed) return // jamais re-relayer son propre écho
      if (!isTabletRef.current || sheetOpenRef.current) return
      setContextSheetOpen(true)
      const evt = new CustomEvent(e.type, { detail: { ...(e.detail || {}), relayed: true } })
      requestAnimationFrame(() => requestAnimationFrame(() => window.dispatchEvent(evt)))
    }
    window.addEventListener('lw:open-note-composer', relay)
    window.addEventListener('lw:open-whatsapp-composer', relay)
    return () => {
      window.removeEventListener('lw:open-note-composer', relay)
      window.removeEventListener('lw:open-whatsapp-composer', relay)
    }
  }, [])
  const mode = lead ? 'edit' : 'create'
  const currentUserId = useSelector((s) => s.auth?.user?.id)

  const { errors, setErrors, setFromResponse } = useServerFieldErrors()
  const draft = useLeadDraft(lead, { mode, currentUserId, onSaved, onFieldErrors: setFromResponse })
  const {
    state, field, setField, saveState, leaveGuard, changeStage, loadFresh,
  } = draft
  // RÈGLE FONDATEUR 08/09/2026 — quel champ nommer sur le chip d'erreur (SaveChip) :
  // la PREMIÈRE clé de `errors` qui a une entrée dans fieldLabels.js (celles sans
  // entrée — `submit`, motif_perte posé par la validation CLIENT de création,
  // etc. — sont ignorées ici, `find(Boolean)` saute silencieusement les `undefined`).
  const primaryErrorField = Object.keys(errors).map((k) => fieldLabels[k]).find(Boolean) || null
  // Primitives STABLES hoistées : le compilateur React (lint v7) refuse de
  // préserver un useCallback dont les deps mêlent optional-chaining et objet
  // entier — on ne dépend que de scalaires.
  const leadId = lead?.id ?? null
  const leadArchived = !!lead?.is_archived
  // Ordre fondateur 2026-08-01 — scalaires du recul confirmé, hoistés pour la
  // même raison que ci-dessus (deps du useCallback = scalaires uniquement).
  // L'étape de RÉFÉRENCE est celle du serveur, jamais celle du draft : `stage`
  // n'entre jamais dans le draft (voir useLeadDraft.changeStage).
  const stageCourant = state.server?.stage ?? null
  const devisLead = state.server?.devis
  const leadNom = state.server?.nom ?? lead?.nom ?? ''

  // ── Données de référence (partagées avec les rails / sections) ────────────
  const [users, setUsers] = useState([])
  const [tagOptions, setTagOptions] = useState([])
  const [motifOptions, setMotifOptions] = useState([])
  const [historique, setHistorique] = useState([])

  useEffect(() => {
    crmApi.getAssignableUsers().then((r) => setUsers(r.data.results ?? r.data)).catch(() => {})
    crmApi.getTags().then((r) => setTagOptions((r.data.results ?? r.data).filter((t) => !t.archived))).catch(() => {})
    crmApi.getMotifsPerte().then((r) => setMotifOptions((r.data.results ?? r.data).filter((m) => !m.archived))).catch(() => {})
  }, [])

  // LW43 — garde d'identité : `leadId` capturé À L'ENVOI (`requestedId`),
  // comparé au VRAI courant (`leadIdRef`, tenu à jour à chaque rendu — jamais
  // le seul `leadId` fermé dans ce callback, qui resterait figé sur l'ancien
  // lead pour CETTE requête déjà en vol) — une réponse lente du lead A ne
  // peint plus jamais sur le lead B après un J/K rapide (même patron
  // `cancelled` que LeadDetailPage.jsx, décliné en ref pour un callback
  // réutilisable hors effet).
  const leadIdRef = useRef(leadId)
  // Racine de la fiche : les raccourcis (d/n/1-4, J/K) se taisent dès qu'une
  // boîte ouverte ne la contient pas (satellite posé par-dessus — incident
  // 02/10/2026, voir dialogueParDessus).
  const rootRef = useRef(null)
  useEffect(() => { leadIdRef.current = leadId })
  const refreshHistorique = useCallback(() => {
    if (!leadId) return
    const requestedId = leadId
    api.get(`/crm/leads/${requestedId}/historique/`)
      .then((r) => { if (leadIdRef.current === requestedId) setHistorique(r.data) })
      .catch(() => {})
  }, [leadId])

  useEffect(() => {
    if (mode !== 'edit' || !leadId) return
    // LW41 — le GET détail embarque déjà `chatter_recent` (LW30) : ne
    // déclencher le fetch initial d'historique QUE s'il est absent/vide à
    // l'ouverture (sinon l'ouverture d'un lead coûtait PLUS cher qu'avant :
    // le GET détail PUIS toujours /historique/ en plus). Les rafraîchissements
    // APRÈS action (note postée, pièce jointe, appel loggé, « voir plus » —
    // TimelineTab/ContextRail) restent inchangés, appelés explicitement
    // ailleurs via `refreshHistorique`. `state.server` volontairement HORS
    // deps (lu à l'exécution) : seul le premier
    // rendu de CE lead doit décider, jamais un ré-arbitrage à chaque PATCH.
    if (!state.server?.chatter_recent?.length) refreshHistorique()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- décision prise une fois par lead, pas à chaque state.server
  }, [mode, leadId, refreshHistorique])

  // ERR-QAH-CRM-HISTORIQUE-VIDE-RELANCE — un autosave RÉUSSI (« Relance le »,
  // responsable, tout champ suivi) écrit côté serveur une entrée de chatter
  // (ancien → nouveau) que ni la réponse du PATCH ni `chatter_recent` (figé à
  // l'ouverture) ne portent : on relit l'historique pour AJOUTER ces lignes
  // aux anciennes, sans attendre un rechargement de la page.
  useEffect(() => {
    if (mode === 'edit' && saveState === 'saved') refreshHistorique()
  }, [mode, saveState, refreshHistorique])

  // ── Satellites (dialogues) ────────────────────────────────────────────────
  const [devisPanel, setDevisPanel] = useState(null)
  const [panelDevisId, setPanelDevisId] = useState(null)
  // EZ5 — puissance cible (kWc) portée par l'intention « Devis automatique »
  // quand le commercial en a tapé une. Vit à côté du mode (et non DANS lui)
  // pour que `devisPanel` reste la chaîne que tout le reste compare.
  const [devisKwc, setDevisKwc] = useState(null)
  const [signeOpen, setSigneOpen] = useState(false)
  const [planOpen, setPlanOpen] = useState(false)
  const [convertOpen, setConvertOpen] = useState(false)
  // LANE Q-C — dialogue « Envoyer un questionnaire » (bouton du rail identité).
  const [questionnaireOpen, setQuestionnaireOpen] = useState(false)
  const [archiveBusy, setArchiveBusy] = useState(false)
  // F4 — bumpé par les raccourcis « ⋯ » du rail identité (onAction
  // 'relance-cadence'/'relance-arreter' ci-dessous) : transmis à
  // SectionPipeline via refData, combiné à son compteur local `friseReload`
  // (ses propres boutons Relancer/Arrêter), pour que CadenceFrise recharge
  // AUSSI après un geste pris hors de SectionPipeline.
  const [relanceVersion, setRelanceVersion] = useState(0)
  // PV22 — « Concevoir la toiture (3D) » : la liste des brouillons à départager
  // (plusieurs candidats) et le message SERVEUR quand le dimensionnement
  // automatique est refusé. `null` = aucun dialogue ouvert.
  const [choixDesign, setChoixDesign] = useState(null)
  const [designBloque, setDesignBloque] = useState(null)

  // Ouverture directe sur un mode devis (⚡ d'une carte / liste).
  const devisIntentRan = useRef(false)
  useEffect(() => {
    if (mode === 'edit' && initialDevis && !devisIntentRan.current) {
      devisIntentRan.current = true
      setDevisPanel(initialDevis)
    }
  }, [mode, initialDevis])

  // Archivage : passe TOUJOURS par leaveGuard (flush d'abord) — l'archivage ne
  // peut plus structurellement jeter des éditions non sauvées (tue P1#3).
  // INCIDENT 02/10/2026 — un lead vivant (« ouissam merbahi ») a été archivé
  // sans que la commerciale s'en rende compte : aucune question, la fenêtre se
  // refermait, et le lead quittait pipeline, agenda et relances. Désormais
  // ARCHIVER est TOUJOURS demandé en nommant le lead (menu « ⋯ » comme ⌘K —
  // plus aucun raccourci à une touche), puis un toast « Annuler » laisse 10 s
  // pour revenir en arrière. La RESTAURATION ne cache rien : pas de question.
  const { confirm: confirmer } = useConfirmDialog()
  const doArchive = useCallback(async () => {
    if (!leadId) return
    if (!leadArchived) {
      const ok = await confirmer({
        title: `Archiver « ${leadNom || 'ce lead'} » ?`,
        description: 'Le lead quitte le pipeline, l’agenda et les relances. '
          + 'Il reste retrouvable avec le filtre « Archivés » de la liste des '
          + 'leads, d’où il se restaure.',
        confirmLabel: 'Archiver',
        cancelLabel: 'Annuler',
        destructive: true,
      })
      if (!ok) return
    }
    leaveGuard(async () => {
      setArchiveBusy(true)
      try {
        if (leadArchived) await dispatch(restoreLead(leadId)).unwrap()
        else {
          await dispatch(archiveLead(leadId)).unwrap()
          toastWithUndo({
            message: `« ${leadNom || 'Lead'} » archivé.`,
            description: 'Retrouvable avec le filtre « Archivés » de la liste des leads.',
            duration: 10000,
            onUndo: () => {
              dispatch(restoreLead(leadId)).unwrap().then(() => onSaved?.()).catch(() => {})
            },
          })
        }
        onSaved?.()
        onClose?.()
      } catch { /* silencieux */ } finally { setArchiveBusy(false) }
    })
  }, [leadId, leadArchived, leadNom, confirmer, leaveGuard, dispatch, onSaved, onClose])

  /* ORDRE FONDATEUR 2026-08-01 — « les leads doivent pouvoir REVENIR EN
     ARRIÈRE d'étape, avec une confirmation avant ».
     Une AVANCÉE part directement (rien à demander) ; un RECUL pose la question
     partagée (elle nomme le lead et les deux étapes) et n'appelle le moteur
     qu'après un oui — avec le marqueur que le serveur exige. Annulée, on ne
     touche à rien : aucun PATCH, l'étape affichée ne bouge pas. */
  const confirmerRecul = useConfirmerRecul()
  const changeStageConfirme = useCallback(async (cible) => {
    // Décision fondateur 08/10/2026 — quitter « Signé » dés-accepte le devis
    // côté serveur : la question est posée même vers Froid (pas un recul) ;
    // un 409 (suite réelle) est affiché par le moteur (texte serveur).
    const fiche = { nom: leadNom, stage: stageCourant, devis: devisLead }
    if (!isStageMoveBackward(stageCourant, cible) && isSortieSigne(stageCourant, cible)) {
      if (!(await confirmerRecul(fiche, cible))) return undefined
      return changeStage(cible)
    }
    if (!isStageMoveBackward(stageCourant, cible)) return changeStage(cible)
    const ok = await confirmerRecul(fiche, cible)
    if (!ok) return undefined
    return changeStage(cible, { confirmeRecul: true })
  }, [changeStage, confirmerRecul, stageCourant, leadNom, devisLead])

  /* PV22 — « Concevoir la toiture (3D) » NE MÈNE PLUS À UN ÉCRAN VIDE.
     La conception 3D travaille désormais SUR un devis (PV20/PV21) : le geste
     résout donc d'abord quel devis calepiner.

     * exactement 1 devis concevable → on l'ouvre, sans rien demander ;
     * plusieurs                     → on les montre et le commercial choisit
                                       (on ne devine JAMAIS lequel est le bon) ;
     * aucun                         → le Copilote en dimensionne un depuis la
                                       fiche (jamais un brouillon vide) ; s'il
                                       refuse (422), son message FR est affiché
                                       tel quel et la seule sortie est le
                                       générateur complet.

     QJR636 — « concevable » est décidé par le SERVEUR (`?concevable=1`, la
     table de modifiabilité : brouillon + envoyé, hors agricole et
     multi-villa) ; aucun filtre de statut ici. */
  const ouvrirConceptionToiture = useCallback(async () => {
    if (!leadId) return
    setChoixDesign(null)
    setDesignBloque(null)

    let concevables = []
    try {
      const res = await ventesApi.getDevis({ lead: leadId, concevable: 1 })
      const rows = Array.isArray(res?.data) ? res.data : (res?.data?.results ?? [])
      concevables = rows.filter(Boolean)
    } catch { concevables = [] }

    if (concevables.length === 1) {
      navigate(`/ventes/devis/${concevables[0].id}/design`)
      return
    }
    if (concevables.length > 1) {
      setChoixDesign(concevables)
      return
    }

    try {
      const res = await ventesApi.creerDevisAuto({ lead: leadId })
      const nouveau = res?.data?.id
      if (nouveau) {
        navigate(`/ventes/devis/${nouveau}/design`)
        return
      }
      setDesignBloque('Devis créé sans identifiant — ouvrez-le depuis la liste des devis.')
    } catch (err) {
      setDesignBloque(
        err?.response?.data?.detail
        || "Impossible de créer un devis pour ce lead — ouvrez le générateur.")
    }
  }, [leadId, navigate])

  // Contrat d'action des rails (IdentityRail/ContextRail — autres lanes) :
  // toutes les sorties/points de mutation passent par ici.
  const onAction = useCallback((type, payload) => {
    switch (type) {
      case 'archive': return doArchive()
      case 'convert': return setConvertOpen(true)
      case 'plan': return setPlanOpen(true)
      case 'signe': return setSigneOpen(true)
      // LANE Q-C — « Envoyer un questionnaire » (IdentityRail, menu « Plus
      // d'actions »).
      case 'questionnaire': return setQuestionnaireOpen(true)
      // PV22 — le geste résout le devis à calepiner avant de naviguer.
      case 'toiture-3d':
        return leaveGuard(() => { ouvrirConceptionToiture() })
      // EZ5 — le payload reste la CHAÎNE de mode historique ('auto', 'remise',
      // 'onepage', 'premium', 'edit' — IdentityRail, palette, DevisTab sans
      // cible) ; il accepte EN PLUS un objet { mode, targetKwc } quand une
      // puissance cible a été saisie. Aucun appelant existant ne change.
      case 'open-devis': {
        const intent = (payload && typeof payload === 'object') ? payload : { mode: payload }
        setDevisKwc(intent.targetKwc || null)
        return setDevisPanel(intent.mode || 'auto')
      }
      case 'view-devis': setPanelDevisId(payload); return setDevisPanel('view')
      // QJR534 — « Modifier » une carte devis : ouvre le panneau en phase
      // `edit` SUR CE devis (existingDevisId), plus un nouveau devis.
      case 'edit-devis': setPanelDevisId(payload); return setDevisPanel('edit')
      // LW16-wire — édition rapide du rail (responsable/relance) : un simple
      // SET_FIELD, débouncé/flushé par le moteur comme toute autre frappe.
      case 'set-field': return setField(payload.key, payload.value)
      // LW16-wire — StageControl (transitions non-SIGNED) : passe TOUJOURS par
      // le moteur `changeStage` (flush-puis-PATCH dédié, LW23 s'en sert déjà
      // pour 1-4) ; un recul de funnel refusé (400) surface un toast — géré
      // à l'INTÉRIEUR de `changeStage` (useLeadDraft.js), un seul endroit
      // pour les DEUX appelants (raccourci clavier + StageControl).
      // ORDRE FONDATEUR 2026-08-01 — un recul est désormais possible, sous
      // confirmation. La QUESTION se pose ici et pas dans StageControl :
      // c'est le seul point par lequel passent les DEUX entrées du contrôle
      // (le menu d'étape ET les raccourcis « 1-4 »), et StageControl reste ce
      // que son contrat annonce — un déclencheur qui ne patche jamais.
      case 'change-stage': return changeStageConfirme(payload)
      // 'apply-card' : volontairement inerte pour l'instant (hors périmètre).
      case 'refresh': return draft.refreshServer()
      // MRY15 — raccourcis du menu « ⋯ » du rail identité (contrat
      // PerduPopover : jamais de crmApi direct dans le rail, il passe
      // toujours par onAction). Cadence par défaut 'contact' — le choix
      // complet (contact/après devis/réveil) vit dans la section Suivi
      // commercial (SectionPipeline), plus visible pour un geste réfléchi.
      // F4 — bump `relanceVersion` EN PLUS de refreshServer() : ce raccourci
      // vit hors SectionPipeline, son compteur local `friseReload` ne peut
      // donc pas le voir — sans ce bump la frise de la fiche (CadenceFrise)
      // restait figée après un geste pris ICI.
      case 'relance-cadence': {
        if (!leadId) return undefined
        return toastPromise(
          crmApi.initialiserRelance(leadId, { cadence: 'contact' })
            .then(() => { draft.refreshServer(); setRelanceVersion((n) => n + 1) }),
          {
            loading: 'Relance de la cadence…',
            success: 'Cadence relancée.',
            error: 'Relance de la cadence impossible.',
          },
        ).catch(() => {})
      }
      case 'relance-arreter': {
        if (!leadId) return undefined
        const motif = window.prompt("Motif d'arrêt de la cadence :")
        if (!motif || !motif.trim()) return undefined
        return toastPromise(
          crmApi.arreterCadence(leadId, { motif: motif.trim() })
            .then(() => { draft.refreshServer(); setRelanceVersion((n) => n + 1) }),
          {
            loading: 'Arrêt de la cadence…',
            success: 'Cadence arrêtée.',
            error: 'Arrêt de la cadence impossible.',
          },
        ).catch(() => {})
      }
      case 'close': return leaveGuard(onClose)
      default: return undefined
    }
  }, [doArchive, leaveGuard, draft, onClose, setField, leadId,
    changeStageConfirme, ouvrirConceptionToiture])

  // ── File de rafale (◀▶ + J/K), gardée par leaveGuard (draft flushé) ───────
  const queueIndex = (leadsQueue && mode === 'edit')
    ? leadsQueue.findIndex((l) => l.id === lead.id) : -1
  const prevInQueue = queueIndex > 0 ? leadsQueue[queueIndex - 1] : null
  const nextInQueue = (queueIndex >= 0 && queueIndex < leadsQueue.length - 1)
    ? leadsQueue[queueIndex + 1] : null

  const goToLead = useCallback((target) => {
    if (!target || !onNavigateLead) return
    leaveGuard(() => onNavigateLead(target))
  }, [onNavigateLead, leaveGuard])

  // J/K façon Gmail — effet AVEC dep array (corrige le smell recon 01 §6.4 :
  // ré-abonnement à chaque rendu) + garde isTypingTarget.
  useEffect(() => {
    if (mode !== 'edit' || !leadsQueue || !onNavigateLead) return undefined
    const onKey = (e) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return
      if (isTypingTarget(e.target)) return
      // Incident 02/10/2026 — une frappe dans le panneau devis (ou tout
      // satellite posé par-dessus) ne fait jamais changer la fiche de lead
      // sous un éditeur resté ouvert sur l'ancien.
      if (dialogueParDessus(rootRef.current)) return
      if (e.key === 'j' || e.key === 'J') { e.preventDefault(); goToLead(nextInQueue) }
      else if (e.key === 'k' || e.key === 'K') { e.preventDefault(); goToLead(prevInQueue) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [mode, leadsQueue, onNavigateLead, goToLead, nextInQueue, prevInQueue])

  // ── LW24 : pré-chargement en idle des voisins de file (J/K instantané) ────
  // Se contente d'ALIMENTER le cache module-level (leadPrefetch.js) — la
  // CONSOMMATION (premier rendu instantané) vit dans useLeadDraft.js
  // (LOAD_LEAD). Annulé proprement si la file change avant le déclenchement.
  useEffect(() => {
    if (mode !== 'edit' || !leadsQueue) return undefined
    const ids = [prevInQueue?.id, nextInQueue?.id].filter((id) => id != null)
    if (!ids.length) return undefined
    return schedulePrefetch(ids, (id) => crmApi.getLead(id).then((r) => r.data))
  }, [mode, leadsQueue, prevInQueue, nextInQueue])

  // ── LW25 : GET complet systématique à l'ouverture (+ LW24 : rejoué en
  // arrière-plan à CHAQUE navigation J/K, même mécanisme unique — `loadFresh`
  // remplace TOUJOURS le premier rendu, qu'il vienne de la ligne partielle ou
  // du cache voisin, garde `res.id===leadId` déjà dans le réducteur). Piloté
  // par `useDelayedLoading` : rien avant 300ms, squelette au-delà de 500ms —
  // jamais de spinner nu (recon 03 #23).
  const [leadLoading, setLeadLoading] = useState(false)
  useEffect(() => {
    if (mode !== 'edit' || !leadId) return undefined
    let cancelled = false
    // Synchronise le squelette avec le GET en vol (même patron que
    // LeadDevisPanel.jsx setPreviewLoading) : ce n'est pas un dérivé de
    // props/state, c'est le vrai début d'une opération réseau déclenchée PAR
    // cet effet.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLeadLoading(true)
    loadFresh(leadId).finally(() => { if (!cancelled) setLeadLoading(false) })
    return () => { cancelled = true }
  }, [mode, leadId, loadFresh])
  const { showSkeleton } = useDelayedLoading(leadLoading)

  // ── LW26 : actions contextuelles ⌘K tant que CE lead est ouvert ───────────
  // `taqinor:lead-workspace-actions` (posé/retiré au mount/unmount, motif de
  // `taqinor:command-palette` déjà en place) — providers/CommandPalette.jsx
  // les fusionne dans sa propre liste. « Envoyer les devis WhatsApp » et
  // « Épingler une note » n'ont pas ENCORE de surface concrète tant que le
  // rail contexte (LW19-LW21, ContextRail toujours un placeholder à ce jour)
  // n'a pas ses onglets — même patron d'événement `lw:open-*` que le
  // raccourci « n » ci-dessous, DOCUMENTÉ pour cette lane-là (voir rapport).
  const paletteActions = useMemo(() => {
    if (mode !== 'edit' || !leadId) return []
    return [
      {
        id: 'lw-wa-devis',
        label: 'Envoyer les devis par WhatsApp',
        run: () => window.dispatchEvent(new CustomEvent('lw:open-whatsapp-composer', { detail: { leadId } })),
      },
      { id: 'lw-devis-auto', label: 'Devis automatique', run: () => onAction('open-devis', 'auto') },
      // QJR599 — un devis MANUEL, même sans devis automatique prêt.
      {
        id: 'lw-devis-edition',
        label: 'Nouveau devis (édition complète)',
        run: () => onAction('open-devis', 'edit'),
      },
      {
        id: 'lw-archive',
        label: leadArchived ? 'Restaurer le lead' : 'Archiver le lead',
        run: () => onAction('archive'),
      },
      { id: 'lw-convert', label: 'Convertir en client', run: () => onAction('convert') },
      {
        id: 'lw-note',
        label: 'Épingler une note',
        run: () => window.dispatchEvent(new CustomEvent('lw:open-note-composer', { detail: { leadId } })),
      },
      ...SECTION_JUMP_TARGETS.map((s) => ({
        id: `lw-goto-${s.id}`, label: s.label, run: () => goToSection(s.id),
      })),
    ]
  }, [mode, leadId, leadArchived, onAction])

  useEffect(() => {
    if (!paletteActions.length) return undefined
    window.dispatchEvent(new CustomEvent('taqinor:lead-workspace-actions', { detail: { actions: paletteActions } }))
    return () => {
      window.dispatchEvent(new CustomEvent('taqinor:lead-workspace-actions', { detail: { actions: [] } }))
    }
  }, [paletteActions])

  // LW44 — `pushRecentEntity` à l'OUVERTURE uniquement (jamais à chaque
  // frappe du nom), avec le VRAI nom du lead OUVERT. L'ancien code dépendait
  // de `[mode, leadId]` (le PROP, synchro immédiate au changement de fiche)
  // mais lisait `nomTitreRef.current`, resynchronisé par un effet séparé plus
  // bas dans CE fichier — les deux effets s'exécutant dans le MÊME commit
  // (celui-ci déclaré en premier), ce push lisait TOUJOURS l'ancienne valeur :
  // libellé vide à la 1re ouverture, nom du lead PRÉCÉDENT en J/K. Fix :
  // dépendre de `state.leadId` (posé par le réducteur seulement APRÈS
  // `LOAD_LEAD`, un commit APRÈS le simple changement du prop `leadId`) et
  // lire le nom directement sur `state`, garanti à jour pour CE lead à ce
  // moment-là — plus besoin de ref du tout.
  useEffect(() => {
    if (mode !== 'edit' || state.leadId == null) return
    const nom = `${getField(state, 'nom') || ''} ${getField(state, 'prenom') || ''}`.trim()
    pushRecentEntity({ type: 'lead', id: state.leadId, label: nom ? `Lead — ${nom}` : 'Lead' })
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ne réagit qu'au VRAI changement de lead (state.leadId après LOAD_LEAD), jamais à chaque frappe du nom
  }, [mode, state.leadId])

  // ── LW23 : registre de raccourcis propre (d/n/1-4) ────────────────────────
  // (`a` archiver RETIRÉ — incident 02/10/2026, voir doArchive.) `d` focus le
  // picker Responsable de l'IdentityRail (hook DOM stable `.ap-trigger` —
  // fichier d'une autre lane, jamais importé), `n` bascule Historique +
  // focus composer (événement `lw:open-note-composer`, ContextRail — LW19-21
  // — DOIT écouter), `1`-`4` = StageControl (LEAD_STAGE_SHORTCUTS, jamais
  // SIGNED/COLD). Handlers mémoïsés → `useFocusedRecordShortcuts` reçoit un
  // objet STABLE, donc son propre effet clavier (dep array réparé,
  // providers/focusedRecordShortcuts.jsx) ne se réabonne plus à chaque rendu.
  // Les touches 1-4 appartiennent à StageControl (il s'enregistre lui-même,
  // StageControl.jsx — critique Fable #5 : la double inscription exécutait
  // chaque changement d'étape DEUX fois : double PATCH, double toast).
  const focusedHandlers = useMemo(() => ({
    d: () => { document.querySelector('.ap-trigger')?.focus() },
    n: () => { window.dispatchEvent(new CustomEvent('lw:open-note-composer', { detail: { leadId } })) },
  }), [leadId])
  // `scopeRef` : les touches se taisent dès qu'un satellite (panneau devis,
  // confirmation, popover…) est ouvert PAR-DESSUS la fiche (incident 02/10).
  useFocusedRecordShortcuts('leadForm', focusedHandlers, mode === 'edit', { scopeRef: rootRef })

  // ── Fermeture (✕/overlay/Escape) via leaveGuard ──────────────────────────
  const requestClose = useCallback(() => { leaveGuard(onClose) }, [leaveGuard, onClose])

  // ── Création : le formulaire rapide (défauts VX93, « créer un autre ») ────
  const [saving, setSaving] = useState(false)
  const [creerUnAutre, setCreerUnAutre] = useState(() => mode === 'create' && lireCreerUnAutre())
  const [savedConfirm, setSavedConfirm] = useState(false)
  const savedConfirmTimer = useRef(null)
  useEffect(() => () => { if (savedConfirmTimer.current) clearTimeout(savedConfirmTimer.current) }, [])

  const CREATE_FORM_ID = 'lw-create-form'
  const handleCreateSubmit = async (e) => {
    e.preventDefault()
    // Validation client identique à LeadForm (nom requis, email regex,
    // perdu→motif requis). SIGNED est structurellement impossible en création
    // (pas de StageControl, stage=NEW par défaut).
    const ve = {}
    if (!String(field('nom') || '').trim()) ve.nom = 'Nom requis'
    const email = String(field('email') || '').trim()
    if (email && !EMAIL_RE.test(email)) ve.email = 'Email invalide'
    if (field('perdu') && !String(field('motif_perte') || '').trim()) {
      ve.motif_perte = 'Indiquez le motif de perte'
    }
    if (Object.keys(ve).length) { setErrors(ve); return }
    setSaving(true)
    try {
      await dispatch(createLead(draft.createPayload())).unwrap()
      rememberVille(field('ville')) // VX93 — mémorise la ville pour le prochain lead
      onSaved?.()
      if (creerUnAutre) {
        // Reset COMPLET vers les défauts VX93 frais (owner=moi, ville mémorisée,
        // canal walk_in) — customData INCLUS (parité LW4, purgé par LOAD_LEAD) —
        // puis refocus #lf-nom, au lieu de fermer.
        draft.resetForCreate()
        setErrors({})
        if (savedConfirmTimer.current) clearTimeout(savedConfirmTimer.current)
        setSavedConfirm(true)
        savedConfirmTimer.current = setTimeout(() => setSavedConfirm(false), 2000)
        setTimeout(() => document.getElementById('lf-nom')?.focus(), 0)
      } else {
        onClose?.()
      }
    } catch (err) {
      setFromResponse(err)
    } finally {
      setSaving(false)
    }
  }

  const nomTitre = mode === 'edit'
    ? `Lead — ${getField(state, 'nom') || ''} ${getField(state, 'prenom') || ''}`.trim()
    : 'Nouveau lead'

  // LW34 — barre-pouce mobile (Appeler · WhatsApp · Note) : même résolution
  // téléphone que IdentityRail.jsx (callPhone/waPhone — mêmes deux lignes),
  // dupliquée ici à dessein : deux dérivations de présentation indépendantes
  // du même state, pas une logique métier partagée (aucune mutation).
  const telephoneWs = (getField(state, 'telephone') || '').trim()
  const whatsappWs = (getField(state, 'whatsapp') || '').trim()
  const callPhone = telephoneWs || whatsappWs
  const waPhone = normalizePhoneE164(whatsappWs || telephoneWs)

  // ── Rendu du contenu (partagé dialog / sheet / page) ──────────────────────
  const renderBody = (TitleComp) => (
    <div className="lw-root" ref={rootRef}>
      <header className="lw-topbar">
        <div className="lw-topbar-left">
          {mode === 'edit' && leadsQueue && (
            <span className="lw-nav">
              <IconButton
                label="Lead précédent (touche K)" variant="ghost" size="icon-sm"
                disabled={!prevInQueue} onClick={() => goToLead(prevInQueue)}
              >
                ◀
              </IconButton>
              {queueIndex >= 0 && (
                <span className="lw-nav-pos">{queueIndex + 1} / {leadsQueue.length}</span>
              )}
              <IconButton
                label="Lead suivant (touche J)" variant="ghost" size="icon-sm"
                disabled={!nextInQueue} onClick={() => goToLead(nextInQueue)}
              >
                ▶
              </IconButton>
            </span>
          )}
          {/* createElement explicite : le pipeline compilateur+no-unused-vars
              perd la référence du paramètre quand il est utilisé comme balise
              JSX dynamique (faux positif « TitleComp is never used ») —
              l'appel de fonction direct est, lui, toujours compté. */}
          {createElement(
            TitleComp,
            { className: 'modal-title lw-title' },
            nomTitre,
            (mode === 'edit' && lead?.is_archived)
              ? <span key="arch" className="lw-archived-badge">Archivé</span>
              : null,
          )}
        </div>
        <div className="lw-topbar-right">
          {/* LW34 — 768-1023 : le rail contexte quitte la grille (2 colonnes
              seulement) ; ce bouton l'ouvre en Sheet côté droit (patron
              LeadDevisPanel). Absent en dehors de ce palier — aucun état mort
              dans le DOM desktop/mobile. */}
          {mode === 'edit' && isTablet && (
            <Button
              type="button" variant="ghost" size="sm" className="lw-context-toggle"
              onClick={() => setContextSheetOpen(true)}
            >
              Contexte
            </Button>
          )}
          {mode === 'edit' && (
            <SaveChip
              saveState={saveState}
              saveError={state.saveError}
              errorField={primaryErrorField}
              onRetry={draft.retry}
            />
          )}
          <button type="button" className="modal-close" onClick={requestClose} aria-label="Fermer">✕</button>
        </div>
      </header>

      {state.restored && (
        <div role="status" className="lw-banner lw-banner--info">
          <span>Brouillon restauré — vos modifications non enregistrées ont été récupérées.</span>
          <Button type="button" size="sm" variant="ghost" onClick={draft.clearRestored}>OK</Button>
        </div>
      )}

      {state.stale && (
        <div role="alert" className="lw-banner lw-banner--warning">
          <span>
            Modifié par {state.stale.theirs || 'un autre utilisateur'} pendant votre édition —
            {' '}vérifiez avant d&apos;enregistrer.
          </span>
          <span className="lw-banner-actions">
            <Button type="button" size="sm" variant="outline" onClick={draft.dismissStale}>Revoir</Button>
            <Button type="button" size="sm" variant="outline" onClick={draft.saveAnyway}>Enregistrer quand même</Button>
          </span>
        </div>
      )}

      {mode === 'create' ? (
        <div className="lw-body lw-body--create">
          <SectionsPane
            state={state}
            setField={setField}
            errors={errors}
            mode={mode}
            focusSection={focusSection}
            formId={CREATE_FORM_ID}
            onSubmit={handleCreateSubmit}
            refData={{
              users, tagOptions, motifOptions,
              leadId: lead?.id ?? null, onOpenDuplicate, suggested: draft.suggested,
            }}
          />
        </div>
      ) : (
        // LW25 — squelette EN FORME de la vraie grille (rail identité :
        // avatar + 3 lignes ; centre : 2 cartes ; rail contexte : texte),
        // crossfade via FadeSwap. LW45 — commentaire corrigé : seul le
        // bandeau (`nomTitre`, header ci-dessus) est VRAIMENT hors de cette
        // zone body et reste visible pendant le chargement. L'IdentityRail
        // est lui DANS le FadeSwap (children ci-dessous) — masqué comme le
        // reste du corps tant que `showSkeleton` est vrai, remplacé par son
        // propre squelette (avatar + 3 lignes) le temps du GET détail.
        <FadeSwap
          loading={showSkeleton}
          className="lw-skeleton-swap"
          skeleton={(
            <div className="lw-body lw-body--edit" aria-hidden="true">
              <div className="lw-zone lw-rail-identity lw-skeleton-pane">
                <SkeletonAvatar />
                <SkeletonLine />
                <SkeletonLine />
                <SkeletonLine />
              </div>
              <div className="lw-zone lw-center lw-skeleton-pane lw-skeleton-pane--center">
                <SkeletonCard />
                <SkeletonCard />
              </div>
              <div className="lw-zone lw-rail-context lw-skeleton-pane">
                <SkeletonText lines={5} />
              </div>
            </div>
          )}
        >
          <div className="lw-body lw-body--edit">
            <IdentityRail state={state} onAction={onAction} users={users} archiveBusy={archiveBusy} />
            <SectionsPane
              state={state}
              setField={setField}
              errors={errors}
              mode={mode}
              focusSection={focusSection}
              formId={CREATE_FORM_ID}
              onSubmit={handleCreateSubmit}
              refData={{
                users, tagOptions, motifOptions,
                leadId: lead?.id ?? null, onOpenDuplicate, suggested: draft.suggested,
                // QJ-ARBRE (09/09/2026) — l'arbre « Historique en un coup
                // d'œil » (SectionPipeline, colonne droite du Suivi
                // commercial) lit le MÊME historique que TimelineTab —
                // aucun fetch supplémentaire, même précédence LW30/LW41
                // (repli chatter_recent du GET lead dans le composant).
                historique,
                // F4 — voir la déclaration de relanceVersion plus haut.
                relanceVersion,
                // MRY32 — la frise de la fiche (CadenceFrise, via
                // SectionPipeline) fait désormais elle-même Fait/Sauter/
                // Reporter/WhatsApp sur ses touches compactes : ce callback
                // lui permet de rafraîchir la FICHE ENTIÈRE (pas seulement
                // elle-même) — même geste que 'relance-cadence'/'relance-
                // arreter' ci-dessus (onAction), factorisé ici pour ne pas
                // dupliquer `draft.refreshServer()` + `setRelanceVersion`.
                onRelanceChanged: () => { draft.refreshServer(); setRelanceVersion((n) => n + 1) },
              }}
            />
            {/* LW34 — 768-1023 : le rail contexte quitte la grille 2 colonnes,
                rendu UNE SEULE FOIS (jamais dupliqué — mêmes compteurs
                Activités/Pièces, même sessionStorage d'onglet) soit ici en
                ligne (≥1024), soit dans le Sheet ci-dessous (tablette). */}
            {!isTablet && (
              <ContextRail
                state={state}
                users={users}
                historique={historique}
                refreshHistorique={refreshHistorique}
                onAction={onAction}
                // Câblage moteur (demande lane 3) : composer/wa vivent dans le
                // réducteur — le repli local de ContextRail devient inactif et
                // le miroir sessionStorage anti-perte couvre aussi la note.
                dispatch={draft.dispatch}
              />
            )}
          </div>
        </FadeSwap>
      )}

      {mode === 'edit' && isTablet && (
        <Sheet open={contextSheetOpen} onOpenChange={setContextSheetOpen}>
          <SheetContent side="right" className="lw-context-sheet">
            <SheetTitle className="sr-only">Contexte du lead</SheetTitle>
            <ContextRail
              state={state}
              users={users}
              historique={historique}
              refreshHistorique={refreshHistorique}
              onAction={onAction}
              dispatch={draft.dispatch}
            />
          </SheetContent>
        </Sheet>
      )}

      {/* LW34 — barre-pouce mobile (<768) : les 3 actions rapides du rail
          identité (☎/🟢 déjà là, plus « Note ») en sticky bas safe-area,
          toujours atteignables sans défiler le formulaire. La « Note »
          réutilise l'événement `lw:open-note-composer` déjà écouté par
          ContextRail (câblage lane 4, inchangé). */}
      {mode === 'edit' && isMobile && (
        <div className="lw-thumbbar" role="toolbar" aria-label="Actions rapides">
          {/* SUIVI-BLOCAGE (30/09/2026) — plus un `tel:` nu : le bouton ouvre la
              MÊME fenêtre d'appel que le rail (script, questions, issue) via
              l'événement `lw:open-appel` que IdentityRail écoute ; on compose
              depuis la fenêtre. Sans numéro, rien ne s'ouvre (le rail le dit). */}
          <button
            type="button"
            className="lw-thumbbar-btn"
            disabled={!callPhone}
            onClick={() => window.dispatchEvent(new CustomEvent('lw:open-appel', { detail: { leadId } }))}
          >
            <span aria-hidden="true">☎</span>
            <span>Appeler</span>
          </button>
          <button
            type="button"
            className="lw-thumbbar-btn"
            disabled={!waPhone}
            onClick={() => {
              // QJR635 — constructeur wa.me unique (lib/contactLinks).
              const url = buildWaUrl(waPhone)
              if (url) window.open(url, '_blank', 'noopener')
            }}
          >
            <span aria-hidden="true">🟢</span>
            <span>WhatsApp</span>
          </button>
          <button
            type="button"
            className="lw-thumbbar-btn"
            onClick={() => window.dispatchEvent(new Event('lw:open-note-composer'))}
          >
            <span aria-hidden="true">📝</span>
            <span>Note</span>
          </button>
        </div>
      )}

      {mode === 'create' && (
        <FormActions className="lw-footer-create">
          {/* VX224/VX92 — « Créer un autre » : création uniquement, persisté. */}
          <label className="mr-auto flex items-center gap-2 text-sm text-muted-foreground">
            <Switch
              checked={creerUnAutre}
              onCheckedChange={(v) => { setCreerUnAutre(v); ecrireCreerUnAutre(v) }}
              aria-label="Créer un autre"
            />
            Créer un autre
          </label>
          {savedConfirm && (
            <span className="lw-savechip lw-savechip--saved" role="status" aria-live="polite">
              ✓ Enregistré
            </span>
          )}
          {errors.submit && <span className="lw-footer-error" role="alert">{errors.submit}</span>}
          <Button type="button" variant="outline" onClick={requestClose}>Annuler</Button>
          <Button type="submit" form={CREATE_FORM_ID} loading={saving} disabled={saving}>
            {saving ? 'Enregistrement…' : 'Créer le lead'}
          </Button>
        </FormActions>
      )}
    </div>
  )

  // ── Satellites montés hors flux (édition uniquement) ─────────────────────
  const satellites = mode === 'edit' && (
    <>
      {devisPanel && (
        <LeadDevisPanel
          lead={state.server}
          mode={devisPanel}
          existingDevisId={(devisPanel === 'view' || devisPanel === 'edit') ? panelDevisId : null}
          targetKwc={devisKwc}
          onDevisChanged={draft.refreshServer}
          onClose={() => { setDevisPanel(null); setPanelDevisId(null); setDevisKwc(null); draft.refreshServer() }}
        />
      )}
      {signeOpen && (
        <SigneDialog
          lead={state.server}
          onClose={() => setSigneOpen(false)}
          onConfirmed={() => { setSigneOpen(false); onClose?.() }}
          onAccepted={() => onSaved?.()}
          onFailed={() => onSaved?.()}
        />
      )}
      {planOpen && (
        <PlanActiviteDialog
          lead={state.server}
          onClose={() => setPlanOpen(false)}
          onApplied={() => onSaved?.()}
        />
      )}
      {convertOpen && (
        <ConvertirClientDialog
          lead={state.server}
          onClose={() => setConvertOpen(false)}
          onConverted={draft.refreshServer}
        />
      )}
      {/* LANE Q-C — « Envoyer un questionnaire » : même state.server que les
          autres satellites (le lien porte sur les DONNÉES connues du
          serveur, pas sur un brouillon non enregistré). */}
      {questionnaireOpen && (
        <QuestionnaireDialog
          lead={state.server}
          onClose={() => setQuestionnaireOpen(false)}
        />
      )}
      {/* PV22 — plusieurs devis concevables : le commercial départage. */}
      {choixDesign && (
        <ChoisirDevisPourDesign
          open
          devis={choixDesign}
          description="Ce lead a plusieurs devis à calepiner. Choisissez celui dont la toiture doit être calepinée."
          onChoisir={(d) => {
            setChoixDesign(null)
            navigate(`/ventes/devis/${d.id}/design`)
          }}
          onClose={() => setChoixDesign(null)}
        />
      )}
      {/* PV22 — le serveur refuse de dimensionner : son message, son geste. */}
      {designBloque && (
        <DevisAutoImpossibleDialog
          open
          message={designBloque}
          onGenerateur={() => {
            setDesignBloque(null)
            navigate(`/ventes/devis/nouveau?lead=${encodeURIComponent(leadId)}`)
          }}
          onClose={() => setDesignBloque(null)}
        />
      )}
    </>
  )

  // ── Enveloppes ────────────────────────────────────────────────────────────
  if (variant === 'page') {
    return (
      <div className="lw-page">
        {renderBody('h1')}
        {satellites}
      </div>
    )
  }

  if (isMobile) {
    return (
      <>
        <Sheet open onOpenChange={(o) => { if (!o) requestClose() }}>
          <SheetContent side="bottom" showClose={false} className="lw-sheet p-0">
            {renderBody(SheetTitle)}
          </SheetContent>
        </Sheet>
        {satellites}
      </>
    )
  }

  return (
    <>
      <Dialog open onOpenChange={(o) => { if (!o) requestClose() }}>
        <DialogContent
          showClose={false}
          className="lw-dialog p-0 gap-0 overflow-hidden"
          // Le cockpit quasi-plein-écran ne se ferme JAMAIS sur un pointer
          // « extérieur » : la fermeture passe par ✕/Escape → leaveGuard.
          // Corrige aussi le bug E4 : le clic sur le ✕ du panneau devis
          // (Sheet satellite, portail frère) était vu comme une interaction
          // extérieure par la couche du Dialog parent → la fenêtre entière
          // se fermait (reproduit par sonde Playwright, Escape ne le faisait
          // pas — seule la voie pointeur).
          onPointerDownOutside={(e) => e.preventDefault()}
          onInteractOutside={(e) => e.preventDefault()}
        >
          {renderBody(DialogTitle)}
        </DialogContent>
      </Dialog>
      {satellites}
    </>
  )
}
