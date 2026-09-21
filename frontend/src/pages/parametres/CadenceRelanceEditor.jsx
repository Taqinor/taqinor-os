// MRY28 — Paramètres → CRM : éditeur des trois cadences de relance nommées
// (gabarit `parametres.CadenceRelanceEtape`, MRY4 — contrat `cadence_relance_v2`
// de MRY25). Édition EN PLACE des lignes seedées par cadence.
//
// CAD53 (décision fondateur du 21/09/2026) — l'éditeur OUVRE l'ajout et la
// suppression d'un barreau, et expose la case « Autorisée le dimanche
// (16 h-19 h) » que le moteur lit déjà (`dimanche_ok`). Garde-fou décisif :
// **jamais rétroactif**. Le gabarit est copié barreau par barreau à
// l'initialisation d'un plan (`initialiser_plan_relance`), donc un plan DÉJÀ
// lancé garde ses touches, ses libellés et ses dates — l'écran le rappelle en
// toutes lettres plutôt que de laisser la commerciale le deviner.
import { useEffect, useState } from 'react'
import { Plus, Trash2, Info } from 'lucide-react'
import parametresApi from '../../api/parametresApi'
import {
  Input, Switch, Spinner, Label, Button, IconButton,
  Tabs, TabsList, TabsTrigger, TabsContent,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { ConfirmDialog } from '../../ui/ConfirmDialog'
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

// CAD53 — la phrase que l'écran doit dire, et qu'il ne disait pas : modifier
// le gabarit ne touche AUCUN plan en cours.
const AVERTISSEMENT_NON_RETROACTIF = (
  'Ces réglages ne s’appliquent qu’aux relances à venir : un plan déjà lancé '
  + 'garde ses touches, ses libellés et ses dates.'
)

function CadenceTable({ cadence, gabarits }) {
  const [rows, setRows] = useState(null)
  // CAD53 — suppression d'un barreau : confirmation explicite, jamais un
  // `window.confirm` (patron maison `ConfirmDialog`).
  const [aSupprimer, setASupprimer] = useState(null)
  const [suppression, setSuppression] = useState(false)
  const [ajout, setAjout] = useState(false)

  useEffect(() => {
    let cancelled = false
    parametresApi.getCadenceRelance(cadence)
      .then(r => { if (!cancelled) setRows(asList(r.data)) })
      .catch(() => { if (!cancelled) setRows([]) })
    return () => { cancelled = true }
  }, [cadence])

  const recharger = () => parametresApi.getCadenceRelance(cadence)
    .then(r => setRows(asList(r.data)))
    .catch(() => { /* la liste affichée reste celle qu'on avait */ })

  const ajouter = async () => {
    setAjout(true)
    try {
      // `ordre` est calculé par le serveur (le seul à connaître la cadence
      // entière) ; le libellé est modifiable juste après, en place.
      await parametresApi.createCadenceRelanceEtape({
        cadence, libelle: 'Nouveau barreau', delai_jours: 1,
        delai_minutes: 0, canal: 'appel', template_cle: '',
        dimanche_ok: false, actif: true,
      })
      await recharger()
    } catch (e) {
      const data = e?.response?.data
      toast.error(data?.ordre ?? data?.detail ?? 'Ajout impossible.')
    } finally {
      setAjout(false)
    }
  }

  const confirmerSuppression = async () => {
    if (!aSupprimer) return
    setSuppression(true)
    try {
      await parametresApi.deleteCadenceRelanceEtape(aSupprimer.id)
      setASupprimer(null)
      await recharger()
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Suppression impossible.')
    } finally {
      setSuppression(false)
    }
  }

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
  const entete = (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <p className="flex items-start gap-1.5 text-xs text-muted-foreground"
         role="note">
        <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
        {AVERTISSEMENT_NON_RETROACTIF}
      </p>
      <Button size="sm" variant="outline" onClick={ajouter} disabled={ajout}>
        <Plus className="size-3.5" /> Ajouter un barreau
      </Button>
    </div>
  )
  if (rows.length === 0) {
    return (
      <div className="space-y-2" data-testid={`cadence-table-${cadence}`}>
        {entete}
        <p className="py-2 text-xs text-muted-foreground">Aucune étape pour cette cadence.</p>
      </div>
    )
  }
  return (
    <div className="space-y-2" data-testid={`cadence-table-${cadence}`}>
      {entete}
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
          {/* CAD53 — la case que le moteur lit déjà (`dimanche_ok`) : seule
              une touche marquée ainsi peut tomber un dimanche, dans la
              fenêtre 16 h-19 h du protocole v3. Elle était invisible ici. */}
          <label className="flex items-center gap-1.5 pb-2 text-sm text-foreground">
            <Switch checked={!!row.dimanche_ok}
                    onCheckedChange={v => patch(row, { dimanche_ok: v })}
                    aria-label={`Autorisée le dimanche (16 h-19 h) — étape ${row.ordre}`} />
            Dimanche
          </label>
          <label className="flex items-center gap-1.5 pb-2 text-sm text-foreground">
            <Switch checked={row.actif} onCheckedChange={v => patch(row, { actif: v })}
                    aria-label={`Active — étape ${row.ordre}`} />
            Active
          </label>
          <IconButton className="mb-1" variant="ghost" size="sm"
                      aria-label={`Supprimer le barreau ${row.ordre}`}
                      onClick={() => setASupprimer(row)}>
            <Trash2 className="size-4" />
          </IconButton>
        </div>
      ))}
      <ConfirmDialog
        open={aSupprimer != null}
        onOpenChange={o => { if (!o) setASupprimer(null) }}
        title="Supprimer ce barreau de la cadence ?"
        description={
          `« ${aSupprimer?.libelle ?? ''} » ne sera plus posé sur les futurs `
          + `plans. ${AVERTISSEMENT_NON_RETROACTIF}`
        }
        confirmLabel="Supprimer"
        loading={suppression}
        onConfirm={confirmerSuppression}
      />
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
