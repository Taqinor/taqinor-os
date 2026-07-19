import { useCallback, useEffect, useState } from 'react'
import { Badge, Button, Spinner } from '../../ui'
import savApi from '../../api/savApi'

/* ============================================================================
   WIR119 — Panneau de saisie de la feuille de maintenance (worksheet) sur le
   ticket (ZMFG6). Le technicien REMPLIT des champs typés (texte/nombre/case/
   mesure) définis par un modèle. Gaté société par
   `SavSlaSettings.worksheets_maintenance_actifs` (le GET renvoie 404 tant que
   la fonctionnalité n'est pas activée) : dans ce cas le panneau affiche une
   note d'activation au lieu d'un formulaire. Les modèles se gèrent en
   Paramètres SAV (onglet « Feuilles de maintenance »).
   ========================================================================== */

// Rend un champ typé selon sa définition de modèle.
function ChampInput({ champ, value, onChange, disabled }) {
  const id = `ws-${champ.cle}`
  const label = (
    <label className="form-label" htmlFor={id}>
      {champ.libelle || champ.cle}{champ.requis ? ' *' : ''}
      {champ.type === 'mesure' && champ.unite ? ` (${champ.unite})` : ''}
    </label>
  )
  if (champ.type === 'case') {
    return (
      <div className="flex items-center gap-2">
        <input id={id} type="checkbox" disabled={disabled}
          checked={value === true || value === 'true'}
          onChange={(e) => onChange(e.target.checked)} />
        {label}
      </div>
    )
  }
  const type = (champ.type === 'nombre' || champ.type === 'mesure') ? 'number' : 'text'
  return (
    <div className="flex flex-col gap-1">
      {label}
      <input id={id} type={type} step={type === 'number' ? 'any' : undefined}
        className="form-control" disabled={disabled}
        value={value ?? ''} onChange={(e) => onChange(e.target.value)} />
    </div>
  )
}

export default function TicketWorksheetPanel({ ticketId }) {
  const [worksheet, setWorksheet] = useState(null)
  const [modeles, setModeles] = useState([])
  const [loading, setLoading] = useState(true)
  const [featureOff, setFeatureOff] = useState(false)
  const [error, setError] = useState(null)
  const [modeleId, setModeleId] = useState('')
  const [valeurs, setValeurs] = useState({})
  const [busy, setBusy] = useState(false)

  const loadModeles = useCallback(() => {
    savApi.getWorksheetModeles()
      .then((r) => setModeles((r.data?.results ?? r.data ?? []).filter((m) => m.actif)))
      .catch(() => setModeles([]))
  }, [])

  const load = useCallback(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    savApi.getTicketWorksheet(ticketId)
      .then((r) => {
        if (cancelled) return
        setWorksheet(r.data)
        setValeurs(r.data?.valeurs ?? {})
        loadModeles()
      })
      .catch((err) => {
        if (cancelled) return
        const status = err?.response?.status
        const detail = err?.response?.data?.detail || ''
        if (status === 404 && /activ/i.test(detail)) {
          setFeatureOff(true)
        } else if (status === 404) {
          setWorksheet(null)
          loadModeles()
        } else {
          setError(detail || 'Chargement impossible.')
        }
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [ticketId, loadModeles])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => load(), [load])

  const modeleCourant = worksheet
    ? modeles.find((m) => m.id === worksheet.modele)
    : null
  const champs = modeleCourant?.champs ?? []

  const creer = async () => {
    if (!modeleId) { setError('Choisissez un modèle.'); return }
    setBusy(true); setError(null)
    try {
      await savApi.creerTicketWorksheet(ticketId, Number(modeleId))
      load()
    } catch (err) {
      setError(err?.response?.data?.detail || 'Création impossible.')
    } finally { setBusy(false) }
  }

  const enregistrer = async () => {
    setBusy(true); setError(null)
    try {
      const r = await savApi.updateTicketWorksheet(ticketId, { valeurs })
      setWorksheet(r.data)
      setValeurs(r.data?.valeurs ?? valeurs)
    } catch (err) {
      setError(err?.response?.data?.detail || 'Enregistrement impossible.')
    } finally { setBusy(false) }
  }

  const marquerComplete = async () => {
    setBusy(true); setError(null)
    try {
      // Enregistre d'abord les valeurs saisies, puis marque complétée.
      const r = await savApi.updateTicketWorksheet(ticketId, { valeurs, complete: true })
      setWorksheet(r.data)
    } catch (err) {
      setError(err?.response?.data?.detail || 'Complétion impossible.')
    } finally { setBusy(false) }
  }

  if (loading) return (
    <p className="flex items-center gap-2 text-sm text-muted-foreground">
      <Spinner className="size-4 text-primary" /> Chargement…
    </p>
  )
  if (featureOff) return (
    <p className="text-sm text-muted-foreground">
      Les feuilles de maintenance ne sont pas activées. Un directeur peut les
      activer dans Paramètres SAV → SLA / Automatisation.
    </p>
  )

  // Pas encore de feuille : proposer la création depuis un modèle.
  if (!worksheet) {
    return (
      <div className="flex flex-col gap-2">
        {modeles.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Aucun modèle de feuille de maintenance. Créez-en un dans Paramètres SAV.
          </p>
        ) : (
          <div className="flex flex-wrap items-end gap-2">
            <div className="flex flex-col gap-1">
              <label className="form-label" htmlFor="ws-modele">Modèle</label>
              <select id="ws-modele" className="form-control" value={modeleId}
                onChange={(e) => setModeleId(e.target.value)}>
                <option value="">— Choisir —</option>
                {modeles.map((m) => <option key={m.id} value={m.id}>{m.nom}</option>)}
              </select>
            </div>
            <Button type="button" loading={busy} disabled={busy} onClick={creer}>
              Créer la feuille
            </Button>
          </div>
        )}
        {error && <p className="form-error" role="alert">{error}</p>}
      </div>
    )
  }

  const manquants = worksheet.champs_requis_manquants ?? []

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium">{worksheet.modele_nom}</span>
        {worksheet.complete
          ? <Badge tone="success">Complétée</Badge>
          : <Badge tone="warning">En cours</Badge>}
      </div>

      <div className="flex flex-col gap-3">
        {champs.map((champ) => (
          <ChampInput key={champ.cle} champ={champ}
            value={valeurs[champ.cle]}
            disabled={busy || worksheet.complete}
            onChange={(v) => setValeurs((prev) => ({ ...prev, [champ.cle]: v }))} />
        ))}
        {champs.length === 0 && (
          <p className="text-sm text-muted-foreground">Ce modèle n'a aucun champ défini.</p>
        )}
      </div>

      {!worksheet.complete && manquants.length > 0 && (
        <p className="text-xs text-muted-foreground">
          Champs requis restants : {manquants.join(', ')}
        </p>
      )}
      {error && <p className="form-error" role="alert">{error}</p>}

      {!worksheet.complete && (
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" loading={busy} disabled={busy} onClick={enregistrer}>
            Enregistrer
          </Button>
          <Button type="button" loading={busy} disabled={busy} onClick={marquerComplete}>
            Marquer complétée
          </Button>
        </div>
      )}
    </div>
  )
}
