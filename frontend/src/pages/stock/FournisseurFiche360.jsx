import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { useHasPermission, useIsAdminOrResponsable } from '../../hooks/useHasPermission'
import {
  BarChart3, FileWarning, PackageCheck, Receipt, Wallet,
  Undo2, ShieldCheck, Tags, CreditCard, FileMinus2, Users, Plus,
  Pencil, Trash2,
} from 'lucide-react'
import stockApi from '../../api/stockApi'
import { formatMAD } from '../../lib/format'
import { telHref } from '../../lib/contactLinks'
import {
  Spinner, Tabs, TabsList, TabsTrigger, TabsContent,
  Card, CardHeader, CardTitle, CardContent, Stat, RelationCounters,
  Button, IconButton, Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogDescription, DialogFooter, Form, FormField, Input, Textarea,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem, Badge,
} from '../../ui'
// APX24 — en-tête UNIQUE de l'app (VX28) + accent de la famille inventaire :
// les 15 écrans Stock parlaient chacun leur propre idiome d'en-tête.
import OnboardingFournisseurWizard from '../../components/OnboardingFournisseurWizard'
import ScoreRisqueFournisseurBadge from '../../components/ScoreRisqueFournisseurBadge'
import { PageHeader } from '../../ui/PageHeader'
import { INVENTAIRE_ACCENT } from '../../features/stock/inventaireAccent'

// XPUR25 — Fiche fournisseur 360 : une page à onglets qui rassemble les
// briques déjà existantes (performance FG59, factures/solde AP, retours/avoirs,
// réceptions, documents de conformité XPUR1, accords de prix FG318) derrière
// UN endpoint d'agrégat + les endpoints détaillés déjà câblés ailleurs
// (WR4). Réservé aux rôles porteurs de la lecture stock (donnée d'achat
// INTERNE, jamais client-facing) — même garde que le reste de l'écran
// fournisseur (`FournisseursStock.jsx`).
//
// NOTE IMPORTANTE (voir docs/PLAN.md XPUR25) : l'endpoint d'agrégat
// `fournisseurs/{id}/vue-360/` N'EXISTE PAS ENCORE côté backend (BLOCKED).
// Cette page reste pleinement utilisable : le panneau résumé qui consomme
// l'agrégat affiche un état « indisponible » propre (pas de crash, pas de
// message technique) tant que l'agrégat 404, et les onglets détaillés
// continuent à fonctionner via les vrais endpoints existants.

const fmtMad = (v) => formatMAD(v)

const fmtDate = (v) => {
  if (!v) return '—'
  try { return new Date(v).toLocaleDateString('fr-FR') } catch { return '—' }
}

function frErr(err, fallback = 'Une erreur est survenue.') {
  const data = err?.response?.data
  if (!data) return fallback
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  return fallback
}

function Indisponible({ message }) {
  return (
    <p data-testid="f360-indisponible" className="text-sm text-muted-foreground">
      {message ?? 'Indisponible pour le moment.'}
    </p>
  )
}

// ── Panneau résumé — consomme l'agrégat vue-360 (BLOCKED côté backend) ──────
// VX159/VX250 — la requête (`stockApi.getFournisseur360`) est REMONTÉE au
// parent (`FournisseurFiche360`) : RelationCounters (tête de page) et ce
// panneau consomment désormais le MÊME appel réseau — jamais un second fetch
// dupliqué du même endpoint.
function ResumePanel({ data, unavailable, loading }) {
  if (loading) {
    return (
      <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
        <Spinner /> Chargement…
      </div>
    )
  }
  if (unavailable || !data) {
    return (
      <Indisponible message="Vue d'ensemble indisponible (agrégat non encore construit côté serveur)." />
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="grid gap-3 sm:grid-cols-4">
      <Stat label="BCF ouverts" value={String(data.bcf_ouverts ?? 0)} />
      <Stat label="BCF en retard" value={String(data.bcf_en_retard ?? 0)} />
      <Stat label="Réceptions attendues" value={String(data.receptions_attendues ?? 0)} />
      <Stat label="Solde dû total" value={fmtMad(data.solde_total_du)} />
      <Stat label="Factures ouvertes" value={String(data.factures_ouvertes ?? 0)} />
      <Stat label="Score performance" value={data.score_performance != null ? String(data.score_performance) : '—'} />
      <Stat label="Retours/avoirs" value={String(data.nb_retours_avoirs ?? 0)} />
      <Stat label="Accords de prix actifs" value={String(data.accords_prix_actifs ?? 0)} />
      </div>
    </div>
  )
}

// ── Onglet Performance (FG59, déjà câblé ailleurs — WR4) ────────────────────
function OngletPerformance({ fournisseurId }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    stockApi.performanceFournisseur(fournisseurId)
      .then((r) => { if (active) setData(r.data ?? null) })
      .catch((e) => { if (active) setError(frErr(e, 'Performance indisponible.')) })
    return () => { active = false }
  }, [fournisseurId])

  if (error) return <Indisponible message={error} />
  if (!data) return <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground"><Spinner /> Chargement…</div>

  const pct = (v) => (v == null ? '—' : `${v} %`)
  const jours = (v) => (v == null ? '—' : `${v} j`)

  return (
    <div className="grid gap-3 sm:grid-cols-3">
      <Stat label="Bons de commande" value={String(data.nb_bons ?? 0)} />
      <Stat label="Délai moyen de livraison" value={jours(data.avg_lead_time_days)} />
      <Stat label="Taux de remplissage" value={pct(data.fill_rate_pct)} />
      <Stat label="Retours" value={String(data.nb_retours ?? 0)} />
      <Stat label="Taux de retour" value={pct(data.return_rate_pct)} />
      <Stat label="Dépenses totales (interne)" value={fmtMad(data.total_achats_ht)} />
    </div>
  )
}

