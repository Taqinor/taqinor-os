import { useState, useEffect, useCallback } from 'react'
import { Tabs, TabsList, TabsTrigger, TabsContent, Button } from '../../../ui'
import ActivitiesPanel from '../../../components/ActivitiesPanel'
import AttachmentsPanel from '../../../components/AttachmentsPanel'
import recordsApi from '../../../api/recordsApi'
import TimelineTab from './TimelineTab'
import DevisTab from './DevisTab'

// LW19 — Rail contexte (zone droite) : `ui/Tabs` (clavier/ARIA gratuits,
// remplace le rail maison sans ARIA — recon 04 §6) avec 4 onglets — Historique
// (défaut), Devis (N), Activités (N), Pièces (N) — mémorisation de l'onglet
// actif PAR SESSION (sessionStorage, blueprint D3). Masqué entièrement en
// création par le shell (LeadWorkspace ne rend `<ContextRail>` qu'en édition).

const TAB_KEY = 'taqinor.lw.contextTab'
const readTab = () => {
  try { return sessionStorage.getItem(TAB_KEY) || 'historique' } catch { return 'historique' }
}
const writeTab = (v) => {
  try { sessionStorage.setItem(TAB_KEY, v) } catch { /* best-effort */ }
}

// LW20/LW22 — composer (note en cours) + sélection WhatsApp DOIVENT vivre sur
// le MOTEUR (state.composer / state.wa, blueprint D2) pour que la navigation
// J/K/◀▶ (LOAD_LEAD) les vide ATOMIQUEMENT — sinon une note tapée sur le lead A
// ou une sélection de devis pourrait fuiter sur le lead B (recon 05 P1#2/#4).
// Le contrat de props actuel de `ContextRail` (LeadWorkspace.jsx, hors
// périmètre de cette lane) ne transmet PAS encore le `dispatch` du réducteur.
// On accepte un `dispatch` OPTIONNEL et ADDITIF (câblage à venir — voir le
// rapport de fin de lane) : s'il est fourni, on pilote `state.composer`/
// `state.wa` via les actions de l'engine (SET_COMPOSER/RESET_COMPOSER/
// WA_TOGGLE/WA_LANGUE/WA_PREVIEW/WA_RESET, draftCore.js) ; sinon, un repli
// LOCAL réinitialisé sur CHAQUE changement de lead (`state.leadId`) préserve
// la même garantie anti-fuite structurelle, au prix du miroir sessionStorage
// de secours (D2#6) qui reste inactif tant que `dispatch` n'est pas câblé.
export default function ContextRail({
  state, users, historique, refreshHistorique, onAction, dispatch,
}) {
  const leadId = state.leadId
  const [tab, setTab] = useState(readTab)
  const changeTab = useCallback((v) => { setTab(v); writeTab(v) }, [])

  // Câblage inter-lanes (lane 4) : « n » / actions de la palette ⌘K ouvrent
  // le bon onglet puis focusent le composer correspondant. Le focus part au
  // frame suivant (l'onglet doit être monté par Radix avant le querySelector).
  useEffect(() => {
    const openNote = () => {
      changeTab('historique')
      requestAnimationFrame(() => {
        document.querySelector('.lw-context-timeline .chatter-note-box input.form-control')?.focus()
      })
    }
    const openWa = () => {
      changeTab('devis')
      requestAnimationFrame(() => {
        document.querySelector('.lw-context-devis input[type="checkbox"]')?.focus()
      })
    }
    window.addEventListener('lw:open-note-composer', openNote)
    window.addEventListener('lw:open-whatsapp-composer', openWa)
    return () => {
      window.removeEventListener('lw:open-note-composer', openNote)
      window.removeEventListener('lw:open-whatsapp-composer', openWa)
    }
  }, [changeTab])

  const [openActivites, setOpenActivites] = useState(0)
  const [nbPieces, setNbPieces] = useState(0)

  const loadCounts = useCallback(() => {
    if (!leadId) return
    recordsApi.getActivities('crm.lead', leadId)
      .then((r) => {
        const list = r.data.results ?? r.data
        setOpenActivites(list.filter((a) => !a.done).length)
      })
      .catch(() => {})
    recordsApi.getAttachments('crm.lead', leadId)
      .then((r) => setNbPieces((r.data.results ?? r.data).length))
      .catch(() => {})
  }, [leadId])

  useEffect(() => { loadCounts() }, [loadCounts])

  const nbDevis = (state.server?.devis ?? []).length

  const [localComposer, setLocalComposer] = useState(state.composer)
  const [localWa, setLocalWa] = useState(state.wa)
  // Réinitialisation garantie à CHAQUE changement de lead (repli local
  // uniquement — l'engine se réinitialise déjà lui-même via LOAD_LEAD).
  // Motif « adjust state during render » (react-hooks v7 interdit le
  // setState synchrone en effet) — même pattern que SectionContact.
  const [localFor, setLocalFor] = useState(leadId)
  if (localFor !== leadId) {
    setLocalFor(leadId)
    setLocalComposer(state.composer)
    setLocalWa(state.wa)
  }

  const composer = dispatch ? state.composer : localComposer
  const setComposer = useCallback((patch) => {
    if (dispatch) dispatch({ type: 'SET_COMPOSER', patch })
    else setLocalComposer((c) => ({ ...c, ...patch }))
  }, [dispatch])
  const resetComposer = useCallback(() => {
    if (dispatch) dispatch({ type: 'RESET_COMPOSER' })
    else setLocalComposer({ note: '', file: null })
  }, [dispatch])

  const wa = dispatch ? state.wa : localWa
  const onWaToggle = useCallback((id) => {
    if (dispatch) { dispatch({ type: 'WA_TOGGLE', id }); return }
    setLocalWa((w) => {
      const set = new Set(w.selected)
      if (set.has(id)) set.delete(id)
      else set.add(id)
      return { ...w, selected: [...set] }
    })
  }, [dispatch])
  const onWaLangue = useCallback((langue) => {
    if (dispatch) { dispatch({ type: 'WA_LANGUE', langue }); return }
    setLocalWa((w) => ({ ...w, langue }))
  }, [dispatch])
  const onWaPreview = useCallback((preview) => {
    if (dispatch) { dispatch({ type: 'WA_PREVIEW', preview }); return }
    setLocalWa((w) => ({ ...w, preview }))
  }, [dispatch])
  const onWaReset = useCallback(() => {
    if (dispatch) { dispatch({ type: 'WA_RESET' }); return }
    setLocalWa((w) => ({ ...w, selected: [], preview: null }))
  }, [dispatch])

  return (
    <aside className="lw-zone lw-rail-context" data-testid="lw-context-rail">
      <Tabs value={tab} onValueChange={changeTab}>
        <TabsList className="lw-context-tabs">
          <TabsTrigger value="historique">Historique</TabsTrigger>
          {/* `.lead-devis-badge` + « N devis » : hook du spec e2e CI-GATED
              devis.spec.js E4 (l'ancien badge d'en-tête LeadForm a disparu
              avec LW13) — la CLASSE est le contrat, le style vient des
              tokens de l'onglet. `.is-zero` (LW31) reprend le modificateur
              atténué de l'ancien en-tête quand le lead n'a encore aucun
              devis. */}
          <TabsTrigger value="devis">
            <span className={`lead-devis-badge${nbDevis ? '' : ' is-zero'}`}>
              {nbDevis ? `${nbDevis} devis` : 'Devis'}
            </span>
          </TabsTrigger>
          <TabsTrigger value="activites">Activités{openActivites ? ` (${openActivites})` : ''}</TabsTrigger>
          <TabsTrigger value="pieces">Pièces{nbPieces ? ` (${nbPieces})` : ''}</TabsTrigger>
        </TabsList>

        <TabsContent value="historique">
          <TimelineTab
            state={state}
            historique={historique}
            refreshHistorique={refreshHistorique}
            composer={composer}
            setComposer={setComposer}
            resetComposer={resetComposer}
          />
        </TabsContent>

        <TabsContent value="devis">
          <DevisTab
            state={state}
            onAction={onAction}
            wa={wa}
            onWaToggle={onWaToggle}
            onWaLangue={onWaLangue}
            onWaPreview={onWaPreview}
            onWaReset={onWaReset}
          />
        </TabsContent>

        <TabsContent value="activites">
          <div className="lw-context-activites-head">
            <Button type="button" size="sm" variant="outline" onClick={() => onAction?.('plan')}>
              📋 Appliquer un plan
            </Button>
          </div>
          <ActivitiesPanel model="crm.lead" id={leadId} users={users} onChange={loadCounts} />
        </TabsContent>

        <TabsContent value="pieces">
          <AttachmentsPanel model="crm.lead" id={leadId} onChange={loadCounts} />
        </TabsContent>
      </Tabs>
    </aside>
  )
}
