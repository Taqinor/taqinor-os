/* ============================================================================
   PACT55 — Sous-traitance chantier : ordres, factures, règlements,
   attestations, évaluations et retenues de garantie, depuis la fiche d'un
   sous-traitant, SANS quitter l'écran.
   ----------------------------------------------------------------------------
   Trou (a) : le backend sait déjà tout faire (FG304-309, DC34) mais aucun
   fichier frontend, pas même un wrapper client, ne l'appelait. Cet écran est
   le premier consommateur : annuaire à gauche, fiche à onglets à droite.
   ========================================================================== */
import { useCallback, useEffect, useState } from 'react'
import { PlusCircle } from 'lucide-react'
import PageHeader from '../../components/layout/PageHeader'
import {
  Badge, Button, IconButton, Spinner, EmptyState,
  Tabs, TabsList, TabsTrigger, TabsContent,
} from '../../ui'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
import { formatDate, formatMAD } from '../../lib/format'
import installationsApi from '../../api/installationsApi'

const METIERS = [
  ['terrassement', 'Terrassement'], ['genie_civil', 'Génie civil'],
  ['electricite', 'Électricité'], ['levage', 'Levage'],
  ['transport', 'Transport'], ['autre', 'Autre'],
]
const TYPES_PIECE = [
  ['cnss', 'Attestation CNSS'], ['rc_decennale', 'Assurance RC décennale'],
  ['rc_travaux', 'Assurance RC travaux'], ['agrement', 'Agrément métier'],
  ['fiscale', 'Attestation fiscale'], ['autre', 'Autre pièce'],
]
const ORDRE_STATUT_TONE = {
  brouillon: 'neutral', emis: 'info', en_cours: 'warning',
  receptionne: 'success', clos: 'success',
}

function unwrap(res) {
  const p = res?.data
  return Array.isArray(p) ? p : (p?.results ?? [])
}

function useFilteredList(fetcher, params) {
  const key = JSON.stringify(params)
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const load = useCallback(() => {
    let cancelled = false
    setLoading(true); setError(null)
    fetcher(params)
      .then((res) => { if (!cancelled) setRows(unwrap(res)) })
      .catch((err) => {
        if (!cancelled) setError(err?.response?.data?.detail || 'Chargement impossible.')
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])
  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage/changement de filtre
  useEffect(() => load(), [load])
  return { rows, loading, error, reload: load }
}

function ListShell({ loading, error, empty, children }) {
  if (loading) return (
    <p className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
      <Spinner className="size-4 text-primary" /> Chargement…
    </p>
  )
  if (error) return <EmptyState title="Impossible de charger" description={error} className="py-6" />
  if (!children) return <EmptyState title={empty} className="py-6" />
  return children
}

// ── Annuaire : créer un sous-traitant ───────────────────────────────────────
function CreateSousTraitantDialog({ onClose, onCreated }) {
  const [raisonSociale, setRaisonSociale] = useState('')
  const [metier, setMetier] = useState('autre')
  const [telephone, setTelephone] = useState('')
  const [ice, setIce] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const create = async () => {
    if (!raisonSociale.trim()) { setError('La raison sociale est obligatoire.'); return }
    setBusy(true); setError(null)
    try {
      await installationsApi.createSousTraitant({
        raison_sociale: raisonSociale.trim(), metier,
        telephone: telephone || undefined, ice: ice || undefined,
      })
      onCreated?.()
    } catch (err) {
      setError(err?.response?.data?.raison_sociale?.[0]
        || err?.response?.data?.detail || 'Création impossible.')
    } finally { setBusy(false) }
  }
  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }} className="sm:max-w-lg" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">Nouveau sous-traitant</h3>
        <button type="button" className="modal-close" onClick={onClose}>✕</button>
      </div>
      <div className="modal-body flex flex-col gap-3">
        <label className="form-label" htmlFor="st-nom">Raison sociale</label>
        <input id="st-nom" type="text" className="form-control" value={raisonSociale} onChange={(e) => setRaisonSociale(e.target.value)} autoFocus />
        <label className="form-label" htmlFor="st-metier">Métier</label>
        <select id="st-metier" className="form-control" value={metier} onChange={(e) => setMetier(e.target.value)}>
          {METIERS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <label className="form-label" htmlFor="st-tel">Téléphone (optionnel)</label>
        <input id="st-tel" type="tel" className="form-control" value={telephone} onChange={(e) => setTelephone(e.target.value)} />
        <label className="form-label" htmlFor="st-ice">ICE (optionnel)</label>
        <input id="st-ice" type="text" className="form-control" value={ice} onChange={(e) => setIce(e.target.value)} />
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
      <div className="modal-footer">
        <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
        <Button type="button" loading={busy} disabled={busy} onClick={create}>
          {busy ? 'Création…' : 'Créer'}
        </Button>
      </div>
    </ResponsiveDialog>
  )
}

