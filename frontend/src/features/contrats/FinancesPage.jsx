import { useEffect, useState } from 'react'
import { Wallet } from 'lucide-react'
import contratsApi from '../../api/contratsApi'
import {
  Card, Badge, Button, Tabs, TabsList, TabsTrigger, TabsContent, toast,
} from '../../ui'
import { formatMAD, formatDate } from '../../lib/format'
import SimpleTable from './SimpleTable'
import {
  StatutRetenue, StatutCaution, StatutEcheancier, StatutLigneEcheance, StatutPiece,
} from './status'

/* ============================================================================
   UX37 — Finances de contrat.
   ----------------------------------------------------------------------------
   Retenues de garantie (CONTRAT28), cautions (CONTRAT29), échéanciers de
   paiement + lignes (CONTRAT30), indexations de prix (CONTRAT32) et pièces de
   conformité (CONTRAT34). Montants client-facing via formatMAD — jamais de prix
   d'achat ni de marge. Quelques actions serveur (libérer, pointer paiement).
   ========================================================================== */

const listData = (res) => (Array.isArray(res.data) ? res.data : (res.data?.results ?? []))

export default function FinancesPage() {
  const [retenues, setRetenues] = useState([])
  const [cautions, setCautions] = useState([])
  const [echeanciers, setEcheanciers] = useState([])
  const [lignes, setLignes] = useState([])
  const [indexations, setIndexations] = useState([])
  const [pieces, setPieces] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = () => {
    setLoading(true)
    setError(null)
    Promise.all([
      contratsApi.getRetenues().then((r) => setRetenues(listData(r))),
      contratsApi.getCautions().then((r) => setCautions(listData(r))),
      contratsApi.getEcheanciers().then((r) => setEcheanciers(listData(r))),
      contratsApi.getLignesEcheance().then((r) => setLignes(listData(r))),
      contratsApi.getIndexations().then((r) => setIndexations(listData(r))),
      contratsApi.getPiecesConformite().then((r) => setPieces(listData(r))),
    ])
      .catch(() => setError('Impossible de charger les finances de contrat.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    load()
  }, [])

  const liberer = async (retId) => {
    try {
      await contratsApi.libererRetenue(retId)
      toast.success('Retenue libérée.')
      load()
    } catch (e) { toast.error(e?.response?.data?.detail || 'Libération impossible.') }
  }

  const pointer = async (ligneId) => {
    try {
      await contratsApi.pointerPaiement(ligneId)
      toast.success('Paiement pointé.')
      load()
    } catch { toast.error('Pointage impossible.') }
  }

  const marquerPiece = async (pieceId) => {
    try {
      await contratsApi.marquerPieceFournie(pieceId)
      toast.success('Pièce marquée fournie.')
      load()
    } catch { toast.error('Action impossible.') }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <Wallet className="size-5 text-muted-foreground" aria-hidden="true" />
        <h1 className="font-display text-xl font-semibold tracking-tight">Finances de contrat</h1>
      </div>

      {error && (
        <Card className="border-destructive/40 p-3">
          <p className="text-sm text-destructive">{error}</p>
          <Button variant="outline" size="sm" className="mt-2" onClick={load}>Réessayer</Button>
        </Card>
      )}

      <Tabs defaultValue="retenues">
        <TabsList className="flex-wrap">
          <TabsTrigger value="retenues">Retenues ({retenues.length})</TabsTrigger>
          <TabsTrigger value="cautions">Cautions ({cautions.length})</TabsTrigger>
          <TabsTrigger value="echeanciers">Échéanciers ({echeanciers.length})</TabsTrigger>
          <TabsTrigger value="lignes">Lignes ({lignes.length})</TabsTrigger>
          <TabsTrigger value="indexations">Indexations ({indexations.length})</TabsTrigger>
          <TabsTrigger value="pieces">Conformité ({pieces.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="retenues">
          <SimpleTable
            emptyText={loading ? 'Chargement…' : 'Aucune retenue de garantie.'}
            rows={retenues}
            columns={[
              { header: 'Contrat', cell: (r) => <span className="font-mono text-xs">#{r.contrat}</span> },
              { header: 'Base', cell: (r) => (r.montant_base != null ? formatMAD(r.montant_base) : '—'), align: 'right' },
              { header: 'Taux', cell: (r) => (r.taux != null ? `${r.taux} %` : '—') },
              { header: 'Retenu', cell: (r) => (r.montant_retenu != null ? formatMAD(r.montant_retenu) : '—'), align: 'right' },
              { header: 'Libération prévue', cell: (r) => (r.date_liberation_prevue ? formatDate(r.date_liberation_prevue) : '—') },
              { header: 'Statut', cell: (r) => <StatutRetenue status={r.statut} /> },
              { header: '', cell: (r) => (r.statut === 'retenue' ? (
                <Button variant="outline" size="sm" onClick={() => liberer(r.id)}>Libérer</Button>
              ) : null), align: 'right' },
            ]}
          />
        </TabsContent>

        <TabsContent value="cautions">
          <SimpleTable
            emptyText={loading ? 'Chargement…' : 'Aucune caution.'}
            rows={cautions}
            columns={[
              { header: 'Type', cell: (c) => c.type_caution_display || c.type_caution },
              { header: 'Garant', cell: (c) => <span className="font-medium">{c.garant || '—'}</span> },
              { header: 'Référence', cell: (c) => c.reference || '—' },
              { header: 'Montant', cell: (c) => (c.montant != null ? formatMAD(c.montant) : '—'), align: 'right' },
              { header: 'Expiration', cell: (c) => (c.date_expiration ? formatDate(c.date_expiration) : '—') },
              { header: 'Statut', cell: (c) => <StatutCaution status={c.statut} /> },
            ]}
          />
        </TabsContent>

        <TabsContent value="echeanciers">
          <SimpleTable
            emptyText={loading ? 'Chargement…' : 'Aucun échéancier.'}
            rows={echeanciers}
            columns={[
              { header: 'Libellé', cell: (e) => <span className="font-medium">{e.libelle || `Échéancier #${e.id}`}</span> },
              { header: 'Contrat', cell: (e) => <span className="font-mono text-xs">#{e.contrat}</span> },
              { header: 'Périodicité', cell: (e) => e.periodicite_display || e.periodicite },
              { header: 'Total', cell: (e) => (e.montant_total != null ? formatMAD(e.montant_total) : '—'), align: 'right' },
              { header: 'Facturation', cell: (e) => <Badge tone={e.facturation_active ? 'success' : 'neutral'}>{e.facturation_active ? 'Active' : 'Inactive'}</Badge> },
              { header: 'Statut', cell: (e) => <StatutEcheancier status={e.statut} /> },
            ]}
          />
        </TabsContent>

        <TabsContent value="lignes">
          <SimpleTable
            emptyText={loading ? 'Chargement…' : 'Aucune ligne d’échéance.'}
            rows={lignes}
            columns={[
              { header: 'N°', cell: (l) => <span className="font-mono">#{l.numero}</span> },
              { header: 'Libellé', cell: (l) => l.libelle || '—' },
              { header: 'Échéance', cell: (l) => (l.date_echeance ? formatDate(l.date_echeance) : '—') },
              { header: 'Montant', cell: (l) => (l.montant != null ? formatMAD(l.montant) : '—'), align: 'right' },
              { header: 'Statut', cell: (l) => <StatutLigneEcheance status={l.statut} /> },
              { header: '', cell: (l) => (l.statut === 'a_venir' || l.statut === 'en_retard' ? (
                <Button variant="outline" size="sm" onClick={() => pointer(l.id)}>Pointer payé</Button>
              ) : null), align: 'right' },
            ]}
          />
        </TabsContent>

        <TabsContent value="indexations">
          <SimpleTable
            emptyText={loading ? 'Chargement…' : 'Aucune règle d’indexation.'}
            rows={indexations}
            columns={[
              { header: 'Libellé', cell: (i) => <span className="font-medium">{i.libelle}</span> },
              { header: 'Indice', cell: (i) => i.indice || '—' },
              { header: 'Valeur base', cell: (i) => (i.valeur_base != null ? i.valeur_base : '—'), align: 'right' },
              { header: 'Périodicité', cell: (i) => i.periodicite_display || i.periodicite },
              { header: 'Dernière révision', cell: (i) => (i.date_derniere_revision ? formatDate(i.date_derniere_revision) : '—') },
              { header: 'Actif', cell: (i) => <Badge tone={i.actif ? 'success' : 'neutral'}>{i.actif ? 'Actif' : 'Inactif'}</Badge> },
            ]}
          />
        </TabsContent>

        <TabsContent value="pieces">
          <SimpleTable
            emptyText={loading ? 'Chargement…' : 'Aucune pièce de conformité.'}
            rows={pieces}
            columns={[
              { header: 'Type', cell: (p) => p.type_piece_display || p.type_piece },
              { header: 'Libellé', cell: (p) => <span className="font-medium">{p.libelle || '—'}</span> },
              { header: 'Obligatoire', cell: (p) => <Badge tone={p.obligatoire ? 'warning' : 'neutral'}>{p.obligatoire ? 'Oui' : 'Non'}</Badge> },
              { header: 'Expiration', cell: (p) => (p.date_expiration ? formatDate(p.date_expiration) : '—') },
              { header: 'Statut', cell: (p) => <StatutPiece status={p.statut} /> },
              { header: '', cell: (p) => (p.statut === 'manquante' ? (
                <Button variant="outline" size="sm" onClick={() => marquerPiece(p.id)}>Marquer fournie</Button>
              ) : null), align: 'right' },
            ]}
          />
        </TabsContent>
      </Tabs>
    </div>
  )
}
