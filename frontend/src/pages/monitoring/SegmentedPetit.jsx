import { Segmented } from '../../ui'

/* Segmented compact (size="sm") PARTAGÉ des écrans Supervision : fenêtre
   d'analyse, période, mode d'affichage… */
export default function SegmentedPetit({ options, value, onChange, label }) {
  return (
    <Segmented
      size="sm"
      options={options}
      value={value}
      onChange={onChange}
      aria-label={label}
    />
  )
}
