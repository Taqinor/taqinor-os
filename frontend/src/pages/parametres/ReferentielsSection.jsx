// WIR66 — onglet « Référentiels » de la page Paramètres.
// Expose les trois référentiels société seedés au signup mais sans écran :
// taux de TVA (ARC23), conditions de paiement (ARC24) et unités de mesure
// (ARC27). Lister / activer / modifier / créer. Section autonome (comme
// StatutsSection) : elle charge ses propres données et écrit via parametresApi.
// L'écriture est réservée admin/responsable côté serveur (403 sinon).
import { useEffect, useState } from 'react'
import { Plus, Trash2, Star } from 'lucide-react'
import parametresApi from '../../api/parametresApi'
import { Card, CardContent, Input, Button, IconButton, Switch, Spinner, Badge } from '../../ui'
import { SectionTitle } from './peComponents'
import { toast } from '../../ui/confirm'

// Icône (chemins bruts) partagée par les trois cartes de référentiel.
const REF_ICON = <><path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" /></>

// Extrait la liste d'un retour DRF (liste nue ou { results: [...] }).
const asList = (data) => (Array.isArray(data) ? data : (data?.results ?? []))

// ── Taux de TVA ────────────────────────────────────────────────────────────
function TauxTvaList() {
  const [rows, setRows] = useState(null)
  const [draft, setDraft] = useState({ code: '', libelle: '', taux: '' })

  const load = () => parametresApi.getTauxTva()
    .then(r => setRows(asList(r.data))).catch(() => setRows([]))
  useEffect(() => { load() }, [])

  const create = async () => {
    if (!draft.code.trim() || !draft.libelle.trim()) return
    try {
      await parametresApi.createTauxTva({
        code: draft.code.trim(), libelle: draft.libelle.trim(),
        taux: draft.taux || '0',
      })
      setDraft({ code: '', libelle: '', taux: '' })
      load()
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Création impossible.')
    }
  }
  const toggle = async (row) => {
    try { await parametresApi.updateTauxTva(row.id, { actif: !row.actif }); load() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Modification impossible.') }
  }
  const setDefaut = async (row) => {
    try { await parametresApi.setDefautTauxTva(row.id); load() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Action impossible.') }
  }
  const remove = async (row) => {
    try { await parametresApi.deleteTauxTva(row.id); load() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Suppression impossible.') }
  }

  if (rows === null) return <Spinner />
  return (
    <div className="space-y-2" data-testid="ref-tva">
      {rows.map(row => (
        <div key={row.id} className="flex items-center gap-3 border rounded-md px-3 py-2">
          <div className="flex-1">
            <div className="font-medium flex items-center gap-2">
              {row.libelle}
              {row.defaut && <Badge>Par défaut</Badge>}
              {!row.actif && <Badge>Inactif</Badge>}
            </div>
            <div className="text-sm text-muted-foreground">{row.code} — {row.taux} %</div>
          </div>
          <IconButton title="Définir par défaut" onClick={() => setDefaut(row)}
            disabled={row.defaut}>
            <Star className={row.defaut ? 'text-amber-500' : ''} size={16} />
          </IconButton>
          <Switch checked={row.actif} onCheckedChange={() => toggle(row)}
            aria-label="Actif" />
          <IconButton title="Supprimer" onClick={() => remove(row)}>
            <Trash2 size={16} />
          </IconButton>
        </div>
      ))}
      <div className="flex items-end gap-2 pt-2">
        <Input placeholder="Code" value={draft.code}
          onChange={e => setDraft(d => ({ ...d, code: e.target.value }))} />
        <Input placeholder="Libellé" value={draft.libelle}
          onChange={e => setDraft(d => ({ ...d, libelle: e.target.value }))} />
        <Input placeholder="Taux %" value={draft.taux}
          onChange={e => setDraft(d => ({ ...d, taux: e.target.value }))} />
        <Button onClick={create}><Plus size={16} /> Ajouter</Button>
      </div>
    </div>
  )
}

// ── Conditions de paiement ───────────────────────────────────────────────────
function ConditionsList() {
  const [rows, setRows] = useState(null)
  const [draft, setDraft] = useState({ libelle: '', delai_jours: '', escompte_pct: '' })

  const load = () => parametresApi.getConditionsPaiement()
    .then(r => setRows(asList(r.data))).catch(() => setRows([]))
  useEffect(() => { load() }, [])

  const create = async () => {
    if (!draft.libelle.trim()) return
    try {
      await parametresApi.createConditionPaiement({
        libelle: draft.libelle.trim(),
        delai_jours: Number(draft.delai_jours) || 0,
        escompte_pct: draft.escompte_pct || '0',
      })
      setDraft({ libelle: '', delai_jours: '', escompte_pct: '' })
      load()
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Création impossible.')
    }
  }
  const toggle = async (row) => {
    try { await parametresApi.updateConditionPaiement(row.id, { actif: !row.actif }); load() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Modification impossible.') }
  }
  const remove = async (row) => {
    try { await parametresApi.deleteConditionPaiement(row.id); load() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Suppression impossible.') }
  }

  if (rows === null) return <Spinner />
  return (
    <div className="space-y-2" data-testid="ref-conditions">
      {rows.map(row => (
        <div key={row.id} className="flex items-center gap-3 border rounded-md px-3 py-2">
          <div className="flex-1">
            <div className="font-medium">{row.libelle} {!row.actif && <Badge>Inactif</Badge>}</div>
            <div className="text-sm text-muted-foreground">
              {row.delai_jours} j{row.fin_de_mois ? ' fin de mois' : ''}
              {Number(row.escompte_pct) > 0 ? ` — escompte ${row.escompte_pct} %` : ''}
            </div>
          </div>
          <Switch checked={row.actif} onCheckedChange={() => toggle(row)}
            aria-label="Actif" />
          <IconButton title="Supprimer" onClick={() => remove(row)}>
            <Trash2 size={16} />
          </IconButton>
        </div>
      ))}
      <div className="flex items-end gap-2 pt-2">
        <Input placeholder="Libellé" value={draft.libelle}
          onChange={e => setDraft(d => ({ ...d, libelle: e.target.value }))} />
        <Input placeholder="Délai (j)" value={draft.delai_jours}
          onChange={e => setDraft(d => ({ ...d, delai_jours: e.target.value }))} />
        <Input placeholder="Escompte %" value={draft.escompte_pct}
          onChange={e => setDraft(d => ({ ...d, escompte_pct: e.target.value }))} />
        <Button onClick={create}><Plus size={16} /> Ajouter</Button>
      </div>
    </div>
  )
}

// ── Unités de mesure ─────────────────────────────────────────────────────────
function UnitesList() {
  const [rows, setRows] = useState(null)
  const [draft, setDraft] = useState({ code: '', libelle: '' })

  const load = () => parametresApi.getUnitesMesure()
    .then(r => setRows(asList(r.data))).catch(() => setRows([]))
  useEffect(() => { load() }, [])

  const create = async () => {
    if (!draft.code.trim() || !draft.libelle.trim()) return
    try {
      await parametresApi.createUniteMesure({
        code: draft.code.trim(), libelle: draft.libelle.trim(),
      })
      setDraft({ code: '', libelle: '' })
      load()
    } catch (e) {
      toast.error(e?.response?.data?.detail ?? 'Création impossible.')
    }
  }
  const toggle = async (row) => {
    try { await parametresApi.updateUniteMesure(row.id, { actif: !row.actif }); load() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Modification impossible.') }
  }
  const remove = async (row) => {
    try { await parametresApi.deleteUniteMesure(row.id); load() }
    catch (e) { toast.error(e?.response?.data?.detail ?? 'Suppression impossible.') }
  }

  if (rows === null) return <Spinner />
  return (
    <div className="space-y-2" data-testid="ref-unites">
      {rows.map(row => (
        <div key={row.id} className="flex items-center gap-3 border rounded-md px-3 py-2">
          <div className="flex-1">
            <div className="font-medium">{row.libelle} {!row.actif && <Badge>Inactif</Badge>}</div>
            <div className="text-sm text-muted-foreground">{row.code}</div>
          </div>
          <Switch checked={row.actif} onCheckedChange={() => toggle(row)}
            aria-label="Actif" />
          <IconButton title="Supprimer" onClick={() => remove(row)}>
            <Trash2 size={16} />
          </IconButton>
        </div>
      ))}
      <div className="flex items-end gap-2 pt-2">
        <Input placeholder="Code" value={draft.code}
          onChange={e => setDraft(d => ({ ...d, code: e.target.value }))} />
        <Input placeholder="Libellé" value={draft.libelle}
          onChange={e => setDraft(d => ({ ...d, libelle: e.target.value }))} />
        <Button onClick={create}><Plus size={16} /> Ajouter</Button>
      </div>
    </div>
  )
}

export default function ReferentielsSection() {
  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="space-y-3 pt-4">
          <SectionTitle icon={REF_ICON} label="Taux de TVA" />
          <p className="text-sm text-muted-foreground">
            Taux de TVA de référence de la société. Le taux « par défaut »
            alimente les nouveaux documents ; il ne réécrit jamais un document
            déjà émis.
          </p>
          <TauxTvaList />
        </CardContent>
      </Card>
      <Card>
        <CardContent className="space-y-3 pt-4">
          <SectionTitle icon={REF_ICON} label="Conditions de paiement" />
          <ConditionsList />
        </CardContent>
      </Card>
      <Card>
        <CardContent className="space-y-3 pt-4">
          <SectionTitle icon={REF_ICON} label="Unités de mesure" />
          <UnitesList />
        </CardContent>
      </Card>
    </div>
  )
}
