// Module Outillage (F1) — catalogue de l'équipement DURABLE (perceuses,
// échelles, multimètres…), tenu strictement séparé du stock vendable. On suit
// chaque outil à travers les emplacements de stock existants (dépôt +
// camionnette) plus un état « En intervention ». Jamais consommé, jamais
// client-facing. Tout le texte est en français.
import { useEffect, useMemo, useState } from 'react'
import { Plus, Search, Pencil, Trash2, CalendarCheck } from 'lucide-react'
import outillageApi from '../../api/outillageApi'
import stockApi from '../../api/stockApi'
import AttachmentsPanel from '../../components/AttachmentsPanel'
import {
  Card, CardContent, Button, IconButton, Input, Textarea,
  StatusPill, EmptyState, Skeleton, Badge,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
  toast,
} from '../../ui'

const STATUTS = [
  ['disponible', 'Disponible'],
  ['en_intervention', 'En intervention'],
  ['en_reparation', 'En réparation'],
  ['perdu', 'Perdu'],
]
const STATUT_LABELS = Object.fromEntries(STATUTS)
// La couleur n'est jamais le seul signal : le libellé reste toujours affiché.
const STATUT_TONES = {
  disponible: 'success',
  en_intervention: 'neutral',
  en_reparation: 'warning',
  perdu: 'danger',
}

const EMPTY_FORM = {
  nom: '', categorie: '', asset_tag: '', numero_serie: '',
  emplacement: '', statut: 'disponible', date_achat: '', note: '',
  // FG80/WIR28 — 0 = pas de calibration périodique requise.
  intervalle_calibration_mois: 0,
}

