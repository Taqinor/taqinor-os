import { useState } from 'react'
import { Sparkles } from 'lucide-react'
import { Button, toast } from '../../ui'
import iaApi from '../../api/iaApi'
import { AI_ACTIONS, isKeyMissing, textForAction, applyAiResult } from './aiWriting'

/* XKB23 — Barre d'actions IA d'écriture & résumé au-dessus du champ
   « Contenu » de l'éditeur KB : générer / reformuler / corriger / traduire
   FR↔AR / résumer, réutilisant la clé LLM déjà en place (GROQ/Anthropic du
   service IA) — key-gated, no-op propre avec message clair sans clé.

   `available` (calculé UNE fois par l'écran parent, jamais deviné ici) fait
   masquer/désactiver proprement la barre entière quand la clé LLM est
   absente — mais on tente quand même l'appel une première fois pour
   afficher le message exact du backend plutôt qu'une hypothèse locale, sauf
   quand `available === false` est déjà connu (dégradation immédiate). */
export default function AiWritingToolbar({ available = true, textareaRef, corps, onApply, disabled }) {
  const [pending, setPending] = useState(null) // action en cours

  if (available === false) return null

  const run = async (action) => {
    const el = textareaRef?.current
    const selectionStart = el?.selectionStart ?? 0
    const selectionEnd = el?.selectionEnd ?? 0
    const texte = textForAction(action, { corps, selectionStart, selectionEnd })
    if ((action === 'reformuler' || action === 'corriger'
      || action === 'traduire_fr_ar' || action === 'traduire_ar_fr') && !texte.trim()) {
      toast.error('Sélectionnez du texte à traiter, ou laissez le curseur pour traiter tout le contenu.')
      return
    }
    setPending(action)
    try {
      const res = await iaApi.kbRedaction({ action, texte })
      const result = res.data?.texte ?? res.data?.result ?? res.data?.answer ?? ''
      if (!result) {
        toast.error('Aucun résultat renvoyé par l’assistant.')
        return
      }
      onApply(applyAiResult(action, result, { corps, selectionStart, selectionEnd }))
    } catch (err) {
      const detail = err.response?.data?.detail || err.message
      toast.error(isKeyMissing(detail)
        ? 'Assistant indisponible (configuration manquante).'
        : 'L’assistant n’a pas pu traiter la demande.')
    } finally {
      setPending(null)
    }
  }

  return (
    <div
      className="flex flex-wrap items-center gap-1.5 rounded-md border border-dashed border-border bg-muted/30 p-1.5"
      data-testid="kb-ai-toolbar"
    >
      <Sparkles className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
      {AI_ACTIONS.map((a) => (
        <Button
          key={a.action}
          type="button"
          size="sm"
          variant="ghost"
          disabled={disabled || pending != null}
          loading={pending === a.action}
          onClick={() => run(a.action)}
        >
          {a.label}
        </Button>
      ))}
    </div>
  )
}
