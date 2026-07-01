import { useEffect, useMemo, useState } from 'react'
import { BellRing } from 'lucide-react'
import contratsApi from '../../api/contratsApi'
import {
  Card, Badge, Button, Tabs, TabsList, TabsTrigger, TabsContent, toast,
} from '../../ui'
import { EcheanceCenter } from '../../ui/module'
import { formatDate } from '../../lib/format'
import SimpleTable from './SimpleTable'
import {
  StatutAlerte, StatutJalon, StatutObligation,
} from './status'

/* ============================================================================
   UX36 — Échéances & alertes.
   ----------------------------------------------------------------------------
   Centre d'échéances (préavis CONTRAT20 + à renouveler CONTRAT21) via
   EcheanceCenter, plus onglets : alertes planifiées (CONTRAT22), jalons
   (CONTRAT26), obligations à faire (CONTRAT26), SLA (CONTRAT27) et règles
   d'approbation (CONTRAT13). Lecture + quelques actions déclencheur.
   ========================================================================== */

const listData = (res) => (Array.isArray(res.data) ? res.data : (res.data?.results ?? []))

export default function EcheancesPage() {
  const [preavis, setPreavis] = useState([])
  const [renouveler, setRenouveler] = useState([])
  const [alertes, setAlertes] = useState([])
  const [jalons, setJalons] = useState([])
  const [obligations, setObligations] = useState([])
  const [sla, setSla] = useState([])
  const [regles, setRegles] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = () => {
    setLoading(true)
    setError(null)
    Promise.all([
      contratsApi.getPreavis().then((r) => setPreavis(Array.isArray(r.data) ? r.data : listData(r))),
      contratsApi.getARenouveler().then((r) => setRenouveler(Array.isArray(r.data) ? r.data : listData(r))),
      contratsApi.getAlertes().then((r) => setAlertes(listData(r))),
      contratsApi.getJalons().then((r) => setJalons(listData(r))),
      contratsApi.getObligations().then((r) => setObligations(listData(r))),
      contratsApi.getSla().then((r) => setSla(listData(r))),
      contratsApi.getReglesApprobation().then((r) => setRegles(listData(r))),
    ])
      .catch(() => setError('Impossible de charger les échéances.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    load()
  }, [])

  // Fusionne préavis + échéances en items du centre d'échéances.
  const echeanceItems = useMemo(() => {
    const items = []
    for (const c of preavis) {
      items.push({
        id: `preavis-${c.id}`,
        label: c.reference || c.objet || `Contrat #${c.id}`,
        meta: 'Préavis à traiter',
        daysLeft: c.jours_avant_preavis,
        to: `/contrats/${c.id}`,
      })
    }
    for (const c of renouveler) {
      items.push({
        id: `renew-${c.id}`,
        label: c.reference || c.objet || `Contrat #${c.id}`,
        meta: 'À renouveler / clôturer',
        daysLeft: c.jours_avant_echeance,
        to: `/contrats/${c.id}`,
      })
    }
    return items
  }, [preavis, renouveler])

  const declencher = async () => {
    try {
      const res = await contratsApi.declencherAlertes()
      toast.success(`${res.data?.nb_envoyees ?? 0} alerte(s) envoyée(s).`)
      load()
    } catch { toast.error('Déclenchement impossible.') }
  }

  const semer = async () => {
    try {
      const res = await contratsApi.semerAlertes(30)
      toast.success(`${res.data?.nb_creees ?? 0} alerte(s) créée(s).`)
      load()
    } catch { toast.error('Génération impossible.') }
  }

  const marquerJalon = async (jalonId) => {
    try {
      await contratsApi.marquerJalonAtteint(jalonId)
      toast.success('Jalon marqué atteint.')
      load()
    } catch { toast.error('Action impossible.') }
  }

  const marquerObligation = async (oblId) => {
    try {
      await contratsApi.marquerObligationFaite(oblId)
      toast.success('Obligation marquée réalisée.')
      load()
    } catch { toast.error('Action impossible.') }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <BellRing className="size-5 text-muted-foreground" aria-hidden="true" />
          <h1 className="font-display text-xl font-semibold tracking-tight">Échéances &amp; alertes</h1>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={semer}>Générer les alertes</Button>
          <Button size="sm" onClick={declencher}>Déclencher les alertes dues</Button>
        </div>
      </div>

      <EcheanceCenter
        title="Contrats à échéance (préavis + renouvellement)"
        items={echeanceItems}
        loading={loading}
        error={error}
        emptyText="Aucune échéance dans la fenêtre à venir."
      />

      <Tabs defaultValue="alertes">
        <TabsList className="flex-wrap">
          <TabsTrigger value="alertes">Alertes ({alertes.length})</TabsTrigger>
          <TabsTrigger value="jalons">Jalons ({jalons.length})</TabsTrigger>
          <TabsTrigger value="obligations">Obligations ({obligations.length})</TabsTrigger>
          <TabsTrigger value="sla">SLA ({sla.length})</TabsTrigger>
          <TabsTrigger value="regles">Approbation ({regles.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="alertes">
          <SimpleTable
            emptyText="Aucune alerte planifiée."
            rows={alertes}
            columns={[
              { header: 'Contrat', cell: (a) => <span className="font-mono text-xs">#{a.contrat}</span> },
              { header: 'Type', cell: (a) => a.type_alerte_display || a.type_alerte },
              { header: 'Déclenchement', cell: (a) => (a.date_declenchement ? formatDate(a.date_declenchement) : '—') },
              { header: 'Statut', cell: (a) => <StatutAlerte status={a.statut} /> },
            ]}
          />
        </TabsContent>

        <TabsContent value="jalons">
          <SimpleTable
            emptyText="Aucun jalon."
            rows={jalons}
            columns={[
              { header: 'N°', cell: (j) => <span className="font-mono">#{j.numero}</span> },
              { header: 'Intitulé', cell: (j) => <span className="font-medium">{j.intitule}</span> },
              { header: 'Cible', cell: (j) => (j.date_cible ? formatDate(j.date_cible) : '—') },
              { header: 'Statut', cell: (j) => <StatutJalon status={j.statut} /> },
              { header: '', cell: (j) => (j.statut !== 'atteint' ? (
                <Button variant="outline" size="sm" onClick={() => marquerJalon(j.id)}>Marquer atteint</Button>
              ) : <span className="text-xs text-muted-foreground">✓</span>), align: 'right' },
            ]}
          />
        </TabsContent>

        <TabsContent value="obligations">
          <SimpleTable
            emptyText="Aucune obligation."
            rows={obligations}
            columns={[
              { header: 'Intitulé', cell: (o) => <span className="font-medium">{o.intitule}</span> },
              { header: 'Redevable', cell: (o) => o.redevable_display || o.redevable },
              { header: 'Échéance', cell: (o) => (o.date_echeance ? formatDate(o.date_echeance) : '—') },
              { header: 'Statut', cell: (o) => <StatutObligation status={o.statut} /> },
              { header: '', cell: (o) => (o.statut !== 'faite' ? (
                <Button variant="outline" size="sm" onClick={() => marquerObligation(o.id)}>Marquer faite</Button>
              ) : <span className="text-xs text-muted-foreground">✓</span>), align: 'right' },
            ]}
          />
        </TabsContent>

        <TabsContent value="sla">
          <SimpleTable
            emptyText="Aucun engagement SLA."
            rows={sla}
            columns={[
              { header: 'Libellé', cell: (s) => <span className="font-medium">{s.libelle}</span> },
              { header: 'Taux cible', cell: (s) => (s.taux_cible != null ? `${s.taux_cible} %` : '—') },
              { header: 'Pénalité', cell: (s) => s.mode_penalite_display || s.mode_penalite },
              { header: 'Actif', cell: (s) => <Badge tone={s.actif ? 'success' : 'neutral'}>{s.actif ? 'Actif' : 'Inactif'}</Badge> },
            ]}
          />
        </TabsContent>

        <TabsContent value="regles">
          <Card className="mb-3 border-info/40 bg-info/5 p-3 text-sm text-muted-foreground">
            Workflow d’approbation interne : la règle ACTIVE la plus spécifique (montant + type) instancie les étapes du contrat.
          </Card>
          <SimpleTable
            emptyText="Aucune règle d’approbation."
            rows={regles}
            columns={[
              { header: 'Libellé', cell: (r) => <span className="font-medium">{r.libelle}</span> },
              { header: 'Type', cell: (r) => r.type_contrat_display || r.type_contrat || 'Tous' },
              { header: 'Bornes', cell: (r) => `${r.montant_min ?? '—'} → ${r.montant_max ?? '∞'}` },
              { header: 'Niveau', cell: (r) => r.niveau_approbation_display || r.niveau_approbation },
              { header: 'Actif', cell: (r) => <Badge tone={r.actif ? 'success' : 'neutral'}>{r.actif ? 'Actif' : 'Inactif'}</Badge> },
            ]}
          />
        </TabsContent>
      </Tabs>
    </div>
  )
}
