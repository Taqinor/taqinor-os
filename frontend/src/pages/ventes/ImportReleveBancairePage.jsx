import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Upload, ArrowLeft } from 'lucide-react'
import ventesApi from '../../api/ventesApi'
import { frenchError } from '../../lib/frenchError'
import {
  Card, CardContent, Button, Input, Label, Badge, EmptyState,
} from '../../ui'
import { Table } from '../reporting/Table'
import { PageHeader } from '../../ui/PageHeader'
import { VENTES_ACCENT_STYLE } from '../../features/ventes/accent'

/* WIR265/FG42 — Import d'un relevé bancaire pour créer les encaissements
   clients. Le couple dry-run / commit existait côté serveur depuis FG42 sans
   AUCUN consommateur : cet écran est ce consommateur.

   Deux étapes strictes :
     1. « Analyser » → dry-run. N'écrit RIEN. Rend le mapping des colonnes, les
        en-têtes non reconnus, le statut de chaque ligne et les totaux.
     2. « Importer » → commit. Crée les Paiement manquants, puis affiche le
        bilan (créés / ignorés / erreurs).
   Les 400 métier du serveur (format invalide, fichier trop gros, trop de
   lignes) sont affichés en français, jamais du JSON brut. */

// Statuts renvoyés par `apps/ventes/paiement_import.dry_run`.
// source-choix: apps.ventes.paiement_import (statuts d'aperçu)
const STATUTS = {
  a_importer: { label: 'À importer', tone: 'success' },
  non_trouve: { label: 'Facture introuvable', tone: 'neutral' },
  deja_regle: { label: 'Déjà réglée', tone: 'neutral' },
  surpaiement: { label: 'Sur-paiement', tone: 'warning' },
  montant_invalide: { label: 'Montant invalide', tone: 'warning' },
}

const statutBadge = (s) => {
  const def = STATUTS[s] ?? { label: s, tone: 'neutral' }
  return <Badge tone={def.tone}>{def.label}</Badge>
}

