import { useState } from 'react'
import { Plus, Wand2, AlertTriangle, CheckCircle2 } from 'lucide-react'
import { ListShell } from '../../../ui/module'
import { Button, Card, Input, Label, toast } from '../../../ui'
import { formatDate } from '../../../lib/format'
import comptaApi from '../../../api/comptaApi'
import useComptaList from '../components/useComptaList.js'

/* ============================================================================
   PACT38 — Assistant de vente guidée.
   ----------------------------------------------------------------------------
   FG211 : fait répondre un commercial junior étape par étape (kWc du champ
   PV, puissance onduleur, type de système, présence batterie), valide la
   cohérence technique côté serveur (`services.evaluer_session_guided_selling`
   — ratio onduleur/kWc, hybride sans batterie…) et propose une composition.
   Ne crée PAS le devis lui-même. Une réponse incohérente affiche l'alerte
   renvoyée par le serveur — jamais un écran silencieusement « complet ».
   Endpoint /compta/guided-selling/.
   ========================================================================== */

const TYPES_SYSTEME = [
  { value: 'reseau', label: 'Réseau (injection)' },
  { value: 'hybride', label: 'Hybride' },
  { value: 'autonome', label: 'Autonome' },
]

function SessionForm({ session, onClose, onSaved }) {
  const [marche, setMarche] = useState(session?.marche || 'residentiel')
  const [kwc, setKwc] = useState(session?.reponses?.kwc ?? '')
  const [onduleurKw, setOnduleurKw] = useState(session?.reponses?.onduleur_kw ?? '')
  const [typeSysteme, setTypeSysteme] = useState(session?.reponses?.type_systeme || 'reseau')
  const [batterie, setBatterie] = useState(Boolean(session?.reponses?.batterie))
  const [resultat, setResultat] = useState(null)
  const [saving, setSaving] = useState(false)

  const evaluer = async () => {
    setSaving(true)
    setResultat(null)
    try {
      const reponses = {
        kwc: kwc === '' ? null : Number(kwc),
        onduleur_kw: onduleurKw === '' ? null : Number(onduleurKw),
        type_systeme: typeSysteme,
        batterie,
      }
      let id = session?.id
      if (id) {
        await comptaApi.sessionsGuidedSelling.update(id, { marche, reponses })
      } else {
        const res = await comptaApi.sessionsGuidedSelling.create({ marche, reponses })
        id = res.data.id
      }
      const res = await comptaApi.sessionsGuidedSelling.evaluer(id)
      setResultat(res.data)
      onSaved?.()
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : (d?.detail || 'Évaluation impossible.'))
    } finally {
      setSaving(false)
    }
  }

  const alertes = resultat?.alertes || []

  return (
    <Card className="flex flex-col gap-4 p-4 sm:p-5">
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <Label htmlFor="gs-marche">Marché</Label>
          <Input id="gs-marche" value={marche} onChange={(e) => setMarche(e.target.value)} />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="gs-kwc">Puissance du champ PV (kWc)</Label>
          <Input id="gs-kwc" type="number" step="any" value={kwc} onChange={(e) => setKwc(e.target.value)} />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="gs-onduleur">Puissance onduleur (kW)</Label>
          <Input id="gs-onduleur" type="number" step="any" value={onduleurKw}
            onChange={(e) => setOnduleurKw(e.target.value)} />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="gs-type">Type de système</Label>
          <select id="gs-type" className="h-[var(--control-h)] rounded-md border border-input bg-card px-[var(--control-px)] text-sm"
            value={typeSysteme} onChange={(e) => setTypeSysteme(e.target.value)}>
            {TYPES_SYSTEME.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={batterie} onChange={(e) => setBatterie(e.target.checked)} />
          Batterie
        </label>
        <Button onClick={evaluer} disabled={saving}>
          <Wand2 className="size-4" /> {saving ? 'Évaluation…' : 'Évaluer'}
        </Button>
        {onClose && <Button type="button" variant="outline" onClick={onClose}>Fermer</Button>}
      </div>

      {resultat && (
        <div className="flex flex-col gap-2">
          {alertes.length > 0 ? (
            alertes.map((a, i) => (
              <div key={i} className="flex items-center gap-2 rounded-md border border-warning/40 bg-warning/10 p-2 text-sm text-warning">
                <AlertTriangle className="size-4 shrink-0" /> {a}
              </div>
            ))
          ) : (
            <div className="flex items-center gap-2 rounded-md border border-success/40 bg-success/10 p-2 text-sm text-success">
              <CheckCircle2 className="size-4 shrink-0" />
              {resultat.complet ? 'Configuration cohérente et complète.' : 'Aucune alerte, configuration incomplète.'}
            </div>
          )}
          <p className="text-xs text-muted-foreground">
            Composition proposée (calculée par le serveur) : {JSON.stringify(resultat.composition)}
          </p>
        </div>
      )}
    </Card>
  )
}

export default function GuidedSellingPage() {
  const [ouverte, setOuverte] = useState(null)
  const [nouvelle, setNouvelle] = useState(false)
  const list = useComptaList(comptaApi.sessionsGuidedSelling.list, undefined)

  const columns = [
    { id: 'id', header: 'Session', accessor: (r) => r.id, cell: (v) => <span className="font-mono text-xs">#{v}</span>, width: 90 },
    { id: 'marche', header: 'Marché', accessor: (r) => r.marche },
    { id: 'complet', header: 'État', accessor: (r) => (r.complet ? 'Complète' : 'Incomplète') },
    { id: 'date', header: 'Créée le', accessor: (r) => r.date_creation, searchable: false, cell: (v) => formatDate(v) },
  ]

  return (
    <div className="page">
      <div className="page-header">
        <h2>Assistant de vente guidée</h2>
        <div className="page-header-actions">
          <Button onClick={() => { setOuverte(null); setNouvelle(true) }}><Plus /> Nouvelle session</Button>
        </div>
      </div>

      {(nouvelle || ouverte) && (
        <SessionForm
          session={ouverte}
          onClose={() => { setNouvelle(false); setOuverte(null) }}
          onSaved={list.reload}
        />
      )}

      <ListShell
        hideHeader
        title="Sessions"
        columns={columns}
        rows={list.rows}
        loading={list.loading}
        error={list.error}
        onRowClick={(row) => { setNouvelle(false); setOuverte(row) }}
        exportName="guided-selling"
        emptyTitle="Aucune session"
        emptyDescription="Aucune session de configuration guidée pour l'instant."
      />
    </div>
  )
}