// ── Onglet Ordres ────────────────────────────────────────────────────────────
function CreateOrdreDialog({ sousTraitantId, chantiers, onClose, onCreated }) {
  const [chantier, setChantier] = useState('')
  const [prestation, setPrestation] = useState('')
  const [montant, setMontant] = useState('')
  const [dateEcheance, setDateEcheance] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const create = async () => {
    if (!prestation.trim() || !montant) {
      setError('Prestation et montant sont requis.')
      return
    }
    setBusy(true); setError(null)
    try {
      await installationsApi.createOrdreSousTraitance({
        sous_traitant: sousTraitantId,
        chantier: chantier ? Number(chantier) : null,
        prestation: prestation.trim(), montant,
        date_echeance: dateEcheance || null,
      })
      onCreated?.()
    } catch (err) {
      setError(err?.response?.data?.detail || 'Création impossible.')
    } finally { setBusy(false) }
  }
  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }} className="sm:max-w-lg" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">Nouvel ordre de travaux</h3>
        <button type="button" className="modal-close" onClick={onClose}>✕</button>
      </div>
      <div className="modal-body flex flex-col gap-3">
        <label className="form-label" htmlFor="ost-chantier">Chantier (optionnel)</label>
        <select id="ost-chantier" className="form-control" value={chantier} onChange={(e) => setChantier(e.target.value)} autoFocus>
          <option value="">—</option>
          {chantiers.map((c) => <option key={c.id} value={c.id}>{c.reference || `#${c.id}`}</option>)}
        </select>
        <label className="form-label" htmlFor="ost-prestation">Prestation</label>
        <textarea id="ost-prestation" className="form-control" rows={2} value={prestation} onChange={(e) => setPrestation(e.target.value)} />
        <label className="form-label" htmlFor="ost-montant">Montant (MAD)</label>
        <input id="ost-montant" type="number" step="any" className="form-control" value={montant} onChange={(e) => setMontant(e.target.value)} />
        <label className="form-label" htmlFor="ost-echeance">Échéance (optionnel)</label>
        <input id="ost-echeance" type="date" className="form-control" value={dateEcheance} onChange={(e) => setDateEcheance(e.target.value)} />
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
      <div className="modal-footer">
        <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
        <Button type="button" loading={busy} disabled={busy} onClick={create}>
          {busy ? 'Création…' : 'Créer'}
        </Button>
      </div>
    </ResponsiveDialog>
  )
}

function OrdresTab({ sousTraitantId, chantiers }) {
  const { rows, loading, error, reload } = useFilteredList(
    installationsApi.getOrdresSousTraitance, { sous_traitant: sousTraitantId })
  const [showCreate, setShowCreate] = useState(false)
  const [busyId, setBusyId] = useState(null)

  const emettre = async (id) => {
    setBusyId(id)
    await installationsApi.emettreOrdreSousTraitance(id).catch(() => {})
    setBusyId(null); reload()
  }
  const receptionner = async (id) => {
    setBusyId(id)
    await installationsApi.receptionnerOrdreSousTraitance(id).catch(() => {})
    setBusyId(null); reload()
  }
  const cloturer = async (id) => {
    setBusyId(id)
    await installationsApi.cloturerOrdreSousTraitance(id).catch(() => {})
    setBusyId(null); reload()
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setShowCreate(true)}>
          <PlusCircle className="size-4" aria-hidden="true" /> Nouvel ordre
        </Button>
      </div>
      <ListShell loading={loading} error={error} empty="Aucun ordre de travaux">
        {rows.length > 0 && rows.map((r) => (
          <div key={r.id} className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card p-3" data-testid={`ordre-${r.id}`}>
            <span className="font-medium text-sm">{r.reference}</span>
            <Badge tone={ORDRE_STATUT_TONE[r.statut] || 'neutral'}>{r.statut_display || r.statut}</Badge>
            <span className="text-sm text-muted-foreground truncate max-w-xs">{r.prestation}</span>
            <span className="text-sm font-medium ml-auto">{formatMAD(r.montant)}</span>
            {r.statut === 'brouillon' && (
              <Button size="sm" variant="outline" disabled={busyId === r.id} onClick={() => emettre(r.id)}>Émettre</Button>
            )}
            {(r.statut === 'emis' || r.statut === 'en_cours') && (
              <Button size="sm" variant="outline" disabled={busyId === r.id} onClick={() => receptionner(r.id)}>Réceptionner</Button>
            )}
            {r.statut === 'receptionne' && (
              <Button size="sm" variant="outline" disabled={busyId === r.id} onClick={() => cloturer(r.id)}>Clôturer</Button>
            )}
          </div>
        ))}
      </ListShell>
      {showCreate && (
        <CreateOrdreDialog sousTraitantId={sousTraitantId} chantiers={chantiers}
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); reload() }} />
      )}
    </div>
  )
}