export default function ImportReleveBancairePage() {
  const [fichier, setFichier] = useState(null)
  const [apercu, setApercu] = useState(null)   // réponse du dry-run
  const [bilan, setBilan] = useState(null)     // réponse du commit
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const choisirFichier = (e) => {
    setFichier(e.target.files?.[0] ?? null)
    // Changer de fichier invalide l'aperçu ET le bilan précédents : on ne
    // laisse jamais un « Importer » armé sur un fichier qui n'est plus celui
    // qui a été analysé.
    setApercu(null)
    setBilan(null)
    setError('')
  }

  const analyser = async () => {
    if (!fichier) { setError('Choisissez d\'abord un fichier de relevé.'); return }
    setBusy(true); setError(''); setBilan(null)
    try {
      const res = await ventesApi.importReleveDryRun(fichier)
      setApercu(res.data)
    } catch (err) {
      setApercu(null)
      setError(frenchError(err, 'Analyse du relevé impossible.'))
    } finally { setBusy(false) }
  }

  const importer = async () => {
    if (!fichier) return
    setBusy(true); setError('')
    try {
      const res = await ventesApi.importReleveCommit(fichier)
      setBilan(res.data)
    } catch (err) {
      setError(frenchError(err, 'Import du relevé impossible.'))
    } finally { setBusy(false) }
  }

  const aImporter = (apercu?.preview ?? [])
    .filter(l => l.statut === 'a_importer').length

  return (
    <div className="ui-root page">
      <PageHeader
        style={VENTES_ACCENT_STYLE}
        className="app-accent-rail"
        icon={Upload}
        title="Importer un relevé bancaire"
        subtitle="Créer les encaissements clients depuis un relevé XLSX ou CSV"
        actions={(
          <Button asChild size="sm" variant="outline">
            <Link to="/ventes/paiements">
              <ArrowLeft className="size-4" /> Encaissements
            </Link>
          </Button>
        )}
      />

      {error && (
        <div role="alert" className="mb-3 rounded border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* ── Étape 1 — choix du fichier + analyse (aucune écriture) ── */}
      <Card className="mb-4">
        <CardContent className="pt-5">
          <h2 className="mb-1 text-sm font-semibold">1. Choisir le relevé</h2>
          <p className="mb-3 text-[11.5px] text-muted-foreground">
            Fichier XLSX ou CSV, 5 Mo maximum. L'analyse ne crée aucun
            encaissement : elle montre d'abord ce qui serait importé.
          </p>
          <div className="flex flex-wrap items-end gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="ir-fichier">Fichier de relevé</Label>
              <Input id="ir-fichier" type="file" accept=".xlsx,.csv"
                     onChange={choisirFichier} />
            </div>
            <Button type="button" onClick={analyser} disabled={busy || !fichier}>
              {busy && !bilan ? 'Analyse…' : 'Analyser'}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* ── Étape 2 — aperçu du mapping + statuts + totaux, puis import ── */}
      {apercu && (
        <Card className="mb-4">
          <CardContent className="pt-5">
            <h2 className="mb-1 text-sm font-semibold">2. Vérifier puis importer</h2>

            <div className="mb-3 flex flex-wrap gap-4 text-sm">
              <span><strong>{apercu.total_rows}</strong> ligne(s) lue(s)</span>
              <span><strong>{apercu.matched}</strong> facture(s) trouvée(s)</span>
              <span><strong>{apercu.already_paid}</strong> déjà réglée(s)</span>
            </div>

            <div className="mb-3 text-[11.5px] text-muted-foreground">
              <div>
                Colonnes reconnues :{' '}
                {Object.keys(apercu.columns ?? {}).length === 0
                  ? 'aucune'
                  : Object.entries(apercu.columns)
                    .map(([entete, champ]) => `${entete} → ${champ}`).join(', ')}
              </div>
              {(apercu.unmapped ?? []).length > 0 && (
                <div className="mt-0.5">
                  Colonnes ignorées : {apercu.unmapped.join(', ')}
                </div>
              )}
            </div>

            <Table
              aria-label="Aperçu du relevé"
              getRowKey={(l) => l.ligne}
              columns={[
                { key: 'ligne', header: 'Ligne', cell: (l) => l.ligne },
                { key: 'date', header: 'Date', cell: (l) => l.date || '—' },
                { key: 'reference', header: 'Référence', cell: (l) => l.reference || '—' },
                { key: 'montant', header: 'Montant', align: 'right', cell: (l) => l.montant ?? '—' },
                { key: 'facture', header: 'Facture', cell: (l) => l.facture_reference || '—' },
                { key: 'statut', header: 'Statut', cell: (l) => statutBadge(l.statut) },
              ]}
              rows={apercu.preview ?? []}
              empty={(
                <EmptyState
                  icon={Upload}
                  title="Aucune ligne exploitable"
                  description="Le fichier ne contient aucune ligne de relevé reconnaissable."
                  className="border-0 py-6"
                />
              )}
            />

            <div className="mt-3 flex flex-wrap items-center gap-3">
              <Button type="button" onClick={importer} disabled={busy}>
                {busy ? 'Import…' : 'Importer'}
              </Button>
              <span className="text-[11.5px] text-muted-foreground">
                {aImporter} ligne(s) prête(s) à l'import dans cet aperçu (les
                dix premières lignes seulement sont affichées ; l'import traite
                tout le fichier).
              </span>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ── Bilan du commit ── */}
      {bilan && (
        <Card>
          <CardContent className="pt-5">
            <h2 className="mb-2 text-sm font-semibold">Résultat de l'import</h2>
            <div className="mb-3 flex flex-wrap gap-4 text-sm">
              <span><strong>{bilan.created}</strong> encaissement(s) créé(s)</span>
              <span><strong>{bilan.skipped}</strong> ignoré(s)</span>
              <span><strong>{bilan.errors}</strong> en erreur</span>
            </div>
            <p className="text-[11.5px] text-muted-foreground">
              Les encaissements créés apparaissent dans{' '}
              <Link className="text-info hover:underline" to="/ventes/paiements">
                Encaissements
              </Link>.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
