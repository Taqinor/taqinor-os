// XPLT23 — Onglet « Confidentialité » de la page Paramètres (loi 09-08 / CNDP).
//
// Deux blocs autonomes :
//  1. Registre des traitements CNDP (`core.RegistreTraitement`) — CRUD complet
//     + export CSV (déclaration à la CNDP).
//  2. Demandes de personnes concernées (`core.DataSubjectRequest`) — soumission
//     (accès / effacement / rectification) + suivi + exécution (« traiter »,
//     déléguée aux fournisseurs DSR enregistrés côté serveur : `core.dsr`).
//
// Réservé admin/responsable (le backend re-vérifie : IsAdminOrResponsableTier).
// Section autonome : charge et enregistre ses propres données, sans le bouton
// « Enregistrer » global. Texte en français ; clés techniques en anglais.
import { useEffect, useState } from 'react'
import { useIsAdminOrResponsable } from '../../hooks/useHasPermission'
import { Plus, Trash2, Download, Lock, FileCheck2 } from 'lucide-react'
import { toast } from '../../ui/confirm'
import coreApi from '../../api/coreApi'
import { downloadBlob, filenameFromResponse } from '../../api/importApi'
import {
  Card, CardContent, Input, Button, IconButton, Badge, Spinner, EmptyState,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { SectionTitle } from './peComponents'

const KIND_LABELS = {
  acces: 'Accès (export)',
  effacement: 'Effacement',
  rectification: 'Rectification',
}
const STATUT_TONE = { recue: 'warning', traitee: 'success', refusee: 'danger' }
const STATUT_LABELS = { recue: 'Reçue', traitee: 'Traitée', refusee: 'Refusée' }

// ── Bloc 1 : registre des traitements CNDP ───────────────────────────────────
function RegistreTraitements() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [draft, setDraft] = useState({ code: '', finalite: '', base_legale: '' })
  const [busy, setBusy] = useState(false)

  const load = () => coreApi.confidentialite.registreTraitements.list()
    .then((r) => { setRows(r.data.results ?? r.data ?? []); setLoadError(false) })
    .catch(() => setLoadError(true))
    .finally(() => setLoading(false))

  useEffect(() => { load() }, [])

  const addRow = async () => {
    const code = draft.code.trim()
    const finalite = draft.finalite.trim()
    if (!code || !finalite) return
    setBusy(true)
    try {
      await coreApi.confidentialite.registreTraitements.create({
        code, finalite, base_legale: draft.base_legale.trim(),
      })
      setDraft({ code: '', finalite: '', base_legale: '' })
      load()
    } catch (e) { toast.error(e?.response?.data?.detail ?? 'Ajout impossible.') }
    finally { setBusy(false) }
  }

  const toggleActif = async (row) => {
    try {
      await coreApi.confidentialite.registreTraitements.update(row.id, { actif: !row.actif })
      load()
    } catch { /* best-effort */ }
  }

  const delRow = async (row) => {
    if (!window.confirm(`Supprimer le traitement « ${row.code} » ?`)) return
    try { await coreApi.confidentialite.registreTraitements.remove(row.id); load() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Suppression impossible.') }
  }

  const exportCsv = async () => {
    try {
      const res = await coreApi.confidentialite.registreTraitements.exportCsv()
      downloadBlob(res.data, filenameFromResponse(res, 'registre-traitements-cndp.csv'))
    } catch { /* best-effort */ }
  }

  if (loading) return (
    <p className="flex items-center gap-2 text-sm text-muted-foreground">
      <Spinner className="size-4 text-primary" /> Chargement…
    </p>
  )
  if (loadError) {
    return (
      <EmptyState title="Impossible de charger le registre"
        description="Une erreur est survenue lors du chargement." className="py-6" />
    )
  }

  return (
    <Card>
      <CardContent className="pt-4 sm:pt-5">
        <div className="flex items-center justify-between">
          <SectionTitle label="Registre des traitements (CNDP)"
            icon={<><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M16 13H8"/><path d="M16 17H8"/></>}/>
          <Button type="button" size="sm" variant="outline" onClick={exportCsv}>
            <Download className="size-4" aria-hidden="true" /> Exporter en CSV
          </Button>
        </div>
        <p className="mb-3.5 text-[11.5px] text-muted-foreground">
          Déclaration des traitements de données personnelles auprès de la CNDP
          (loi 09-08) : une ligne par finalité (ex. « gestion des prospects »,
          « paie »). Le CSV exporté sert de base à la déclaration officielle.
        </p>

        <div className="flex flex-col gap-2">
          {rows.length === 0 && (
            <EmptyState title="Aucun traitement déclaré"
              description="Ajoutez votre premier traitement ci-dessous." className="py-6" />
          )}
          {rows.map((row) => (
            <div key={row.id} className="rounded-lg border border-border p-3">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className={['min-w-[140px] flex-[1_1_140px] font-medium text-sm',
                  row.actif ? '' : 'opacity-50'].join(' ')}>{row.code}</span>
                <span className="text-xs text-muted-foreground">{row.finalite}</span>
                <div className="ml-auto flex items-center gap-1">
                  <Button type="button" size="sm"
                    variant={row.actif ? 'success' : 'secondary'}
                    onClick={() => toggleActif(row)}>
                    {row.actif ? 'Actif' : 'Inactif'}
                  </Button>
                  <IconButton size="sm" variant="outline" label="Supprimer le traitement"
                    className="text-destructive hover:text-destructive"
                    onClick={() => delRow(row)}>
                    <Trash2 className="size-4" aria-hidden="true" />
                  </IconButton>
                </div>
              </div>
              {row.base_legale && (
                <p className="mt-1 text-xs text-muted-foreground">Base légale : {row.base_legale}</p>
              )}
            </div>
          ))}
        </div>

        <div className="mt-3 rounded-lg border border-dashed border-border p-3">
          <div className="flex flex-wrap gap-1.5">
            <Input className="min-w-[140px] flex-[1_1_140px]" placeholder="Code (ex. leads_clients)"
              value={draft.code} onChange={(e) => setDraft((d) => ({ ...d, code: e.target.value }))} />
            <Input className="min-w-[200px] flex-[2_1_200px]" placeholder="Finalité (ex. gestion des prospects)"
              value={draft.finalite} onChange={(e) => setDraft((d) => ({ ...d, finalite: e.target.value }))} />
          </div>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            <Input className="min-w-[200px] flex-1" placeholder="Base légale (ex. consentement, contrat)"
              value={draft.base_legale} onChange={(e) => setDraft((d) => ({ ...d, base_legale: e.target.value }))} />
            <Button type="button" onClick={addRow} disabled={busy}>
              <Plus className="size-4" aria-hidden="true" /> Ajouter
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

// ── Bloc 2 : demandes de personnes concernées (DSR) ──────────────────────────
function DsrRequests() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [draft, setDraft] = useState({ subject_identifier: '', kind: 'acces' })
  const [busy, setBusy] = useState(false)
  const [traitingId, setTraitingId] = useState(null)

  const load = () => coreApi.confidentialite.dsrRequests.list()
    .then((r) => { setRows(r.data.results ?? r.data ?? []); setLoadError(false) })
    .catch(() => setLoadError(true))
    .finally(() => setLoading(false))

  useEffect(() => { load() }, [])

  const submit = async () => {
    const subject = draft.subject_identifier.trim()
    if (!subject) return
    setBusy(true)
    try {
      await coreApi.confidentialite.dsrRequests.create({
        subject_identifier: subject, kind: draft.kind,
      })
      setDraft({ subject_identifier: '', kind: 'acces' })
      load()
    } catch (e) { toast.error(e?.response?.data?.detail ?? 'Soumission impossible.') }
    finally { setBusy(false) }
  }

  const traiter = async (row) => {
    setTraitingId(row.id)
    try { await coreApi.confidentialite.dsrRequests.traiter(row.id); load() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Traitement impossible.') }
    finally { setTraitingId(null) }
  }

  if (loading) return (
    <p className="flex items-center gap-2 text-sm text-muted-foreground">
      <Spinner className="size-4 text-primary" /> Chargement…
    </p>
  )
  if (loadError) {
    return (
      <EmptyState title="Impossible de charger les demandes"
        description="Une erreur est survenue lors du chargement." className="py-6" />
    )
  }

  return (
    <Card>
      <CardContent className="pt-4 sm:pt-5">
        <SectionTitle label="Demandes de personnes concernées"
          icon={<><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></>}/>
        <p className="mb-3.5 text-[11.5px] text-muted-foreground">
          Accès, effacement ou rectification des données d'une personne
          concernée (loi 09-08). Le traitement exécute l'export/effacement
          réel (fournisseurs DSR internes) ; la rectification reste manuelle.
        </p>

        <div className="flex flex-col gap-2">
          {rows.length === 0 && (
            <EmptyState title="Aucune demande" data-testid="dsr-empty"
              description="Soumettez votre première demande ci-dessous." className="py-6" />
          )}
          {rows.map((row) => (
            <div key={row.id} data-testid="dsr-row"
              className="flex flex-wrap items-center gap-1.5 rounded-lg border border-border p-3">
              <span className="min-w-[140px] flex-[1_1_140px] font-medium text-sm">
                {row.subject_identifier}
              </span>
              <Badge tone="info">{KIND_LABELS[row.kind] ?? row.kind}</Badge>
              <Badge tone={STATUT_TONE[row.statut] ?? 'neutral'}>
                {STATUT_LABELS[row.statut] ?? row.statut}
              </Badge>
              <div className="ml-auto flex items-center gap-1">
                {row.statut === 'recue' && (
                  <Button type="button" size="sm" variant="outline"
                    disabled={traitingId === row.id}
                    onClick={() => traiter(row)}>
                    <FileCheck2 className="size-4" aria-hidden="true" />
                    {traitingId === row.id ? 'Traitement…' : 'Traiter'}
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-3 rounded-lg border border-dashed border-border p-3">
          <div className="flex flex-wrap gap-1.5">
            <Input className="min-w-[200px] flex-[2_1_200px]"
              placeholder="Email ou téléphone de la personne concernée"
              value={draft.subject_identifier}
              onChange={(e) => setDraft((d) => ({ ...d, subject_identifier: e.target.value }))} />
            <div className="min-w-[160px] flex-1">
              <Select value={draft.kind} onValueChange={(v) => setDraft((d) => ({ ...d, kind: v }))}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {Object.entries(KIND_LABELS).map(([k, label]) => (
                    <SelectItem key={k} value={k}>{label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button type="button" onClick={submit} disabled={busy}>
              <Plus className="size-4" aria-hidden="true" /> Soumettre
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

// ── Bloc 3 : consentement au benchmarking anonymisé (SCA46) ──────────────────
// Le CONSENTEMENT est une donnée (Company.benchmarking_opt_in, défaut False) ;
// aucune agrégation n'existe encore. Bloc autonome : lit le profil, écrit via
// PATCH /parametres/update/ (posé côté serveur sur la société de l'appelant).
function BenchmarkingConsent() {
  const [optIn, setOptIn] = useState(false)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let actif = true
    import('../../api/parametresApi').then(({ default: parametresApi }) =>
      parametresApi.getProfile()
        .then((r) => { if (actif) setOptIn(!!r.data?.benchmarking_opt_in) })
        .catch(() => {})
        .finally(() => { if (actif) setLoading(false) }))
    return () => { actif = false }
  }, [])

  const toggle = async () => {
    setBusy(true)
    const next = !optIn
    try {
      const { default: parametresApi } = await import('../../api/parametresApi')
      await parametresApi.updateProfile({ benchmarking_opt_in: next })
      setOptIn(next)
    } catch { /* best-effort : l'état affiché reste l'ancien */ }
    finally { setBusy(false) }
  }

  return (
    <Card>
      <CardContent className="pt-4 sm:pt-5">
        <SectionTitle
          label="Benchmarking anonymisé"
          hint="Consentement d'entreprise (désactivé par défaut)"
        />
        <label className="flex items-start gap-3" style={{ cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={optIn}
            disabled={loading || busy}
            onChange={toggle}
            aria-label="Consentir au benchmarking anonymisé"
          />
          <span>
            J'accepte que des indicateurs <strong>agrégés et anonymisés</strong>{' '}
            de mon entreprise (jamais de données nominatives, jamais de
            documents) puissent être utilisés pour des comparatifs sectoriels.
            Ce consentement est révocable à tout moment ; aucune agrégation
            n'est réalisée tant qu'il n'est pas donné.
          </span>
        </label>
      </CardContent>
    </Card>
  )
}

export default function ConfidentialiteSection() {
  const canManage = useIsAdminOrResponsable()

  if (!canManage) {
    return (
      <EmptyState
        icon={Lock}
        title="Accès restreint"
        description="La Confidentialité (registre CNDP, demandes de personnes concernées) est réservée aux comptes Administrateur/Responsable."
        className="my-6"
      />
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <RegistreTraitements />
      <DsrRequests />
      <BenchmarkingConsent />
    </div>
  )
}