// ── Onglet Factures & règlements ────────────────────────────────────────────
function CreateFactureDialog({ sousTraitantId, onClose, onCreated }) {
  const [numero, setNumero] = useState('')
  const [montantTtc, setMontantTtc] = useState('')
  const [dateFacture, setDateFacture] = useState('')
  const [dateEcheance, setDateEcheance] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const create = async () => {
    if (!montantTtc) { setError('Le montant TTC est requis.'); return }
    setBusy(true); setError(null)
    try {
      await installationsApi.createFactureSousTraitant({
        sous_traitant: sousTraitantId, numero: numero || undefined,
        montant_ttc: montantTtc, date_facture: dateFacture || null,
        date_echeance: dateEcheance || null,
      })
      onCreated?.()
    } catch (err) {
      setError(err?.response?.data?.detail || 'Création impossible.')
    } finally { setBusy(false) }
  }
  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }} className="sm:max-w-lg" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">Nouvelle facture sous-traitant</h3>
        <button type="button" className="modal-close" onClick={onClose}>✕</button>
      </div>
      <div className="modal-body flex flex-col gap-3">
        <label className="form-label" htmlFor="fst-numero">N° facture fournisseur (optionnel)</label>
        <input id="fst-numero" type="text" className="form-control" value={numero} onChange={(e) => setNumero(e.target.value)} autoFocus />
        <label className="form-label" htmlFor="fst-ttc">Montant TTC (MAD)</label>
        <input id="fst-ttc" type="number" step="any" className="form-control" value={montantTtc} onChange={(e) => setMontantTtc(e.target.value)} />
        <label className="form-label" htmlFor="fst-date">Date facture (optionnel)</label>
        <input id="fst-date" type="date" className="form-control" value={dateFacture} onChange={(e) => setDateFacture(e.target.value)} />
        <label className="form-label" htmlFor="fst-echeance">Échéance (optionnel)</label>
        <input id="fst-echeance" type="date" className="form-control" value={dateEcheance} onChange={(e) => setDateEcheance(e.target.value)} />
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
      <div className="modal-footer">
        <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
        <Button type="button" loading={busy} disabled={busy} onClick={create}>
          {busy ? 'Création…' : 'Créer'}
        </Button>
      </div>
    </ResponsiveDialog>
  )
}

function AddPaiementDialog({ factureId, onClose, onCreated }) {
  const [montant, setMontant] = useState('')
  const [datePaiement, setDatePaiement] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const create = async () => {
    if (!montant) { setError('Le montant est requis.'); return }
    setBusy(true); setError(null)
    try {
      await installationsApi.createPaiementSousTraitant({
        facture: factureId, montant, date_paiement: datePaiement || null,
      })
      onCreated?.()
    } catch (err) {
      setError(err?.response?.data?.montant?.[0]
        || err?.response?.data?.detail || 'Règlement impossible.')
    } finally { setBusy(false) }
  }
  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }} className="sm:max-w-sm" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">Nouveau règlement</h3>
        <button type="button" className="modal-close" onClick={onClose}>✕</button>
      </div>
      <div className="modal-body flex flex-col gap-3">
        <label className="form-label" htmlFor="pst-montant">Montant (MAD)</label>
        <input id="pst-montant" type="number" step="any" className="form-control" value={montant} onChange={(e) => setMontant(e.target.value)} autoFocus />
        <label className="form-label" htmlFor="pst-date">Date de paiement (optionnel)</label>
        <input id="pst-date" type="date" className="form-control" value={datePaiement} onChange={(e) => setDatePaiement(e.target.value)} />
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
      <div className="modal-footer">
        <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
        <Button type="button" loading={busy} disabled={busy} onClick={create}>
          {busy ? 'Enregistrement…' : 'Enregistrer'}
        </Button>
      </div>
    </ResponsiveDialog>
  )
}

