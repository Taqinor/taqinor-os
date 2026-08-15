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

export default function BlocInsertPicker({
  textareaRef, corps, onApply, disabled, rafraichir = 0, onBlocsChange,
}) {
  const [blocs, setBlocs] = useState([])
  const [choix, setChoix] = useState('')

  useEffect(() => {
    kbApi.listBlocs()
      .then((res) => {
        const rows = Array.isArray(res.data) ? res.data : (res.data?.results ?? [])
        setBlocs(rows)
        onBlocsChange?.(rows)
      })
      .catch(() => setBlocs([]))
    // `rafraichir` change à chaque bloc créé/supprimé par l'éditeur.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rafraichir])

  const supprimerBloc = async () => {
    if (!choix) return
    const bloc = blocs.find((b) => String(b.id) === choix)
    try {
      await kbApi.removeBloc(Number(choix))
      setBlocs((rows) => rows.filter((b) => String(b.id) !== choix))
      setChoix('')
      toast.success(`Bloc « ${bloc?.nom ?? choix} » supprimé.`)
    } catch {
      toast.error('Suppression du bloc impossible.')
    }
  }

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

  // WIR250 — le `return null` d'origine rendait la fonctionnalité INVISIBLE
  // PAR CONSTRUCTION : sans bloc en base, le sélecteur disparaissait, et
  // comme rien d'autre n'en créait, il ne réapparaissait jamais. On rend
  // désormais toujours la barre : l'éditeur y expose « Enregistrer la
  // sélection comme bloc », qui est le seul chemin de création.
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <PanelsTopLeft className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
      {blocs.length ? (
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
          <Button type="button" variant="outline" size="sm" disabled={disabled || !choix} onClick={insererBloc}>
            Insérer
          </Button>
          <Button
            type="button" variant="ghost" size="sm"
            disabled={disabled || !choix}
            onClick={supprimerBloc}
          >
            Supprimer le bloc
          </Button>
        </>
      ) : (
        <span className="text-xs text-muted-foreground">
          Aucun bloc réutilisable — sélectionnez du texte puis « Enregistrer la
          sélection comme bloc ».
        </span>
      )}
    </div>
  )
}
