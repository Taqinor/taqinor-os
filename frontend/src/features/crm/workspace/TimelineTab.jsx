import { useMemo, useState, useEffect, useLayoutEffect, useRef, useCallback } from 'react'
import { Paperclip } from 'lucide-react'
import { Button, IconButton, HelpTip } from '../../../ui'
// EZ15 — dictée INLINE navigateur (bureau). Frontière avec NTMOB30, qui
// possède le TERRAIN (enregistrement + transcription serveur) : jamais deux
// boutons micro sur un même champ.
import { DictationButton, DICTATION_PRIVACY_FR } from '../../../ui/DictationButton'
import api from '../../../api/axios'
import crmApi from '../../../api/crmApi'
import marketingApi from '../../../api/marketingApi'
import CallLogPopover from '../CallLogPopover'
import ChatterTimeline, { parseMarketingTouch } from '../../../components/ChatterTimeline'
import { formatDate } from '../../../lib/format'
import { toastError, errorMessageFrom } from '../../../lib/toast'

// LW20 — Onglet Historique : le chatter devient le fil unique — en-tête
// multi-touch (points-contact/), filtre par type persisté, notes épinglées en
// tête (backend LW28) via `ChatterTimeline`'s `pinned`/`onTogglePin`, composer
// (note + pièce jointe + CallLogPopover) porté tel quel — SAUF que l'état du
// composer vient du MOTEUR (`props.composer`, jamais un `useState` local) :
// une note tapée sur un lead ne peut plus structurellement fuiter sur un
// autre (blueprint D2, recon 05 P1#4).

const FILTER_KEY = 'taqinor.lw.timelineFilter'
const readFilter = () => {
  try { return localStorage.getItem(FILTER_KEY) || 'tous' } catch { return 'tous' }
}
const writeFilter = (v) => {
  try { localStorage.setItem(FILTER_KEY, v) } catch { /* best-effort */ }
}

// eslint-disable-next-line react-refresh/only-export-components -- constante co-localisée (testable), même motif que ChatterTimeline.OUTCOME_LABELS
export const TIMELINE_FILTERS = [
  { key: 'tous', label: 'Tous' },
  { key: 'notes', label: 'Notes' },
  { key: 'appels', label: 'Appels' },
  { key: 'emails', label: 'E-mails' },
  { key: 'devis', label: 'Devis' },
  { key: 'systeme', label: 'Système' },
]

// Logique pure co-localisée (même motif que `ChatterTimeline.parseMarketingTouch`) :
// testable sans DOM, sans réseau.
// eslint-disable-next-line react-refresh/only-export-components -- logique pure co-localisée (testable)
export function matchesTimelineFilter(kind, filterKey) {
  switch (filterKey) {
    case 'notes': return kind === 'note'
    case 'appels': return kind === 'appel'
    case 'emails': return kind === 'email'
    case 'devis': return typeof kind === 'string' && kind.startsWith('devis_')
    case 'systeme': return kind === 'creation' || kind === 'modification'
    default: return true
  }
}

const NOTE_ACCEPT = 'application/pdf,image/png,image/jpeg,image/webp'

// PACT104 — vocabulaire STRICTEMENT réutilisé de `Lead.Canal` (aucun nouveau
// jeu de valeurs inventé — même contrat que le serveur, `models.py:282`).
const CANAL_OPTIONS = [
  ['meta_ads', 'Publicité Meta'],
  ['whatsapp_ctwa', 'WhatsApp/CTWA'],
  ['site_web', 'Site web'],
  ['reference', 'Référence'],
  ['telephone', 'Téléphone'],
  ['walk_in', 'Visite/Walk-in'],
  ['autre', 'Autre'],
]

