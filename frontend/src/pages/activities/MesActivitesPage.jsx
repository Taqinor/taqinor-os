import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { useIsAdmin } from '../../hooks/useHasPermission'
// VX211 — « Ma file » par persona (ordre des `kind` selon le rôle) +
// départage optionnel « Victoires rapides d'abord ».
import {
  getQuickWinsPref, setQuickWinsPref, sortMaFileItems,
} from '../../features/queue/queueViews'
// VX217(a) — aperçu sans naviguer (survol desktop / appui long mobile).
import AttentionPeek from '../../features/queue/AttentionPeek'
import {
  AlarmClock, CalendarCheck2, CalendarClock, ExternalLink, PartyPopper, Sparkles, Users,
  PhoneCall, MessageCircle, ListChecks, Plus, AtSign, ClipboardCheck, Flame, FileWarning,
  HardHat, Wrench, ShoppingCart, ArrowRightLeft,
} from 'lucide-react'
import recordsApi from '../../api/recordsApi'
import {
  Button, Badge, Card, CardHeader, CardTitle, CardContent,
  EmptyState, Spinner, Input,
} from '../../ui'
import { Table } from '../reporting/Table'

// QX25 — « Mes activités » est la liste d'appels du jour : chaque ligne doit
// être prête à appeler/WhatsApper en un tap, sans ouvrir la fiche. Le
// serializer ajoute `target_phone` (numéro déjà résolu — lead, client…) ;
// on dérive tel:/wa.me localement, en silence si absent (aucun champ cassé).
const telHref = (raw) => {
  const s = String(raw ?? '').trim()
  if (!s) return null
  const cleaned = s.replace(/[^\d+]/g, '')
  return cleaned ? `tel:${cleaned}` : null
}
const waHref = (raw) => {
  const s = String(raw ?? '').trim()
  if (!s) return null
  const digits = s.replace(/\D/g, '')
  return digits ? `https://wa.me/${digits}` : null
}