function FactureRow({ facture, onChanged }) {
  const [expanded, setExpanded] = useState(false)
  const [showPay, setShowPay] = useState(false)
  const { rows: paiements, loading, reload } = useFilteredList(
    installationsApi.getPaiementsSousTraitant,
    expanded ? { facture: facture.id } : { facture: -1 })

  return (
    <div className="rounded-xl border border-border bg-card p-3" data-testid={`facture-${facture.id}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium text-sm">{facture.numero || facture.reference}</span>
        <Badge tone="neutral">{facture.statut_display || facture.statut}</Badge>
        <span className="text-sm font-medium">{formatMAD(facture.montant_ttc)}</span>
        <span className="text-xs text-muted-foreground">Reste dû : {formatMAD(facture.reste_a_payer)}</span>
        <Button size="sm" variant="outline" className="ml-auto" onClick={() => setExpanded((v) => !v)}>
          {expanded ? 'Masquer les règlements' : 'Règlements'}
        </Button>
        <Button size="sm" variant="outline" onClick={() => setShowPay(true)}>
          Ajouter un règlement
        </Button>
      </div>
      {expanded && (
        <div className="mt-2 flex flex-col gap-1 pl-3 border-l border-border">
          {loading ? <Spinner className="size-4" /> : (
            paiements.length === 0
              ? <p className="text-xs text-muted-foreground">Aucun règlement.</p>
              : paiements.map((p) => (
                <div key={p.id} className="flex items-center gap-2 text-sm" data-testid={`paiement-${p.id}`}>
                  <span>{formatDate(p.date_paiement)}</span>
                  <span className="font-medium">{formatMAD(p.montant)}</span>
                  <span className="text-xs text-muted-foreground">{p.mode}</span>
                </div>
              ))
          )}
        </div>
      )}
      {showPay && (
        <AddPaiementDialog factureId={facture.id}
          onClose={() => setShowPay(false)}
          onCreated={() => { setShowPay(false); reload(); onChanged?.() }} />
      )}
    </div>
  )
}

function FacturesTab({ sousTraitantId }) {
  const { rows, loading, error, reload } = useFilteredList(
    installationsApi.getFacturesSousTraitant, { sous_traitant: sousTraitantId })
  const [showCreate, setShowCreate] = useState(false)
  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setShowCreate(true)}>
          <PlusCircle className="size-4" aria-hidden="true" /> Nouvelle facture
        </Button>
      </div>
      <ListShell loading={loading} error={error} empty="Aucune facture sous-traitant">
        {rows.length > 0 && (
          <div className="flex flex-col gap-2">
            {rows.map((f) => <FactureRow key={f.id} facture={f} onChanged={reload} />)}
          </div>
        )}
      </ListShell>
      {showCreate && (
        <CreateFactureDialog sousTraitantId={sousTraitantId}
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); reload() }} />
      )}
    </div>
  )
}

// ── Onglet Attestations ─────────────────────────────────────────────────────
function CreateAttestationDialog({ sousTraitantId, onClose, onCreated }) {
  const [typePiece, setTypePiece] = useState('cnss')
  const [reference, setReference] = useState('')
  const [dateExpiration, setDateExpiration] = useState('')
  const [obligatoire, setObligatoire] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const create = async () => {
    setBusy(true); setError(null)
    try {
      await installationsApi.createAttestationSousTraitant({
        sous_traitant: sousTraitantId, type_piece: typePiece,
        reference: reference || undefined,
        date_expiration: dateExpiration || null, obligatoire,
      })
      onCreated?.()
    } catch (err) {
      setError(err?.response?.data?.detail || 'Création impossible.')
    } finally { setBusy(false) }
  }
  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }} className="sm:max-w-lg" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">Nouvelle attestation</h3>
        <button type="button" className="modal-close" onClick={onClose}>✕</button>
      </div>
      <div className="modal-body flex flex-col gap-3">
        <label className="form-label" htmlFor="att-type">Type de pièce</label>
        <select id="att-type" className="form-control" value={typePiece} onChange={(e) => setTypePiece(e.target.value)} autoFocus>
          {TYPES_PIECE.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <label className="form-label" htmlFor="att-ref">Référence (optionnel)</label>
        <input id="att-ref" type="text" className="form-control" value={reference} onChange={(e) => setReference(e.target.value)} />
        <label className="form-label" htmlFor="att-expiration">Date d'expiration (optionnel)</label>
        <input id="att-expiration" type="date" className="form-control" value={dateExpiration} onChange={(e) => setDateExpiration(e.target.value)} />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={obligatoire} onChange={(e) => setObligatoire(e.target.checked)} />
          Pièce obligatoire
        </label>
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
      <div className="modal-footer">
        <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
        <Button type="button" loading={busy} disabled={busy} onClick={create}>
          {busy ? 'Création…' : 'Créer'}
        </Button>
      </div>
    </ResponsiveDialog>
  )
}

function AttestationsTab({ sousTraitantId }) {
  const { rows, loading, error, reload } = useFilteredList(
    installationsApi.getAttestationsSousTraitant, { sous_traitant: sousTraitantId })
  const [showCreate, setShowCreate] = useState(false)
  const [affectable, setAffectable] = useState(null)

  useEffect(() => {
    let alive = true
    installationsApi.getAffectabiliteSousTraitant(sousTraitantId)
      .then((res) => { if (alive) setAffectable(res?.data ?? null) })
      .catch(() => { if (alive) setAffectable(null) })
    return () => { alive = false }
  }, [sousTraitantId, rows.length])

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        {affectable != null && (
          <Badge tone={affectable.affectable ? 'success' : 'danger'}>
            {affectable.affectable ? 'Affectable' : 'Non affectable'}
          </Badge>
        )}
        <Button size="sm" className="ml-auto" onClick={() => setShowCreate(true)}>
          <PlusCircle className="size-4" aria-hidden="true" /> Nouvelle attestation
        </Button>
      </div>
      <ListShell loading={loading} error={error} empty="Aucune attestation enregistrée">
        {rows.length > 0 && rows.map((a) => (
          <div key={a.id} className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card p-3" data-testid={`attestation-${a.id}`}>
            <span className="font-medium text-sm">{a.type_piece_display || a.type_piece}</span>
            {a.reference && <span className="text-sm text-muted-foreground">{a.reference}</span>}
            <span className="text-sm text-muted-foreground ml-auto">
              {a.date_expiration ? `Expire le ${formatDate(a.date_expiration)}` : 'Sans expiration'}
            </span>
            <Badge tone={a.est_valide ? 'success' : 'danger'}>{a.est_valide ? 'Valide' : 'Expirée'}</Badge>
          </div>
        ))}
      </ListShell>
      {showCreate && (
        <CreateAttestationDialog sousTraitantId={sousTraitantId}
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); reload() }} />
      )}
    </div>
  )
}

// ── Onglet Évaluation ────────────────────────────────────────────────────────
function CreateEvaluationDialog({ sousTraitantId, chantiers, onClose, onCreated }) {
  const [chantier, setChantier] = useState('')
  const [qualite, setQualite] = useState('5')
  const [delai, setDelai] = useState('5')
  const [securite, setSecurite] = useState('5')
  const [commentaire, setCommentaire] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const create = async () => {
    setBusy(true); setError(null)
    try {
      await installationsApi.createEvaluationSousTraitant({
        sous_traitant: sousTraitantId, chantier: chantier ? Number(chantier) : null,
        note_qualite: Number(qualite), note_delai: Number(delai),
        note_securite: Number(securite), commentaire: commentaire || undefined,
      })
      onCreated?.()
    } catch (err) {
      setError(err?.response?.data?.detail || 'Création impossible.')
    } finally { setBusy(false) }
  }
  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }} className="sm:max-w-lg" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">Nouvelle évaluation</h3>
        <button type="button" className="modal-close" onClick={onClose}>✕</button>
      </div>
      <div className="modal-body flex flex-col gap-3">
        <label className="form-label" htmlFor="ev-chantier">Chantier (optionnel)</label>
        <select id="ev-chantier" className="form-control" value={chantier} onChange={(e) => setChantier(e.target.value)} autoFocus>
          <option value="">—</option>
          {chantiers.map((c) => <option key={c.id} value={c.id}>{c.reference || `#${c.id}`}</option>)}
        </select>
        <label className="form-label" htmlFor="ev-qualite">Qualité (1-5)</label>
        <input id="ev-qualite" type="number" min="1" max="5" className="form-control" value={qualite} onChange={(e) => setQualite(e.target.value)} />
        <label className="form-label" htmlFor="ev-delai">Délai (1-5)</label>
        <input id="ev-delai" type="number" min="1" max="5" className="form-control" value={delai} onChange={(e) => setDelai(e.target.value)} />
        <label className="form-label" htmlFor="ev-securite">Sécurité (1-5)</label>
        <input id="ev-securite" type="number" min="1" max="5" className="form-control" value={securite} onChange={(e) => setSecurite(e.target.value)} />
        <label className="form-label" htmlFor="ev-commentaire">Commentaire (optionnel)</label>
        <textarea id="ev-commentaire" className="form-control" rows={2} value={commentaire} onChange={(e) => setCommentaire(e.target.value)} />
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
      <div className="modal-footer">
        <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
        <Button type="button" loading={busy} disabled={busy} onClick={create}>
          {busy ? 'Création…' : 'Créer'}
        </Button>
      </div>
    </ResponsiveDialog>
  )
}

function EvaluationTab({ sousTraitantId, chantiers }) {
  const { rows, loading, error, reload } = useFilteredList(
    installationsApi.getEvaluationsSousTraitant, { sous_traitant: sousTraitantId })
  const [showCreate, setShowCreate] = useState(false)
  const [scorecard, setScorecard] = useState(null)

  useEffect(() => {
    let alive = true
    installationsApi.getScorecardSousTraitant(sousTraitantId)
      .then((res) => { if (alive) setScorecard(res?.data ?? null) })
      .catch(() => { if (alive) setScorecard(null) })
    return () => { alive = false }
  }, [sousTraitantId, rows.length])

  return (
    <div className="flex flex-col gap-3">
      {scorecard && scorecard.nb_evaluations > 0 && (
        <div className="flex flex-wrap gap-4 rounded-xl border border-border bg-card p-3 text-sm" data-testid="scorecard">
          <span>Note globale : <strong>{scorecard.note_globale ?? '—'}</strong></span>
          <span>Qualité : {scorecard.note_qualite ?? '—'}</span>
          <span>Délai : {scorecard.note_delai ?? '—'}</span>
          <span>Sécurité : {scorecard.note_securite ?? '—'}</span>
          <span className="text-muted-foreground">({scorecard.nb_evaluations} évaluation(s))</span>
        </div>
      )}
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setShowCreate(true)}>
          <PlusCircle className="size-4" aria-hidden="true" /> Nouvelle évaluation
        </Button>
      </div>
      <ListShell loading={loading} error={error} empty="Aucune évaluation enregistrée">
        {rows.length > 0 && rows.map((e) => (
          <div key={e.id} className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card p-3" data-testid={`evaluation-${e.id}`}>
            <span className="text-sm text-muted-foreground">{formatDate(e.date_evaluation || e.date_creation)}</span>
            <Badge tone="info">Qualité {e.note_qualite}</Badge>
            <Badge tone="info">Délai {e.note_delai}</Badge>
            <Badge tone="info">Sécurité {e.note_securite}</Badge>
            <span className="font-medium ml-auto">{e.note_globale}</span>
          </div>
        ))}
      </ListShell>
      {showCreate && (
        <CreateEvaluationDialog sousTraitantId={sousTraitantId} chantiers={chantiers}
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); reload() }} />
      )}
    </div>
  )
}

