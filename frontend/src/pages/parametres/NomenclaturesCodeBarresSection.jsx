// ZSTK12 — Nomenclatures de code-barres (Paramètres → Stock) : une société qui
// imprime ses PROPRES codes internes (préfixe magasin) peut les router vers le
// bon type d'entité (produit/lot/série/emplacement/quantité) sans toucher au
// parsing GS1/EAN existant. Sans nomenclature ACTIVE, le résolveur de scan se
// comporte exactement comme avant (comportement historique inchangé).
import { useEffect, useState } from 'react'
import { Plus, Trash2, Barcode } from 'lucide-react'
import stockApi from '../../api/stockApi'
import {
  Card, CardContent, Button, IconButton, Input, Badge, Spinner, EmptyState,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { SectionTitle } from './peComponents'

const TYPES = [
  { value: 'default', label: 'Défaut (EAN/UPC)' },
  { value: 'gs1', label: 'GS1' },
]
const ENCODES = [
  { value: 'produit', label: 'Produit' },
  { value: 'lot', label: 'Lot' },
  { value: 'serie', label: 'Série' },
  { value: 'emplacement', label: 'Emplacement' },
  { value: 'quantite', label: 'Quantité' },
]

function frErr(err, fallback = "L'opération a échoué.") {
  const data = err?.response?.data
  if (!data) return fallback
  if (typeof data === 'string') return data
  if (data.detail) return data.detail
  return fallback
}

// ── Règles d'une nomenclature (motif → type d'entité, triées par priorité) ──
function ReglesTable({ nomenclature, onChanged }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [nouvelle, setNouvelle] = useState({ motif: '', est_regex: false, encode: 'produit', priorite: 100 })

  const regles = [...(nomenclature.regles ?? [])].sort((a, b) => a.priorite - b.priorite)

  const ajouter = async () => {
    if (!nouvelle.motif.trim()) { setError('Le motif est requis.'); return }
    setBusy(true); setError(null)
    try {
      await stockApi.createRegleCodeBarres({
        nomenclature: nomenclature.id,
        motif: nouvelle.motif.trim(),
        est_regex: nouvelle.est_regex,
        encode: nouvelle.encode,
        priorite: Number(nouvelle.priorite) || 100,
      })
      setNouvelle({ motif: '', est_regex: false, encode: 'produit', priorite: 100 })
      onChanged?.()
    } catch (err) {
      setError(frErr(err, "L'ajout de la règle a échoué."))
    } finally { setBusy(false) }
  }

  const supprimer = async (id) => {
    if (!window.confirm('Supprimer cette règle ?')) return
    try {
      await stockApi.deleteRegleCodeBarres(id)
      onChanged?.()
    } catch { setError('La suppression a échoué.') }
  }

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border bg-muted/20 p-3">
      {regles.length === 0 && (
        <p className="text-xs text-muted-foreground">Aucune règle. Sans règle, cette nomenclature ne route rien.</p>
      )}
      {regles.map((r) => (
        <div key={r.id} className="flex flex-wrap items-center gap-2 text-sm">
          <span className="font-mono text-xs">{r.motif}</span>
          <Badge tone="neutral">{r.est_regex ? 'Regex' : 'Préfixe'}</Badge>
          <Badge tone="primary">{ENCODES.find((e) => e.value === r.encode)?.label ?? r.encode}</Badge>
          <span className="text-xs text-muted-foreground">priorité {r.priorite}</span>
          <IconButton label="Supprimer la règle" variant="ghost" size="icon" className="ml-auto size-7"
                      onClick={() => supprimer(r.id)}>
            <Trash2 className="size-3.5 text-destructive" />
          </IconButton>
        </div>
      ))}
      <div className="mt-1 flex flex-wrap items-center gap-1.5">
        <Input className="h-8 w-32 text-sm" placeholder="Motif (ex. 22)"
               value={nouvelle.motif}
               onChange={(e) => setNouvelle((n) => ({ ...n, motif: e.target.value }))} />
        <Select value={nouvelle.encode} onValueChange={(v) => setNouvelle((n) => ({ ...n, encode: v }))}>
          <SelectTrigger className="h-8 w-36 text-sm"><SelectValue /></SelectTrigger>
          <SelectContent>
            {ENCODES.map((e) => <SelectItem key={e.value} value={e.value}>{e.label}</SelectItem>)}
          </SelectContent>
        </Select>
        <Input type="number" className="h-8 w-20 text-sm" placeholder="Priorité"
               value={nouvelle.priorite}
               onChange={(e) => setNouvelle((n) => ({ ...n, priorite: e.target.value }))} />
        <Button type="button" size="sm" disabled={busy} onClick={ajouter}>
          <Plus className="size-3.5" /> Ajouter
        </Button>
      </div>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}

export default function NomenclaturesCodeBarresSection() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [nouveauNom, setNouveauNom] = useState('')
  const [nouveauType, setNouveauType] = useState('default')
  const [busy, setBusy] = useState(false)

  const reload = () => {
    stockApi.getNomenclaturesCodeBarres()
      .then((r) => setItems(r.data?.results ?? r.data ?? []))
      .catch(() => setError('Chargement des nomenclatures impossible.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { reload() }, [])

  const creer = async () => {
    if (!nouveauNom.trim()) return
    setBusy(true); setError(null)
    try {
      await stockApi.createNomenclatureCodeBarres({ nom: nouveauNom.trim(), type_nomenclature: nouveauType })
      setNouveauNom('')
      reload()
    } catch (err) {
      setError(frErr(err, 'La création a échoué.'))
    } finally { setBusy(false) }
  }

  const toggleActif = async (item) => {
    try {
      await stockApi.updateNomenclatureCodeBarres(item.id, { actif: !item.actif })
      reload()
    } catch { setError("Le changement d'état a échoué.") }
  }

  const supprimer = async (item) => {
    if (!window.confirm(`Supprimer la nomenclature « ${item.nom} » ?`)) return
    try {
      await stockApi.deleteNomenclatureCodeBarres(item.id)
      reload()
    } catch { setError('La suppression a échoué.') }
  }

  return (
    <Card>
      <CardContent className="pt-4 sm:pt-5">
        <SectionTitle label="Stock — Nomenclatures de code-barres"
                      icon={<><path d="M3 5v14M8 5v14M12 5v14M17 5v14M21 5v14"/></>} />
        <p className="mb-3.5 text-[11.5px] text-muted-foreground">
          Route vos codes internes (préfixe magasin) vers le bon type d&apos;entité. Sans
          nomenclature active, le scan continue de fonctionner comme avant (jetons internes,
          GS1, EAN).
        </p>

        {loading ? (
          <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
            <Spinner /> Chargement…
          </div>
        ) : items.length === 0 ? (
          <EmptyState title="Aucune nomenclature" description="Créez-en une pour router vos codes internes." className="py-6" />
        ) : (
          <div className="mb-3 flex flex-col gap-3">
            {items.map((item) => (
              <div key={item.id} className="rounded-lg border border-border p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Barcode className="size-4 text-muted-foreground" />
                  <span className="font-medium">{item.nom}</span>
                  <Badge tone="neutral">{TYPES.find((t) => t.value === item.type_nomenclature)?.label}</Badge>
                  <Badge tone={item.actif ? 'success' : 'neutral'}>{item.actif ? 'Active' : 'Inactive'}</Badge>
                  <div className="ml-auto flex items-center gap-1.5">
                    <Button type="button" size="sm" variant="outline" onClick={() => toggleActif(item)}>
                      {item.actif ? 'Désactiver' : 'Activer'}
                    </Button>
                    <IconButton label="Supprimer la nomenclature" variant="outline" size="sm"
                                className="text-destructive hover:text-destructive"
                                onClick={() => supprimer(item)}>
                      <Trash2 className="size-4" />
                    </IconButton>
                  </div>
                </div>
                <div className="mt-2.5">
                  <ReglesTable nomenclature={item} onChanged={reload} />
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="flex flex-wrap items-center gap-1.5">
          <Input className="h-9 flex-1" placeholder="Nom de la nomenclature"
                 value={nouveauNom} onChange={(e) => setNouveauNom(e.target.value)}
                 onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); creer() } }} />
          <Select value={nouveauType} onValueChange={setNouveauType}>
            <SelectTrigger className="h-9 w-40"><SelectValue /></SelectTrigger>
            <SelectContent>
              {TYPES.map((t) => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
            </SelectContent>
          </Select>
          <Button type="button" disabled={busy} onClick={creer}>
            <Plus className="size-4" /> Créer
          </Button>
        </div>
        {error && <p className="mt-2 text-xs text-destructive">{error}</p>}
      </CardContent>
    </Card>
  )
}