// ZSAL1 — échéance par défaut de l'activité de suivi suggérée : aujourd'hui +
// le délai configuré sur le type d'activité clôturé (delai_jours, ≥ 0).
function addDaysIso(days) {
  const d = new Date()
  d.setDate(d.getDate() + (Number(days) || 0))
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

// Date du jour au format ISO (YYYY-MM-DD), pour comparer aux échéances.
const todayStr = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

// Compteur d'activités EN RETARD par responsable, à partir de la liste complète
// des activités de la société (ouvertes, échéance dépassée). Logique pure →
// alimente le panneau admin « Charge de l'équipe ».
function overdueByResponsable(activities, today = todayStr()) {
  const counts = new Map()
  for (const a of activities ?? []) {
    if (a.done) continue
    if (!a.due_date || a.due_date >= today) continue
    const nom = a.assigned_to_nom || 'Non assigné'
    counts.set(nom, (counts.get(nom) || 0) + 1)
  }
  return [...counts.entries()]
    .map(([nom, count]) => ({ nom, count }))
    .sort((a, b) => b.count - a.count)
}

// Buckets de la cockpit : clé API, libellé FR, ton (Badge / point de couleur).
const BUCKETS = [
  ['en_retard', 'En retard', 'danger'],
  ['aujourdhui', "Aujourd'hui", 'warning'],
  ['a_venir', 'À venir', 'success'],
]

const DOT = {
  danger: 'bg-destructive',
  warning: 'bg-warning',
  success: 'bg-success',
}

// Lien profond vers l'enregistrement parent de l'activité.
const targetLink = (a) => {
  if (a.target_model === 'crm.lead') return `/crm/leads?lead=${a.object_id}`
  if (a.target_model === 'crm.client') return '/crm'
  if (a.target_model === 'installations.installation') return '/chantiers'
  if (a.target_model === 'sav.ticket') return '/sav'
  return null
}

// VX83 — « Ma file » : icône + ton par famille d'item cross-module. L'urgence
// (overdue/today/upcoming) décide de la couleur, le `kind` de l'icône.
const MA_FILE_ICON = {
  activite: AlarmClock,
  approbation: ClipboardCheck,
  mention: AtSign,
  relance: PhoneCall,
  lead_chaud: Flame,
  devis_expire: FileWarning,
  // VX214 — kinds d'EXÉCUTION (chantier/intervention/DA/ticket transféré).
  chantier_assigne: HardHat,
  intervention_du_jour: Wrench,
  da_approuvee_a_commander: ShoppingCart,
  ticket_transfere: ArrowRightLeft,
}
const URGENCY_TONE = { overdue: 'danger', today: 'warning', upcoming: 'success' }
const URGENCY_DOT = {
  overdue: 'bg-destructive', today: 'bg-warning', upcoming: 'bg-success',
}

export default function MesActivitesPage() {
  const navigate = useNavigate()
  const isAdmin = useIsAdmin()
  const [data, setData] = useState({ en_retard: [], aujourdhui: [], a_venir: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  // Erreur d'ACTION (marquer fait / reporter) : distincte de l'échec de
  // chargement (qui, lui, remplace la liste par un état d'erreur).
  const [actionError, setActionError] = useState(null)
  // Reprogrammation inline d'une activité (« Reporter »).
  const [reschedId, setReschedId] = useState(null)
  const [reschedDate, setReschedDate] = useState('')
  // « Charge de l'équipe » (admin) : activités en retard par responsable, depuis
  // la liste complète des activités de la société (l'endpoint « mine » ne
  // renvoie que celles de l'utilisateur courant).
  const [teamActivities, setTeamActivities] = useState([])
  // ZSAL1 — activité de suivi proposée par le serveur (mode « suggérer » du
  // type d'activité clôturé) : { activity_type, activity_type_nom, delai_jours }.
  // null = aucune proposition en attente.
  const [suggestion, setSuggestion] = useState(null)
  const [suggestionBusy, setSuggestionBusy] = useState(false)
  // VX83 — « Ma file » : la file de travail unique cross-module (union classée
  // des activités + approbations + mentions + items commerciaux). Chargée à
  // part des buckets pour NE PAS régresser l'écran d'activités existant.
  const [maFile, setMaFile] = useState({ items: [], total: 0, resume: {} })
  // VX211 — persona (ordre des `kind`) déduite de `state.auth.role_nom` ;
  // départage « Victoires rapides d'abord » opt-in, persisté localStorage.
  const roleNom = useSelector((s) => s.auth.role_nom)
  const [quickWinsFirst, setQuickWinsFirst] = useState(getQuickWinsPref)
  const toggleQuickWins = () => {
    setQuickWinsFirst((v) => {
      const next = !v
      setQuickWinsPref(next)
      return next
    })
  }
  // VX83 — quick-add « + À faire » : créer une activité personnelle assignée à
  // soi (XKB4). `todoText` vide = formulaire replié.
  const [todoText, setTodoText] = useState('')
  const [todoDate, setTodoDate] = useState('')
  const [todoBusy, setTodoBusy] = useState(false)

  const load = () => {
    setLoading(true)
    setError(false)
    setActionError(null)
    recordsApi.getMyActivities()
      .then(r => setData(r.data))
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }

  const loadTeam = () => {
    // Liste complète (toutes les activités ouvertes de la société) ; échec
    // silencieux : la charge d'équipe est un encart secondaire, pas la page.
    recordsApi.getActivities()
      .then(r => setTeamActivities(r.data.results ?? r.data))
      .catch(() => setTeamActivities([]))
  }

  // VX83 — recharge la file unifiée (best-effort : un échec laisse la file
  // vide sans casser l'écran d'activités classique juste en dessous).
  const loadMaFile = () => {
    recordsApi.getMaFile()
      .then(r => setMaFile(r.data ?? { items: [], total: 0, resume: {} }))
      .catch(() => setMaFile({ items: [], total: 0, resume: {} }))
  }

  const reloadAll = () => {
    load()
    loadMaFile()
    if (isAdmin) loadTeam()
  }

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { load(); loadMaFile(); if (isAdmin) loadTeam() }, [isAdmin])

  const markDone = async (a) => {
    setActionError(null)
    try {
      const res = await recordsApi.markActivityDone(a.id)
      // ZSAL1 — le serveur ne CRÉE rien en mode « suggérer » : il renvoie juste
      // la proposition, à confirmer explicitement par l'utilisateur ici.
      setSuggestion(res?.data?.suggestion
        ? { ...res.data.suggestion, source: a } : null)
      reloadAll()
    } catch { setActionError('Action impossible — réessayez.') }
  }

  const dismissSuggestion = () => setSuggestion(null)

  const acceptSuggestion = async () => {
    if (!suggestion) return
    setSuggestionBusy(true)
    setActionError(null)
    try {
      await recordsApi.createActivity({
        model: suggestion.source?.target_model,
        id: suggestion.source?.object_id,
        activity_type: suggestion.activity_type,
        summary: suggestion.activity_type_nom,
        due_date: addDaysIso(suggestion.delai_jours),
      })
      setSuggestion(null)
      reloadAll()
    } catch { setActionError("La création de l'activité de suivi a échoué — réessayez.") }
    finally { setSuggestionBusy(false) }
  }

  // VX83 — quick-add « + À faire » : POST /records/activities/ SANS model/id →
  // le serveur crée une activité `personnelle` assignée à l'utilisateur courant
  // (company forcée serveur). Une file où on ne peut pas s'ajouter une tâche
  // n'est qu'une demi-file.
  const addTodo = async (e) => {
    e?.preventDefault?.()
    const txt = todoText.trim()
    if (!txt) return
    setTodoBusy(true)
    setActionError(null)
    try {
      await recordsApi.createActivity({
        summary: txt,
        ...(todoDate ? { due_date: todoDate } : {}),
      })
      setTodoText('')
      setTodoDate('')
      reloadAll()
    } catch { setActionError("L'ajout de la tâche a échoué — réessayez.") }
    finally { setTodoBusy(false) }
  }

  const openResched = (a) => {
    setReschedId(a.id)
    setReschedDate(a.due_date || todayStr())
    setActionError(null)
  }
  const cancelResched = () => { setReschedId(null); setReschedDate('') }
  const saveResched = async (a) => {
    if (!reschedDate) return
    if (reschedDate < todayStr()) {
      setActionError("L'échéance ne peut pas être dans le passé.")
      return
    }
    setActionError(null)
    try {
      await recordsApi.updateActivity(a.id, { due_date: reschedDate })
      cancelResched()
      reloadAll()
    } catch { setActionError('Action impossible — réessayez.') }
  }

  // VX210(b) — « ⏰ Plus tard » sur un item d'approbation hétérogène de « Ma
  // file » : masque-le +3 j via la table générique `SnoozedItem` (jamais
  // retiré de l'inbox dédiée /approbations elle-même). Best-effort, discret
  // (pas de picker — un délai fixe suffit ici, contrairement aux activités
  // qui ont leur propre picker complet dans `ActivitiesPanel`).
  const snoozeApprobationItem = async (it) => {
    if (it.kind !== 'approbation' || !it.source || !it.source_id) return
    const d = new Date(); d.setDate(d.getDate() + 3)
    const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    setActionError(null)
    try {
      await recordsApi.snoozeApprobation(it.source, it.source_id, iso)
      loadMaFile()
    } catch { setActionError('Action impossible — réessayez.') }
  }

  const teamOverdue = useMemo(
    () => overdueByResponsable(teamActivities), [teamActivities])

  const total = data.en_retard.length + data.aujourdhui.length + data.a_venir.length

  // VX83 — en-tête compté « X en retard · Y aujourd'hui · Z approbation(s) ».
  const resume = maFile.resume || {}

  // VX211 — ordre par persona (rôle) + départage optionnel « Victoires
  // rapides d'abord ». JAMAIS un filtre : tous les items de `maFile.items`
  // restent présents, seul leur ORDRE change. Un rôle non reconnu retombe
  // sur l'ordre global d'origine (comportement VX83 inchangé).
  const maFileItemsSorted = useMemo(
    () => sortMaFileItems(maFile.items, { roleNom, quickWinsFirst }),
    [maFile.items, roleNom, quickWinsFirst])

  return (
    <div className="page">
      <div className="page-header">
        <h2>
          <ListChecks className="mr-2 inline size-5 align-[-3px] text-muted-foreground" aria-hidden="true" />
          Ma file
          {maFile.total > 0 && <Badge tone="primary" className="ml-2 align-middle">{maFile.total}</Badge>}
        </h2>
      </div>
      <p className="mb-3 text-sm text-muted-foreground">
        {/* VX83 — en-tête unique, plus-urgent-d'abord, à travers les modules. */}
        {[
          resume.en_retard ? `${resume.en_retard} en retard` : null,
          resume.aujourdhui ? `${resume.aujourdhui} aujourd'hui` : null,
          resume.approbations ? `${resume.approbations} approbation${resume.approbations > 1 ? 's' : ''}` : null,
        ].filter(Boolean).join(' · ')
          || 'Tout ce qui vous attend, à travers les modules, du plus urgent au moins urgent.'}
      </p>

      {actionError && (
        <p className="form-error mb-3" role="alert">{actionError}</p>
      )}

      {/* VX83 — quick-add « + À faire » : promesse XKB4 rendue concrète. Une
          file où l'on ne peut pas s'ajouter une tâche est une demi-file. */}
      <form onSubmit={addTodo} className="mb-4 flex flex-wrap items-center gap-2">
        <Plus className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <Input
          className="w-auto min-w-[16rem] flex-1"
          placeholder="+ À faire — ajouter une tâche personnelle…"
          aria-label="Nouvelle tâche à faire"
          value={todoText}
          onChange={e => setTodoText(e.target.value)}
        />
        <input type="date" min={todayStr()}
               className="form-control form-control-sm w-auto"
               aria-label="Échéance de la tâche"
               value={todoDate}
               onChange={e => setTodoDate(e.target.value)} />
        <Button type="submit" size="sm"
                loading={todoBusy} disabled={todoBusy || !todoText.trim()}>
          Ajouter
        </Button>
      </form>

      {/* ZSAL1 — proposition d'activité de suivi à la clôture d'une activité
          « suggérer » : ne crée RIEN tant que l'utilisateur ne confirme pas. */}
      {suggestion && (
        <Card className="mb-4 overflow-hidden border-primary/40" role="alert">
          <CardContent className="flex flex-wrap items-center gap-2 py-3">
            <Sparkles className="size-4 shrink-0 text-primary" aria-hidden="true" />
            <span className="flex-1 text-sm">
              Planifier une suite : <strong>{suggestion.activity_type_nom}</strong>
              {' '}({addDaysIso(suggestion.delai_jours)}) ?
            </span>
            <Button size="sm" onClick={acceptSuggestion}
                    loading={suggestionBusy} disabled={suggestionBusy}>
              Planifier
            </Button>
            <Button size="sm" variant="outline" onClick={dismissSuggestion}
                    disabled={suggestionBusy}>
              Ignorer
            </Button>
          </CardContent>
        </Card>
      )}

      {/* VX83 — LA file de travail unique : union cross-module classée
          plus-urgent-d'abord (activités + approbations + mentions + relances /
          leads chauds / devis). « Ouvrir » suit le `link` fourni par le
          serveur ; décider une approbation ouvre l'écran /approbations (le
          `decider` existant). N'affiche RIEN si la file est vide (l'écran
          d'activités détaillé ci-dessous reste la vue de travail). */}
      {maFile.items.length > 0 && (
        <Card className="mb-5 overflow-hidden">
          <CardHeader className="flex-row items-center gap-2">
            <ListChecks className="size-4 text-muted-foreground" aria-hidden="true" />
            <CardTitle className="flex-1">File de travail</CardTitle>
            {/* VX211 — départage optionnel, jamais actif par défaut (le tri
                par défaut — ordre par persona puis urgence — reste inchangé
                tant que ce n'est pas coché). */}
            <label className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
              <input type="checkbox" checked={quickWinsFirst} onChange={toggleQuickWins} />
              Victoires rapides d'abord
            </label>
            <Badge tone="primary">{maFile.total}</Badge>
          </CardHeader>
          <CardContent className="p-0 sm:p-0">
            <Table
              aria-label="Ma file"
              getRowKey={(it, i) => `${it.kind}-${it.activity_id ?? it.notification_id ?? it.source_id ?? it.link ?? i}`}
              columns={[
                {
                  key: 'urgence',
                  header: '',
                  cell: (it) => (
                    <span aria-hidden="true"
                          className={`inline-block size-2 rounded-full ${URGENCY_DOT[it.urgency] || 'bg-muted'}`} />
                  ),
                },
                {
                  key: 'title',
                  header: 'À traiter',
                  cell: (it) => {
                    const Icon = MA_FILE_ICON[it.kind] || AlarmClock
                    return (
                      // VX217(a) — aperçu sans naviguer (déjà les données de
                      // l'item : client/montant/échéance quand présents).
                      <AttentionPeek item={it} onOpen={(x) => x.link && navigate(x.link)}>
                        <span className="inline-flex items-center gap-2">
                          <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                          <span>{it.title}</span>
                        </span>
                      </AttentionPeek>
                    )
                  },
                },
                {
                  key: 'due',
                  header: 'Échéance',
                  cellClassName: 'tabular-nums',
                  cell: (it) => (it.due ? String(it.due).slice(0, 10) : '—'),
                },
                {
                  key: 'montant',
                  header: 'Montant',
                  cellClassName: 'tabular-nums',
                  align: 'right',
                  cell: (it) => (it.montant ? `${it.montant} DH` : '—'),
                },
                {
                  key: 'urgency_badge',
                  header: '',
                  cell: (it) => (
                    <Badge tone={URGENCY_TONE[it.urgency] || 'neutral'}>
                      {it.urgency === 'overdue' ? 'En retard'
                        : it.urgency === 'today' ? "Aujourd'hui" : 'À venir'}
                    </Badge>
                  ),
                },
                {
                  key: 'actions',
                  header: '',
                  align: 'right',
                  cell: (it) => (
                    <span className="inline-flex items-center gap-1.5">
                      {it.kind === 'approbation' && (
                        <Button size="sm" variant="outline"
                                title="Reporter de 3 jours"
                                onClick={() => snoozeApprobationItem(it)}>
                          ⏰
                        </Button>
                      )}
                      {it.link && (
                        <Button size="sm" variant="outline" onClick={() => navigate(it.link)}>
                          <ExternalLink /> Ouvrir
                        </Button>
                      )}
                    </span>
                  ),
                },
              ]}
              rows={maFileItemsSorted}
            />
          </CardContent>
        </Card>
      )}

      {isAdmin && teamOverdue.length > 0 && (
        <Card className="mb-4 overflow-hidden">
          <CardHeader className="flex-row items-center gap-2">
            <Users className="size-4 text-muted-foreground" aria-hidden="true" />
            <CardTitle className="flex-1">Charge de l'équipe — activités en retard</CardTitle>
            <Badge tone="danger">{teamOverdue.reduce((s, r) => s + r.count, 0)}</Badge>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2 pt-3">
            {teamOverdue.map(r => (
              <span key={r.nom}
                    className="inline-flex items-center gap-1.5 rounded-full border border-border bg-muted/40 px-3 py-1 text-sm">
                <span className="font-medium">{r.nom}</span>
                <Badge tone="danger">{r.count}</Badge>
              </span>
            ))}
          </CardContent>
        </Card>
      )}

      {/* ── Écran d'activités détaillé (préservé 1:1) ──────────────────────
          Sous la file unifiée, la vue de travail « Mes activités » d'origine :
          buckets par échéance, colonne contact QX25, actions Fait/Reporter,
          moteur de tableau partagé P167. Rien n'a été retiré. */}
      <div className="page-header mt-2">
        <h3 className="text-base font-semibold">
          <AlarmClock className="mr-2 inline size-4 align-[-2px] text-muted-foreground" aria-hidden="true" />
          Mes activités
          {total > 0 && <Badge tone="primary" className="ml-2 align-middle">{total}</Badge>}
        </h3>
      </div>
      <p className="mb-3 text-sm text-muted-foreground">
        Vos activités planifiées, regroupées par échéance.
      </p>

      {loading ? (
        <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
          <Spinner /> Chargement…
        </div>
      ) : error ? (
        <EmptyState
          icon={AlarmClock}
          title="Chargement impossible"
          description="Les activités n'ont pas pu être récupérées. Réessayez."
          action={<Button size="sm" onClick={load}>Réessayer</Button>}
          className="mt-1"
        />
      ) : total === 0 ? (
        <EmptyState
          icon={PartyPopper}
          title="Aucune activité planifiée"
          description="Rien à traiter pour le moment — tout est à jour. 🎉"
          className="mt-1"
        />
      ) : (
        <div className="flex flex-col gap-5">
          {BUCKETS.map(([key, label, tone]) => (
            data[key].length > 0 && (
              <Card key={key} className="overflow-hidden">
                <CardHeader className="flex-row items-center gap-2">
                  <span aria-hidden="true" className={`size-2 rounded-full ${DOT[tone]}`} />
                  <CardTitle className="flex-1">{label}</CardTitle>
                  <Badge tone={tone}>{data[key].length}</Badge>
                </CardHeader>
                <CardContent className="p-0 sm:p-0">
                  {/* P167 — migré vers le moteur de tableau partagé. */}
                  <Table
                    aria-label={label}
                    getRowKey={(a) => a.id}
                    columns={[
                      { key: 'type', header: 'Type', cell: (a) => `${a.activity_type_icone} ${a.activity_type_nom}` },
                      { key: 'summary', header: 'Résumé', cell: (a) => a.summary || '—' },
                      { key: 'due_date', header: 'Échéance', cellClassName: 'tabular-nums', cell: (a) => a.due_date || '—' },
                      {
                        key: 'enregistrement',
                        header: 'Enregistrement',
                        cell: (a) => {
                          const link = targetLink(a)
                          return link ? (
                            <Button size="sm" variant="outline" onClick={() => navigate(link)}>
                              <ExternalLink /> {a.target_label || 'Ouvrir'}
                            </Button>
                          ) : (a.target_label || '—')
                        },
                      },
                      {
                        // QX25 — liste d'appels prête à l'emploi : tel:/wa.me
                        // directs depuis `target_phone` (résolu côté serveur),
                        // sans ouvrir la fiche. Colonne vide (rien affiché)
                        // quand aucun numéro n'est disponible.
                        key: 'contact',
                        header: '',
                        cell: (a) => {
                          const tel = telHref(a.target_phone)
                          const wa = waHref(a.target_phone)
                          if (!tel && !wa) return null
                          return (
                            <span className="inline-flex items-center gap-2">
                              {tel && (
                                <a href={tel} title="Appeler" aria-label={`Appeler ${a.target_label || ''}`}
                                   className="text-muted-foreground hover:text-foreground">
                                  <PhoneCall className="size-4" aria-hidden="true" />
                                </a>
                              )}
                              {wa && (
                                <a href={wa} target="_blank" rel="noopener noreferrer" title="Ouvrir WhatsApp"
                                   aria-label={`WhatsApp ${a.target_label || ''}`}
                                   className="text-muted-foreground hover:text-foreground">
                                  <MessageCircle className="size-4" aria-hidden="true" />
                                </a>
                              )}
                            </span>
                          )
                        },
                      },
                      {
                        key: 'actions',
                        header: '',
                        align: 'right',
                        cell: (a) => (reschedId === a.id ? (
                          <span className="inline-flex flex-wrap items-center justify-end gap-1.5">
                            <input type="date" min={todayStr()}
                                   className="form-control form-control-sm w-auto"
                                   value={reschedDate}
                                   onChange={e => setReschedDate(e.target.value)} />
                            <Button size="sm" onClick={() => saveResched(a)}>OK</Button>
                            <Button size="sm" variant="outline" onClick={cancelResched}>Annuler</Button>
                          </span>
                        ) : (
                          <span className="inline-flex flex-wrap items-center justify-end gap-1.5">
                            <Button size="sm" variant="outline" onClick={() => openResched(a)}>
                              <CalendarClock /> Reporter
                            </Button>
                            <Button size="sm" onClick={() => markDone(a)}>
                              <CalendarCheck2 /> Fait
                            </Button>
                          </span>
                        )),
                      },
                    ]}
                    rows={data[key]}
                  />
                </CardContent>
              </Card>
            )
          ))}
        </div>
      )}
    </div>
  )
}