// ── Onglet Retenues de garantie ──────────────────────────────────────────────
function CreateRetenueDialog({ ordreId, onClose, onCreated }) {
  const [pourcentage, setPourcentage] = useState('10')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const create = async () => {
    setBusy(true); setError(null)
    try {
      await installationsApi.createRetenueGarantieSousTraitant({
        ordre: ordreId, pourcentage,
      })
      onCreated?.()
    } catch (err) {
      setError(err?.response?.data?.detail || 'Création impossible.')
    } finally { setBusy(false) }
  }
  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }} className="sm:max-w-sm" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">Nouvelle retenue de garantie</h3>
        <button type="button" className="modal-close" onClick={onClose}>✕</button>
      </div>
      <div className="modal-body flex flex-col gap-3">
        <label className="form-label" htmlFor="ret-pct">Pourcentage retenu</label>
        <input id="ret-pct" type="number" step="any" min="0" max="100" className="form-control" value={pourcentage} onChange={(e) => setPourcentage(e.target.value)} autoFocus />
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
      <div className="modal-footer">
        <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
        <Button type="button" loading={busy} disabled={busy} onClick={create}>
          {busy ? 'Création…' : 'Créer'}
        </Button>
      </div>
    </ResponsiveDialog>
  )
}

function RetenuesTab({ sousTraitantId }) {
  const { rows: ordres } = useFilteredList(
    installationsApi.getOrdresSousTraitance, { sous_traitant: sousTraitantId })
  const [ordreId, setOrdreId] = useState('')
  const { rows, loading, error, reload } = useFilteredList(
    installationsApi.getRetenuesGarantieSousTraitant,
    ordreId ? { ordre: ordreId } : { ordre: -1 })
  const [showCreate, setShowCreate] = useState(false)
  const [busyId, setBusyId] = useState(null)

  const lever = async (id) => {
    setBusyId(id)
    await installationsApi.leverRetenueGarantieSousTraitant(id).catch(() => {})
    setBusyId(null); reload()
  }

  return (
    <div className="flex flex-col gap-3">
      <label className="form-label" htmlFor="ret-ordre">Ordre de travaux</label>
      <select id="ret-ordre" className="form-control max-w-sm" value={ordreId} onChange={(e) => setOrdreId(e.target.value)}>
        <option value="">— Choisir un ordre —</option>
        {ordres.map((o) => <option key={o.id} value={o.id}>{o.reference}</option>)}
      </select>
      {!ordreId ? (
        <EmptyState title="Choisissez un ordre de travaux pour suivre ses retenues" className="py-6" />
      ) : (
        <>
          <div className="flex justify-end">
            <Button size="sm" onClick={() => setShowCreate(true)}>
              <PlusCircle className="size-4" aria-hidden="true" /> Nouvelle retenue
            </Button>
          </div>
          <ListShell loading={loading} error={error} empty="Aucune retenue sur cet ordre">
            {rows.length > 0 && rows.map((r) => (
              <div key={r.id} className="flex flex-wrap items-center gap-2 rounded-xl border border-border bg-card p-3" data-testid={`retenue-${r.id}`}>
                <span className="text-sm font-medium">{r.pourcentage}%</span>
                <span className="text-sm text-muted-foreground">Retenu : {formatMAD(r.montant_retenu)}</span>
                <Badge tone={r.levee ? 'success' : 'warning'}>{r.levee ? 'Levée' : 'Bloquée'}</Badge>
                {!r.levee && (
                  <Button size="sm" variant="outline" className="ml-auto" disabled={busyId === r.id} onClick={() => lever(r.id)}>
                    Lever la retenue
                  </Button>
                )}
              </div>
            ))}
          </ListShell>
          {showCreate && (
            <CreateRetenueDialog ordreId={Number(ordreId)}
              onClose={() => setShowCreate(false)}
              onCreated={() => { setShowCreate(false); reload() }} />
          )}
        </>
      )}
    </div>
  )
}

