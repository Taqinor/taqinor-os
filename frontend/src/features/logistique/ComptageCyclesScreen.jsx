import { useCallback, useEffect, useMemo, useState } from 'react'
import { ClipboardList, PlusCircle } from 'lucide-react'
import PageHeader from '../../components/layout/PageHeader'
import { Button, Badge, Spinner, EmptyState } from '../../ui'
import installationsApi from '../../api/installationsApi'
import stockApi from '../../api/stockApi'
import {
  SESSION_COMPTAGE_STATUTS, CLASSE_ABC, grouperLignesParEcart, progressionComptage,
} from './logistique'

/* ============================================================================
   XSTK2 — Comptages cycliques (`/logistique/comptages`, FG324).
   ----------------------------------------------------------------------------
   Sessions de comptage TOURNANT (cycle ABC) : saisie des quantités comptées
   par SKU, écarts visibles avant clôture. DISTINCT de l'UI `inventaire-
   sessions` one-shot (stockApi, câblée par WR5) — ne pas dupliquer, ne pas
   toucher à cet écran ici. `quantite_theorique` est un SNAPSHOT posé serveur
   à l'ajout de ligne ; aucun prix d'achat n'est affiché ici (quantités
   uniquement).
   ========================================================================== */

export default function ComptageCyclesScreen() {
  const [sessions, setSessions] = useState([])
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    installationsApi.getSessionsComptage()
      .then((r) => {
        if (cancelled) return
        const rows = r.data?.results ?? r.data ?? []
        setSessions(rows)
        setSelected((prev) => (prev ? rows.find((s) => s.id === prev.id) || null : null))
      })
      .catch((err) => {
        if (cancelled) return
        setError(err?.response?.data?.detail || 'Chargement impossible.')
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => load(), [load])

  const creerSession = async () => {
    try {
      await installationsApi.createSessionComptage({ classe_abc: 'toutes' })
      load()
    } catch { /* remonté visuellement au prochain chargement si besoin */ }
  }

  return (
    <div className="page flex flex-col gap-6">
      <PageHeader
        title="Comptages cycliques"
        subtitle="Sessions de comptage tournant (cycle ABC) — saisie et validation des écarts."
        actions={(
          <Button size="sm" onClick={creerSession}>
            <PlusCircle className="size-4" aria-hidden="true" /> Nouvelle session
          </Button>
        )}
      />

      {loading && <p className="flex items-center gap-2 text-sm text-muted-foreground"><Spinner /> Chargement…</p>}
      {error && !loading && <EmptyState title="Impossible de charger les sessions" description={error} />}

      {!loading && !error && (
        <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
          <div className="flex flex-col gap-2">
            {sessions.length === 0 && (
              <EmptyState
                icon={ClipboardList}
                title="Aucune session"
                description="Créez une session de comptage cyclique."
              />
            )}
            {sessions.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => setSelected(s)}
                className={`rounded-xl border p-3 text-left transition-colors ${
                  selected?.id === s.id ? 'border-primary bg-primary/5' : 'border-border bg-card hover:bg-muted/40'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm font-medium">{s.reference}</span>
                  <Badge tone={s.statut === 'termine' ? 'success' : s.statut === 'en_cours' ? 'info' : 'neutral'}>
                    {SESSION_COMPTAGE_STATUTS[s.statut] || s.statut}
                  </Badge>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  {s.intitule || CLASSE_ABC[s.classe_abc] || s.classe_abc}
                </p>
              </button>
            ))}
          </div>

          <div>
            {selected ? (
              <SessionDetail session={selected} onChanged={load} />
            ) : (
              <EmptyState
                icon={ClipboardList}
                title="Sélectionnez une session"
                description="Choisissez une session dans la liste pour saisir les comptes."
              />
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function SessionDetail({ session, onChanged }) {
  const [produits, setProduits] = useState([])
  const [produitAAjouter, setProduitAAjouter] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    let alive = true
    stockApi.getProduits({ page_size: 200 })
      .then((r) => { if (alive) setProduits(r.data?.results ?? r.data ?? []) })
      .catch(() => { if (alive) setProduits([]) })
    return () => { alive = false }
  }, [])

  const { nonComptees, conformes, ecarts } = useMemo(
    () => grouperLignesParEcart(session.lignes), [session.lignes])
  const progression = useMemo(() => progressionComptage(session.lignes), [session.lignes])

  const ajouterLigne = async () => {
    if (!produitAAjouter) return
    setBusy(true)
    setError(null)
    try {
      await installationsApi.ajouterLigneComptage(session.id, produitAAjouter)
      setProduitAAjouter('')
      onChanged?.()
    } catch (err) {
      setError(err?.response?.data?.produit || 'Ajout impossible.')
    } finally { setBusy(false) }
  }

  const saisirCompte = async (ligne, quantite) => {
    setBusy(true)
    try {
      await installationsApi.updateComptageLigne(ligne.id, {
        quantite_comptee: quantite, compte: true,
      })
      onChanged?.()
    } catch { /* silencieux — la ligne reste éditable */ }
    finally { setBusy(false) }
  }

  const demarrer = async () => {
    setBusy(true)
    try { await installationsApi.demarrerComptage(session.id); onChanged?.() }
    finally { setBusy(false) }
  }
  const terminer = async () => {
    setBusy(true)
    try { await installationsApi.terminerComptage(session.id); onChanged?.() }
    finally { setBusy(false) }
  }

  const enCours = session.statut === 'en_cours'
  const termine = session.statut === 'termine'

  return (
    <div className="flex flex-col gap-4 rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-sm font-medium">{session.reference}</span>
        <Badge tone={termine ? 'success' : enCours ? 'info' : 'neutral'}>
          {SESSION_COMPTAGE_STATUTS[session.statut] || session.statut}
        </Badge>
        <span className="ml-auto text-xs text-muted-foreground">
          {progression.comptees}/{progression.total} comptées ({progression.pct}%)
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {session.statut === 'planifie' && (
          <Button size="sm" disabled={busy} onClick={demarrer}>Démarrer la session</Button>
        )}
        {enCours && (
          <Button size="sm" disabled={busy} onClick={terminer}>
            Clôturer (poste les écarts)
          </Button>
        )}
      </div>

      {enCours && (
        <div className="flex flex-wrap items-center gap-2">
          <select
            className="form-control w-auto min-w-[220px]"
            value={produitAAjouter}
            onChange={(e) => setProduitAAjouter(e.target.value)}
          >
            <option value="">— Ajouter un SKU à compter —</option>
            {produits.map((p) => (
              <option key={p.id} value={p.id}>{p.nom || p.sku}</option>
            ))}
          </select>
          <Button size="sm" variant="outline" disabled={busy || !produitAAjouter} onClick={ajouterLigne}>
            Ajouter
          </Button>
        </div>
      )}
      {error && <p className="form-error" role="alert">{error}</p>}

      {ecarts.length > 0 && (
        <section>
          <h4 className="mb-2 text-sm font-semibold text-destructive">Écarts constatés</h4>
          <LigneTable lignes={ecarts} enCours={enCours} onSaisir={saisirCompte} showEcart />
        </section>
      )}
      {nonComptees.length > 0 && (
        <section>
          <h4 className="mb-2 text-sm font-semibold">À compter</h4>
          <LigneTable lignes={nonComptees} enCours={enCours} onSaisir={saisirCompte} />
        </section>
      )}
      {conformes.length > 0 && (
        <section>
          <h4 className="mb-2 text-sm font-semibold text-success">Conformes</h4>
          <LigneTable lignes={conformes} enCours={enCours} onSaisir={saisirCompte} />
        </section>
      )}
      {session.lignes?.length === 0 && (
        <p className="text-sm text-muted-foreground">Aucun SKU dans cette session pour l’instant.</p>
      )}
    </div>
  )
}

function LigneTable({ lignes, enCours, onSaisir, showEcart }) {
  return (
    <div className="flex flex-col gap-1">
      {lignes.map((l) => (
        <div key={l.id} className="flex items-center gap-2 rounded border border-border p-2 text-sm">
          <span className="flex-1 truncate">{l.designation || l.produit_nom || '—'}</span>
          <span className="text-xs text-muted-foreground">théo. {l.quantite_theorique}</span>
          {enCours ? (
            <input
              type="number"
              noValidate
              step="any"
              className="form-control w-24"
              defaultValue={l.quantite_comptee ?? ''}
              onBlur={(e) => {
                const v = e.target.value
                if (v !== '' && Number(v) !== l.quantite_comptee) {
                  onSaisir(l, Math.round(Number(v)))
                }
              }}
              aria-label={`Quantité comptée pour ${l.designation || l.produit_nom || l.id}`}
            />
          ) : (
            <span className="w-24 text-right tabular-nums">{l.quantite_comptee ?? '—'}</span>
          )}
          {showEcart && (
            <Badge tone={l.ecart > 0 ? 'info' : 'danger'}>
              {l.ecart > 0 ? `+${l.ecart}` : l.ecart}
            </Badge>
          )}
        </div>
      ))}
    </div>
  )
}
