// N4 — Checklist d'exécution du chantier (étapes cochables, avancement %).
// N9 — Sur les étapes « capture de série », on peut saisir un produit + n° de
// série qui crée un équipement du parc. La saisie de série ne bloque JAMAIS
// la complétion (cocher reste possible sans série).
// J43 — portée sur le système de design (Progress, Checkbox, Input, Spinner).
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import installationsApi from '../../api/installationsApi'
import ProduitPicker from '../../components/ProduitPicker'
import { Progress, Checkbox, Input, Spinner, toast } from '../../ui'
import { cn } from '../../lib/cn'
import { formatDate } from '../../lib/format'
import {
  withOfflineFallback, FIELD_OPS,
} from '../../features/installations/offline/fieldOutbox'

export default function ChantierChecklist({
  installationId, produits, series = [], interventionSeries = [], onChanged,
}) {
  const [items, setItems] = useState([])
  const [completion, setCompletion] = useState(null)
  const [loading, setLoading] = useState(true)
  // Saisies de série en attente, par clé d'étape : { produit, numero_serie }
  const [serie, setSerie] = useState({})
  // N15 / VX227 — n° de série déjà présents sur ce chantier (avertissement de
  // doublon). Le Set UNIT désormais les deux sources : les séries du parc
  // (`series`) ET les relevés saisis côté intervention (`interventionSeries`,
  // F9) — une série saisie côté N9 est détectée en doublon côté F9 et
  // réciproquement, sans jamais fusionner les magasins.
  const seriesSet = new Set(
    [...series, ...interventionSeries]
      .map((s) => String(s || '').trim().toLowerCase())
      .filter(Boolean),
  )
  const isDoublon = (v) => {
    const t = (v || '').trim().toLowerCase()
    return !!t && seriesSet.has(t)
  }

  const load = () => {
    installationsApi.getChecklist(installationId)
      .then((r) => { setItems(r.data.items ?? []); setCompletion(r.data.completion) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [installationId]) // eslint-disable-line react-hooks/exhaustive-deps

  const toggle = async (item, fait) => {
    const payload = { cle: item.cle, fait }
    // Sur une étape de capture, joindre l'éventuelle série saisie (optionnel).
    if (fait && item.capture_serie) {
      const s = serie[item.cle]
      if (s?.produit) {
        payload.equipements = [{ produit: s.produit, numero_serie: s.numero_serie || '' }]
      }
    }
    try {
      // N91 — repli hors-ligne : on file le cochage (la capture de série
      // optionnelle, qui crée un équipement parc, reste en ligne — elle n'est
      // pas portée par l'op JSON et sera ressaisie/synchronisée si besoin).
      const r = await withOfflineFallback(
        () => installationsApi.cocherChecklist(installationId, payload),
        FIELD_OPS.COCHER_CHECKLIST,
        { chantier: installationId, cle: item.cle, fait })
      if (r.queued) {
        // Reflète l'état localement ; la synchro reposera le serveur au retour.
        setItems((prev) => prev.map((it) => it.cle === item.cle ? { ...it, fait } : it))
        toast.success('Hors ligne — coché, synchro au retour du réseau.')
      } else {
        setItems(r.data.items ?? [])
        setCompletion(r.data.completion)
      }
      setSerie((prev) => ({ ...prev, [item.cle]: undefined }))
      onChanged?.()
    } catch { /* erreur silencieuse */ }
  }

  const setSerieField = (cle, k, v) =>
    setSerie((prev) => ({ ...prev, [cle]: { ...(prev[cle] ?? {}), [k]: v } }))

  return (
    <div className="flex flex-col gap-3">
      {completion != null && (
        <div className="flex items-center gap-3">
          <Progress
            value={completion}
            tone={completion === 100 ? 'success' : 'primary'}
            className="flex-1"
          />
          <span className={cn(
            'text-sm font-semibold tabular-nums',
            completion === 100 ? 'text-success' : 'text-muted-foreground',
          )}>
            {completion}%
          </span>
        </div>
      )}
      {loading ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground"><Spinner /> Chargement…</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Aucune étape modèle.{' '}
          <Link to="/parametres" className="font-medium text-primary underline">
            Configurer les étapes (Paramètres → Chantiers)
          </Link>
          .
        </p>
      ) : (
        <div className="flex flex-col">
          {items.map((item) => (
            <div key={item.id} className="border-b border-border py-2.5 last:border-0">
              {/* N12 — zones tactiles agrandies pour usage terrain/gants. */}
              <label className="flex min-h-11 cursor-pointer items-center gap-3">
                <Checkbox
                  className="size-6"
                  checked={!!item.fait}
                  onCheckedChange={(c) => toggle(item, c === true)}
                />
                <span className={cn(
                  'text-sm',
                  item.fait ? 'text-muted-foreground line-through' : 'text-foreground',
                )}>
                  {item.libelle}
                </span>
                {item.fait && (item.fait_par_nom || item.fait_le) && (
                  <span className="ml-auto text-right text-xs text-muted-foreground">
                    {item.fait_par_nom ? `par ${item.fait_par_nom}` : ''}
                    {item.fait_le ? ` le ${formatDate(item.fait_le)}` : ''}
                  </span>
                )}
              </label>
              {/* N9 — saisie optionnelle de série sur les étapes concernées.
                  N12 — empilé pleine largeur sur mobile, deux colonnes en sm+. */}
              {item.capture_serie && !item.fait && (
                <div className="ml-7 mt-1.5 flex flex-col gap-2 sm:grid sm:grid-cols-2">
                  <ProduitPicker produits={produits ?? []}
                                 value={serie[item.cle]?.produit ?? ''}
                                 onChange={(v) => setSerieField(item.cle, 'produit', v)} />
                  <Input className="w-full" placeholder="N° de série (optionnel)"
                         value={serie[item.cle]?.numero_serie ?? ''}
                         onChange={(e) => setSerieField(item.cle, 'numero_serie', e.target.value)} />
                  {isDoublon(serie[item.cle]?.numero_serie) && (
                    <span className="text-xs text-destructive sm:col-span-2">
                      Ce numéro de série existe déjà sur ce chantier.
                    </span>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
