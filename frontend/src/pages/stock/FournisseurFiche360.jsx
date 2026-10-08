import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { useHasPermission, useIsAdmin, useIsAdminOrResponsable } from '../../hooks/useHasPermission'
import { useVoitPrixAchat } from '../../features/stock/useVoitPrixAchat'
import {
  BarChart3, FileWarning, PackageCheck, Receipt, Wallet,
  Undo2, ShieldCheck, Tags, CreditCard, FileMinus2, Users, Plus,
  Pencil, Trash2, Check, X, Download, Upload,
} from 'lucide-react'
import stockApi from '../../api/stockApi'
import { formatDate, formatMAD } from '../../lib/format'
import { ConfirmDialog } from '../../ui/ConfirmDialog'
import { telHref } from '../../lib/contactLinks'
import { downloadBlobInGesture } from '../../utils/downloadBlob'
import {
  Spinner, Tabs, TabsList, TabsTrigger, TabsContent,
  Card, CardHeader, CardTitle, CardContent, Stat, RelationCounters,
  Button, IconButton, Dialog, DialogContent, DialogHeader, DialogTitle,
  DialogDescription, DialogFooter, Form, FormField, Input, Textarea,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem, Badge,
  Checkbox, FileUpload,
} from '../../ui'
// APX24 — en-tête UNIQUE de l'app (VX28) + accent de la famille inventaire :
// les 15 écrans Stock parlaient chacun leur propre idiome d'en-tête.
import OnboardingFournisseurWizard from '../../components/OnboardingFournisseurWizard'
import ScoreRisqueFournisseurBadge from '../../components/ScoreRisqueFournisseurBadge'
import { PageHeader } from '../../ui/PageHeader'
import { INVENTAIRE_ACCENT } from '../../features/stock/inventaireAccent'
// ASTK231 — confirmations par l'AlertDialog commune (aucune boîte native).
import { useConfirmation } from '../../features/stock/useConfirmation'

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

  // ASTK15 — soldes masqués (sans `prix_achat_voir`) : « — », jamais 0,00.
  const soldesConnus = items.some((f) => f.solde_du !== undefined)
  const totalDu = soldesConnus
    ? items.reduce((s, f) => s + (Number(f.solde_du) || 0), 0)
    : null

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
// WIR222/XPUR9 — « Générer l'avoir » sur un retour validé. `avoirsGeneres`
// (Set d'ids, LOCAL à cette session) évite un second clic garanti-refusé sans
// exiger de champ « a un avoir » côté serializer — un rechargement de page
// retombe honnêtement sur le 400 serveur, affiché tel quel.
function OngletRetours({ fournisseurId, canWrite }) {
  const [items, setItems] = useState(null)
  const [error, setError] = useState(null)
  const [avoirsGeneres, setAvoirsGeneres] = useState(() => new Set())
  const [generatingId, setGeneratingId] = useState(null)
  const [genError, setGenError] = useState(null)

  useEffect(() => {
    let active = true
    stockApi.getRetoursFournisseurDe(fournisseurId)
      .then((r) => { if (active) setItems(r.data?.results ?? r.data ?? []) })
      .catch((e) => { if (active) setError(frErr(e, 'Retours indisponibles.')) })
    return () => { active = false }
  }, [fournisseurId])

  const genererAvoir = async (retour) => {
    setGeneratingId(retour.id); setGenError(null)
    try {
      await stockApi.genererAvoirDepuisRetour(retour.id)
      setAvoirsGeneres((s) => new Set(s).add(retour.id))
    } catch (e) {
      setGenError(frErr(e, "La génération de l'avoir a échoué."))
    } finally { setGeneratingId(null) }
  }

  if (error) return <Indisponible message={error} />
  if (items === null) return <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground"><Spinner /> Chargement…</div>
  if (items.length === 0) return <Indisponible message="Aucun retour." />

  return (
    <div className="flex flex-col gap-2">
      {genError && (
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-2 text-sm text-destructive">
          {genError}
        </div>
      )}
      <ul className="flex flex-col gap-2">
        {items.map((r) => (
          <li key={r.id} className="flex items-center justify-between rounded-md border border-border p-2 text-sm">
            <span>{r.reference ?? `Retour #${r.id}`}</span>
            <span className="flex items-center gap-2">
              <span className="text-muted-foreground">{r.statut ?? '—'}</span>
              {canWrite && r.statut === 'valide' && !avoirsGeneres.has(r.id) && (
                <Button size="sm" variant="outline" loading={generatingId === r.id}
                        onClick={() => genererAvoir(r)}>
                  <FileMinus2 className="size-3.5" /> Générer l&apos;avoir
                </Button>
              )}
              {avoirsGeneres.has(r.id) && <Badge tone="success">Avoir généré</Badge>}
            </span>
          </li>
        ))}
      </ul>
    </div>
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
  const [confirmer, dialogueConfirmation] = useConfirmation()
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
    if (!(await confirmer({ title: `Supprimer le contact « ${c.nom} » ?`, confirmLabel: 'Supprimer' }))) return
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
      {dialogueConfirmation}
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

// ASTK225 — types XPUR1 (DocumentConformiteFournisseur.Type, models.py).
const TYPES_CONFORMITE = [
  { value: 'arf', label: 'Attestation de régularité fiscale (ARF)' },
  { value: 'cnss', label: 'Attestation CNSS' },
  { value: 'rc', label: 'Registre du commerce (RC)' },
  { value: 'assurance', label: 'Assurance' },
  { value: 'autre', label: 'Autre pièce' },
]
const libelleTypeConformite = (v) => TYPES_CONFORMITE.find((t) => t.value === v)?.label ?? v

// ASTK225 — premier message d'un 400 DRF par champ (sous le champ fautif).
function erreursParChamp(err, champs) {
  const data = err?.response?.data ?? {}
  const out = {}
  for (const k of champs) {
    const v = data[k]
    const m = Array.isArray(v) ? v[0] : v
    if (typeof m === 'string') out[k] = m
  }
  return out
}

function DocumentConformiteForm({ fournisseurId, document, onClose, onSaved }) {
  const isNew = !document?.id
  const [fields, setFields] = useState({
    type_document: document?.type_document ?? 'arf',
    reference: document?.reference ?? '',
    date_emission: document?.date_emission ?? '',
    date_expiration: document?.date_expiration ?? '',
    obligatoire: document?.obligatoire ?? true,
  })
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)
  const setField = (k, v) => setFields((f) => ({ ...f, [k]: v }))

  const submit = async (ev) => {
    ev.preventDefault()
    setSaving(true); setErrors({})
    const payload = {
      type_document: fields.type_document,
      reference: fields.reference.trim() || null,
      date_emission: fields.date_emission || null,
      date_expiration: fields.date_expiration || null,
      obligatoire: !!fields.obligatoire,
    }
    try {
      if (isNew) {
        await stockApi.createDocumentConformiteFournisseur({ fournisseur: Number(fournisseurId), ...payload })
      } else {
        await stockApi.updateDocumentConformiteFournisseur(document.id, payload)
      }
      onSaved?.()
      onClose()
    } catch (err) {
      const parChamp = erreursParChamp(err, Object.keys(payload))
      setErrors({ ...parChamp, submit: Object.keys(parChamp).length ? undefined : frErr(err, "L'enregistrement a échoué.") })
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{isNew ? 'Nouvelle pièce de conformité' : 'Modifier la pièce'}</DialogTitle>
          <DialogDescription>Pièce légale du fournisseur (donnée interne).</DialogDescription>
        </DialogHeader>
        <Form onSubmit={submit} className="gap-4">
          <FormField label="Type de pièce" htmlFor="conf-type" error={errors.type_document}>
            <Select value={fields.type_document} onValueChange={(v) => setField('type_document', v)}>
              <SelectTrigger id="conf-type"><SelectValue /></SelectTrigger>
              <SelectContent>
                {TYPES_CONFORMITE.map((t) => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </FormField>
          <FormField label="Référence" htmlFor="conf-ref" error={errors.reference}>
            <Input id="conf-ref" value={fields.reference} onChange={(e) => setField('reference', e.target.value)} />
          </FormField>
          <FormField label="Date d'émission" htmlFor="conf-emission" error={errors.date_emission}>
            <Input id="conf-emission" type="date" value={fields.date_emission}
                   onChange={(e) => setField('date_emission', e.target.value)} />
          </FormField>
          <FormField label="Date d'expiration" htmlFor="conf-expiration" error={errors.date_expiration}>
            <Input id="conf-expiration" type="date" value={fields.date_expiration}
                   onChange={(e) => setField('date_expiration', e.target.value)} />
          </FormField>
          <label className="flex items-center gap-2 text-sm sm:col-span-2">
            <Checkbox checked={!!fields.obligatoire} onCheckedChange={(v) => setField('obligatoire', !!v)} />
            Pièce obligatoire
          </label>
          {errors.submit && <p role="alert" className="text-sm text-destructive sm:col-span-2">{errors.submit}</p>}
          <DialogFooter className="sm:col-span-2">
            <Button type="button" variant="ghost" onClick={onClose}>Annuler</Button>
            <Button type="submit" loading={saving}>Enregistrer</Button>
          </DialogFooter>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

function OngletDocuments({ fournisseurId, canWrite, resume, onConformiteChange }) {
  const [items, setItems] = useState(null)
  const [error, setError] = useState(null)
  const [editing, setEditing] = useState(null) // {} = nouvelle pièce
  const [aSupprimer, setASupprimer] = useState(null)
  const [actionError, setActionError] = useState(null)
  const isAdmin = useIsAdmin()

  const reload = () => {
    stockApi.getDocumentsConformiteFournisseur(fournisseurId)
      .then((r) => setItems(r.data?.results ?? r.data ?? []))
      .catch((e) => setError(frErr(e, 'Documents indisponibles.')))
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { reload() }, [fournisseurId])

  const apresEcriture = () => { reload(); onConformiteChange?.() }
  const supprimer = async (d) => {
    setASupprimer(null); setActionError(null)
    try {
      await stockApi.deleteDocumentConformiteFournisseur(d.id)
      apresEcriture()
    } catch (err) {
      setActionError(frErr(err, 'Suppression impossible.'))
    }
  }

  if (error) return <Indisponible message={error} />
  if (items === null) return <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground"><Spinner /> Chargement…</div>

  const toneClass = {
    destructive: 'text-destructive',
    warning: 'text-amber-600',
    success: 'text-emerald-600',
    muted: 'text-muted-foreground',
  }
  // ASTK188 — TYPES requis manquants, calculés par le serveur (vue-360).
  const manquants = Array.isArray(resume?.conformite_documents_manquants)
    ? resume.conformite_documents_manquants : null

  return (
    <div className="flex flex-col gap-3">
      {manquants && (
        manquants.length > 0 ? (
          <div data-testid="conformite-manquants" role="status"
               className="rounded-lg border border-warning/30 bg-warning/10 p-2 text-sm">
            Pièces requises manquantes : {manquants.map(libelleTypeConformite).join(', ')}
          </div>
        ) : (
          <div data-testid="conformite-manquants" className="text-sm text-emerald-600">
            Toutes les pièces requises sont présentes et valides.
          </div>
        )
      )}
      {canWrite && (
        <div>
          <Button type="button" size="sm" onClick={() => setEditing({})}>
            <Plus className="size-4" /> Ajouter une pièce
          </Button>
        </div>
      )}
      {actionError && <p role="alert" className="text-sm text-destructive">{actionError}</p>}
      {items.length === 0 ? (
        <Indisponible message="Aucun document de conformité." />
      ) : (
        <ul className="flex flex-col gap-2">
          {items.map((d) => {
            const st = statutExpiration(d.date_expiration)
            return (
              <li key={d.id} className="flex items-center justify-between gap-2 rounded-md border border-border p-2 text-sm">
                <span className="flex-1">
                  {d.type_document_display ?? libelleTypeConformite(d.type_document) ?? `Document #${d.id}`}
                  {d.reference ? <span className="text-muted-foreground"> · {d.reference}</span> : null}
                </span>
                <span className={toneClass[st.tone]}>
                  {st.label}{d.date_expiration ? ` · ${formatDate(d.date_expiration)}` : ''}
                </span>
                {canWrite && (
                  <IconButton size="sm" variant="ghost" label="Modifier la pièce" onClick={() => setEditing(d)}>
                    <Pencil className="size-4" aria-hidden="true" />
                  </IconButton>
                )}
                {isAdmin && (
                  <IconButton size="sm" variant="ghost" label="Supprimer la pièce"
                              className="text-destructive hover:text-destructive"
                              onClick={() => setASupprimer(d)}>
                    <Trash2 className="size-4" aria-hidden="true" />
                  </IconButton>
                )}
              </li>
            )
          })}
        </ul>
      )}
      {editing && (
        <DocumentConformiteForm fournisseurId={fournisseurId} document={editing.id ? editing : null}
                                onClose={() => setEditing(null)} onSaved={apresEcriture} />
      )}
      <ConfirmDialog
        open={!!aSupprimer}
        onOpenChange={(o) => { if (!o) setASupprimer(null) }}
        title="Supprimer la pièce ?"
        description={aSupprimer ? `${libelleTypeConformite(aSupprimer.type_document)} sera supprimée.` : ''}
        confirmLabel="Supprimer"
        onConfirm={() => supprimer(aSupprimer)}
      />
    </div>
  )
}

// ── Onglet Incidents qualité (NTSCM9) — ASTK226 ─────────────────────────────
// Déclarer / suivre / résoudre les incidents qualité du fournisseur. Liste
// filtrée CÔTÉ SERVEUR (`?fournisseur=`) ; `declare_par` posé par le serveur ;
// route Responsable/Admin (un 403 s'affiche tel quel). Le badge de risque
// (ASTK187) est recalculé après chaque écriture.
const GRAVITES_INCIDENT = [
  { value: 'mineure', label: 'Mineure' },
  { value: 'majeure', label: 'Majeure' },
  { value: 'critique', label: 'Critique' },
]
const TYPES_INCIDENT = [
  { value: 'non_conforme', label: 'Non conforme' },
  { value: 'endommage', label: 'Endommagé' },
  { value: 'erreur_reference', label: 'Erreur de référence' },
  { value: 'documentation_manquante', label: 'Documentation manquante' },
  { value: 'autre', label: 'Autre' },
]
const libelle = (liste, v) => liste.find((x) => x.value === v)?.label ?? v
// Date du jour (calendrier marocain) au format ISO attendu par DRF.
const aujourdhuiIso = () => new Date().toLocaleDateString('sv-SE', { timeZone: 'Africa/Casablanca' })

function IncidentForm({ fournisseurId, onClose, onSaved }) {
  const [fields, setFields] = useState({
    type_incident: 'non_conforme', gravite: 'mineure', date_incident: aujourdhuiIso(),
    quantite_affectee: '0', description: '',
  })
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)
  const setField = (k, v) => setFields((f) => ({ ...f, [k]: v }))

  const submit = async (ev) => {
    ev.preventDefault()
    setSaving(true); setErrors({})
    const payload = {
      fournisseur: Number(fournisseurId),
      type_incident: fields.type_incident,
      gravite: fields.gravite,
      date_incident: fields.date_incident,
      quantite_affectee: Number(fields.quantite_affectee || 0),
      description: fields.description.trim(),
    }
    try {
      await stockApi.createIncidentQualiteFournisseur(payload)
      onSaved?.()
      onClose()
    } catch (err) {
      const parChamp = erreursParChamp(err, Object.keys(payload))
      setErrors({ ...parChamp, submit: Object.keys(parChamp).length ? undefined : frErr(err, 'Déclaration impossible.') })
    } finally { setSaving(false) }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Déclarer un incident qualité</DialogTitle>
          <DialogDescription>Incident imputable au fournisseur (donnée interne).</DialogDescription>
        </DialogHeader>
        <Form onSubmit={submit} className="gap-4">
          <FormField label="Type d'incident" htmlFor="inc-type" error={errors.type_incident}>
            <Select value={fields.type_incident} onValueChange={(v) => setField('type_incident', v)}>
              <SelectTrigger id="inc-type"><SelectValue /></SelectTrigger>
              <SelectContent>
                {TYPES_INCIDENT.map((t) => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </FormField>
          <FormField label="Gravité" htmlFor="inc-gravite" error={errors.gravite}>
            <Select value={fields.gravite} onValueChange={(v) => setField('gravite', v)}>
              <SelectTrigger id="inc-gravite"><SelectValue /></SelectTrigger>
              <SelectContent>
                {GRAVITES_INCIDENT.map((g) => <SelectItem key={g.value} value={g.value}>{g.label}</SelectItem>)}
              </SelectContent>
            </Select>
          </FormField>
          <FormField label="Date de l'incident" htmlFor="inc-date" error={errors.date_incident}>
            <Input id="inc-date" type="date" value={fields.date_incident}
                   onChange={(e) => setField('date_incident', e.target.value)} />
          </FormField>
          <FormField label="Quantité affectée" htmlFor="inc-qte" error={errors.quantite_affectee}>
            <Input id="inc-qte" type="number" step="any" value={fields.quantite_affectee}
                   onChange={(e) => setField('quantite_affectee', e.target.value)} />
          </FormField>
          <FormField label="Description" htmlFor="inc-desc" error={errors.description} fullWidth>
            <Textarea id="inc-desc" rows={2} value={fields.description}
                      onChange={(e) => setField('description', e.target.value)} />
          </FormField>
          {errors.submit && <p role="alert" className="text-sm text-destructive sm:col-span-2">{errors.submit}</p>}
          <DialogFooter className="sm:col-span-2">
            <Button type="button" variant="ghost" onClick={onClose}>Annuler</Button>
            <Button type="submit" loading={saving}>Déclarer</Button>
          </DialogFooter>
        </Form>
      </DialogContent>
    </Dialog>
  )
}

function OngletIncidents({ fournisseurId, canWrite, onConformiteChange }) {
  const [items, setItems] = useState(null)
  const [error, setError] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [actionError, setActionError] = useState(null)
  const [resolvingId, setResolvingId] = useState(null)

  const reload = () => {
    stockApi.getIncidentsQualiteFournisseurDe(fournisseurId)
      .then((r) => setItems(r.data?.results ?? r.data ?? []))
      .catch((e) => setError(frErr(e, 'Incidents indisponibles.')))
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { reload() }, [fournisseurId])

  const apresEcriture = () => { reload(); onConformiteChange?.() }
  const resoudre = async (inc) => {
    setResolvingId(inc.id); setActionError(null)
    try {
      await stockApi.updateIncidentQualiteFournisseur(inc.id, { resolu: true, date_resolution: aujourdhuiIso() })
      apresEcriture()
    } catch (err) {
      setActionError(frErr(err, 'Résolution impossible.'))
    } finally { setResolvingId(null) }
  }

  if (error) return <Indisponible message={error} />
  if (items === null) return <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground"><Spinner /> Chargement…</div>

  return (
    <div className="flex flex-col gap-3">
      {canWrite && (
        <div>
          <Button type="button" size="sm" onClick={() => setShowForm(true)}>
            <Plus className="size-4" /> Déclarer un incident
          </Button>
        </div>
      )}
      {actionError && <p role="alert" className="text-sm text-destructive">{actionError}</p>}
      {items.length === 0 ? (
        <Indisponible message="Aucun incident qualité." />
      ) : (
        <ul className="flex flex-col gap-2">
          {items.map((inc) => (
            <li key={inc.id} data-testid={`incident-${inc.id}`}
                className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border p-2 text-sm">
              <span className="flex items-center gap-2">
                <Badge tone={inc.gravite === 'critique' ? 'danger' : inc.gravite === 'majeure' ? 'warning' : 'neutral'}>
                  {libelle(GRAVITES_INCIDENT, inc.gravite)}
                </Badge>
                {libelle(TYPES_INCIDENT, inc.type_incident)}
                {inc.description ? <span className="text-muted-foreground">· {inc.description}</span> : null}
              </span>
              <span className="flex items-center gap-2">
                <span className="text-muted-foreground">{formatDate(inc.date_incident)}</span>
                {inc.resolu ? (
                  <Badge tone="success">
                    Résolu{inc.date_resolution ? ` le ${formatDate(inc.date_resolution)}` : ''}
                  </Badge>
                ) : canWrite ? (
                  <Button type="button" size="sm" variant="outline" loading={resolvingId === inc.id}
                          onClick={() => resoudre(inc)}>
                    <Check className="size-4" /> Résoudre
                  </Button>
                ) : (
                  <Badge tone="warning">Ouvert</Badge>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
      {showForm && (
        <IncidentForm fournisseurId={fournisseurId} onClose={() => setShowForm(false)} onSaved={apresEcriture} />
      )}
    </div>
  )
}

// ── Onglet Accès (XPUR22 + NTPRT3) — ASTK227 ────────────────────────────────
// Compte portail du fournisseur (provisionner / révoquer — Admin) et liens à
// jeton (générer / lister / révoquer — URL ABSOLUE copiable vers la page
// publique /fournisseur/lien/<token>, ASTK228). L'onglet n'est monté que pour
// un administrateur ; le SERVEUR reste la garde (un 403 s'affiche tel quel).
// Révoquer l'accès coupe AUSSI les liens publics (ASTK179) : le nombre de
// jetons révoqués renvoyé par le serveur est affiché.
const urlLienFournisseur = (token) => `${window.location.origin}/fournisseur/lien/${token}`

function OngletAcces({ fournisseurId }) {
  const [jetons, setJetons] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(null) // 'provisionner' | 'generer' | 'revoquer' | id jeton
  const [info, setInfo] = useState(null)
  const [actionError, setActionError] = useState(null)
  const [confirmation, setConfirmation] = useState(null) // { kind: 'acces' } | { kind: 'jeton', jeton }
  const [copie, setCopie] = useState(null)

  const reload = () => {
    stockApi.getPortailTokensFournisseur(fournisseurId)
      .then((r) => setJetons(Array.isArray(r.data) ? r.data : (r.data?.results ?? [])))
      .catch((e) => setError(frErr(e, 'Liens du portail indisponibles.')))
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { reload() }, [fournisseurId])

  const agir = async (cle, appel, succes) => {
    setBusy(cle); setActionError(null); setInfo(null)
    try {
      const r = await appel()
      setInfo(succes(r?.data ?? {}))
      reload()
    } catch (err) {
      setActionError(frErr(err, 'Action impossible.'))
    } finally { setBusy(null) }
  }
  const provisionner = () => agir('provisionner',
    () => stockApi.provisionnerAccesFournisseur(fournisseurId),
    (d) => d.detail || 'Accès portail ouvert.')
  const generer = () => agir('generer',
    () => stockApi.genererPortailTokenFournisseur(fournisseurId),
    () => 'Nouveau lien généré.')
  const revoquerAcces = () => agir('revoquer',
    () => stockApi.revoquerAccesFournisseur(fournisseurId),
    (d) => `${d.detail || "L'accès portail de ce fournisseur est fermé."} `
      + `${d.jetons_revoques ?? 0} lien(s) révoqué(s).`)
  const revoquerJeton = (j) => agir(j.id,
    () => stockApi.revoquerPortailTokenFournisseur(fournisseurId, j.id),
    () => 'Lien révoqué.')
  const copier = async (j) => {
    try {
      await navigator.clipboard.writeText(urlLienFournisseur(j.token))
      setCopie(j.id)
    } catch {
      setActionError('Copie impossible : sélectionnez le lien à la main.')
    }
  }

  if (error) return <Indisponible message={error} />
  if (jetons === null) return <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground"><Spinner /> Chargement…</div>

  return (
    <div className="flex flex-col gap-4">
      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-semibold">Compte portail</h3>
        <div className="flex flex-wrap gap-2">
          <Button type="button" size="sm" variant="outline" loading={busy === 'provisionner'} onClick={provisionner}>
            <Check className="size-4" /> Ouvrir l&apos;accès portail
          </Button>
          <Button type="button" size="sm" variant="destructive" loading={busy === 'revoquer'}
                  onClick={() => setConfirmation({ kind: 'acces' })}>
            <X className="size-4" /> Révoquer l&apos;accès
          </Button>
        </div>
      </section>
      {info && <p role="status" data-testid="acces-info" className="text-sm text-emerald-600">{info}</p>}
      {actionError && <p role="alert" className="text-sm text-destructive">{actionError}</p>}
      <section className="flex flex-col gap-2">
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold">Liens à jeton</h3>
          <Button type="button" size="sm" loading={busy === 'generer'} onClick={generer}>
            <Plus className="size-4" /> Générer un lien
          </Button>
        </div>
        {jetons.length === 0 ? (
          <Indisponible message="Aucun lien généré." />
        ) : (
          <ul className="flex flex-col gap-2">
            {jetons.map((j) => (
              <li key={j.id} data-testid={`jeton-${j.id}`}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border p-2 text-sm">
                <span className="flex min-w-0 flex-1 flex-col">
                  <code className="truncate text-xs">{urlLienFournisseur(j.token)}</code>
                  <span className="text-xs text-muted-foreground">
                    Créé le {formatDate(j.created_at)}
                    {j.expires_at ? ` · expire le ${formatDate(j.expires_at)}` : ''}
                  </span>
                </span>
                {j.est_valide ? (
                  <span className="flex items-center gap-1">
                    <Badge tone="success">Actif</Badge>
                    <Button type="button" size="sm" variant="outline" onClick={() => copier(j)}>
                      {copie === j.id ? 'Copié' : 'Copier le lien'}
                    </Button>
                    <Button type="button" size="sm" variant="outline" loading={busy === j.id}
                            onClick={() => setConfirmation({ kind: 'jeton', jeton: j })}>
                      Révoquer le lien
                    </Button>
                  </span>
                ) : (
                  <Badge tone={j.revoked ? 'danger' : 'neutral'}>{j.revoked ? 'Révoqué' : 'Expiré'}</Badge>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
      <ConfirmDialog
        open={!!confirmation}
        onOpenChange={(o) => { if (!o) setConfirmation(null) }}
        title={confirmation?.kind === 'acces' ? "Révoquer l'accès du fournisseur ?" : 'Révoquer ce lien ?'}
        description={confirmation?.kind === 'acces'
          ? 'Le compte portail est fermé et TOUS les liens à jeton cessent de fonctionner immédiatement.'
          : 'Le lien cesse de fonctionner immédiatement.'}
        confirmLabel="Révoquer"
        onConfirm={() => {
          const c = confirmation
          setConfirmation(null)
          if (c?.kind === 'acces') revoquerAcces()
          else if (c?.jeton) revoquerJeton(c.jeton)
        }}
      />
    </div>
  )
}

// ── Onglet Tarif (WIR268/XPUR14) — export/import xlsx du tarif fournisseur ──
// Garde-fou « écrasement » côté écran : l'import passe TOUJOURS par un aperçu
// (apercu=true, aucune écriture) avant que « Écraser » (décoché par défaut)
// n'autorise le remplacement d'un prix déjà saisi.
function OngletTarif({ fournisseurId, canWrite }) {
  const [exporting, setExporting] = useState(false)
  const [file, setFile] = useState(null)
  const [apercu, setApercu] = useState(null)
  const [ecraser, setEcraser] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [info, setInfo] = useState(null)

  const exporter = async () => {
    const pending = downloadBlobInGesture()
    setExporting(true); setError(null)
    try {
      const r = await stockApi.exportPrixFournisseurXlsx(fournisseurId)
      pending.deliver(new Blob([r.data]), 'tarif-fournisseur.xlsx')
    } catch {
      setError('Export indisponible.')
    } finally { setExporting(false) }
  }

  const previewImport = async () => {
    if (!file) { setError('Choisissez un fichier .xlsx.'); return }
    setBusy(true); setError(null); setInfo(null); setApercu(null)
    try {
      const r = await stockApi.importPrixFournisseurXlsx(fournisseurId, file, { apercu: true })
      setApercu(r.data)
    } catch (e) {
      setError(frErr(e, "L'aperçu de l'import a échoué."))
    } finally { setBusy(false) }
  }

  const confirmerImport = async () => {
    setBusy(true); setError(null)
    try {
      const r = await stockApi.importPrixFournisseurXlsx(fournisseurId, file, { apercu: false, ecraser })
      setInfo(`Import effectué : ${r.data?.created ?? 0} création(s), ${r.data?.updated ?? 0} mise(s) à jour.`)
      setApercu(null); setFile(null); setEcraser(false)
    } catch (e) {
      setError(frErr(e, "L'import a échoué."))
    } finally { setBusy(false) }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button type="button" size="sm" variant="outline" loading={exporting} onClick={exporter}>
          <Download className="size-4" /> Exporter le tarif
        </Button>
      </div>

      {canWrite && (
        <div className="flex flex-col gap-2 rounded-lg border border-border p-3">
          <span className="text-sm font-semibold">Importer un tarif (xlsx)</span>
          <p className="text-xs text-muted-foreground">
            Même format que l&apos;export. Un aperçu (aucune écriture) précède
            toujours l&apos;import réel.
          </p>
          <FileUpload accept=".xlsx"
                      onFiles={(files) => { setFile(files?.[0] ?? null); setApercu(null); setInfo(null) }} />
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" size="sm" variant="outline" disabled={!file} loading={busy && !apercu}
                    onClick={previewImport}>
              <Upload className="size-4" /> Aperçu
            </Button>
            {apercu && (
              <>
                <label className="flex items-center gap-1.5 text-sm">
                  <Checkbox checked={ecraser} onCheckedChange={(v) => setEcraser(Boolean(v))} />
                  Écraser les prix déjà saisis
                </label>
                <Button type="button" size="sm" loading={busy} onClick={confirmerImport}>
                  Importer
                </Button>
              </>
            )}
          </div>
          {apercu && (
            <p className="text-xs text-muted-foreground">
              Aperçu : {apercu.created ?? 0} création(s), {apercu.updated ?? 0} mise(s) à jour,{' '}
              {(apercu.refuses ?? []).length} refusé(s) (déjà saisi, sans « écraser »).
            </p>
          )}
        </div>
      )}

      {error && (
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-2 text-sm text-destructive">
          {error}
        </div>
      )}
      {info && (
        <div role="status" className="rounded-lg border border-success/30 bg-success/10 p-2 text-sm text-success">
          {info}
        </div>
      )}
    </div>
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
  // ASTK15 (D-ASTK-2) — « Accords de prix » et « Tarif » (export/import des
  // prix d'achat) n'existent que pour un compte qui VOIT les prix d'achat :
  // jamais montés (donc jamais de requête 403) sans `prix_achat_voir`.
  const voitPrix = useVoitPrixAchat()
  // VX108 — tap-to-call : la fiche n'affichait aucun téléphone.
  const tel = telHref(fournisseurTelephone)

  // VX159/VX250 — remonté depuis ResumePanel : RelationCounters (tête de
  // page) ET le panneau résumé consomment le MÊME fetch, jamais un doublon.
  const [resumeData, setResumeData] = useState(null)
  const [resumeUnavailable, setResumeUnavailable] = useState(false)
  const [resumeLoading, setResumeLoading] = useState(true)
  // ASTK225 — rechargé après chaque écriture de conformité (types manquants).
  const [resumeVersion, setResumeVersion] = useState(0)
  useEffect(() => {
    if (!fournisseurId || !canView) return undefined
    let active = true
    stockApi.getFournisseur360(fournisseurId)
      .then((r) => { if (active) setResumeData(r.data ?? null) })
      .catch(() => { if (active) setResumeUnavailable(true) })
      .finally(() => { if (active) setResumeLoading(false) })
    return () => { active = false }
  }, [fournisseurId, canView, resumeVersion])

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
    // ASTK226 — `resumeVersion` : recalculé après un incident / une pièce.
  }, [fournisseurId, canView, resumeVersion])

  // WIR219/NTPRT25 — candidature d'auto-inscription au portail : visible et
  // décidable directement sur la fiche 360 (même garde Admin que la liste
  // FournisseursStock.jsx).
  const isAdmin = useIsAdmin()
  const [statutValidation, setStatutValidation] = useState(null)
  const [decidingCandidature, setDecidingCandidature] = useState(false)
  const [candidatureError, setCandidatureError] = useState(null)
  useEffect(() => {
    if (!fournisseurId || !canView) return undefined
    let active = true
    // Fable review (fix WIR219) — `stockApi.getFournisseur` existe réellement
    // (ajouté à ce même correctif) : plus d'optional-chaining, qui aurait
    // rendu ce bloc silencieusement mort si le wrapper venait à disparaître.
    stockApi.getFournisseur(fournisseurId)
      .then((r) => { if (active) setStatutValidation(r.data?.statut_validation ?? null) })
      .catch(() => { if (active) setStatutValidation(null) })
    return () => { active = false }
  }, [fournisseurId, canView])
  const deciderCandidatureFiche = async (valider) => {
    setDecidingCandidature(true); setCandidatureError(null)
    try {
      const r = await stockApi.deciderCandidatureFournisseur(fournisseurId, valider)
      setStatutValidation(r.data?.statut_validation ?? null)
    } catch (err) {
      setCandidatureError(err?.response?.data?.detail
        || (valider ? 'Validation impossible.' : 'Rejet impossible.'))
    } finally { setDecidingCandidature(false) }
  }

  const tabs = useMemo(() => ([
    { value: 'performance', label: 'Performance', icon: BarChart3, Comp: OngletPerformance },
    { value: 'bcf', label: 'Bons de commande', icon: PackageCheck, Comp: OngletBcf },
    { value: 'factures', label: 'Factures / solde', icon: Receipt, Comp: OngletFactures },
    { value: 'retours', label: 'Retours', icon: Undo2, Comp: OngletRetours },
    { value: 'acomptes', label: 'Acomptes', icon: CreditCard, Comp: OngletAcomptes },
    { value: 'avoirs', label: 'Avoirs', icon: FileMinus2, Comp: OngletAvoirs },
    { value: 'contacts', label: 'Contacts', icon: Users, Comp: OngletContacts },
    { value: 'documents', label: 'Conformité', icon: ShieldCheck, Comp: OngletDocuments },
    // ASTK226 — incidents qualité (NTSCM9), jusqu'ici sans écran.
    { value: 'incidents', label: 'Incidents qualité', icon: FileWarning, Comp: OngletIncidents },
    // ASTK227 — accès fournisseur (compte portail + liens à jeton), Admin seul.
    { value: 'acces', label: 'Accès', icon: Users, Comp: OngletAcces, admin: true },
    // NTP2P29 — wizard d'onboarding (dossier NTP2P7). Contextuelle : atteinte
    // par la fiche fournisseur, jamais une route autonome.
    { value: 'onboarding', label: 'Onboarding', icon: ShieldCheck, Comp: OngletOnboarding },
    { value: 'prix', label: 'Accords de prix', icon: Tags, Comp: OngletAccordsPrix, prix: true },
    // WIR268/XPUR14 — export/import xlsx du tarif fournisseur.
    { value: 'tarif', label: 'Tarif', icon: Wallet, Comp: OngletTarif, prix: true },
  ].filter((t) => (voitPrix || !t.prix) && (isAdmin || !t.admin))), [voitPrix, isAdmin])

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
        {/* WIR219/NTPRT25 — candidature d'auto-inscription : visible et
            décidable ici (garde Admin, comme la liste FournisseursStock). */}
        {statutValidation === 'en_attente_validation' && (
          <div className="mt-2 flex flex-wrap items-center gap-2 rounded-lg border border-warning/30 bg-warning/10 p-2 text-sm">
            <Badge tone="warning">En attente de validation</Badge>
            <span className="text-muted-foreground">Candidature d&apos;auto-inscription au portail.</span>
            {isAdmin && (
              <span className="flex items-center gap-1">
                <Button type="button" size="sm" variant="outline" loading={decidingCandidature}
                        onClick={() => deciderCandidatureFiche(true)}>
                  <Check className="size-4" /> Valider
                </Button>
                <Button type="button" size="sm" variant="outline" loading={decidingCandidature}
                        onClick={() => deciderCandidatureFiche(false)}>
                  <X className="size-4" /> Rejeter
                </Button>
              </span>
            )}
          </div>
        )}
        {statutValidation === 'rejete' && (
          <Badge tone="danger" className="mt-2">Candidature rejetée</Badge>
        )}
        {candidatureError && (
          <p className="mt-1 text-sm text-destructive">{candidatureError}</p>
        )}
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
            <t.Comp fournisseurId={fournisseurId} canWrite={canWrite} resume={resumeData}
                    onConformiteChange={() => setResumeVersion((v) => v + 1)} />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  )
}
