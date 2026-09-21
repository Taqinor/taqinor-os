import { useCallback, useEffect, useState } from 'react'
import { Play, Square, Timer } from 'lucide-react'
import { Badge, Button, toast } from '../../../ui'
import gestionProjetApi from '../../../api/gestionProjetApi'
import { errMessage } from '../constants'

/* XPRJ5 — Chrono de tâche : un seul chrono actif par utilisateur (démarrer sur
   une autre tâche l'arrête implicitement côté serveur). Indicateur global
   (chrono-actif) + démarrer/arrêter sur une tâche donnée, avec optimistic UI
   et rollback réseau (toast). */

function dureeDepuis(startedAt) {
  if (!startedAt) return '00:00:00'
  const start = new Date(startedAt).getTime()
  if (Number.isNaN(start)) return '00:00:00'
  const diff = Math.max(0, Date.now() - start)
  const h = Math.floor(diff / 3600000)
  const m = Math.floor((diff % 3600000) / 60000)
  const s = Math.floor((diff % 60000) / 1000)
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(h)}:${pad(m)}:${pad(s)}`
}

// Indicateur global du chrono actif de l'utilisateur (n'importe quel projet).
export function ChronoActifIndicator() {
  const [chrono, setChrono] = useState(null)
  const [tick, setTick] = useState(0)

  const load = useCallback(async () => {
    try {
      const res = await gestionProjetApi.getChronoActif()
      setChrono(res.status === 204 ? null : res.data)
    } catch {
      setChrono(null)
    }
  }, [])

  useEffect(() => {
    let alive = true
    ;(async () => { if (alive) await load() })()
    const interval = setInterval(() => setTick((t) => t + 1), 1000)
    return () => { alive = false; clearInterval(interval) }
  }, [load])

  if (!chrono) return null

  return (
    <Badge tone="warning" title={`Chrono actif — ${chrono.tache_libelle ?? ''}`}>
      <Timer className="mr-1 inline size-3.5" aria-hidden="true" />
      {chrono.tache_libelle ?? 'Chrono actif'} · {dureeDepuis(chrono.date_debut ?? chrono.started_at)}
      <span className="sr-only">{tick}</span>
    </Badge>
  )
}

// Bouton démarrer/arrêter le chrono sur UNE tâche donnée.
export default function ChronoButton({ tache, onChanged }) {
  const [busy, setBusy] = useState(false)
  const [chrono, setChrono] = useState(null)

  const refresh = useCallback(async () => {
    try {
      const res = await gestionProjetApi.getChronoActif()
      setChrono(res.status === 204 ? null : res.data)
    } catch {
      setChrono(null)
    }
  }, [])

  useEffect(() => {
    let alive = true
    ;(async () => { if (alive) await refresh() })()
    return () => { alive = false }
  }, [refresh])

  const estActif = chrono && (chrono.tache === tache.id || chrono.tache_id === tache.id)

  const demarrer = async () => {
    setBusy(true)
    try {
      const res = await gestionProjetApi.demarrerChrono(tache.id)
      setChrono(res.data)
      toast.success(`Chrono démarré sur « ${tache.libelle} ».`)
      onChanged?.()
    } catch (err) {
      toast.error(errMessage(err, 'Démarrage du chrono impossible.'))
    } finally {
      setBusy(false)
    }
  }

  const arreter = async () => {
    setBusy(true)
    try {
      await gestionProjetApi.arreterChrono(tache.id)
      setChrono(null)
      toast.success('Chrono arrêté — feuille de temps créée.')
      onChanged?.()
    } catch (err) {
      toast.error(errMessage(err, 'Arrêt du chrono impossible.'))
    } finally {
      setBusy(false)
    }
  }

  return estActif ? (
    <Button size="sm" variant="outline" disabled={busy} onClick={arreter} title="Arrêter le chrono">
      <Square className="size-3.5" aria-hidden="true" /> Arrêter
    </Button>
  ) : (
    <Button size="sm" variant="ghost" disabled={busy} onClick={demarrer} title="Démarrer le chrono">
      <Play className="size-3.5" aria-hidden="true" /> Chrono
    </Button>
  )
}