export default function TimelineTab({
  state, historique, refreshHistorique, composer, setComposer, resetComposer,
}) {
  const leadId = state.leadId

  // LW30 — `chatter_recent` (embarqué sur le GET du lead) alimente le PREMIER
  // rendu sans attendre le round-trip `/historique/` ; dès que `historique`
  // (rafraîchi par le shell au montage, et par nos propres actions) a des
  // entrées, il devient la source (plus complet — jusqu'à N entrées, pas
  // limité à 50, et déjà rafraîchi après une action locale).
  const chatterRecent = state.server?.chatter_recent
  const entries = useMemo(
    () => ((historique && historique.length > 0) ? historique : (chatterRecent ?? [])),
    [historique, chatterRecent],
  )

  const [filter, setFilter] = useState(readFilter)
  const changeFilter = useCallback((key) => { setFilter(key); writeFilter(key) }, [])
  const filtered = entries.filter((a) => matchesTimelineFilter(a.kind, filter))

  // FG204 — en-tête « 1er contact / dernier contact / N touches ». GET
  // paresseux (une fois par lead), silencieux si vide ou en erreur (jamais de
  // toast pour un enrichissement passif).
  const [touch, setTouch] = useState(null)
  // Reset pendant le rendu (jamais de setState synchrone en effet — lint v7),
  // le GET paresseux reste en effet avec garde d'annulation.
  const [touchFor, setTouchFor] = useState(leadId)
  if (touchFor !== leadId) {
    setTouchFor(leadId)
    setTouch(null)
  }
  useEffect(() => {
    if (!leadId) return undefined
    let cancelled = false
    crmApi.getLeadPointsContact(leadId)
      .then((r) => { if (!cancelled) setTouch(r.data) })
      .catch(() => {})
    return () => { cancelled = true }
  }, [leadId])

  // PACT104 — la collection racine `/crm/points-contact/` (créer un point de
  // contact) n'avait aucun appelant : la lecture agrégée ci-dessus était
  // câblée, l'écriture manquait. Un point ajouté ici recharge IMMÉDIATEMENT
  // le résumé multi-touch déjà affiché ci-dessus — jamais un second calcul
  // d'attribution côté client.
  const [pcOpen, setPcOpen] = useState(false)
  const [pcForm, setPcForm] = useState({ canal: 'site_web', source: '', detail: '' })
  const [pcSaving, setPcSaving] = useState(false)

  const ajouterPointContact = useCallback((event) => {
    event.preventDefault()
    if (!leadId) return
    setPcSaving(true)
    crmApi.createPointContact({
      lead: leadId, canal: pcForm.canal, source: pcForm.source, detail: pcForm.detail,
    })
      .then(() => crmApi.getLeadPointsContact(leadId))
      .then((r) => {
        setTouch(r.data)
        setPcForm({ canal: 'site_web', source: '', detail: '' })
        setPcOpen(false)
      })
      .catch((err) => toastError(errorMessageFrom(
        err, "Le point de contact n'a pas pu être enregistré — réessayez.")))
      .finally(() => setPcSaving(false))
  }, [leadId, pcForm])

  // NTMKT11 — lien cliquable vers la campagne/séquence source d'une touche
  // marketing reconnue dans une note (voir `ChatterTimeline.parseMarketingTouch`).
  // Résolu PARESSEUSEMENT une seule fois, seulement si le chatter contient au
  // moins une touche marketing (aucun appel réseau sinon).
  const [marketingLookup, setMarketingLookup] = useState(null)
  useEffect(() => {
    if (marketingLookup) return
    const aUneToucheMarketing = entries.some((a) => a.kind === 'note' && parseMarketingTouch(a.body))
    if (!aUneToucheMarketing) return
    Promise.all([marketingApi.campagnes.list(), marketingApi.sequences.list()])
      .then(([campagnesRes, sequencesRes]) => {
        const campagnes = marketingApi.unwrapList(campagnesRes)
        const sequences = marketingApi.unwrapList(sequencesRes)
        const parNom = (liste) => {
          const map = {}
          for (const item of liste) {
            map[item.nom] = map[item.nom] === undefined ? item.id : null
          }
          return map
        }
        setMarketingLookup({ campagnes: parNom(campagnes), sequences: parNom(sequences) })
      })
      .catch(() => setMarketingLookup({ campagnes: {}, sequences: {} }))
  }, [entries, marketingLookup])

  const resolveMarketingLink = useCallback((type, nom) => {
    if (!marketingLookup) return null
    const id = type === 'campagne' ? marketingLookup.campagnes[nom] : marketingLookup.sequences[nom]
    if (!id) return null
    return type === 'campagne' ? `/marketing/campagnes/${id}` : `/marketing/sequences/${id}`
  }, [marketingLookup])

  // ── Épingler / désépingler (backend LW28) ────────────────────────────────
  const togglePin = useCallback((item) => {
    if (!leadId) return
    const path = item.pinned ? 'desepingler' : 'epingler'
    api.post(`/crm/leads/${leadId}/activites/${item.id}/${path}/`)
      .then(() => refreshHistorique?.())
      .catch((err) => toastError(errorMessageFrom(err, "L'action n'a pas pu être effectuée — réessayez.")))
  }, [leadId, refreshHistorique])

  // ── Composer (note + pièce jointe VX111 + CallLogPopover) — état MOTEUR ──
  const noteFileInputRef = useRef(null)
  const [posting, setPosting] = useState(false)
  const [callLogOpen, setCallLogOpen] = useState(false)

  /* ORDRE FONDATEUR 2026-08-01 — la zone de note grandit avec ce qu'on y
     écrit. On remet la hauteur à `auto` AVANT de lire `scrollHeight` : sans
     ça on mesure la hauteur qu'on a soi-même posée au frame précédent, et le
     champ ne peut plus jamais RÉTRÉCIR (l'erreur classique de l'autosize).
     Les BORNES ne sont pas ici : `min-height`/`max-height` vivent en CSS, en
     `em`, donc solidaires de la taille de police et du zoom — et c'est le
     `max-height` qui produit le défilement interne au-delà de ~8 lignes,
     sans aucun calcul de lignes en JS. `useLayoutEffect` (et non `useEffect`)
     : la mesure se fait avant la peinture, le champ ne saute jamais. */
  const noteRef = useRef(null)
  useLayoutEffect(() => {
    const el = noteRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight}px`
  }, [composer.note])

  const postNote = useCallback(() => {
    if (!leadId) return
    const body = (composer.note || '').trim()
    if (!body && !composer.file) return
    setPosting(true)
    const done = () => {
      resetComposer()
      if (noteFileInputRef.current) noteFileInputRef.current.value = ''
      refreshHistorique?.()
      setPosting(false)
    }
    const fail = (err) => {
      toastError(errorMessageFrom(err, "La note n'a pas pu être enregistrée — réessayez."))
      setPosting(false)
    }
    if (composer.file) {
      const form = new FormData()
      form.append('body', body)
      form.append('file', composer.file)
      api.post(`/crm/leads/${leadId}/noter/`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      }).then(done).catch(fail)
    } else {
      api.post(`/crm/leads/${leadId}/noter/`, { body }).then(done).catch(fail)
    }
  }, [leadId, composer, resetComposer, refreshHistorique])

  return (
    <div className="lw-context-timeline">
      {touch && touch.count > 0 && (
        <div className="lw-context-touch-summary">
          <span>1er contact&nbsp;: {formatDate(touch.timeline?.[0]?.date_contact)}</span>
          <span>
            Dernier contact&nbsp;:
            {' '}{formatDate(touch.timeline?.[touch.timeline.length - 1]?.date_contact)}
          </span>
          <span>{touch.count} touche{touch.count > 1 ? 's' : ''}</span>
        </div>
      )}

      <div className="lw-context-touch-add">
        <Button type="button" variant="ghost" size="sm" onClick={() => setPcOpen((o) => !o)}>
          {pcOpen ? 'Annuler' : 'Ajouter un point de contact'}
        </Button>
        {pcOpen && (
          <form onSubmit={ajouterPointContact} className="lw-context-touch-form">
            <select
              value={pcForm.canal}
              onChange={(e) => setPcForm({ ...pcForm, canal: e.target.value })}
              aria-label="Canal du point de contact"
            >
              {CANAL_OPTIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
            <input
              placeholder="Source (ex. campagne Meta)"
              value={pcForm.source}
              onChange={(e) => setPcForm({ ...pcForm, source: e.target.value })}
              aria-label="Source du point de contact"
            />
            <input
              placeholder="Détail"
              value={pcForm.detail}
              onChange={(e) => setPcForm({ ...pcForm, detail: e.target.value })}
              aria-label="Détail du point de contact"
            />
            <Button type="submit" disabled={pcSaving}>
              {pcSaving ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
          </form>
        )}
      </div>

      <div className="lw-context-filter" role="group" aria-label="Filtrer l'historique">
        {TIMELINE_FILTERS.map((f) => (
          <button
            key={f.key}
            type="button"
            className={`lw-context-filter-chip${filter === f.key ? ' is-active' : ''}`}
            aria-pressed={filter === f.key}
            onClick={() => changeFilter(f.key)}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="chatter-note-box">
        {/* ORDRE FONDATEUR 2026-08-01 — « la zone de NOTE est trop petite ».
            C'était une <input> d'UNE ligne de 36 px : on y écrit le compte
            rendu d'un appel, et on ne relisait jamais que les huit derniers
            mots tapés. C'est un <textarea> qui s'ouvre sur TROIS lignes et
            grandit avec le texte jusqu'à huit, puis défile — les bornes
            vivent en CSS (en `em`, donc solidaires de la taille de police),
            le JS ne fait que suivre le contenu.
            Conséquence directe : Entrée écrit une NOUVELLE LIGNE (sinon une
            note multiligne serait impossible à taper). L'envoi passe par
            Ctrl/⌘+Entrée — la convention de tous les composers — et par le
            bouton « Noter », qui n'a jamais bougé. */}
        <textarea
          ref={noteRef}
          className="form-control chatter-note-input"
          rows={3}
          placeholder="Écrire une note (appel, commentaire…)"
          value={composer.note}
          onChange={(e) => setComposer({ note: e.target.value })}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
              e.preventDefault()
              postNote()
            }
          }}
        />
        {/* ORDRE FONDATEUR 2026-08-02 — « il faut que ça tienne sur TOUTE la
            ligne » : le champ occupe seul sa rangée (pleine largeur), les
            actions (dictée · trombone · Noter) vivent sur une rangée dédiée
            en dessous, alignées à droite sous la fin du texte. */}
        <div className="chatter-note-actions">
        {/* EZ15 — dictée inline au BUREAU. Le bouton n'existe pas sur un
            navigateur sans Web Speech (Firefox) : le champ est alors
            strictement celui d'avant. Le texte s'AJOUTE (jamais un
            remplacement) — on peut dicter après avoir tapé, et l'inverse. */}
        <DictationButton
          label="Dicter la note"
          onText={(txt) => setComposer({
            note: composer.note ? `${composer.note} ${txt}` : txt,
          })}
        />
        <HelpTip label="Confidentialité de la dictée">{DICTATION_PRIVACY_FR}</HelpTip>
        <input
          ref={noteFileInputRef}
          type="file"
          accept={NOTE_ACCEPT}
          className="chatter-note-file-input"
          aria-label="Joindre un fichier à la note"
          onChange={(e) => setComposer({ file: e.target.files?.[0] ?? null })}
        />
        <IconButton
          type="button"
          variant="outline"
          label="Attacher une pièce jointe à la note"
          onClick={() => noteFileInputRef.current?.click()}
        >
          <Paperclip aria-hidden="true" size={16} />
        </IconButton>
        <Button type="button" variant="outline" disabled={posting} onClick={postNote}>
          {posting ? '…' : 'Noter'}
        </Button>
        <CallLogPopover
          leadId={leadId}
          open={callLogOpen}
          onOpenChange={setCallLogOpen}
          onLogged={refreshHistorique}
        />
        </div>
      </div>
      {composer.file && (
        <p className="chatter-note-file-preview" data-testid="chatter-note-file-preview">
          <Paperclip size={12} aria-hidden="true" /> {composer.file.name}
          <button
            type="button"
            className="chatter-note-file-clear"
            aria-label="Retirer la pièce jointe"
            onClick={() => {
              setComposer({ file: null })
              if (noteFileInputRef.current) noteFileInputRef.current.value = ''
            }}
          >
            ✕
          </button>
        </p>
      )}

      <ChatterTimeline
        entries={filtered}
        resolveMarketingLink={resolveMarketingLink}
        pinned
        onTogglePin={togglePin}
      />
    </div>
  )
}
