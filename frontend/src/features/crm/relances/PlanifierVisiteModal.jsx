// VISCAD3 — Modale « Planifier la visite technique », PARTAGÉE par les trois
// entrées de la fonctionnalité « la visite devient une étape du suivi
// commercial » : le CTA du panneau de coaching (PanneauProposerVisite), le
// bouton principal de SectionVisite (fiche lead), et l'issue « Visite
// acceptée » du mini-formulaire Fait (RelanceEtapeRow) — une seule modale,
// un seul appel serveur (`crmApi.planifierVisiteLead`), jamais trois copies.
//
// Écrit dans le VRAI module visites (apps/visites) : aucun doublon de champ
// côté lead (contrairement aux anciens `visite_prevue_le`/`visite_effectuee`
// legacy de SectionVisite, conservés à part).
//
// Self-suffisante comme `ToucheMessageDialog.jsx` : charge elle-même la liste
// des commerciaux assignables (même source que le sélecteur « Responsable »
// du Suivi commercial, `crmApi.getAssignableUsers`) à l'ouverture — aucune
// prop `users` à faire remonter depuis les trois points d'entrée différents.
//
// Erreurs de champ (règle fondateur « le champ fautif, message exact ») :
// une 400 `{date_prevue: ["…"]}` s'affiche SOUS le champ concerné (message
// EXACT du serveur) ET dans un bandeau qui NOMME le(s) champ(s) en cause
// (`FormErrorSummary`, clic = focus le champ) — jamais un « Non enregistré »
// générique. Une erreur inattendue (réseau/500) affiche UNE phrase claire.
import { useState, useEffect } from 'react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Button, Input, Textarea, FormField, FormErrorSummary,
} from '../../../ui'
import crmApi from '../../../api/crmApi'
import { toastSuccess } from '../../../lib/toast'
import MicDicteeButton from '../../../components/MicDicteeButton'

const FIELD_LABELS = {
  date_prevue: 'Date prévue',
  commercial: 'Commercial assigné',
  notes: 'Note',
}

// F1 — date du jour ancrée Casablanca (jamais le fuseau du navigateur),
// même patron que `heureDue`/les tests MRY32 (Intl `en-CA` → YYYY-MM-DD,
// directement utilisable comme `min`/valeur d'un `<input type="date">`).
function aujourdhuiCasablanca() {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Africa/Casablanca' }).format(new Date())
}

export default function PlanifierVisiteModal({ leadId, open, onOpenChange, onPlanifie }) {
  const [date, setDate] = useState('')
  const [commercial, setCommercial] = useState('')
  const [notes, setNotes] = useState('')
  const [users, setUsers] = useState([])
  const [saving, setSaving] = useState(false)
  const [erreurs, setErreurs] = useState({})
  const [erreurGenerale, setErreurGenerale] = useState('')

  // Réinitialise le formulaire à CHAQUE ouverture (jamais les valeurs d'une
  // planification précédente qui traîneraient sur le lead suivant). Même
  // patron que `ToucheMessageDialog.jsx` — `queueMicrotask` plutôt qu'un
  // `setState` synchrone direct dans l'effet.
  useEffect(() => {
    if (!open) return undefined
    let active = true
    queueMicrotask(() => {
      if (!active) return
      setDate(''); setCommercial(''); setNotes('')
      setErreurs({}); setErreurGenerale(''); setSaving(false)
    })
    return () => { active = false }
  }, [open])

  // Liste des commerciaux assignables — même endpoint que le sélecteur
  // « Responsable » déjà utilisé dans le Suivi commercial (SectionPipeline
  // AssigneePicker), jamais un champ numérique brut.
  useEffect(() => {
    if (!open) return undefined
    let active = true
    crmApi.getAssignableUsers()
      .then((r) => { if (active) setUsers(r.data ?? []) })
      .catch(() => { if (active) setUsers([]) })
    return () => { active = false }
  }, [open])

  const fermer = () => { if (!saving) onOpenChange(false) }

  const soumettre = async (e) => {
    e?.preventDefault?.()
    if (!leadId || !date) return
    setSaving(true)
    setErreurs({})
    setErreurGenerale('')
    const payload = { date_prevue: date }
    if (commercial) payload.commercial = Number(commercial)
    if (notes.trim()) payload.notes = notes.trim()
    try {
      const res = await crmApi.planifierVisiteLead(leadId, payload)
      toastSuccess('Visite planifiée — relances décalées après la visite')
      onPlanifie?.(res?.data?.visite)
      onOpenChange(false)
    } catch (err) {
      const data = err?.response?.data
      // CKP4 — même distinction que RelanceEtapeRow : une 400 de VALIDATION
      // (objet de champs) s'affiche SOUS les champs + un bandeau qui les
      // nomme ; toute autre erreur (réseau, 500…) affiche UNE phrase claire,
      // jamais « Non enregistré ».
      if (err?.response?.status === 400 && data && typeof data === 'object' && !Array.isArray(data)) {
        setErreurs(data)
      } else {
        setErreurGenerale('La planification de la visite a échoué — réessayez.')
      }
    } finally {
      setSaving(false)
    }
  }

  // FormErrorSummary : chaque entrée NOMME le champ (libellé FR) ET porte le
  // message EXACT du serveur — jamais l'un sans l'autre (règle fondateur).
  const bandeauErreurs = Object.entries(erreurs).map(([champ, messages]) => {
    const msg = Array.isArray(messages) ? messages[0] : String(messages)
    const libelle = FIELD_LABELS[champ] ?? champ
    return { field: `pv-${champ.replace(/_/g, '-')}`, message: `${libelle} : ${msg}` }
  })

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) fermer() }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Planifier la visite technique</DialogTitle>
          <DialogDescription>
            Crée une visite dans le module Visites — les relances en attente
            sont décalées après la visite (jamais annulées, jamais
            redémarrées). La visite se fait avec le client lui-même — jamais
            le gardien ni la bonne : confirmez sa présence au créneau choisi.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={soumettre} noValidate className="flex flex-col gap-3">
          {bandeauErreurs.length > 0 && <FormErrorSummary errors={bandeauErreurs} />}
          <FormField
            label="Date prévue" required htmlFor="pv-date-prevue"
            error={erreurs.date_prevue?.[0]} errorKind="required"
          >
            <Input
              id="pv-date-prevue" type="date" min={aujourdhuiCasablanca()}
              invalid={!!erreurs.date_prevue} value={date}
              onChange={(e) => setDate(e.target.value)}
            />
          </FormField>
          <FormField label="Commercial assigné" htmlFor="pv-commercial" error={erreurs.commercial?.[0]}>
            <select
              id="pv-commercial" className={erreurs.commercial ? 'form-select is-invalid' : 'form-select'}
              value={commercial} onChange={(e) => setCommercial(e.target.value)}
            >
              <option value="">— Non assigné —</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>{u.username}</option>
              ))}
            </select>
          </FormField>
          <FormField label="Note (optionnelle)" htmlFor="pv-notes" error={erreurs.notes?.[0]}>
            <div className="flex items-start gap-2">
              <Textarea
                id="pv-notes" rows={2} value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Contexte pour le technicien…"
                className="flex-1"
              />
              <MicDicteeButton
                onTexte={(texte) => setNotes((n) => (n ? `${n} ${texte}` : texte))}
              />
            </div>
          </FormField>
          {erreurGenerale && (
            <p role="alert" className="text-sm text-destructive">{erreurGenerale}</p>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" disabled={saving} onClick={fermer}>
              Annuler
            </Button>
            <Button type="submit" disabled={saving || !date} loading={saving}>
              Planifier la visite
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
