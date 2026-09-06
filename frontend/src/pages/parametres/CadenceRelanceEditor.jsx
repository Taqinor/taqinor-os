// MRY28 — Paramètres → CRM : éditeur des trois cadences de relance nommées
// (gabarit `parametres.CadenceRelanceEtape`, MRY4 — contrat `cadence_relance_v2`
// de MRY25). Édition EN PLACE des lignes seedées par cadence — aucune
// création/suppression ici : les gabarits sont posés par `seed_cadence`
// (idempotent, côté serveur), jamais inventés depuis cet écran.
import { useEffect, useState } from 'react'
import parametresApi from '../../api/parametresApi'
import {
  Input, Switch, Spinner, Label,
  Tabs, TabsList, TabsTrigger, TabsContent,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { toast } from '../../ui/confirm'

const CADENCES = [
  { value: 'contact', label: 'Contact' },
  { value: 'apres_devis', label: 'Après devis' },
  { value: 'reveil', label: 'Réveil' },
]

// L'enum du GABARIT de cadence, jamais `crm.Canal` (source du lead).
const CANAUX = [
  { value: 'appel', label: 'Appel' },
  { value: 'whatsapp', label: 'WhatsApp' },
  { value: 'email', label: 'E-mail' },
  { value: 'visite', label: 'Visite' },
]

// Sentinel pour l'option « aucun » : Radix Select n'autorise pas la valeur ''.
const NONE = '__none__'

const asList = (data) => (Array.isArray(data) ? data : (data?.results ?? []))

function CadenceTable({ cadence, gabarits }) {
  const [rows, setRows] = useState(null)

  useEffect(() => {
    let cancelled = false
    parametresApi.getCadenceRelance(cadence)
      .then(r => { if (!cancelled) setRows(asList(r.data)) })
      .catch(() => { if (!cancelled) setRows([]) })
    return () => { cancelled = true }
  }, [cadence])

  const patch = async (row, data) => {
    const prev = rows
    // Optimiste : reflète tout de suite, revient en arrière si le serveur refuse.
    setRows(rs => rs.map(r => (r.id === row.id ? { ...r, ...data } : r)))
    try {
      await parametresApi.updateCadenceRelanceEtape(row.id, data)
    } catch (e) {
      setRows(prev)
      toast.error(e?.response?.data?.detail ?? 'Modification impossible.')
    }
  }

  if (rows === null) return <Spinner />
  if (rows.length === 0) {
    return <p className="py-2 text-xs text-muted-foreground">Aucune étape pour cette cadence.</p>
  }
  return (
    <div className="space-y-2" data-testid={`cadence-table-${cadence}`}>
      {rows.map(row => (
        <div key={row.id}
             className="flex flex-wrap items-end gap-2 border rounded-md px-3 py-2">
          <div className="w-8 shrink-0 pb-2 text-sm text-muted-foreground">
            #{row.ordre}
          </div>
          <div className="flex flex-col gap-1">
            <Label className="text-xs" htmlFor={`cre-lib-${row.id}`}>Libellé</Label>
            <Input id={`cre-lib-${row.id}`} className="w-40" defaultValue={row.libelle}
                   onBlur={e => {
                     const v = e.target.value.trim()
                     if (v && v !== row.libelle) patch(row, { libelle: v })
                   }} />
          </div>
          <div className="flex flex-col gap-1">
            <Label className="text-xs" htmlFor={`cre-jours-${row.id}`}>Délai (j)</Label>
            <Input id={`cre-jours-${row.id}`} className="w-16" type="number" min="0" step="1"
                   defaultValue={row.delai_jours}
                   onBlur={e => {
                     const v = Math.max(0, Math.trunc(Number(e.target.value) || 0))
                     if (v !== row.delai_jours) patch(row, { delai_jours: v })
                   }} />
          </div>
          <div className="flex flex-col gap-1">
            <Label className="text-xs" htmlFor={`cre-min-${row.id}`}>Délai (min)</Label>
            <Input id={`cre-min-${row.id}`} className="w-16" type="number" min="0" max="1439" step="1"
                   defaultValue={row.delai_minutes}
                   onBlur={e => {
                     const v = Math.max(0, Math.trunc(Number(e.target.value) || 0))
                     if (v !== row.delai_minutes) patch(row, { delai_minutes: v })
                   }} />
          </div>
          <div className="flex flex-col gap-1">
            <Label className="text-xs" htmlFor={`cre-heure-${row.id}`}>Heure cible</Label>
            <Input id={`cre-heure-${row.id}`} className="w-28" type="time"
                   defaultValue={row.heure_cible ? row.heure_cible.slice(0, 5) : ''}
                   onBlur={e => {
                     const v = e.target.value || null
                     if (v !== (row.heure_cible ? row.heure_cible.slice(0, 5) : null)) {
                       patch(row, { heure_cible: v })
                     }
                   }} />
          </div>
          <div className="flex flex-col gap-1">
            <Label className="text-xs" id={`cre-canal-lbl-${row.id}`}>Canal</Label>
            <Select value={row.canal} onValueChange={v => patch(row, { canal: v })}>
              <SelectTrigger className="w-32" aria-labelledby={`cre-canal-lbl-${row.id}`}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CANAUX.map(c => (
                  <SelectItem key={c.value} value={c.value}>{c.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1">
            <Label className="text-xs" id={`cre-gab-lbl-${row.id}`}>Gabarit de message</Label>
            <Select value={row.template_cle || NONE}
                    onValueChange={v => patch(row, { template_cle: v === NONE ? '' : v })}>
              <SelectTrigger className="w-48" aria-labelledby={`cre-gab-lbl-${row.id}`}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE}>— Aucun —</SelectItem>
                {gabarits.map(g => (
                  <SelectItem key={g.cle} value={g.cle}>{g.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <label className="flex items-center gap-1.5 pb-2 text-sm text-foreground">
            <Switch checked={row.actif} onCheckedChange={v => patch(row, { actif: v })}
                    aria-label={`Active — étape ${row.ordre}`} />
            Active
          </label>
        </div>
      ))}
    </div>
  )
}

export default function CadenceRelanceEditor() {
  const [tab, setTab] = useState('contact')
  const [gabarits, setGabarits] = useState([])

  useEffect(() => {
    parametresApi.getMessages()
      .then(r => setGabarits(asList(r.data).map(m => ({ cle: m.cle, label: m.label }))))
      .catch(() => setGabarits([]))
  }, [])

  return (
    <Tabs value={tab} onValueChange={setTab} data-testid="cadence-relance-editor">
      <TabsList>
        {CADENCES.map(c => (
          <TabsTrigger key={c.value} value={c.value}>{c.label}</TabsTrigger>
        ))}
      </TabsList>
      {CADENCES.map(c => (
        <TabsContent key={c.value} value={c.value}>
          <CadenceTable cadence={c.value} gabarits={gabarits} />
        </TabsContent>
      ))}
    </Tabs>
  )
}