// ── Onglet BCF (ouverts + en retard) ─────────────────────────────────────────
function OngletBcf({ fournisseurId }) {
  const [items, setItems] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    stockApi.getBonsCommandeFournisseurDe(fournisseurId)
      .then((r) => { if (active) setItems(r.data?.results ?? r.data ?? []) })
      .catch((e) => { if (active) setError(frErr(e, 'Bons de commande indisponibles.')) })
    return () => { active = false }
  }, [fournisseurId])

  if (error) return <Indisponible message={error} />
  if (items === null) return <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground"><Spinner /> Chargement…</div>
  if (items.length === 0) return <Indisponible message="Aucun bon de commande." />

  return (
    <ul className="flex flex-col gap-2">
      {items.map((b) => (
        <li key={b.id} className="flex items-center justify-between rounded-md border border-border p-2 text-sm">
          <span>{b.reference ?? `BCF #${b.id}`}</span>
          <span className="text-muted-foreground">{b.statut ?? '—'}</span>
        </li>
      ))}
    </ul>
  )
}

// ── Onglet Factures / solde ───────────────────────────────────────────────
function OngletFactures({ fournisseurId }) {
  const [items, setItems] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    stockApi.getFacturesFournisseurDe(fournisseurId)
      .then((r) => { if (active) setItems(r.data?.results ?? r.data ?? []) })
      .catch((e) => { if (active) setError(frErr(e, 'Factures indisponibles.')) })
    return () => { active = false }
  }, [fournisseurId])

  if (error) return <Indisponible message={error} />
  if (items === null) return <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground"><Spinner /> Chargement…</div>
  if (items.length === 0) return <Indisponible message="Aucune facture." />

  const totalDu = items.reduce((s, f) => s + (Number(f.solde_du) || 0), 0)

  return (
    <div className="flex flex-col gap-3">
      <Stat label="Solde dû total (onglet)" value={fmtMad(totalDu)} />
      <ul className="flex flex-col gap-2">
        {items.map((f) => (
          <li key={f.id} className="flex items-center justify-between rounded-md border border-border p-2 text-sm">
            <span>{f.reference ?? `Facture #${f.id}`}</span>
            <span className="text-muted-foreground tabular-nums">{fmtMad(f.solde_du)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

// ── Onglet Retours / avoirs ───────────────────────────────────────────────
function OngletRetours({ fournisseurId }) {
  const [items, setItems] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    stockApi.getRetoursFournisseurDe(fournisseurId)
      .then((r) => { if (active) setItems(r.data?.results ?? r.data ?? []) })
      .catch((e) => { if (active) setError(frErr(e, 'Retours indisponibles.')) })
    return () => { active = false }
  }, [fournisseurId])

  if (error) return <Indisponible message={error} />
  if (items === null) return <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground"><Spinner /> Chargement…</div>
  if (items.length === 0) return <Indisponible message="Aucun retour." />

  return (
    <ul className="flex flex-col gap-2">
      {items.map((r) => (
        <li key={r.id} className="flex items-center justify-between rounded-md border border-border p-2 text-sm">
          <span>{r.reference ?? `Retour #${r.id}`}</span>
          <span className="text-muted-foreground">{r.statut ?? '—'}</span>
        </li>
      ))}
    </ul>
  )
}

// ── Onglet Acomptes (XPUR8) ───────────────────────────────────────────────
// Un acompte est rattaché à un BCF du fournisseur (pas de FK directe vers le
// fournisseur côté serveur) : le formulaire propose les BCF du fournisseur
// (déjà chargés pour l'onglet BCF). Imputation automatique à la facturation
// (`consommer_acomptes_bcf`, serveur) — pas d'action manuelle ici.
function AcompteForm({ bcfs, onClose, onSaved }) {
  const [fields, setFields] = useState({
    bon_commande: bcfs[0]?.id ? String(bcfs[0].id) : '',
    montant: '', date_versement: '', mode: 'virement', note: '',
  })
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const setField = (k, v) => setFields((f) => ({ ...f, [k]: v }))

  const submit = async (ev) => {
    ev.preventDefault()
    if (!fields.bon_commande) { setError('Un bon de commande est requis.'); return }
    const montant = Number(fields.montant)
    if (!montant || montant <= 0) { setError('Le montant doit être positif.'); return }
    setSaving(true)
    setError(null)
    try {
      await stockApi.createAcompteFournisseur({
        bon_commande: Number(fields.bon_commande),
        montant,
        date_versement: fields.date_versement || null,
        mode: fields.mode,
        note: fields.note.trim() || null,
      })
      onSaved?.()
      onClose()
    } catch (err) {
      setError(frErr(err, "L'enregistrement a échoué."))
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Nouvel acompte fournisseur</DialogTitle>
          <DialogDescription>Avance versée sur un bon de commande. Donnée interne.</DialogDescription>
        </DialogHeader>
        <Form onSubmit={submit} className="gap-4">
          <FormField label="Bon de commande" required htmlFor="acpt-bcf" fullWidth>
            <Select value={fields.bon_commande} onValueChange={(v) => setField('bon_commande', v)}>
              <SelectTrigger id="acpt-bcf"><SelectValue placeholder="Choisir un BCF…" /></SelectTrigger>
              <SelectContent>
                {bcfs.map((b) => (
                  <SelectItem key={b.id} value={String(b.id)}>
                    {b.reference ?? `BCF #${b.id}`}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FormField>
          <FormField label="Montant (MAD)" required htmlFor="acpt-montant">
            <Input id="acpt-montant" type="number" step="any" value={fields.montant}
                   onChange={(e) => setField('montant', e.target.value)} />
          </FormField>
          <FormField label="Date de versement" htmlFor="acpt-date">
            <Input id="acpt-date" type="date" value={fields.date_versement}
                   onChange={(e) => setField('date_versement', e.target.value)} />
          </FormField>
          <FormField label="Mode de paiement" htmlFor="acpt-mode">
            <Select value={fields.mode} onValueChange={(v) => setField('mode', v)}>
              <SelectTrigger id="acpt-mode"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="virement">Virement</SelectItem>
                <SelectItem value="cheque">Chèque</SelectItem>
                <SelectItem value="especes">Espèces</SelectItem>
                <SelectItem value="carte">Carte</SelectItem>
                <SelectItem value="effet">Effet / traite</SelectItem>
                <SelectItem value="autre">Autre</SelectItem>
              </SelectContent>
            </Select>
          </FormField>
          <FormField label="Note" htmlFor="acpt-note" fullWidth>
            <Textarea id="acpt-note" rows={2} value={fields.note}
                      onChange={(e) => setField('note', e.target.value)} />
          </FormField>
          {error && (
            <div role="alert" className="sm:col-span-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}
          <DialogFooter className="sm:col-span-2">
            <Button type="button" variant="ghost" onClick={onClose}>Annuler</Button>
            <Button type="submit" loading={saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</Button>
          </DialogFooter>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

function OngletAcomptes({ fournisseurId, canWrite }) {
  const [items, setItems] = useState(null)
  const [error, setError] = useState(null)
  const [bcfs, setBcfs] = useState([])
  const [showForm, setShowForm] = useState(false)

  const reload = () => {
    stockApi.getAcomptesFournisseurDe(fournisseurId)
      .then((data) => setItems(data ?? []))
      .catch((e) => setError(frErr(e, 'Acomptes indisponibles.')))
  }

  useEffect(() => {
    let active = true
    reload()
    stockApi.getBonsCommandeFournisseurDe(fournisseurId)
      .then((r) => { if (active) setBcfs(r.data?.results ?? r.data ?? []) })
      .catch(() => {})
    return () => { active = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fournisseurId])

  if (error) return <Indisponible message={error} />
  if (items === null) return <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground"><Spinner /> Chargement…</div>

  return (
    <div className="flex flex-col gap-3">
      {canWrite && (
        <div className="flex justify-end">
          <Button size="sm" disabled={bcfs.length === 0} onClick={() => setShowForm(true)}>
            <Plus className="size-4" /> Nouvel acompte
          </Button>
        </div>
      )}
      {items.length === 0 ? (
        <Indisponible message="Aucun acompte." />
      ) : (
        <ul className="flex flex-col gap-2">
          {items.map((a) => (
            <li key={a.id} className="flex items-center justify-between rounded-md border border-border p-2 text-sm">
              <span>{a.bon_commande_reference ?? `BCF #${a.bon_commande}`} · {fmtDate(a.date_versement)}</span>
              <span className="flex items-center gap-2 text-muted-foreground tabular-nums">
                {fmtMad(a.montant)}
                {Number(a.montant_consomme) > 0 && (
                  <Badge tone="success">Consommé {fmtMad(a.montant_consomme)}</Badge>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
      {showForm && (
        <AcompteForm bcfs={bcfs}
                     onClose={() => setShowForm(false)} onSaved={reload} />
      )}
    </div>
  )
}

// ── Onglet Avoirs (XPUR9 — notes de crédit AP) ─────────────────────────────
function AvoirForm({ fournisseurId, onClose, onSaved }) {
  const [fields, setFields] = useState({
    montant_ht: '', montant_tva: '', montant_ttc: '', note: '',
  })
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const setField = (k, v) => setFields((f) => ({ ...f, [k]: v }))

  const submit = async (ev) => {
    ev.preventDefault()
    const ttc = Number(fields.montant_ttc)
    if (!ttc || ttc <= 0) { setError('Le montant TTC doit être positif.'); return }
    setSaving(true)
    setError(null)
    try {
      await stockApi.createAvoirFournisseur({
        fournisseur: Number(fournisseurId),
        montant_ht: Number(fields.montant_ht) || 0,
        montant_tva: Number(fields.montant_tva) || 0,
        montant_ttc: ttc,
        note: fields.note.trim() || null,
      })
      onSaved?.()
      onClose()
    } catch (err) {
      setError(frErr(err, "L'enregistrement a échoué."))
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Nouvel avoir fournisseur</DialogTitle>
          <DialogDescription>Note de crédit AP. Donnée interne, jamais client-facing.</DialogDescription>
        </DialogHeader>
        <Form onSubmit={submit} className="gap-4">
          <FormField label="Montant HT (MAD)" htmlFor="avf-ht">
            <Input id="avf-ht" type="number" step="any" value={fields.montant_ht}
                   onChange={(e) => setField('montant_ht', e.target.value)} />
          </FormField>
          <FormField label="TVA (MAD)" htmlFor="avf-tva">
            <Input id="avf-tva" type="number" step="any" value={fields.montant_tva}
                   onChange={(e) => setField('montant_tva', e.target.value)} />
          </FormField>
          <FormField label="Montant TTC (MAD)" required htmlFor="avf-ttc">
            <Input id="avf-ttc" type="number" step="any" value={fields.montant_ttc}
                   onChange={(e) => setField('montant_ttc', e.target.value)} />
          </FormField>
          <FormField label="Note" htmlFor="avf-note" fullWidth>
            <Textarea id="avf-note" rows={2} value={fields.note}
                      onChange={(e) => setField('note', e.target.value)} />
          </FormField>
          {error && (
            <div role="alert" className="sm:col-span-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}
          <DialogFooter className="sm:col-span-2">
            <Button type="button" variant="ghost" onClick={onClose}>Annuler</Button>
            <Button type="submit" loading={saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</Button>
          </DialogFooter>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

// Petit formulaire d'imputation — réduit le solde dû d'UNE facture du même
// fournisseur (`AvoirFournisseur.imputer`, serveur).
function ImputerAvoirForm({ avoir, factures, onClose, onSaved }) {
  const [factureId, setFactureId] = useState(factures[0]?.id ? String(factures[0].id) : '')
  const [montant, setMontant] = useState('')
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  const submit = async (ev) => {
    ev.preventDefault()
    if (!factureId) { setError('Une facture est requise.'); return }
    setSaving(true)
    setError(null)
    try {
      await stockApi.imputerAvoirFournisseur(avoir.id, {
        facture: Number(factureId),
        ...(montant ? { montant: Number(montant) } : {}),
      })
      onSaved?.()
      onClose()
    } catch (err) {
      setError(frErr(err, "L'imputation a échoué."))
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Imputer l&apos;avoir {avoir.reference}</DialogTitle>
          <DialogDescription>
            Réduit le solde dû de la facture choisie (disponible : {fmtMad(avoir.montant_disponible)}).
          </DialogDescription>
        </DialogHeader>
        <Form onSubmit={submit} className="gap-4">
          <FormField label="Facture" required htmlFor="imp-facture" fullWidth>
            <Select value={factureId} onValueChange={setFactureId}>
              <SelectTrigger id="imp-facture"><SelectValue placeholder="Choisir une facture…" /></SelectTrigger>
              <SelectContent>
                {factures.map((f) => (
                  <SelectItem key={f.id} value={String(f.id)}>
                    {f.reference ?? `Facture #${f.id}`} — dû {fmtMad(f.solde_du)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </FormField>
          <FormField label="Montant (vide = maximum possible)" htmlFor="imp-montant">
            <Input id="imp-montant" type="number" step="any" value={montant}
                   onChange={(e) => setMontant(e.target.value)} />
          </FormField>
          {error && (
            <div role="alert" className="sm:col-span-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}
          <DialogFooter className="sm:col-span-2">
            <Button type="button" variant="ghost" onClick={onClose}>Annuler</Button>
            <Button type="submit" loading={saving}>{saving ? 'Imputation…' : 'Imputer'}</Button>
          </DialogFooter>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

const AVOIR_STATUT_LABELS = { brouillon: 'Brouillon', valide: 'Validé', impute: 'Imputé' }
const AVOIR_STATUT_TONE = { brouillon: 'muted', valide: 'warning', impute: 'success' }

function OngletAvoirs({ fournisseurId, canWrite }) {
  const [items, setItems] = useState(null)
  const [error, setError] = useState(null)
  const [factures, setFactures] = useState([])
  const [showForm, setShowForm] = useState(false)
  const [imputing, setImputing] = useState(null)

  const reload = () => {
    stockApi.getAvoirsFournisseurDe(fournisseurId)
      .then((r) => setItems(r.data?.results ?? r.data ?? []))
      .catch((e) => setError(frErr(e, 'Avoirs indisponibles.')))
  }

  useEffect(() => {
    let active = true
    reload()
    stockApi.getFacturesFournisseurDe(fournisseurId)
      .then((r) => { if (active) setFactures(r.data?.results ?? r.data ?? []) })
      .catch(() => {})
    return () => { active = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fournisseurId])

  const valider = async (avoir) => {
    try { await stockApi.validerAvoirFournisseur(avoir.id); reload() } catch { /* affiché via reload */ }
  }

  if (error) return <Indisponible message={error} />
  if (items === null) return <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground"><Spinner /> Chargement…</div>

  return (
    <div className="flex flex-col gap-3">
      {canWrite && (
        <div className="flex justify-end">
          <Button size="sm" onClick={() => setShowForm(true)}>
            <Plus className="size-4" /> Nouvel avoir
          </Button>
        </div>
      )}
      {items.length === 0 ? (
        <Indisponible message="Aucun avoir." />
      ) : (
        <ul className="flex flex-col gap-2">
          {items.map((a) => (
            <li key={a.id} className="flex items-center justify-between gap-2 rounded-md border border-border p-2 text-sm">
              <span className="flex items-center gap-2">
                {a.reference}
                <Badge tone={AVOIR_STATUT_TONE[a.statut] ?? 'muted'}>
                  {AVOIR_STATUT_LABELS[a.statut] ?? a.statut}
                </Badge>
              </span>
              <span className="flex items-center gap-2 text-muted-foreground tabular-nums">
                {fmtMad(a.montant_ttc)} (disponible {fmtMad(a.montant_disponible)})
                {canWrite && a.statut === 'brouillon' && (
                  <Button size="sm" variant="outline" onClick={() => valider(a)}>Valider</Button>
                )}
                {canWrite && a.statut !== 'brouillon' && Number(a.montant_disponible) > 0 && (
                  <Button size="sm" variant="outline" onClick={() => setImputing(a)}>Imputer</Button>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
      {showForm && (
        <AvoirForm fournisseurId={fournisseurId}
                   onClose={() => setShowForm(false)} onSaved={reload} />
      )}
      {imputing && (
        <ImputerAvoirForm avoir={imputing} factures={factures}
                          onClose={() => setImputing(null)} onSaved={reload} />
      )}
    </div>
  )
}

// ── Onglet Contacts (XPUR5 — N contacts par fournisseur) ────────────────────
function ContactForm({ fournisseurId, contact, onClose, onSaved }) {
  const isNew = !contact?.id
  const [fields, setFields] = useState({
    nom: contact?.nom ?? '', fonction: contact?.fonction ?? '',
    email: contact?.email ?? '', telephone: contact?.telephone ?? '',
  })
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const setField = (k, v) => setFields((f) => ({ ...f, [k]: v }))

  const submit = async (ev) => {
    ev.preventDefault()
    if (!fields.nom.trim()) { setError('Le nom est requis.'); return }
    setSaving(true)
    setError(null)
    try {
      const payload = {
        fournisseur: Number(fournisseurId),
        nom: fields.nom.trim(),
        fonction: fields.fonction.trim(),
        email: fields.email.trim() || null,
        telephone: fields.telephone.trim() || null,
      }
      if (isNew) await stockApi.createContactFournisseur(payload)
      else await stockApi.updateContactFournisseur(contact.id, payload)
      onSaved?.()
      onClose()
    } catch (err) {
      setError(frErr(err, "L'enregistrement a échoué."))
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{isNew ? 'Nouveau contact' : `Contact — ${contact.nom}`}</DialogTitle>
          <DialogDescription>
            Contact secondaire du fournisseur (le contact principal reste sur la fiche).
          </DialogDescription>
        </DialogHeader>
        <Form onSubmit={submit} className="gap-4">
          <FormField label="Nom" required htmlFor="ctf-nom" fullWidth>
            <Input id="ctf-nom" value={fields.nom} onChange={(e) => setField('nom', e.target.value)} />
          </FormField>
          <FormField label="Fonction" htmlFor="ctf-fonction">
            <Input id="ctf-fonction" value={fields.fonction} onChange={(e) => setField('fonction', e.target.value)} />
          </FormField>
          <FormField label="Email" htmlFor="ctf-email">
            <Input id="ctf-email" type="email" value={fields.email} onChange={(e) => setField('email', e.target.value)} />
          </FormField>
          <FormField label="Téléphone" htmlFor="ctf-tel">
            <Input id="ctf-tel" value={fields.telephone} onChange={(e) => setField('telephone', e.target.value)} />
          </FormField>
          {error && (
            <div role="alert" className="sm:col-span-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}
          <DialogFooter className="sm:col-span-2">
            <Button type="button" variant="ghost" onClick={onClose}>Annuler</Button>
            <Button type="submit" loading={saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</Button>
          </DialogFooter>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

function OngletContacts({ fournisseurId, canWrite }) {
  const [items, setItems] = useState(null)
  const [error, setError] = useState(null)
  const [editing, setEditing] = useState(null)

  const reload = () => {
    stockApi.getContactsFournisseurDe(fournisseurId)
      .then((r) => setItems(r.data?.results ?? r.data ?? []))
      .catch((e) => setError(frErr(e, 'Contacts indisponibles.')))
  }

  // `reload` est recréé à chaque rendu ; ne rejouer qu'au changement de fournisseur.
  // eslint-disable-next-line react-hooks/exhaustive-deps -- reload recréé par rendu
  useEffect(() => { reload() }, [fournisseurId])

  const supprimer = async (c) => {
    if (!window.confirm(`Supprimer le contact « ${c.nom} » ?`)) return
    try { await stockApi.deleteContactFournisseur(c.id); reload() } catch { /* affiché via reload */ }
  }

  if (error) return <Indisponible message={error} />
  if (items === null) return <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground"><Spinner /> Chargement…</div>

  return (
    <div className="flex flex-col gap-3">
      {canWrite && (
        <div className="flex justify-end">
          <Button size="sm" onClick={() => setEditing({})}>
            <Plus className="size-4" /> Nouveau contact
          </Button>
        </div>
      )}
      {items.length === 0 ? (
        <Indisponible message="Aucun contact secondaire." />
      ) : (
        <ul className="flex flex-col gap-2">
          {items.map((c) => (
            <li key={c.id} className="flex items-center justify-between rounded-md border border-border p-2 text-sm">
              <span>
                {c.nom}{c.fonction ? ` · ${c.fonction}` : ''}
                {c.email ? ` · ${c.email}` : ''}{c.telephone ? ` · ${c.telephone}` : ''}
              </span>
              {canWrite && (
                <span className="flex items-center gap-1">
                  <IconButton size="sm" variant="ghost" label="Modifier" onClick={() => setEditing(c)}>
                    <Pencil className="size-4" aria-hidden="true" />
                  </IconButton>
                  <IconButton size="sm" variant="ghost" label="Supprimer"
                              className="text-destructive hover:text-destructive"
                              onClick={() => supprimer(c)}>
                    <Trash2 className="size-4" aria-hidden="true" />
                  </IconButton>
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
      {editing && (
        <ContactForm fournisseurId={fournisseurId} contact={editing.id ? editing : null}
                     onClose={() => setEditing(null)} onSaved={reload} />
      )}
    </div>
  )
}

// ── Onglet Documents de conformité (XPUR1) ──────────────────────────────────
function statutExpiration(dateExpiration) {
  if (!dateExpiration) return { label: 'Sans expiration', tone: 'muted' }
  const d = new Date(dateExpiration)
  const now = new Date()
  const joursRestants = Math.floor((d - now) / (1000 * 60 * 60 * 24))
  if (joursRestants < 0) return { label: 'Expiré', tone: 'destructive' }
  if (joursRestants <= 30) return { label: `Expire dans ${joursRestants} j`, tone: 'warning' }
  return { label: 'Valide', tone: 'success' }
}

function OngletDocuments({ fournisseurId }) {
  const [items, setItems] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    stockApi.getDocumentsConformiteFournisseur(fournisseurId)
      .then((r) => { if (active) setItems(r.data?.results ?? r.data ?? []) })
      .catch((e) => { if (active) setError(frErr(e, 'Documents indisponibles.')) })
    return () => { active = false }
  }, [fournisseurId])

  if (error) return <Indisponible message={error} />
  if (items === null) return <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground"><Spinner /> Chargement…</div>
  if (items.length === 0) return <Indisponible message="Aucun document de conformité." />

  const toneClass = {
    destructive: 'text-destructive',
    warning: 'text-amber-600',
    success: 'text-emerald-600',
    muted: 'text-muted-foreground',
  }

  return (
    <ul className="flex flex-col gap-2">
      {items.map((d) => {
        const st = statutExpiration(d.date_expiration)
        return (
          <li key={d.id} className="flex items-center justify-between rounded-md border border-border p-2 text-sm">
            <span>{d.type_document ?? `Document #${d.id}`}</span>
            <span className={toneClass[st.tone]}>{st.label} · {fmtDate(d.date_expiration)}</span>
          </li>
        )
      })}
    </ul>
  )
}

// ── Onglet Accords de prix actifs (FG318) ───────────────────────────────────
// Pas de listing global côté backend aujourd'hui (`prix_convenu_fournisseur`
// est une fonction PAR PRODUIT) : tant que l'agrégat 360 n'existe pas, cet
// onglet affiche ce que l'agrégat renvoie déjà (accords_prix — liste), sinon
// un état indisponible propre.
function OngletAccordsPrix({ fournisseurId }) {
  const [data, setData] = useState(null)
  const [unavailable, setUnavailable] = useState(false)

  useEffect(() => {
    let active = true
    stockApi.getFournisseur360(fournisseurId)
      .then((r) => { if (active) setData(r.data ?? null) })
      .catch(() => { if (active) setUnavailable(true) })
    return () => { active = false }
  }, [fournisseurId])

  if (unavailable) {
    return (
      <Indisponible message="Accords de prix indisponibles (agrégat non encore construit côté serveur)." />
    )
  }
  const accords = data?.accords_prix ?? []
  if (!data) return <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground"><Spinner /> Chargement…</div>
  if (accords.length === 0) return <Indisponible message="Aucun accord de prix actif." />

  return (
    <ul className="flex flex-col gap-2">
      {accords.map((a, i) => (
        <li key={a.contrat_id ?? i} className="flex items-center justify-between rounded-md border border-border p-2 text-sm">
          <span>Produit #{a.produit_id}</span>
          <span className="text-muted-foreground tabular-nums">
            {a.prix_convenu != null ? fmtMad(a.prix_convenu) : '—'}
          </span>
        </li>
      ))}
    </ul>
  )
}

/* NTP2P29 — onglet « Onboarding » : wizard guidé sur le dossier d'entrée en
   relation (NTP2P7). Charge la fiche fournisseur pour l'étape « identité
   légale » (ICE/IF/RC/RIB, déjà portés par le référentiel). */
function OngletOnboarding({ fournisseurId }) {
  const [fournisseur, setFournisseur] = useState(null)
  useEffect(() => {
    let active = true
    stockApi.getFournisseur(fournisseurId)
      .then((r) => { if (active) setFournisseur(r.data ?? null) })
      .catch(() => { if (active) setFournisseur({ id: fournisseurId }) })
    return () => { active = false }
  }, [fournisseurId])
  if (!fournisseur) {
    return <div className="py-4 text-sm text-muted-foreground">Chargement…</div>
  }
  return <OnboardingFournisseurWizard fournisseur={fournisseur} />
}

export default function FournisseurFiche360({
  fournisseurId: fournisseurIdProp, fournisseurNom, fournisseurTelephone,
} = {}) {
  const params = useParams()
  const fournisseurId = fournisseurIdProp ?? params.id
  // ARC47 — gating via le hook partagé. Donnée d'achat INTERNE
  // (prix/solde/performance) : même garde que le reste de l'écran fournisseur —
  // responsable/admin ou droit explicite stock_voir. `hasFinePermissions`
  // (présence de codes ERP, PAS un droit) choisit la branche ; hooks
  // inconditionnels ; sémantique identique à l'origine.
  const hasFinePermissions = useSelector((s) => (s.auth.permissions || []).length > 0)
  const canViewViaPerm = useHasPermission('stock_voir')
  const canViewViaRole = useIsAdminOrResponsable()
  const canView = hasFinePermissions ? canViewViaPerm : canViewViaRole
  // WIR108 — acomptes/avoirs/contacts : même garde en écriture que le reste
  // de l'écran fournisseur (`FournisseursStock.jsx`).
  const canWriteViaPerm = useHasPermission('stock_modifier')
  const canWriteViaRole = useIsAdminOrResponsable()
  const canWrite = hasFinePermissions ? canWriteViaPerm : canWriteViaRole
  // VX108 — tap-to-call : la fiche n'affichait aucun téléphone.
  const tel = telHref(fournisseurTelephone)

  // VX159/VX250 — remonté depuis ResumePanel : RelationCounters (tête de
  // page) ET le panneau résumé consomment le MÊME fetch, jamais un doublon.
  const [resumeData, setResumeData] = useState(null)
  const [resumeUnavailable, setResumeUnavailable] = useState(false)
  const [resumeLoading, setResumeLoading] = useState(true)
  useEffect(() => {
    if (!fournisseurId || !canView) return undefined
    let active = true
    stockApi.getFournisseur360(fournisseurId)
      .then((r) => { if (active) setResumeData(r.data ?? null) })
      .catch(() => { if (active) setResumeUnavailable(true) })
      .finally(() => { if (active) setResumeLoading(false) })
    return () => { active = false }
  }, [fournisseurId, canView])

  // NTP2P8 — score de risque (0-100) affiché en badge sous le titre. En cas
  // d'échec on laisse `null` : le badge disparaît plutôt que d'afficher un
  // score faux.
  const [scoreRisque, setScoreRisque] = useState(null)
  useEffect(() => {
    if (!fournisseurId || !canView) return undefined
    let active = true
    stockApi.getScoreRisqueFournisseur(fournisseurId)
      .then((r) => { if (active) setScoreRisque(r.data ?? null) })
      .catch(() => { if (active) setScoreRisque(null) })
    return () => { active = false }
  }, [fournisseurId, canView])

  const tabs = useMemo(() => ([
    { value: 'performance', label: 'Performance', icon: BarChart3, Comp: OngletPerformance },
    { value: 'bcf', label: 'Bons de commande', icon: PackageCheck, Comp: OngletBcf },
    { value: 'factures', label: 'Factures / solde', icon: Receipt, Comp: OngletFactures },
    { value: 'retours', label: 'Retours', icon: Undo2, Comp: OngletRetours },
    { value: 'acomptes', label: 'Acomptes', icon: CreditCard, Comp: OngletAcomptes },
    { value: 'avoirs', label: 'Avoirs', icon: FileMinus2, Comp: OngletAvoirs },
    { value: 'contacts', label: 'Contacts', icon: Users, Comp: OngletContacts },
    { value: 'documents', label: 'Conformité', icon: ShieldCheck, Comp: OngletDocuments },
    // NTP2P29 — wizard d'onboarding (dossier NTP2P7). Contextuelle : atteinte
    // par la fiche fournisseur, jamais une route autonome.
    { value: 'onboarding', label: 'Onboarding', icon: ShieldCheck, Comp: OngletOnboarding },
    { value: 'prix', label: 'Accords de prix', icon: Tags, Comp: OngletAccordsPrix },
  ]), [])

  if (!fournisseurId) {
    return (
      <div className="ui-root px-4 py-5 sm:px-5">
        <Indisponible message="Fournisseur introuvable." />
      </div>
    )
  }

  if (!canView) {
    return (
      <div className="ui-root px-4 py-5 sm:px-5">
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          <FileWarning className="mr-1.5 inline size-4" aria-hidden="true" />
          Réservé aux rôles habilités (achats/stock).
        </div>
      </div>
    )
  }

  return (
    <div className="ui-root flex flex-col gap-4 px-4 py-5 sm:px-5">
      {/* APX24 — en-tête UNIQUE de l'app (VX28) + icône et accent de la
          famille inventaire ; le niveau de titre (h1) est conservé. */}
      <PageHeader
        style={{ '--module-accent': INVENTAIRE_ACCENT }}
        className="app-accent-rail mb-0"
        headingAs="h1"
        icon={Wallet}
        title={`Fiche fournisseur 360${fournisseurNom ? ` — ${fournisseurNom}` : ''}`}
        subtitle="Vue d'ensemble achats — donnée interne, jamais client-facing."
      >
        {tel && (
          <p className="text-sm">
            <a href={tel} className="link-blue" title="Appeler">☎ {fournisseurTelephone}</a>
          </p>
        )}
        {/* NTP2P8 — badge de score de risque + détail des facteurs. */}
        <ScoreRisqueFournisseurBadge data={scoreRisque} />
        {/* VX159/VX250 — RelationCounters : réutilise `resumeData` (même fetch
            que ResumePanel ci-dessous, jamais un doublon). L'agrégat 360 est
            BLOCKED côté backend (voir note en tête de fichier) : ces
            compteurs restent simplement absents tant qu'il 404 (jamais un
            zéro trompeur). Pas de `to` : BonsCommandeFournisseur.jsx/
            FacturesFournisseur.jsx n'ont pas de filtre par fournisseur (hors
            périmètre de cette tâche) — jamais un lien qui MENT sur un
            pré-filtre qu'il n'applique pas. */}
        {resumeData && (
          <RelationCounters
            className="mt-2"
            counters={[
              { label: 'bons de commande ouverts', count: resumeData.bcf_ouverts ?? 0 },
              { label: 'factures ouvertes', count: resumeData.factures_ouvertes ?? 0 },
              { label: 'retours/avoirs', count: resumeData.nb_retours_avoirs ?? 0 },
            ]}
          />
        )}
      </PageHeader>

      <Card>
        <CardHeader>
          <CardTitle>Vue d&apos;ensemble</CardTitle>
        </CardHeader>
        <CardContent>
          <ResumePanel data={resumeData} unavailable={resumeUnavailable} loading={resumeLoading} />
        </CardContent>
      </Card>

      <Tabs defaultValue="performance">
        <TabsList data-testid="f360-tabs-list">
          {tabs.map((t) => (
            <TabsTrigger key={t.value} value={t.value}>
              <t.icon className="mr-1.5 size-4" aria-hidden="true" />
              {t.label}
            </TabsTrigger>
          ))}
        </TabsList>
        {tabs.map((t) => (
          <TabsContent key={t.value} value={t.value} data-testid={`f360-tab-${t.value}`}>
            <t.Comp fournisseurId={fournisseurId} canWrite={canWrite} />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  )
}
