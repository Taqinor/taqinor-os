// PACT51 — Registre consolidé des paiements fournisseur + relevé RAS-TVA.
//
// NUANCE IMPORTANTE — ce n'est PAS un écran de saisie construit de zéro :
// « enregistrer qu'on a payé une facture » existe déjà, via l'action imbriquée
// de la fiche facture fournisseur (`factures-fournisseur/{id}/paiements/`), qui
// crée le MÊME modèle avec les mêmes garde-fous. Ce qui manquait, et que la
// ressource autonome `/stock/paiements-fournisseur/` exposait sans aucun
// appelant :
//
//   1. l'export du relevé RAS-TVA (XPUR2, LF 2024) pour la télédéclaration
//      Simpl-TVA — calculé côté serveur, aucun bouton nulle part ;
//   2. un REGISTRE CONSOLIDÉ de tous les paiements, tous fournisseurs
//      confondus (jusqu'ici visibles seulement facture par facture, jamais en
//      vue trésorerie) ;
//   3. le FLAG D'ESCOMPTE pour paiement anticipé (XPUR6) : calculé et renvoyé
//      par la ressource autonome à la création (`escompte_disponible_pct`),
//      mais silencieusement perdu par le chemin d'écran actuel, qui renvoie la
//      facture et non le paiement.
//
// La saisie ci-dessous passe donc DÉLIBÉRÉMENT par la ressource autonome : même
// modèle, mêmes contrôles serveur (conformité XPUR1, fournisseur bloqué XPUR4,
// exception 3-voies XPUR10, RAS-TVA XPUR2), mais le pourcentage d'escompte
// disponible est enfin affiché.
//
// Multi-tenant : `company` n'est JAMAIS envoyée — imposée côté serveur.
// Lecture tout rôle ; création réservée responsable/admin (re-vérifié serveur).
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Banknote, Download, Plus, PiggyBank } from 'lucide-react'
import api from '../../api/axios'
import { downloadBlob, filenameFromResponse } from '../../api/importApi'
import { useIsAdminOrResponsable } from '../../hooks/useHasPermission'
import { toast } from '../../ui/confirm'
import { frenchError } from '../../lib/frenchError'
import {
  Button, Input, Badge, Spinner, EmptyState, Card, CardContent,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { PageHeader } from '../../ui/PageHeader'
import { INVENTAIRE_ACCENT } from '../../features/stock/inventaireAccent'

// Miroir de PaiementFournisseur.Mode (backend).
const MODES = [
  ['virement', 'Virement'],
  ['cheque', 'Chèque'],
  ['especes', 'Espèces'],
  ['carte', 'Carte'],
  ['effet', 'Effet / traite'],
  ['autre', 'Autre'],
]
const MODE_LABELS = Object.fromEntries(MODES)

const nombre = (v) => {
  const n = Number(v)
  return Number.isFinite(n) ? n : 0
}

// Montant en dirhams. Formatage EXPLICITE (séparateur de milliers = espace
// ordinaire, virgule décimale) plutôt que `toLocaleString` : le séparateur
// produit par l'ICU varie selon l'environnement (espace fine insécable), ce qui
// rendrait l'affichage — et les tests — dépendants de la machine.
const fmtMad = (v) => {
  const [entier, decimales] = nombre(v).toFixed(2).split('.')
  return `${entier.replace(/\B(?=(\d{3})+(?!\d))/g, ' ')},${decimales} MAD`
}

// Date affichée telle qu'elle est stockée (jamais reconvertie via un fuseau :
// une date de paiement au format YYYY-MM-DD glisserait d'un jour).
const fmtDate = (valeur) => {
  if (!valeur) return '—'
  const m = String(valeur).match(/^(\d{4})-(\d{2})-(\d{2})/)
  return m ? `${m[3]}/${m[2]}/${m[1]}` : String(valeur)
}

export default function PaiementsFournisseurLedgerPage() {
  const canWrite = useIsAdminOrResponsable()

  const [paiements, setPaiements] = useState([])
  const [factures, setFactures] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [busy, setBusy] = useState(false)

  const [periode, setPeriode] = useState({ date_debut: '', date_fin: '' })
  const [draft, setDraft] = useState({
    facture: '', montant: '', date_paiement: '', mode: 'virement',
  })
  // XPUR6 — pourcentage d'escompte disponible sur le dernier paiement saisi.
  const [escompte, setEscompte] = useState(null)

  const charger = useCallback(() => api.get('/stock/paiements-fournisseur/')
    .then((res) => {
      setPaiements(res.data?.results ?? res.data ?? [])
      setLoadError(false)
    })
    .catch(() => setLoadError(true))
    .finally(() => setLoading(false)), [])

  useEffect(() => { charger() }, [charger])

  // Factures ouvertes, pour la saisie. Leur absence ne casse pas le registre.
  useEffect(() => {
    let annule = false
    api.get('/stock/factures-fournisseur/')
      .then((res) => {
        if (annule) return
        const rows = res.data?.results ?? res.data ?? []
        setFactures(Array.isArray(rows) ? rows : [])
      })
      .catch(() => { if (!annule) setFactures([]) })
    return () => { annule = true }
  }, [])

  // Filtre de période appliqué à l'affichage (le même que celui envoyé à
  // l'export RAS-TVA, pour que l'écran et le fichier racontent la même chose).
  const visibles = useMemo(() => paiements.filter((p) => {
    const d = p.date_paiement || ''
    if (periode.date_debut && (!d || d < periode.date_debut)) return false
    if (periode.date_fin && (!d || d > periode.date_fin)) return false
    return true
  }), [paiements, periode])

  const totaux = useMemo(() => visibles.reduce((acc, p) => ({
    brut: acc.brut + nombre(p.montant),
    ras: acc.ras + nombre(p.montant_ras_tva),
    net: acc.net + nombre(p.montant_net_paye ?? (nombre(p.montant) - nombre(p.montant_ras_tva))),
  }), { brut: 0, ras: 0, net: 0 }), [visibles])

  const exporterRasTva = async () => {
    const params = {}
    if (periode.date_debut) params.date_debut = periode.date_debut
    if (periode.date_fin) params.date_fin = periode.date_fin
    try {
      const res = await api.get('/stock/paiements-fournisseur/ras-tva/export/', {
        params, responseType: 'blob',
      })
      downloadBlob(res.data, filenameFromResponse(res, 'releve-ras-tva.xlsx'))
    } catch (e) {
      toast.error(frenchError(e, "L'export du relevé RAS-TVA a échoué."))
    }
  }

  const enregistrer = async () => {
    if (!draft.facture || !(Number(draft.montant) > 0)) return
    setBusy(true)
    setEscompte(null)
    try {
      const res = await api.post('/stock/paiements-fournisseur/', {
        facture: Number(draft.facture),
        montant: Number(draft.montant),
        date_paiement: draft.date_paiement || null,
        mode: draft.mode,
      })
      // XPUR6 — le pourcentage n'existe QUE sur cette réponse : on l'affiche.
      const pct = res.data?.escompte_disponible_pct
      if (pct !== undefined && pct !== null) setEscompte(String(pct))
      setDraft({ facture: '', montant: '', date_paiement: '', mode: 'virement' })
      charger()
    } catch (e) {
      toast.error(frenchError(e, "L'enregistrement du paiement a échoué."))
    } finally { setBusy(false) }
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-[1100px] p-6">
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner className="size-4 text-primary" /> Chargement…
        </p>
      </div>
    )
  }

  return (
    <div className="mx-auto flex max-w-[1100px] flex-col gap-4 p-6">
      <PageHeader
        style={{ '--module-accent': INVENTAIRE_ACCENT }}
        className="app-accent-rail mb-0"
        icon={Banknote}
        title="Paiements fournisseur — registre consolidé"
        subtitle="Tous les règlements, tous fournisseurs confondus, avec la retenue à la source sur la TVA (LF 2024) et le net réellement décaissé. Le relevé exporté sert de base à la télédéclaration Simpl-TVA."
      />

      {/* ── Période + export RAS-TVA ────────────────────────────────────── */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          <div className="flex flex-wrap items-end gap-1.5">
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-foreground" htmlFor="ledger-date-debut">
                Du
              </label>
              <Input id="ledger-date-debut" type="date" className="w-[160px]"
                value={periode.date_debut}
                onChange={(e) => setPeriode((p) => ({ ...p, date_debut: e.target.value }))} />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium text-foreground" htmlFor="ledger-date-fin">
                Au
              </label>
              <Input id="ledger-date-fin" type="date" className="w-[160px]"
                value={periode.date_fin}
                onChange={(e) => setPeriode((p) => ({ ...p, date_fin: e.target.value }))} />
            </div>
            <Button type="button" variant="outline" onClick={exporterRasTva}>
              <Download className="size-4" aria-hidden="true" /> Exporter le relevé RAS-TVA
            </Button>
          </div>
          <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground"
            data-testid="ledger-totaux">
            <span>Payé brut : <strong className="text-foreground">{fmtMad(totaux.brut)}</strong></span>
            <span>RAS-TVA retenue : <strong className="text-foreground">{fmtMad(totaux.ras)}</strong></span>
            <span>Net décaissé : <strong className="text-foreground">{fmtMad(totaux.net)}</strong></span>
          </div>
        </CardContent>
      </Card>

      {/* ── Registre ─────────────────────────────────────────────────────── */}
      <Card>
        <CardContent className="pt-4 sm:pt-5">
          {loadError ? (
            <EmptyState title="Impossible de charger les paiements"
              description="Une erreur est survenue lors du chargement." className="py-6" />
          ) : visibles.length === 0 ? (
            <EmptyState icon={Banknote} title="Aucun paiement sur la période"
              description="Élargissez la période ou enregistrez un règlement ci-dessous."
              className="py-6" />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="table-paiements">
                <thead>
                  <tr className="border-b border-border text-left">
                    <th scope="col" className="px-2 py-1.5 text-xs font-medium text-muted-foreground">Date</th>
                    <th scope="col" className="px-2 py-1.5 text-xs font-medium text-muted-foreground">Facture</th>
                    <th scope="col" className="px-2 py-1.5 text-xs font-medium text-muted-foreground">Mode</th>
                    <th scope="col" className="px-2 py-1.5 text-xs font-medium text-muted-foreground">Montant</th>
                    <th scope="col" className="px-2 py-1.5 text-xs font-medium text-muted-foreground">RAS-TVA</th>
                    <th scope="col" className="px-2 py-1.5 text-xs font-medium text-muted-foreground">Net décaissé</th>
                  </tr>
                </thead>
                <tbody>
                  {visibles.map((p) => (
                    <tr key={p.id} data-testid={`paiement-${p.id}`}
                      className="border-b border-border last:border-0">
                      <td className="px-2 py-1.5">{fmtDate(p.date_paiement || p.date_creation)}</td>
                      <td className="px-2 py-1.5">{p.facture_reference || `#${p.facture}`}</td>
                      <td className="px-2 py-1.5">{p.mode_display || MODE_LABELS[p.mode] || p.mode}</td>
                      <td className="px-2 py-1.5">{fmtMad(p.montant)}</td>
                      <td className="px-2 py-1.5">
                        {nombre(p.montant_ras_tva) > 0 ? (
                          <Badge tone="warning">
                            {fmtMad(p.montant_ras_tva)} ({p.taux_ras} %)
                          </Badge>
                        ) : '—'}
                      </td>
                      <td className="px-2 py-1.5">
                        {fmtMad(p.montant_net_paye ?? (nombre(p.montant) - nombre(p.montant_ras_tva)))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* ── Saisie (ressource autonome → flag d'escompte préservé) ───────── */}
      {canWrite && (
        <Card>
          <CardContent className="pt-4 sm:pt-5">
            <h3 className="mb-1 text-sm font-semibold tracking-tight text-foreground">
              Enregistrer un règlement
            </h3>
            <p className="mb-3 text-[11.5px] text-muted-foreground">
              La retenue à la source est calculée par le serveur ; si le
              règlement tombe dans la fenêtre d'escompte du fournisseur, le
              pourcentage disponible s'affiche ici — il n'est jamais déduit
              automatiquement.
            </p>

            {escompte !== null && (
              <div className="mb-3 flex items-center gap-2 rounded-lg border border-success/30 bg-success/12 px-3 py-2"
                data-testid="escompte-banner">
                <PiggyBank className="size-4 shrink-0 text-success" aria-hidden="true" />
                <span className="text-sm text-success">
                  Escompte pour paiement anticipé disponible : {escompte} %.
                </span>
              </div>
            )}

            <div className="flex flex-wrap items-end gap-1.5">
              <div className="min-w-[220px] flex-[2_1_220px]">
                <Select value={draft.facture}
                  onValueChange={(v) => setDraft((d) => ({ ...d, facture: v }))}>
                  <SelectTrigger aria-label="Facture fournisseur">
                    <SelectValue placeholder="Facture à régler" />
                  </SelectTrigger>
                  <SelectContent>
                    {factures.map((f) => (
                      <SelectItem key={f.id} value={String(f.id)}>
                        {f.reference} — {f.fournisseur_nom} ({fmtMad(f.solde_du)} dus)
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Input className="w-[140px]" type="number" step="any"
                aria-label="Montant du règlement" placeholder="Montant"
                value={draft.montant}
                onChange={(e) => setDraft((d) => ({ ...d, montant: e.target.value }))} />
              <Input className="w-[160px]" type="date"
                aria-label="Date du règlement"
                value={draft.date_paiement}
                onChange={(e) => setDraft((d) => ({ ...d, date_paiement: e.target.value }))} />
              <div className="w-[160px]">
                <Select value={draft.mode}
                  onValueChange={(v) => setDraft((d) => ({ ...d, mode: v }))}>
                  <SelectTrigger aria-label="Mode de règlement"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {MODES.map(([v, label]) => (
                      <SelectItem key={v} value={v}>{label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Button type="button" onClick={enregistrer} disabled={busy}>
                <Plus className="size-4" aria-hidden="true" /> Enregistrer le règlement
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
