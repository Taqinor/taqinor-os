// T8 — barre d'actions EN MASSE du catalogue produit. Visible dès qu'un produit
// est coché. Prix (% ou fixe), garantie, catégorie, marque, export Excel. La
// règle (prix d'achat jamais touché) est appliquée SERVEUR ; ici, UI seulement.
import { useState } from 'react'
import { Download, QrCode, X } from 'lucide-react'
import {
  Button, Input, Segmented,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'

// VX149 — panneaux de la barre en masse : au lieu d'un bouton-onglet
// réinventé à la main (`tabBtn` — bordure blanche translucide, aria-pressed
// codé en dur), le contrôle segmenté partagé (`ui/Segmented`, même primitif
// que les bascules de vue Liste/Kanban/Calendrier). Le panneau reste
// « ouvrable/fermable » (reclique = referme) : Segmented lui-même est un
// choix unique toujours actif, donc la fermeture est gérée ici, un cran
// au-dessus de son onChange.
const PANELS = [
  { value: 'price', label: 'Prix' },
  { value: 'warranty', label: 'Garantie' },
  { value: 'cat', label: 'Catégorie' },
  { value: 'brand', label: 'Marque' },
]

export default function BulkProductBar({
  count, categories = [], marques = [], busy, labelsBusy,
  onAction, onExport, onPrintLabels, onClear,
}) {
  const [panel, setPanel] = useState(null)
  const [priceMode, setPriceMode] = useState('percent')
  const [priceVal, setPriceVal] = useState('')
  const [gar, setGar] = useState('')
  const [garProd, setGarProd] = useState('')
  const [cat, setCat] = useState('')
  const [marque, setMarque] = useState('')

  const toggle = (n) => setPanel((p) => (p === n ? null : n))
  const run = (action, params) => { onAction(action, params); setPanel(null) }

  return (
    <div
      role="region"
      aria-label="Actions produits en masse"
      className="mb-3 flex flex-wrap items-center gap-3 rounded-xl bg-nuit px-4 py-2.5 text-white shadow-ui-md"
    >
      <div className="text-sm">
        <strong className="tabular-nums">{count}</strong> produit{count > 1 ? 's' : ''} sélectionné{count > 1 ? 's' : ''}
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        <Segmented
          size="sm"
          value={panel}
          onChange={busy ? undefined : toggle}
          aria-label="Panneau d'action en masse"
          className="border-white/20 bg-white/10"
          options={PANELS}
        />
        <button
          type="button" disabled={busy} onClick={onExport}
          className="inline-flex items-center gap-1.5 rounded-md border border-white/20 px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-white/10 disabled:opacity-50"
        >
          <Download className="size-3.5" /> Exporter Excel
        </button>
        {onPrintLabels && (
          <button
            type="button" disabled={busy || labelsBusy} onClick={onPrintLabels}
            title="Étiquettes QR imprimables (nom + SKU + code à scanner)"
            className="inline-flex items-center gap-1.5 rounded-md border border-white/20 px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-white/10 disabled:opacity-50"
          >
            <QrCode className="size-3.5" /> Imprimer étiquettes
          </button>
        )}
        <button
          type="button" disabled={busy} onClick={onClear}
          className="inline-flex items-center gap-1.5 rounded-md px-3 py-1 text-xs font-medium text-white/70 transition-colors hover:text-white disabled:opacity-50"
        >
          <X className="size-3.5" /> Désélectionner
        </button>
      </div>

      {panel === 'price' && (
        <div className="flex w-full flex-wrap items-center gap-2 border-t border-white/15 pt-2">
          <div className="w-40">
            <Select value={priceMode} onValueChange={setPriceMode}>
              <SelectTrigger className="h-9"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="percent">Variation (%)</SelectItem>
                <SelectItem value="fixed">Prix fixe (HT)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Input
            type="number" step="any" inputMode="decimal"
            className="h-9 w-36"
            placeholder={priceMode === 'percent' ? 'ex. 10 ou -5' : 'ex. 1200'}
            value={priceVal} onChange={(e) => setPriceVal(e.target.value)}
          />
          <Button size="sm" disabled={priceVal === ''}
                  onClick={() => run('set_price', { mode: priceMode, valeur: priceVal })}>
            Appliquer
          </Button>
          <span className="text-xs text-white/60">Le prix d&apos;achat n&apos;est jamais modifié.</span>
        </div>
      )}
      {panel === 'warranty' && (
        <div className="flex w-full flex-wrap items-center gap-2 border-t border-white/15 pt-2">
          <Input type="number" min="0" inputMode="numeric" className="h-9 w-40"
                 placeholder="Garantie (mois)" value={gar} onChange={(e) => setGar(e.target.value)} />
          <Input type="number" min="0" inputMode="numeric" className="h-9 w-52"
                 placeholder="Garantie production (mois)" value={garProd} onChange={(e) => setGarProd(e.target.value)} />
          <Button size="sm" disabled={gar === '' && garProd === ''}
                  onClick={() => run('set_warranty', { garantie_mois: gar, garantie_production_mois: garProd })}>
            Appliquer
          </Button>
        </div>
      )}
      {panel === 'cat' && (
        <div className="flex w-full flex-wrap items-center gap-2 border-t border-white/15 pt-2">
          <div className="w-60">
            <Select value={cat || '__none'} onValueChange={(v) => setCat(v === '__none' ? '' : v)}>
              <SelectTrigger className="h-9"><SelectValue placeholder="— Aucune catégorie —" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__none">— Aucune catégorie —</SelectItem>
                {categories.map((c) => <SelectItem key={c.id} value={String(c.id)}>{c.nom}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <Button size="sm" onClick={() => run('set_category', { categorie_id: cat || null })}>
            Appliquer
          </Button>
        </div>
      )}
      {panel === 'brand' && (
        <div className="flex w-full flex-wrap items-center gap-2 border-t border-white/15 pt-2">
          <Input list="bpb-marques" className="h-9 w-60"
                 placeholder="Marque" value={marque} onChange={(e) => setMarque(e.target.value)} />
          <datalist id="bpb-marques">
            {marques.map((m) => <option key={m.id} value={m.nom} />)}
          </datalist>
          <Button size="sm" onClick={() => run('set_brand', { marque })}>
            Appliquer
          </Button>
        </div>
      )}
    </div>
  )
}
