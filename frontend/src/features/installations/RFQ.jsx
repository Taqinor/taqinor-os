/* ============================================================================
   PACT60 — Consultation fournisseurs et comparatif d'offres.
   ----------------------------------------------------------------------------
   Trou (a) : `views/rfq.py` porte le cycle complet (envoyer, clôturer, retenir
   une offre avec adjudication possible d'un bon de commande) plus les offres
   reçues et la liste des fournisseurs consultés avec relance — trois
   ressources sans appelant.
   ========================================================================== */
import { useCallback, useEffect, useState } from 'react'
import { PlusCircle } from 'lucide-react'
import PageHeader from '../../components/layout/PageHeader'
import { Badge, Button, Spinner, EmptyState } from '../../ui'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
import { formatDate, formatMAD } from '../../lib/format'
import installationsApi from '../../api/installationsApi'
import stockApi from '../../api/stockApi'

const STATUT_TONE = { brouillon: 'neutral', envoyee: 'info', cloturee: 'success' }

function unwrap(res) {
  const p = res?.data
  return Array.isArray(p) ? p : (p?.results ?? [])
}

// ── Créer une RFQ ────────────────────────────────────────────────────────────
function CreateRFQDialog({ demandes, onClose, onCreated }) {
  const [objet, setObjet] = useState('')
  const [demande, setDemande] = useState('')
  const [dateLimite, setDateLimite] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const create = async () => {
    if (!objet.trim()) { setError("L'objet est obligatoire."); return }
    setBusy(true); setError(null)
    try {
      await installationsApi.createRFQ({
        objet: objet.trim(), demande: demande ? Number(demande) : null,
        date_limite_reponse: dateLimite || null,
      })
      onCreated?.()
    } catch (err) {
      setError(err?.response?.data?.objet?.[0]
        || err?.response?.data?.detail || 'Création impossible.')
    } finally { setBusy(false) }
  }
  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }} className="sm:max-w-lg" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">Nouvelle consultation (RFQ)</h3>
        <button type="button" className="modal-close" onClick={onClose}>✕</button>
      </div>
      <div className="modal-body flex flex-col gap-3">
        <label className="form-label" htmlFor="rfq-objet">Objet</label>
        <input id="rfq-objet" type="text" className="form-control" value={objet} onChange={(e) => setObjet(e.target.value)} autoFocus />
        <label className="form-label" htmlFor="rfq-demande">Demande d'achat (optionnel)</label>
        <select id="rfq-demande" className="form-control" value={demande} onChange={(e) => setDemande(e.target.value)}>
          <option value="">—</option>
          {demandes.map((d) => <option key={d.id} value={d.id}>{d.reference || `#${d.id}`}</option>)}
        </select>
        <label className="form-label" htmlFor="rfq-limite">Date limite de réponse (optionnel)</label>
        <input id="rfq-limite" type="date" className="form-control" value={dateLimite} onChange={(e) => setDateLimite(e.target.value)} />
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

// ── Consulter un fournisseur ────────────────────────────────────────────────
function ConsulterFournisseurDialog({ rfqId, fournisseurs, onClose, onCreated }) {
  const [fournisseur, setFournisseur] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const create = async () => {
    if (!fournisseur) { setError('Choisissez un fournisseur.'); return }
    setBusy(true); setError(null)
    try {
      await installationsApi.consulterFournisseurRFQ(rfqId, Number(fournisseur))
      onCreated?.()
    } catch (err) {
      setError(err?.response?.data?.fournisseur?.[0]
        || err?.response?.data?.detail || 'Ajout impossible.')
    } finally { setBusy(false) }
  }
  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }} className="sm:max-w-sm" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">Consulter un fournisseur</h3>
        <button type="button" className="modal-close" onClick={onClose}>✕</button>
      </div>
      <div className="modal-body flex flex-col gap-3">
        <label className="form-label" htmlFor="rfq-fournisseur">Fournisseur</label>
        <select id="rfq-fournisseur" className="form-control" value={fournisseur} onChange={(e) => setFournisseur(e.target.value)} autoFocus>
          <option value="">— Choisir —</option>
          {fournisseurs.map((f) => <option key={f.id} value={f.id}>{f.nom}</option>)}
        </select>
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
      <div className="modal-footer">
        <Button type="button" variant="outline" onClick={onClose}>Annuler</Button>
        <Button type="button" loading={busy} disabled={busy} onClick={create}>
          {busy ? 'Ajout…' : 'Ajouter'}
        </Button>
      </div>
    </ResponsiveDialog>
  )
}