export default function OutillagePage() {
  const [outils, setOutils] = useState([])
  const [emplacements, setEmplacements] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const [search, setSearch] = useState('')
  const [fStatut, setFStatut] = useState('__all__')
  const [fEmplacement, setFEmplacement] = useState('__all__')

  const [editing, setEditing] = useState(null) // null | {} (nouveau) | outil
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)

  const load = () => outillageApi.getOutils()
    .then((r) => { setOutils(r.data.results ?? r.data); setError(null) })
    .catch(() => setError("Impossible de charger l'outillage. Réessayez."))
    .finally(() => setLoading(false))
  useEffect(() => {
    load()
    stockApi.getEmplacements()
      .then((r) => setEmplacements((r.data.results ?? r.data).filter((e) => !e.archived)))
      .catch(() => {})
  }, [])

  // Filtrage côté client (catalogue d'outillage = petit volume).
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return outils.filter((o) => {
      if (fStatut !== '__all__' && o.statut !== fStatut) return false
      if (fEmplacement !== '__all__' && String(o.emplacement ?? '') !== fEmplacement) return false
      if (!q) return true
      return [o.nom, o.categorie, o.asset_tag, o.numero_serie]
        .some((v) => (v ?? '').toLowerCase().includes(q))
    })
  }, [outils, search, fStatut, fEmplacement])

  const openNew = () => { setForm(EMPTY_FORM); setEditing({}) }
  const openEdit = (o) => {
    setForm({
      nom: o.nom ?? '', categorie: o.categorie ?? '', asset_tag: o.asset_tag ?? '',
      numero_serie: o.numero_serie ?? '', emplacement: o.emplacement ?? '',
      statut: o.statut ?? 'disponible', date_achat: o.date_achat ?? '',
      note: o.note ?? '',
      intervalle_calibration_mois: o.intervalle_calibration_mois ?? 0,
    })
    setEditing(o)
  }
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))

  const save = async () => {
    if (!form.nom.trim()) { toast.error('Le nom de l’outil est requis.'); return }
    setSaving(true)
    const payload = {
      ...form,
      emplacement: form.emplacement === '' ? null : form.emplacement,
      date_achat: form.date_achat || null,
      intervalle_calibration_mois: Number(form.intervalle_calibration_mois) || 0,
    }
    try {
      if (editing && editing.id) {
        const r = await outillageApi.updateOutil(editing.id, payload)
        setEditing(r.data) // garde le panneau ouvert (pièces jointes accessibles)
        toast.success('Outil enregistré.')
      } else {
        const r = await outillageApi.createOutil(payload)
        setEditing(r.data) // bascule en édition → la photo devient possible
        toast.success('Outil créé.')
      }
      await load()
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? "Enregistrement impossible.")
    } finally { setSaving(false) }
  }

  const remove = async (o) => {
    if (!window.confirm(`Supprimer l’outil « ${o.nom} » ?`)) return
    try { await outillageApi.deleteOutil(o.id); toast.success('Outil supprimé.'); load() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Suppression impossible.') }
  }

  // FG80/WIR28 — enregistre une calibration (date du jour, backend
  // recalcule `date_prochaine_calibration`) et met à jour l'outil localement
  // (liste + panneau ouvert éventuel) sans recharger toute la page.
  const calibrer = async (o) => {
    try {
      const r = await outillageApi.calibrer(o.id)
      setOutils((list) => list.map((x) => (x.id === o.id ? r.data : x)))
      setEditing((cur) => (cur?.id === o.id ? r.data : cur))
      toast.success(r.data.date_prochaine_calibration
        ? `Calibration enregistrée — prochaine échéance le ${r.data.date_prochaine_calibration}.`
        : 'Calibration enregistrée.')
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? "Enregistrement de la calibration impossible.")
    }
  }

  return (
    <div className="page">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="mr-auto">
          <h1 className="text-xl font-semibold">Outillage</h1>
          <p className="text-[12.5px] text-muted-foreground">
            Équipement durable du parc — séparé du stock vendable, jamais facturé.
          </p>
        </div>
        <Button onClick={openNew}>
          <Plus className="size-4" aria-hidden="true" /> Nouvel outil
        </Button>
      </div>

      {/* ── Filtres ── */}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="relative min-w-[180px] flex-[1_1_200px]">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <Input className="pl-8" placeholder="Rechercher (nom, étiquette, n° de série)…"
            value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <div className="w-[170px]">
          <Select value={fStatut} onValueChange={setFStatut}>
            <SelectTrigger aria-label="Filtrer par statut"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">Tous les statuts</SelectItem>
              {STATUTS.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="w-[180px]">
          <Select value={fEmplacement} onValueChange={setFEmplacement}>
            <SelectTrigger aria-label="Filtrer par emplacement"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">Tous les emplacements</SelectItem>
              {emplacements.map((e) => (
                <SelectItem key={e.id} value={String(e.id)}>{e.nom}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* ── Liste ── */}
      {loading ? (
        <div className="flex flex-col gap-2">
          {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-11 w-full" />)}
        </div>
      ) : error ? (
        <EmptyState title="Erreur" description={error}
          action={<Button onClick={load}>Réessayer</Button>} />
      ) : filtered.length === 0 ? (
        <EmptyState
          title={outils.length === 0 ? 'Aucun outil' : 'Aucun résultat'}
          description={outils.length === 0
            ? 'Ajoutez votre premier outil durable.'
            : 'Aucun outil ne correspond à ces filtres.'}
          action={outils.length === 0
            ? <Button onClick={openNew}><Plus className="size-4" aria-hidden="true" /> Nouvel outil</Button>
            : undefined} />
      ) : (
        <Card>
          <CardContent className="p-0">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Outil</th>
                  <th className="m-hide">Catégorie</th>
                  <th className="m-hide">Étiquette</th>
                  <th className="m-hide">N° de série</th>
                  <th>Emplacement</th>
                  <th>Statut</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {filtered.map((o) => (
                  <tr key={o.id} className="cursor-pointer" onClick={() => openEdit(o)}>
                    <td data-label="Outil" className="font-medium">
                      <span className="inline-flex items-center gap-1.5">
                        {o.nom}
                        {/* FG80/WIR28 — conformité légale de calibration (multimètres,
                            testeurs de terre, harnais…) : `a_calibrer` vient tel quel
                            du serializer, jamais recalculé côté front. */}
                        {o.a_calibrer && <Badge tone="danger">À calibrer</Badge>}
                      </span>
                    </td>
                    <td data-label="Catégorie" className="m-hide">{o.categorie || '—'}</td>
                    <td data-label="Étiquette" className="m-hide">{o.asset_tag || '—'}</td>
                    <td data-label="N° de série" className="m-hide">{o.numero_serie || '—'}</td>
                    <td data-label="Emplacement">
                      {o.emplacement_nom || <Badge tone="neutral">Hors emplacement</Badge>}
                    </td>
                    <td data-label="Statut">
                      <StatusPill tone={STATUT_TONES[o.statut] ?? 'neutral'}
                        label={STATUT_LABELS[o.statut] ?? o.statut} />
                    </td>
                    <td className="text-right" onClick={(e) => e.stopPropagation()}>
                      {o.intervalle_calibration_mois > 0 && (
                        <IconButton size="sm" variant="ghost" label="Enregistrer une calibration"
                          onClick={() => calibrer(o)}>
                          <CalendarCheck className="size-4" aria-hidden="true" />
                        </IconButton>
                      )}
                      <IconButton size="sm" variant="ghost" label="Modifier" onClick={() => openEdit(o)}>
                        <Pencil className="size-4" aria-hidden="true" />
                      </IconButton>
                      <IconButton size="sm" variant="ghost" label="Supprimer"
                        className="text-destructive hover:text-destructive" onClick={() => remove(o)}>
                        <Trash2 className="size-4" aria-hidden="true" />
                      </IconButton>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}

      {/* ── Panneau création / édition ── */}
      <Sheet open={editing != null} onOpenChange={(o) => { if (!o) setEditing(null) }}>
        <SheetContent className="flex w-full max-w-md flex-col gap-3 overflow-y-auto">
          <SheetHeader>
            <SheetTitle>{editing?.id ? 'Modifier l’outil' : 'Nouvel outil'}</SheetTitle>
            <SheetDescription>
              Équipement durable — jamais vendu ni affiché sur un document client.
            </SheetDescription>
          </SheetHeader>

          <label className="text-sm font-medium">Nom *
            <Input className="mt-1" value={form.nom} onChange={(e) => set('nom', e.target.value)} />
          </label>
          <label className="text-sm font-medium">Catégorie
            <Input className="mt-1" value={form.categorie} placeholder="Électroportatif, Mesure, Échelle…"
              onChange={(e) => set('categorie', e.target.value)} />
          </label>
          <div className="flex gap-2">
            <label className="flex-1 text-sm font-medium">Étiquette (asset tag)
              <Input className="mt-1" value={form.asset_tag} onChange={(e) => set('asset_tag', e.target.value)} />
            </label>
            <label className="flex-1 text-sm font-medium">N° de série
              <Input className="mt-1" value={form.numero_serie} onChange={(e) => set('numero_serie', e.target.value)} />
            </label>
          </div>
          <label className="text-sm font-medium">Emplacement
            <Select value={form.emplacement === '' ? '__none__' : String(form.emplacement)}
              onValueChange={(v) => set('emplacement', v === '__none__' ? '' : v)}>
              <SelectTrigger className="mt-1"><SelectValue placeholder="Aucun" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">Aucun (en intervention / inconnu)</SelectItem>
                {emplacements.map((e) => (
                  <SelectItem key={e.id} value={String(e.id)}>{e.nom}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </label>
          <label className="text-sm font-medium">Statut
            <Select value={form.statut} onValueChange={(v) => set('statut', v)}>
              <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
              <SelectContent>
                {STATUTS.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
              </SelectContent>
            </Select>
          </label>
          <label className="text-sm font-medium">Date d’achat
            <Input type="date" className="mt-1" value={form.date_achat}
              onChange={(e) => set('date_achat', e.target.value)} />
          </label>
          <label className="text-sm font-medium">Intervalle de calibration (mois)
            <Input type="number" step="1" min="0" className="mt-1"
              value={form.intervalle_calibration_mois}
              onChange={(e) => set('intervalle_calibration_mois', e.target.value)} />
            <span className="mt-1 block text-[12px] font-normal text-muted-foreground">
              0 = pas de calibration périodique requise (multimètres, testeurs de
              terre, harnais…). Sinon, le badge « À calibrer » et le bouton
              d’enregistrement apparaissent dans la liste dès l’échéance dépassée.
            </span>
          </label>
          {editing?.id && editing?.intervalle_calibration_mois > 0 && (
            <div className="rounded-md border border-border p-2 text-[12.5px] text-muted-foreground">
              Dernière calibration : {editing.date_derniere_calibration || '—'}
              {' · '}Prochaine échéance : {editing.date_prochaine_calibration || '—'}
              {editing.a_calibrer && <Badge tone="danger" className="ml-2">À calibrer</Badge>}
            </div>
          )}
          <label className="text-sm font-medium">Note
            <Textarea className="mt-1" rows={2} value={form.note}
              onChange={(e) => set('note', e.target.value)} />
          </label>

          <div className="mt-1 flex gap-2">
            <Button onClick={save} disabled={saving}>
              {saving ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
            <Button variant="secondary" onClick={() => setEditing(null)}>Fermer</Button>
          </div>

          {/* Photo (optionnelle) via la pièce jointe générique — uniquement
              une fois l'outil créé (il faut un id pour rattacher le fichier). */}
          {editing?.id ? (
            <div className="mt-2 border-t border-border pt-3">
              <p className="mb-1.5 text-sm font-medium">Photo</p>
              <AttachmentsPanel model="outillage.outillage" id={editing.id} />
            </div>
          ) : (
            <p className="mt-2 border-t border-border pt-3 text-[12px] text-muted-foreground">
              Enregistrez l’outil pour pouvoir ajouter une photo.
            </p>
          )}
        </SheetContent>
      </Sheet>
    </div>
  )
}
