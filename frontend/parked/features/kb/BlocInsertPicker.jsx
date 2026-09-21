import { useEffect, useState } from 'react'
import { PanelsTopLeft, Plus, Trash2 } from 'lucide-react'
import { Button, toast } from '../../ui'
import kbApi from '../../api/kbApi'
import FilterSelect from './FilterSelect'

/* ============================================================================
   ZGED12 — Sélecteur d'insertion de bloc réutilisable dans l'éditeur
   d'article. Charge les blocs visibles (personnels + société) et insère le
   corps du bloc choisi à la position du curseur du ``<textarea>`` référencé
   par ``textareaRef`` — même contrat que ``AiWritingToolbar``.

   WIR250 — jusqu'ici invisible PAR CONSTRUCTION (`if (!blocs.length) return
   null`) : sans aucun bloc existant, il n'y avait ni moyen d'en créer un ni
   la moindre affordance visible — un vrai serpent qui se mord la queue.
   « Enregistrer la sélection comme bloc » (crée depuis le texte sélectionné
   du corps) reste TOUJOURS visible, et la suppression du bloc choisi est
   câblée (`kbApi.removeBloc`). ========================================== */

export default function BlocInsertPicker({ textareaRef, corps, onApply, disabled }) {
  const [blocs, setBlocs] = useState([])
  const [choix, setChoix] = useState('')
  const [busy, setBusy] = useState(false)

  const chargerBlocs = () => {
    kbApi.listBlocs()
      .then((res) => setBlocs(Array.isArray(res.data) ? res.data : (res.data?.results ?? [])))
      .catch(() => setBlocs([]))
  }

  useEffect(() => { chargerBlocs() }, [])

  const insererBloc = () => {
    if (!choix) return
    const bloc = blocs.find((b) => String(b.id) === choix)
    if (!bloc) return
    const el = textareaRef?.current
    const pos = el?.selectionStart ?? (corps || '').length
    const before = (corps || '').slice(0, pos)
    const after = (corps || '').slice(pos)
    const next = `${before}${bloc.corps}${after}`
    onApply?.(next)
    toast.success(`Bloc « ${bloc.nom} » inséré.`)
    setChoix('')
  }

  const enregistrerSelectionCommeBloc = async () => {
    const el = textareaRef?.current
    const debut = el?.selectionStart ?? 0
    const fin = el?.selectionEnd ?? 0
    const selection = (corps || '').slice(debut, fin).trim()
    if (!selection) {
      toast.error('Sélectionnez du texte dans le contenu avant de l’enregistrer comme bloc.')
      return
    }
    const nom = window.prompt('Nom du bloc réutilisable :', '')
    if (!nom || !nom.trim()) return
    setBusy(true)
    try {
      await kbApi.createBloc({ nom: nom.trim(), corps: selection })
      toast.success(`Bloc « ${nom.trim()} » enregistré.`)
      chargerBlocs()
    } catch {
      toast.error('Enregistrement du bloc impossible.')
    } finally {
      setBusy(false)
    }
  }

  const supprimerBloc = async () => {
    if (!choix) return
    const bloc = blocs.find((b) => String(b.id) === choix)
    if (!bloc) return
    setBusy(true)
    try {
      await kbApi.removeBloc(bloc.id)
      toast.success(`Bloc « ${bloc.nom} » supprimé.`)
      setChoix('')
      chargerBlocs()
    } catch {
      toast.error('Suppression du bloc impossible.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <PanelsTopLeft className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
      {blocs.length > 0 ? (
        <>
          <FilterSelect
            value={choix}
            onChange={setChoix}
            aria-label="Choisir un bloc réutilisable"
            options={[
              { value: '', label: 'Insérer un bloc…' },
              ...blocs.map((b) => ({ value: String(b.id), label: b.nom })),
            ]}
          />
          <Button type="button" variant="outline" size="sm" disabled={disabled || busy || !choix} onClick={insererBloc}>
            Insérer
          </Button>
          <Button type="button" variant="ghost" size="sm" disabled={disabled || busy || !choix} onClick={supprimerBloc}>
            <Trash2 className="size-3.5" aria-hidden="true" /> Supprimer
          </Button>
        </>
      ) : (
        <span className="text-xs text-muted-foreground">Aucun bloc réutilisable pour l’instant.</span>
      )}
      <Button type="button" variant="outline" size="sm" disabled={disabled || busy} onClick={enregistrerSelectionCommeBloc}>
        <Plus className="size-3.5" aria-hidden="true" /> Enregistrer la sélection comme bloc
      </Button>
    </div>
  )
}