// ── Saisir une offre ─────────────────────────────────────────────────────────
function AddOffreDialog({ rfqId, fournisseurs, onClose, onCreated }) {
  const [fournisseur, setFournisseur] = useState('')
  const [nomLibre, setNomLibre] = useState('')
  const [montantHt, setMontantHt] = useState('')
  const [delaiJours, setDelaiJours] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const create = async () => {
    if (!fournisseur && !nomLibre.trim()) {
      setError('Indiquez un fournisseur ou un nom libre.')
      return
    }
    if (!montantHt) { setError('Le montant HT est requis.'); return }
    setBusy(true); setError(null)
    try {
      await installationsApi.createRFQOffre({
        rfq: rfqId, fournisseur: fournisseur ? Number(fournisseur) : null,
        fournisseur_nom_libre: fournisseur ? undefined : nomLibre.trim(),
        montant_ht: montantHt, delai_jours: delaiJours || undefined,
      })
      onCreated?.()
    } catch (err) {
      setError(err?.response?.data?.fournisseur?.[0]
        || err?.response?.data?.detail || 'Création impossible.')
    } finally { setBusy(false) }
  }
  return (
    <ResponsiveDialog open onOpenChange={(o) => { if (!o) onClose() }} className="sm:max-w-lg" showClose={false}>
      <div className="modal-header">
        <h3 className="modal-title">Nouvelle offre reçue</h3>
        <button type="button" className="modal-close" onClick={onClose}>✕</button>
      </div>
      <div className="modal-body flex flex-col gap-3">
        <label className="form-label" htmlFor="offre-fournisseur">Fournisseur (annuaire, optionnel)</label>
        <select id="offre-fournisseur" className="form-control" value={fournisseur} onChange={(e) => setFournisseur(e.target.value)} autoFocus>
          <option value="">—</option>
          {fournisseurs.map((f) => <option key={f.id} value={f.id}>{f.nom}</option>)}
        </select>
        <label className="form-label" htmlFor="offre-libre">Ou nom libre (si hors annuaire)</label>
        <input id="offre-libre" type="text" className="form-control" value={nomLibre} onChange={(e) => setNomLibre(e.target.value)} disabled={!!fournisseur} />
        <label className="form-label" htmlFor="offre-montant">Montant HT (MAD)</label>
        <input id="offre-montant" type="number" step="any" className="form-control" value={montantHt} onChange={(e) => setMontantHt(e.target.value)} />
        <label className="form-label" htmlFor="offre-delai">Délai (jours, optionnel)</label>
        <input id="offre-delai" type="number" className="form-control" value={delaiJours} onChange={(e) => setDelaiJours(e.target.value)} />
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

function RFQFiche({ rfq, fournisseurs, onChanged }) {
  const [showConsulter, setShowConsulter] = useState(false)
  const [showOffre, setShowOffre] = useState(false)
  const [busy, setBusy] = useState(false)
  const comparatif = rfq.comparatif || {}
  const offres = rfq.offres || []
  const consultations = rfq.consultations || []

  const envoyer = async () => { setBusy(true); await installationsApi.envoyerRFQ(rfq.id).catch(() => {}); setBusy(false); onChanged?.() }
  const cloturer = async () => { setBusy(true); await installationsApi.cloturerRFQ(rfq.id).catch(() => {}); setBusy(false); onChanged?.() }
  const envoyerConsultations = async () => { setBusy(true); await installationsApi.envoyerConsultationsRFQ(rfq.id).catch(() => {}); setBusy(false); onChanged?.() }
  const relancer = async () => { setBusy(true); await installationsApi.relancerNonRepondantsRFQ(rfq.id).catch(() => {}); setBusy(false); onChanged?.() }
  const retenir = async (offreId) => { setBusy(true); await installationsApi.retenirOffreRFQ(rfq.id, offreId).catch(() => {}); setBusy(false); onChanged?.() }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-lg font-semibold">{rfq.objet}</h2>
        <span className="text-sm text-muted-foreground">{rfq.reference}</span>
        <Badge tone={STATUT_TONE[rfq.statut] || 'neutral'}>{rfq.statut_display || rfq.statut}</Badge>
        <div className="ml-auto flex gap-2">
          {rfq.statut === 'brouillon' && (
            <Button size="sm" variant="outline" disabled={busy} onClick={envoyer}>Envoyer</Button>
          )}
          {rfq.statut !== 'cloturee' && (
            <Button size="sm" variant="outline" disabled={busy} onClick={cloturer}>Clôturer</Button>
          )}
        </div>
      </div>

      <div className="flex flex-col gap-2 rounded-xl border border-border bg-card p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold">Fournisseurs consultés</h3>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={() => setShowConsulter(true)}>
              <PlusCircle className="size-4" aria-hidden="true" /> Consulter
            </Button>
            <Button size="sm" variant="outline" disabled={busy || consultations.length === 0} onClick={envoyerConsultations}>
              Envoyer aux fournisseurs
            </Button>
            <Button size="sm" variant="outline" disabled={busy || consultations.length === 0} onClick={relancer}>
              Relancer non-répondants
            </Button>
          </div>
        </div>
        {consultations.length === 0
          ? <p className="text-xs text-muted-foreground">Aucun fournisseur consulté.</p>
          : consultations.map((c) => (
            <div key={c.id} className="flex flex-wrap items-center gap-2 text-sm" data-testid={`consultation-${c.id}`}>
              <span className="font-medium">{c.fournisseur_nom}</span>
              <Badge tone={c.a_repondu ? 'success' : 'warning'}>{c.a_repondu ? 'A répondu' : 'En attente'}</Badge>
              {c.nb_relances > 0 && <span className="text-xs text-muted-foreground">{c.nb_relances} relance(s)</span>}
            </div>
          ))}
      </div>

      <div className="flex flex-col gap-2 rounded-xl border border-border bg-card p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold">Offres comparées ({comparatif.nb_offres ?? offres.length})</h3>
          <Button size="sm" onClick={() => setShowOffre(true)}>
            <PlusCircle className="size-4" aria-hidden="true" /> Nouvelle offre
          </Button>
        </div>
        {offres.length === 0
          ? <EmptyState title="Aucune offre reçue" className="py-4" />
          : (
            <div className="flex flex-col gap-2">
              {offres.map((o) => (
                <div key={o.id} className="flex flex-wrap items-center gap-2 rounded-lg border border-border p-2 text-sm" data-testid={`offre-${o.id}`}>
                  <span className="font-medium">{o.fournisseur_nom || o.fournisseur_nom_libre}</span>
                  <span>{formatMAD(o.montant_ht)}</span>
                  {o.delai_jours != null && <span className="text-muted-foreground">{o.delai_jours} j</span>}
                  {comparatif.moins_chere_id === o.id && <Badge tone="success">Moins chère</Badge>}
                  {comparatif.plus_rapide_id === o.id && <Badge tone="info">Plus rapide</Badge>}
                  {o.retenue && <Badge tone="primary">Retenue</Badge>}
                  {!o.retenue && (
                    <Button size="sm" variant="outline" className="ml-auto" disabled={busy} onClick={() => retenir(o.id)}>
                      Retenir
                    </Button>
                  )}
                </div>
              ))}
            </div>
          )}
      </div>

      {showConsulter && (
        <ConsulterFournisseurDialog rfqId={rfq.id} fournisseurs={fournisseurs}
          onClose={() => setShowConsulter(false)}
          onCreated={() => { setShowConsulter(false); onChanged?.() }} />
      )}
      {showOffre && (
        <AddOffreDialog rfqId={rfq.id} fournisseurs={fournisseurs}
          onClose={() => setShowOffre(false)}
          onCreated={() => { setShowOffre(false); onChanged?.() }} />
      )}
    </div>
  )
}

export default function RFQ() {
  const [rfqs, setRfqs] = useState([])
  const [loadingList, setLoadingList] = useState(true)
  const [selected, setSelected] = useState(null)
  const [showCreate, setShowCreate] = useState(false)
  const [fournisseurs, setFournisseurs] = useState([])
  const [demandes, setDemandes] = useState([])

  const fetchRFQs = useCallback(() => installationsApi.getRFQs({ page_size: 200 })
    .then((res) => {
      const rows = unwrap(res)
      setRfqs(rows)
      setSelected((cur) => (cur != null && rows.some((r) => r.id === cur))
        ? cur : (rows[0]?.id ?? null))
    })
    .catch(() => {})
    .finally(() => setLoadingList(false)), [])

  const loadRFQs = useCallback(() => {
    setLoadingList(true)
    return fetchRFQs()
  }, [fetchRFQs])

  useEffect(() => { fetchRFQs() }, [fetchRFQs])
  useEffect(() => {
    let alive = true
    Promise.all([
      stockApi.getFournisseurs({ page_size: 200 }).catch(() => ({ data: [] })),
      installationsApi.getDemandesAchat({ page_size: 200 }).catch(() => ({ data: [] })),
    ]).then(([f, d]) => {
      if (!alive) return
      setFournisseurs(unwrap(f))
      setDemandes(unwrap(d))
    })
    return () => { alive = false }
  }, [])

  const current = rfqs.find((r) => r.id === selected) || null

  return (
    <div className="page flex flex-col gap-6">
      <PageHeader
        title="Consultation fournisseurs"
        subtitle="Demandes de prix multi-fournisseurs, envoi, relance et comparatif d'offres côte à côte."
      />
      <div className="flex flex-col gap-4 md:flex-row">
        <aside className="w-full md:w-72 flex-shrink-0 flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold">Consultations (RFQ)</h3>
            <Button size="sm" variant="outline" aria-label="Nouvelle RFQ" onClick={() => setShowCreate(true)}>
              <PlusCircle className="size-4" aria-hidden="true" />
            </Button>
          </div>
          {loadingList ? (
            <p className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
              <Spinner className="size-4 text-primary" /> Chargement…
            </p>
          ) : rfqs.length === 0 ? (
            <EmptyState title="Aucune RFQ" description="Créez la première consultation fournisseurs." className="py-4" />
          ) : (
            <ul className="flex flex-col gap-1" data-testid="liste-rfq">
              {rfqs.map((r) => (
                <li key={r.id}>
                  <button type="button"
                    data-testid={`rfq-${r.id}`}
                    className={`w-full text-left rounded-lg border px-3 py-2 text-sm ${selected === r.id ? 'border-primary bg-primary/5' : 'border-border'}`}
                    onClick={() => setSelected(r.id)}>
                    <span className="font-medium block">{r.objet}</span>
                    <span className="text-xs text-muted-foreground">
                      {r.statut_display || r.statut} · {formatDate(r.date_limite_reponse)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>
        <div className="flex-1 min-w-0">
          {!current ? (
            <EmptyState title="Sélectionnez une consultation"
              description="Choisissez une RFQ dans la liste, ou créez-en une nouvelle."
              className="py-10" />
          ) : (
            <RFQFiche rfq={current} fournisseurs={fournisseurs} onChanged={loadRFQs} />
          )}
        </div>
      </div>
      {showCreate && (
        <CreateRFQDialog demandes={demandes}
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); loadRFQs() }} />
      )}
    </div>
  )
}
