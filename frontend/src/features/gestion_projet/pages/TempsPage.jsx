import { useCallback, useEffect, useMemo, useState } from 'react'
import { Clock3, Copy, ChevronLeft, ChevronRight, Check } from 'lucide-react'
import {
  Card, Button, Spinner, EmptyState, Badge, Label, NumberInput, toast,
} from '../../../ui'
import { formatDate } from '../../../lib/format'
import gestionProjetApi from '../../../api/gestionProjetApi'
import { errMessage } from '../constants'

/* XPRJ6 — Grille hebdomadaire de saisie des temps : lignes = projet/tâche,
   colonnes = 7 jours, saisie inline, totaux jour/semaine, copie de la semaine
   précédente et suggestions à 1 clic dérivées des affectations de la
   ressource (JAMAIS auto-enregistrées — un simple aperçu accepté ou ignoré).
   Formulaire 100 % libre (aucun input numérique ne « snap » une saisie). */

const JOUR_LABELS = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']

// Clé 'YYYY-MM-DD' LOCALE d'une date (jamais toISOString, qui bascule en UTC
// et peut décaler d'un jour — même convention que la vue calendrier CRM).
const pad2 = (n) => String(n).padStart(2, '0')
function toISO(d) {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`
}

function lundiDe(d) {
  const jour = (d.getDay() + 6) % 7 // 0 = lundi
  const out = new Date(d)
  out.setDate(d.getDate() - jour)
  out.setHours(0, 0, 0, 0)
  return out
}

function addDays(iso, n) {
  const d = new Date(`${iso}T00:00:00`)
  d.setDate(d.getDate() + n)
  return toISO(d)
}

const asList = (r) => (Array.isArray(r.data) ? r.data : r.data?.results ?? [])

export default function TempsPage() {
  const [ressources, setRessources] = useState([])
  const [ressourceId, setRessourceId] = useState('')
  const [debutSemaine, setDebutSemaine] = useState(() => toISO(lundiDe(new Date())))
  const [grille, setGrille] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  // Édition inline : { [projetId|tacheId]: [7 valeurs texte] } — clé stable de ligne.
  const [edits, setEdits] = useState({})

  useEffect(() => {
    let alive = true
    gestionProjetApi.getRessources()
      .then((res) => { if (alive) setRessources(asList(res)) })
      .catch(() => {})
    return () => { alive = false }
  }, [])

  const ligneKey = (l) => `${l.projet ?? ''}:${l.tache ?? ''}`

  const load = useCallback(async () => {
    if (!ressourceId) { setGrille(null); return }
    setLoading(true)
    setError(null)
    try {
      const res = await gestionProjetApi.getGrilleSemaineTemps({
        ressource: ressourceId, debut: debutSemaine,
      })
      setGrille(res.data)
      const nextEdits = {}
      for (const l of res.data.lignes ?? []) {
        nextEdits[ligneKey(l)] = l.heures.map((h) => (Number(h) ? h : ''))
      }
      setEdits(nextEdits)
    } catch (err) {
      setError(errMessage(err, 'Chargement de la grille impossible.'))
    } finally {
      setLoading(false)
    }
  }, [ressourceId, debutSemaine])

  useEffect(() => {
    let alive = true
    ;(async () => { if (alive) await load() })()
    return () => { alive = false }
  }, [load])

  const totauxJour = useMemo(() => {
    const totals = [0, 0, 0, 0, 0, 0, 0]
    Object.values(edits).forEach((row) => {
      row.forEach((v, i) => { totals[i] += Number(v) || 0 })
    })
    return totals
  }, [edits])

  const totalSemaine = useMemo(
    () => totauxJour.reduce((a, b) => a + b, 0), [totauxJour],
  )

  const setCell = (key, idx, value) => {
    setEdits((prev) => {
      const row = prev[key] ? [...prev[key]] : ['', '', '', '', '', '', '']
      row[idx] = value
      return { ...prev, [key]: row }
    })
  }

  const enregistrerCellule = async (ligne, idx, valeur) => {
    const heures = Number(valeur)
    if (!valeur || Number.isNaN(heures) || heures <= 0) return
    setBusy(true)
    try {
      await gestionProjetApi.createTimesheet({
        projet: ligne.projet,
        tache: ligne.tache || undefined,
        ressource: ressourceId,
        date: addDays(debutSemaine, idx),
        heures: valeur,
      })
      toast.success('Saisie enregistrée.')
      await load()
    } catch (err) {
      toast.error(errMessage(err, 'Enregistrement impossible.'))
    } finally {
      setBusy(false)
    }
  }

  const accepterSuggestion = async (sugg) => {
    setBusy(true)
    try {
      await gestionProjetApi.createTimesheet({
        projet: sugg.projet,
        tache: sugg.tache || undefined,
        ressource: ressourceId,
        date: sugg.date,
        heures: '8',
      })
      toast.success('Suggestion acceptée.')
      await load()
    } catch (err) {
      toast.error(errMessage(err, 'Acceptation impossible.'))
    } finally {
      setBusy(false)
    }
  }

  const copierSemainePrecedente = async () => {
    if (!ressourceId) return
    setBusy(true)
    try {
      const semaineSource = addDays(debutSemaine, -7)
      const res = await gestionProjetApi.copierSemaineTimesheets({
        ressource: ressourceId,
        semaine_source: semaineSource,
        semaine_cible: debutSemaine,
      })
      const { nb_copiees: nbCopiees, nb_sautees: nbSautees } = res.data
      toast.success(
        `${nbCopiees} saisie(s) copiée(s)${nbSautees ? `, ${nbSautees} déjà présente(s)/verrouillée(s)` : ''}.`,
      )
      await load()
    } catch (err) {
      toast.error(errMessage(err, 'Copie impossible.'))
    } finally {
      setBusy(false)
    }
  }

  const semaineSuivante = (delta) => setDebutSemaine((d) => addDays(d, delta * 7))

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-xl font-semibold tracking-tight">Saisie des temps</h1>
          <p className="text-sm text-muted-foreground">Grille hebdomadaire par projet / tâche.</p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <div className="flex flex-col gap-1">
            <Label htmlFor="tp-ressource">Ressource</Label>
            <select
              id="tp-ressource"
              className="h-9 min-w-56 rounded-md border border-input bg-background px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              value={ressourceId}
              onChange={(e) => setRessourceId(e.target.value)}
            >
              <option value="">— Choisir une ressource —</option>
              {ressources.map((r) => (
                <option key={r.id} value={r.id}>{r.nom}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-1">
            <Button variant="outline" size="sm" onClick={() => semaineSuivante(-1)} disabled={!ressourceId}>
              <ChevronLeft />
            </Button>
            <span className="min-w-40 text-center text-sm font-medium">
              {formatDate(debutSemaine)} – {formatDate(addDays(debutSemaine, 6))}
            </span>
            <Button variant="outline" size="sm" onClick={() => semaineSuivante(1)} disabled={!ressourceId}>
              <ChevronRight />
            </Button>
          </div>
          {ressourceId && (
            <Button variant="outline" size="sm" disabled={busy} onClick={copierSemainePrecedente}>
              <Copy /> Copier la semaine précédente
            </Button>
          )}
        </div>
      </div>

      {!ressourceId ? (
        <EmptyState icon={Clock3} title="Aucune ressource sélectionnée" description="Choisissez une ressource pour afficher sa grille de temps." />
      ) : loading ? (
        <div className="flex justify-center p-10"><Spinner /></div>
      ) : error ? (
        <EmptyState title="Erreur" description={error} action={<Button variant="outline" onClick={load}>Réessayer</Button>} />
      ) : (
        <>
          <Card className="overflow-x-auto p-0">
            <table className="w-full min-w-[720px] border-collapse text-sm">
              <thead>
                <tr className="border-b bg-muted/40">
                  <th className="p-2 text-left font-medium">Projet / Tâche</th>
                  {JOUR_LABELS.map((lbl, idx) => (
                    <th key={lbl} className="p-2 text-center font-medium">
                      {lbl}
                      <div className="text-xs font-normal text-muted-foreground">
                        {formatDate(addDays(debutSemaine, idx))}
                      </div>
                    </th>
                  ))}
                  <th className="p-2 text-center font-medium">Total</th>
                </tr>
              </thead>
              <tbody>
                {(grille?.lignes ?? []).length === 0 ? (
                  <tr>
                    <td colSpan={9} className="p-6 text-center text-muted-foreground">
                      Aucune saisie cette semaine. Utilisez une suggestion ci-dessous ou ajoutez une ligne via une tâche.
                    </td>
                  </tr>
                ) : (
                  (grille?.lignes ?? []).map((l) => {
                    const key = ligneKey(l)
                    const row = edits[key] ?? l.heures
                    return (
                      <tr key={key} className="border-b last:border-0">
                        <td className="p-2">
                          <div className="font-medium">{l.projet_code || '—'}</div>
                          {l.tache_libelle && (
                            <div className="text-xs text-muted-foreground">{l.tache_libelle}</div>
                          )}
                        </td>
                        {row.map((v, idx) => (
                          <td key={idx} className="p-1 text-center">
                            <NumberInput
                              className="h-8 w-16 text-center"
                              value={v}
                              disabled={busy}
                              onChange={(e) => setCell(key, idx, e.target.value)}
                              onBlur={(e) => enregistrerCellule(l, idx, e.target.value)}
                            />
                          </td>
                        ))}
                        <td className="p-2 text-center font-semibold tabular-nums">
                          {row.reduce((a, v) => a + (Number(v) || 0), 0)}
                        </td>
                      </tr>
                    )
                  })
                )}
              </tbody>
              <tfoot>
                <tr className="border-t bg-muted/30 font-semibold">
                  <td className="p-2">Total / jour</td>
                  {totauxJour.map((t, idx) => (
                    <td key={idx} className="p-2 text-center tabular-nums">{t || 0}</td>
                  ))}
                  <td className="p-2 text-center tabular-nums">{totalSemaine || 0}</td>
                </tr>
              </tfoot>
            </table>
          </Card>

          {(grille?.suggestions ?? []).length > 0 && (
            <Card className="p-4 sm:p-5">
              <h3 className="mb-3 font-display text-base font-semibold">
                Suggestions depuis le planning
              </h3>
              <p className="mb-3 text-xs text-muted-foreground">
                Proposées à partir des affectations de la ressource — un clic
                ajoute la saisie, rien n&apos;est jamais enregistré automatiquement.
              </p>
              <ul className="flex flex-col gap-2">
                {grille.suggestions.map((s, idx) => (
                  <li key={`${s.tache}-${s.date}-${idx}`} className="flex items-center gap-2 text-sm">
                    <Badge tone="info">{JOUR_LABELS[s.jour_index]} {formatDate(s.date)}</Badge>
                    <span className="font-medium">{s.projet_code}</span>
                    {s.tache_libelle && <span className="text-muted-foreground">— {s.tache_libelle}</span>}
                    <Button
                      size="sm"
                      variant="outline"
                      className="ml-auto"
                      disabled={busy}
                      onClick={() => accepterSuggestion(s)}
                    >
                      <Check /> Accepter
                    </Button>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </>
      )}
    </div>
  )
}