// ── Fiche sous-traitant (onglets) ────────────────────────────────────────────
function SousTraitantFiche({ sousTraitant, chantiers }) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-lg font-semibold">{sousTraitant.raison_sociale}</h2>
        <Badge tone="neutral">{sousTraitant.metier_display || sousTraitant.metier}</Badge>
        {!sousTraitant.actif && <Badge tone="danger">Archivé</Badge>}
      </div>
      <Tabs defaultValue="ordres" className="flex flex-col gap-4">
        <TabsList className="flex flex-wrap">
          <TabsTrigger value="ordres">Ordres</TabsTrigger>
          <TabsTrigger value="factures">Factures & règlements</TabsTrigger>
          <TabsTrigger value="attestations">Attestations</TabsTrigger>
          <TabsTrigger value="evaluation">Évaluation</TabsTrigger>
          <TabsTrigger value="retenues">Retenues de garantie</TabsTrigger>
        </TabsList>
        <TabsContent value="ordres">
          <OrdresTab sousTraitantId={sousTraitant.id} chantiers={chantiers} />
        </TabsContent>
        <TabsContent value="factures">
          <FacturesTab sousTraitantId={sousTraitant.id} />
        </TabsContent>
        <TabsContent value="attestations">
          <AttestationsTab sousTraitantId={sousTraitant.id} />
        </TabsContent>
        <TabsContent value="evaluation">
          <EvaluationTab sousTraitantId={sousTraitant.id} chantiers={chantiers} />
        </TabsContent>
        <TabsContent value="retenues">
          <RetenuesTab sousTraitantId={sousTraitant.id} chantiers={chantiers} />
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default function SousTraitanceChantier() {
  const [sousTraitants, setSousTraitants] = useState([])
  const [loadingSt, setLoadingSt] = useState(true)
  const [selected, setSelected] = useState(null)
  const [chantiers, setChantiers] = useState([])
  const [showCreateSt, setShowCreateSt] = useState(false)

  const fetchSousTraitants = useCallback(() => installationsApi.getSousTraitants({ page_size: 200 })
    .then((res) => {
      const rows = unwrap(res)
      setSousTraitants(rows)
      setSelected((cur) => (cur != null && rows.some((r) => r.id === cur))
        ? cur : (rows[0]?.id ?? null))
    })
    .catch(() => {})
    .finally(() => setLoadingSt(false)), [])

  const loadSousTraitants = useCallback(() => {
    setLoadingSt(true)
    return fetchSousTraitants()
  }, [fetchSousTraitants])

  useEffect(() => { fetchSousTraitants() }, [fetchSousTraitants])
  useEffect(() => {
    let alive = true
    installationsApi.getInstallations({ page_size: 200 })
      .then((res) => { if (alive) setChantiers(unwrap(res)) })
      .catch(() => {})
    return () => { alive = false }
  }, [])

  const current = sousTraitants.find((s) => s.id === selected) || null

  return (
    <div className="page flex flex-col gap-6">
      <PageHeader
        title="Sous-traitance chantier"
        subtitle="Ordres de travaux, factures, attestations, évaluations et retenues de garantie par sous-traitant."
      />
      <div className="flex flex-col gap-4 md:flex-row">
        <aside className="w-full md:w-72 flex-shrink-0 flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold">Sous-traitants</h3>
            <IconButton size="md" variant="outline" label="Nouveau sous-traitant" onClick={() => setShowCreateSt(true)}>
              <PlusCircle className="size-4" aria-hidden="true" />
            </IconButton>
          </div>
          {loadingSt ? (
            <p className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
              <Spinner className="size-4 text-primary" /> Chargement…
            </p>
          ) : sousTraitants.length === 0 ? (
            <EmptyState title="Aucun sous-traitant" description="Créez le premier sous-traitant de l'annuaire." className="py-4" />
          ) : (
            <ul className="flex flex-col gap-1" data-testid="liste-sous-traitants">
              {sousTraitants.map((s) => (
                <li key={s.id}>
                  <button type="button"
                    data-testid={`sous-traitant-${s.id}`}
                    className={`w-full text-left rounded-lg border px-3 py-2 text-sm ${selected === s.id ? 'border-primary bg-primary/5' : 'border-border'}`}
                    onClick={() => setSelected(s.id)}>
                    <span className="font-medium block">{s.raison_sociale}</span>
                    <span className="text-xs text-muted-foreground">{s.metier_display || s.metier}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>
        <div className="flex-1 min-w-0">
          {!current ? (
            <EmptyState title="Sélectionnez un sous-traitant"
              description="Choisissez un sous-traitant dans la liste, ou créez-en un nouveau."
              className="py-10" />
          ) : (
            <SousTraitantFiche sousTraitant={current} chantiers={chantiers} />
          )}
        </div>
      </div>
      {showCreateSt && (
        <CreateSousTraitantDialog
          onClose={() => setShowCreateSt(false)}
          onCreated={() => { setShowCreateSt(false); loadSousTraitants() }} />
      )}
    </div>
  )
}
