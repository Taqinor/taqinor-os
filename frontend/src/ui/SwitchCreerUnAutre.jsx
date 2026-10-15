import { Switch } from './Switch'

/* Interrupteur « Créer un autre » du pied d'un formulaire de création
   (voir hooks/useCreerUnAutre). `className` : classes de l'étiquette. */
export default function SwitchCreerUnAutre({ checked, onChange, className }) {
  return (
    <label className={className}>
      <Switch
        checked={checked}
        onCheckedChange={onChange}
        aria-label="Créer un autre"
      />
      Créer un autre
    </label>
  )
}
