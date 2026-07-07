import { useEffect, useState } from 'react'
import { PanelsTopLeft } from 'lucide-react'
import { Button, toast } from '../../ui'
import kbApi from '../../api/kbApi'
import FilterSelect from './FilterSelect'

/* ============================================================================
   ZGED12 — Sélecteur d'insertion de bloc réutilisable dans l'éditeur
   d'article. Charge les blocs visibles (personnels + société) et insère le
   corps du bloc choisi à la position du curseur du ``<textarea>`` référencé
   par ``textareaRef`` — même contrat que ``AiWritingToolbar``.
   ========================================================================== */

export default function BlocInsertPicker({ textareaRef, corps, onApply, disabled }) {
  const [blocs, setBlocs] = useState([])
  const [choix, setChoix] = useState('')

  useEffect(() => {
    kbApi.listBlocs()
      .then((res) => setBlocs(Array.isArray(res.data) ? res.data : (res.data?.results ?? [])))
      .catch(() => setBlocs([]))
  }, [])

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

  if (!blocs.length) return null

  return (
    <div className="flex items-center gap-1.5">
      <PanelsTopLeft className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
      <FilterSelect
        value={choix}
        onChange={setChoix}
        aria-label="Choisir un bloc réutilisable"
        options={[
          { value: '', label: 'Insérer un bloc…' },
          ...blocs.map((b) => ({ value: String(b.id), label: b.nom })),
        ]}
      />
      <Button type="button" variant="outline" size="sm" disabled={disabled || !choix} onClick={insererBloc}>
        Insérer
      </Button>
    </div>
  )
}
