import { useMemo, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { MessageCircle, Send } from 'lucide-react'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
  Button, Input, Textarea, toast,
} from '../../ui'
import innovationApi from '../../api/innovationApi'
import { linkedFromLocation } from './linkedContext'

/* ============================================================================
   NTIDE37 — « Envoyer un retour » : petit bouton discret, FIXE en bas à
   GAUCHE de chaque écran ERP principal (symétrique au CTA « Suggérer une
   amélioration » de NTIDE9, en bas à DROITE — les deux canaux restent
   distincts : ici c'est le canal feedback produit 1→N founder, NTIDE36,
   PAS la boîte à idées). Modale légère : titre/description/thème.
   POST direct vers apps.innovation.FeedbackProduit — l'auteur/la société
   sont posés côté serveur depuis le JWT, jamais lus du corps de requête.
   ========================================================================== */

const THEMES = [
  { value: 'ux', label: 'UX' },
  { value: 'performance', label: 'Performance' },
  { value: 'feature', label: 'Fonctionnalité' },
  { value: 'bug', label: 'Bug' },
  { value: 'autre', label: 'Autre' },
]

// NTIDE42 — sentiment optionnel (« +1 / Neutre / -1 »), jamais imposé (une
// valeur vide reste un choix valide, cf. ``FeedbackProduit.sentiment``).
const SENTIMENTS = [
  { value: '', label: 'Non renseigné' },
  { value: 'positif', label: "+1 (je l'adore)" },
  { value: 'neutre', label: "Neutre (c'est ok)" },
  { value: 'negatif', label: "-1 (ça m'énerve)" },
]

// NTIDE43 — même table de labels que ``Idee.LinkedType`` (apps/innovation,
// backend), pour l'affichage « Feedback : Devis #123 ».
const CONTEXT_LABELS = { devis: 'Devis', ticket: 'Ticket SAV', chantier: 'Chantier' }

/* ORDRE FONDATEUR 2026-08-04 — « les deux parties en bas sont bien mais pas
   là tout le temps : garde-les dans profil ou paramètres ». Le bouton FLOTTANT
   est supprimé ; la modale devient PILOTABLE (props `open`/`onOpenChange`) et
   son unique point d'entrée est le menu profil du Header. */
export default function FeedbackButton({ open, onOpenChange }) {
  const location = useLocation()
  const [titre, setTitre] = useState('')
  const [description, setDescription] = useState('')
  const [theme, setTheme] = useState('autre')
  const [sentiment, setSentiment] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // NTIDE43 — contexte pré-détecté (devis/ticket/chantier) depuis l'écran
  // détail ouvert (même détection que le lien d'idée NTIDE11) : stocké
  // opaque (``context_type``/``context_id``), affiché en lecture seule
  // (« Feedback : Devis #123 »), jamais éditable.
  const contexte = useMemo(
    () => linkedFromLocation(location.pathname, location.search),
    [location.pathname, location.search])

  const handleSubmit = async (e) => {
    e.preventDefault()
    const t = titre.trim()
    if (!t) { toast.error('Le titre est obligatoire.'); return }
    setSubmitting(true)
    try {
      await innovationApi.feedback.create({
        titre: t, description: description.trim(), theme, sentiment,
        context_type: contexte?.type || '',
        context_id: contexte?.id || null,
        // NTIDE44 — page d'où part la demande (un-PII, ``user_agent`` est
        // capturé côté serveur depuis l'en-tête HTTP, jamais depuis ici).
        source_page: location.pathname,
      })
      toast.success('Merci pour votre retour !')
      setTitre(''); setDescription(''); setTheme('autre'); setSentiment('')
      onOpenChange?.(false)
    } catch {
      toast.error('Impossible d\'envoyer ce retour — réessayez.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>

      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Envoyer un retour</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            {contexte && (
              <p className="text-xs text-muted-foreground">
                Feedback : {CONTEXT_LABELS[contexte.type] || contexte.type} #{contexte.id}
              </p>
            )}
            <div className="flex flex-col gap-1.5">
              <label htmlFor="fb-titre" className="text-sm font-medium">Titre</label>
              <Input
                id="fb-titre"
                value={titre}
                onChange={(e) => setTitre(e.target.value)}
                placeholder="En une phrase, quel est votre retour ?"
                autoFocus
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="fb-description" className="text-sm font-medium">Description</label>
              <Textarea
                id="fb-description"
                rows={3}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Décrivez ce que vous avez constaté…"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="fb-theme" className="text-sm font-medium">Thème</label>
              <select
                id="fb-theme"
                className="h-[var(--control-h)] w-full rounded-md border border-input bg-card px-2 text-sm text-foreground"
                value={theme}
                onChange={(e) => setTheme(e.target.value)}
              >
                {THEMES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="fb-sentiment" className="text-sm font-medium">Ressenti (optionnel)</label>
              <select
                id="fb-sentiment"
                className="h-[var(--control-h)] w-full rounded-md border border-input bg-card px-2 text-sm text-foreground"
                value={sentiment}
                onChange={(e) => setSentiment(e.target.value)}
              >
                {SENTIMENTS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </div>
            <div className="flex items-center justify-end gap-2 pt-1">
              <Button type="button" variant="ghost" onClick={() => onOpenChange?.(false)} disabled={submitting}>
                Annuler
              </Button>
              <Button type="submit" disabled={submitting}>
                <Send /> Envoyer
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </>
  )
}
