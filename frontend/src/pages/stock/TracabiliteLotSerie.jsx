import { useState } from 'react'
import { GitBranch } from 'lucide-react'
import stockApi from '../../api/stockApi'
import { frErrDetail as frErr } from '../../lib/frErr'
import { Button, Input, FormField } from '../../ui'
import { AlerteErreurStock } from './BandeauxListeStock'

/* ENF15 (D-ENF15-STOCK-22) — NTWMS16 : traçabilité complète d'un lot ou d'un
   n° de série — d'où il vient (réception, fournisseur), ce qu'il en reste et
   où, où il est parti (picking, colis, équipement chez le client). LECTURE
   SEULE, aucun prix. Chargé à la demande. */

const fmtDate = (v) => {
  if (!v) return '—'
  try { return new Date(v).toLocaleDateString('fr-FR') } catch { return '—' }
}

function ligneAmont(a, i) {
  return (
    <li key={`am-${i}`} className="rounded-md border border-border bg-card p-2 text-sm">
      Réception {a.reception_reference}
      {a.bcf_reference ? ` · commande ${a.bcf_reference}` : ''}
      {a.fournisseur_nom ? ` · ${a.fournisseur_nom}` : ''}
      {` · ${fmtDate(a.date)} · quantité ${a.quantite}`}
    </li>
  )
}

function ligneAval(a, i) {
  let texte
  if (a.type === 'picking') {
    texte = `Prélèvement ${a.vague_reference} · quantité ${a.quantite_prelevee}${a.chantier_reference ? ` · chantier ${a.chantier_reference}` : ''}`
  } else if (a.type === 'colis') {
    texte = `Colis ${a.sscc} (${a.statut}) · quantité ${a.quantite}`
  } else if (a.type === 'equipement') {
    texte = `Équipement installé${a.client_nom ? ` chez ${a.client_nom}` : ''}${a.chantier_reference ? ` · chantier ${a.chantier_reference}` : ''} (${a.statut})`
  } else {
    texte = String(a.type ?? '—')
  }
  return (
    <li key={`av-${i}`} className="rounded-md border border-border bg-card p-2 text-sm">{texte}</li>
  )
}

export default function TracabiliteLotSerie() {
  const [mode, setMode] = useState('lot')
  const [numero, setNumero] = useState('')
  const [chaine, setChaine] = useState(null)
  const [introuvable, setIntrouvable] = useState(false)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  const chercher = async () => {
    const n = numero.trim()
    if (!n) { setError('Saisissez un numéro.'); return }
    setLoading(true)
    setError(null)
    setIntrouvable(false)
    try {
      const r = await stockApi.getTracabilite(mode === 'lot' ? { lot: n } : { serie: n })
      setChaine(r.data)
    } catch (err) {
      setChaine(null)
      if (err?.response?.status === 404) setIntrouvable(true)
      else setError(frErr(err, 'Traçabilité indisponible.'))
    } finally { setLoading(false) }
  }

  const casiers = chaine?.stock?.casiers ?? []

  return (
    <section className="flex flex-col gap-3 rounded-lg border border-border bg-muted/30 p-3"
             aria-labelledby="tr-titre">
      <h2 id="tr-titre" className="flex items-center gap-1.5 text-sm font-semibold">
        <GitBranch className="size-4" aria-hidden="true" /> Traçabilité d&apos;un lot ou d&apos;un n° de série
      </h2>
      <div className="flex flex-wrap items-end gap-2">
        <div role="group" aria-label="Type de numéro" className="flex gap-1">
          <Button type="button" size="sm" variant={mode === 'lot' ? 'secondary' : 'outline'}
                  aria-pressed={mode === 'lot'} onClick={() => setMode('lot')}>N° de lot</Button>
          <Button type="button" size="sm" variant={mode === 'serie' ? 'secondary' : 'outline'}
                  aria-pressed={mode === 'serie'} onClick={() => setMode('serie')}>N° de série</Button>
        </div>
        <FormField label="Numéro" htmlFor="tr-numero">
          <Input id="tr-numero" className="w-56" value={numero}
                 onChange={(e) => setNumero(e.target.value)}
                 onKeyDown={(e) => { if (e.key === 'Enter') chercher() }} />
        </FormField>
        <Button type="button" onClick={chercher} loading={loading}>Tracer</Button>
      </div>
      <AlerteErreurStock error={error} />
      {introuvable && (
        <p className="text-sm text-muted-foreground">Aucune traçabilité trouvée pour ce numéro.</p>
      )}
      {chaine && (
        <div className="flex flex-col gap-3">
          <p className="text-sm">
            <strong>{chaine.produit?.nom ?? 'Produit inconnu'}</strong>
            {chaine.produit?.sku ? ` · ${chaine.produit.sku}` : ''}
          </p>
          <div>
            <h3 className="mb-1 text-xs font-semibold uppercase text-muted-foreground">Origine</h3>
            {(chaine.amont ?? []).length === 0
              ? <p className="text-sm text-muted-foreground">Aucune réception retrouvée.</p>
              : <ul className="flex flex-col gap-1.5">{chaine.amont.map(ligneAmont)}</ul>}
          </div>
          <div>
            <h3 className="mb-1 text-xs font-semibold uppercase text-muted-foreground">En stock</h3>
            <p className="text-sm">
              Restant : {chaine.stock?.quantite_restante ?? 0}
              {chaine.stock?.emplacement_nom ? ` · ${chaine.stock.emplacement_nom}` : ''}
              {casiers.length > 0 ? ` · ${casiers.length} casier(s)` : ''}
            </p>
          </div>
          <div>
            <h3 className="mb-1 text-xs font-semibold uppercase text-muted-foreground">Destination</h3>
            {(chaine.aval ?? []).length === 0
              ? <p className="text-sm text-muted-foreground">Pas encore sorti du stock.</p>
              : <ul className="flex flex-col gap-1.5">{chaine.aval.map(ligneAval)}</ul>}
          </div>
        </div>
      )}
    </section>
  )
}
