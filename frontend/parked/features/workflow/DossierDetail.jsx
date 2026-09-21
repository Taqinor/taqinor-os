import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  Link2, Plus, Trash2, MessageSquare, Send, ArrowLeft, ClipboardList,
} from 'lucide-react'
import coreApi from '../../api/coreApi'
import useResource from '../../hooks/useResource'
import {
  Card, CardContent, CardHeader, CardTitle, Button, IconButton, Input,
  Textarea, Badge, StatusPill, Checkbox, Spinner, toast,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import PageHeader from '../../components/layout/PageHeader'
import { formatDate, formatDateTime } from '../../lib/format'
import {
  routeForLien, STATUT_DOSSIER_OPTIONS, PRIORITE_DOSSIER_OPTIONS, estEnRetard,
} from './dossiers'

/* ============================================================================
   NTWFL19 — écran dossier transverse (`/dossiers/:id`).
   ----------------------------------------------------------------------------
   Vue unique : en-tête (statut/priorité/échéance/propriétaire, éditables en
   ligne — `coreApi.dossiers.update`, `company`/auteur toujours posés côté
   serveur), panneau « objets liés » (cartes cliquables vers la route réelle
   de la cible quand elle est connue, `dossierLinks.routeForLien`), checklist
   interactive (bascule OPTIMISTE — NTWFL17 le confirme immédiatement, l'appel
   réseau suit en tâche de fond) et chatter (`historique`/`noter`, NTWFL18).
   ========================================================================== */

function AujourdHuiISO() {
  return new Date().toISOString().slice(0, 10)
}

// Chatter local — même grammaire que le reste de l'OS (creation/modification/
// note), sans dépendre d'un module métier (contrat import-linter : `core`
// reste fondation, ce composant vit dans `workflow`, jamais dans `crm`/`qhse`).
function DossierChatter({ dossierId }) {
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(true)
  const [body, setBody] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    return coreApi.dossiers.historique(dossierId)
      .then((r) => setEntries(Array.isArray(r.data) ? r.data : (r.data?.results ?? [])))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [dossierId])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  const submit = async (e) => {
    e.preventDefault()
    const texte = body.trim()
    if (!texte || submitting) return
    setSubmitting(true)
    try {
      await coreApi.dossiers.noter(dossierId, texte)
      setBody('')
      await load()
    } catch {
      toast.error('Impossible d’ajouter la note.')
    } finally {
      setSubmitting(false)
    }
  }

  const texteEntree = (e) => {
    if (e.kind === 'note') return e.body
    if (e.kind === 'modification') {
      return `${e.field_label || e.field} : ${e.old_value || '—'} → ${e.new_value || '—'}`
    }
    if (e.kind === 'lien') return e.new_value ? `Rattaché : ${e.new_value}` : `Détaché : ${e.old_value}`
    return e.new_value || 'Dossier créé'
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <MessageSquare size={16} aria-hidden="true" />
          Historique {entries.length > 0 && `(${entries.length})`}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {loading && <p className="text-sm text-muted-foreground">Chargement…</p>}
        {!loading && entries.length === 0 && (
          <p className="text-sm text-muted-foreground">Aucune entrée.</p>
        )}
        <div className="flex max-h-80 flex-col gap-2 overflow-y-auto">
          {entries.map((e) => (
            <div key={e.id} className="border-l-2 border-border pl-3">
              <div className="flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">
                <span className="font-medium text-foreground">{e.user_username || 'Système'}</span>
                <span>{formatDateTime(e.created_at)}</span>
              </div>
              <p className="mt-0.5 whitespace-pre-wrap text-sm">{texteEntree(e)}</p>
            </div>
          ))}
        </div>
        <form className="flex flex-col gap-2" onSubmit={submit}>
          <Textarea
            rows={2}
            placeholder="Ajouter une note…"
            value={body}
            onChange={(e) => setBody(e.target.value)}
          />
          <Button type="submit" size="sm" disabled={!body.trim() || submitting} className="self-end">
            <Send size={14} aria-hidden="true" /> Noter
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}

function LiensPanel({ dossier, onChange }) {
  const [cleModele, setCleModele] = useState('')
  const [objectId, setObjectId] = useState('')
  const [libelle, setLibelle] = useState('')
  const [busy, setBusy] = useState(false)
  const liens = dossier?.liens ?? []

  const ajouter = async (e) => {
    e.preventDefault()
    const id = Number.parseInt(objectId, 10)
    if (!cleModele.trim() || !Number.isFinite(id) || id <= 0) return
    setBusy(true)
    try {
      await coreApi.dossiers.lier(dossier.id, cleModele.trim(), id, libelle.trim())
      setCleModele(''); setObjectId(''); setLibelle('')
      await onChange()
    } catch (err) {
      toast.error(err?.response?.data?.cle_modele || err?.response?.data?.object_id
        || 'Rattachement impossible.')
    } finally {
      setBusy(false)
    }
  }

  const detacher = async (lien) => {
    try {
      await coreApi.dossiers.delier(dossier.id, lien.cle_modele, lien.object_id)
      await onChange()
    } catch {
      toast.error('Détachement impossible.')
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <Link2 size={16} aria-hidden="true" />
          Objets liés {liens.length > 0 && `(${liens.length})`}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {liens.length === 0 && (
          <p className="text-sm text-muted-foreground">Aucun objet rattaché pour l’instant.</p>
        )}
        <ul className="flex flex-col gap-2">
          {liens.map((lien) => {
            const route = routeForLien(lien.cle_modele, lien.object_id)
            return (
              <li
                key={lien.id}
                className="flex items-center justify-between gap-2 rounded-lg border border-border px-3 py-2"
              >
                {route ? (
                  <a href={route} className="min-w-0 truncate text-sm font-medium text-primary underline">
                    {lien.libelle || `${lien.cle_modele} #${lien.object_id}`}
                  </a>
                ) : (
                  <span className="min-w-0 truncate text-sm">
                    {lien.libelle || `${lien.cle_modele} #${lien.object_id}`}
                  </span>
                )}
                <IconButton
                  aria-label={`Détacher ${lien.libelle || lien.cle_modele}`}
                  size="sm"
                  variant="ghost"
                  onClick={() => detacher(lien)}
                >
                  <Trash2 size={14} aria-hidden="true" />
                </IconButton>
              </li>
            )
          })}
        </ul>
        <form className="flex flex-col gap-2 border-t border-border pt-3 sm:flex-row" onSubmit={ajouter}>
          <Input
            placeholder="app_label.model (ex. crm.lead)"
            value={cleModele}
            onChange={(e) => setCleModele(e.target.value)}
            aria-label="Type d'objet à rattacher"
          />
          <Input
            placeholder="Identifiant"
            inputMode="numeric"
            value={objectId}
            onChange={(e) => setObjectId(e.target.value)}
            aria-label="Identifiant de l'objet à rattacher"
          />
          <Input
            placeholder="Libellé (optionnel)"
            value={libelle}
            onChange={(e) => setLibelle(e.target.value)}
            aria-label="Libellé du rattachement"
          />
          <Button type="submit" size="sm" disabled={busy || !cleModele.trim() || !objectId.trim()}>
            <Plus size={14} aria-hidden="true" /> Rattacher
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}

function ChecklistPanel({ dossier, setDossier, onChanged }) {
  const [libelle, setLibelle] = useState('')
  const [busy, setBusy] = useState(false)
  const items = dossier?.checklist ?? []

  const toggle = async (item) => {
    const prochain = !item.fait
    setDossier((d) => ({
      ...d,
      checklist: d.checklist.map((it) => (it.id === item.id ? { ...it, fait: prochain } : it)),
    }))
    try {
      await coreApi.dossiers.checklist.cocher(dossier.id, item.id, prochain)
    } catch {
      toast.error('Mise à jour de la checklist impossible.')
      setDossier((d) => ({
        ...d,
        checklist: d.checklist.map((it) => (it.id === item.id ? { ...it, fait: !prochain } : it)),
      }))
    }
  }

  const ajouter = async (e) => {
    e.preventDefault()
    const texte = libelle.trim()
    if (!texte) return
    setBusy(true)
    try {
      const r = await coreApi.dossiers.checklist.ajouter(dossier.id, texte, items.length)
      setDossier((d) => ({ ...d, checklist: [...(d.checklist ?? []), r.data] }))
      setLibelle('')
      onChanged?.()
    } catch {
      toast.error('Ajout de l’étape impossible.')
    } finally {
      setBusy(false)
    }
  }

  const total = items.length
  const faits = items.filter((it) => it.fait).length

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-sm">
          <ClipboardList size={16} aria-hidden="true" />
          Checklist {total > 0 && `(${faits}/${total})`}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        {items.length === 0 && (
          <p className="text-sm text-muted-foreground">Aucune étape pour l’instant.</p>
        )}
        {items.map((item) => (
          <label key={item.id} className="flex items-center gap-2 text-sm">
            <Checkbox checked={item.fait} onCheckedChange={() => toggle(item)} />
            <span className={item.fait ? 'text-muted-foreground line-through' : ''}>
              {item.libelle}
            </span>
          </label>
        ))}
        <form className="mt-2 flex gap-2" onSubmit={ajouter}>
          <Input
            placeholder="Nouvelle étape…"
            value={libelle}
            onChange={(e) => setLibelle(e.target.value)}
            aria-label="Libellé de la nouvelle étape"
          />
          <Button type="submit" size="sm" disabled={busy || !libelle.trim()}>
            <Plus size={14} aria-hidden="true" /> Ajouter
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}

export default function DossierDetail() {
  const { id } = useParams()
  const navigate = useNavigate()

  const { data, loading, error, refetch } = useResource(
    () => coreApi.dossiers.get(id),
    id,
    { select: (r) => r.data, errorMessage: 'Dossier introuvable.' },
  )

  const [dossier, setDossier] = useState(null)
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reflète la dernière réponse serveur
    if (data) setDossier(data)
  }, [data])

  const maj = async (champs) => {
    if (!dossier) return
    try {
      const r = await coreApi.dossiers.update(dossier.id, champs)
      setDossier(r.data)
    } catch {
      toast.error('Mise à jour impossible.')
    }
  }

  if (loading && !dossier) {
    return <div className="flex justify-center p-8"><Spinner /></div>
  }
  if (error || !dossier) {
    return (
      <div className="p-6">
        <p className="text-sm text-destructive">{error || 'Dossier introuvable.'}</p>
        <Button variant="outline" size="sm" className="mt-3" onClick={() => navigate('/dossiers')}>
          <ArrowLeft size={14} aria-hidden="true" /> Retour à la liste
        </Button>
      </div>
    )
  }

  const enRetard = estEnRetard(dossier, AujourdHuiISO())

  return (
    <div className="mx-auto max-w-4xl space-y-4 p-4 sm:p-6">
      <PageHeader
        title={dossier.titre}
        subtitle={dossier.type_dossier_label}
        actions={(
          <Button variant="outline" size="sm" onClick={() => navigate('/dossiers')}>
            <ArrowLeft size={14} aria-hidden="true" /> Retour
          </Button>
        )}
      />

      <Card>
        <CardContent className="flex flex-wrap items-center gap-4 pt-4 sm:pt-5">
          <div className="flex flex-col gap-1">
            <span className="text-xs text-muted-foreground">Statut</span>
            <Select value={dossier.statut} onValueChange={(v) => maj({ statut: v })}>
              <SelectTrigger className="h-8 w-40 text-xs" aria-label="Statut du dossier">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {STATUT_DOSSIER_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-xs text-muted-foreground">Priorité</span>
            <Select value={dossier.priorite} onValueChange={(v) => maj({ priorite: v })}>
              <SelectTrigger className="h-8 w-32 text-xs" aria-label="Priorité du dossier">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PRIORITE_DOSSIER_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-xs text-muted-foreground">Échéance</span>
            <div className="flex items-center gap-2">
              <span className="text-sm">{dossier.echeance ? formatDate(dossier.echeance) : '—'}</span>
              {enRetard && <StatusPill tone="danger" label="En retard" dot={false} />}
            </div>
          </div>
          <div className="flex flex-col gap-1">
            <span className="text-xs text-muted-foreground">Propriétaire</span>
            <span className="text-sm">{dossier.proprietaire_username || '—'}</span>
          </div>
          {dossier.etape_courante && (
            <div className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">Processus attaché</span>
              <Badge tone="info">{dossier.etape_courante.nom} — {dossier.etape_courante.statut_label}</Badge>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-4">
          <LiensPanel dossier={dossier} onChange={refetch} />
          <ChecklistPanel dossier={dossier} setDossier={setDossier} onChanged={refetch} />
        </div>
        <DossierChatter dossierId={dossier.id} />
      </div>
    </div>
  )
}
