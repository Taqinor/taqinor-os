import { useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useChantiers, chantierLabel } from './useChantiers'

/* PACT62 — sélecteur de chantier partagé (voir useChantiers.js).
   CHT19 — pré-sélection par paramètre d'URL `?chantier=<id>`, lue UNE SEULE
   FOIS au montage (patron ?id=/?lead= déjà établi ailleurs dans le dépôt) :
   n'écrase JAMAIS une valeur déjà présente (`value` fourni par le parent, ou
   déjà choisie par l'utilisateur). EFFET DE BORD ASSUMÉ : les 7 écrans
   btp_chantier (AvenantsChantier, DecompteGeneral, DiffusionPlans,
   JournalChantier, ReservesChantier, RFI, VisasDocuments) + SuiviProjetChantier
   + NotesDeFraisPage (CHT16) héritent TOUS de cette pré-sélection sans rien
   changer chez eux — c'est le but recherché. */
export default function ChantierSelect({
  value, onChange, label = 'Chantier', required = false, id,
}) {
  const { chantiers, loading } = useChantiers()
  const [searchParams] = useSearchParams()

  useEffect(() => {
    if (value) return
    const depuisUrl = searchParams.get('chantier')
    if (depuisUrl) onChange(depuisUrl)
    // Une seule fois au montage : un changement ultérieur de l'URL ne doit
    // jamais écraser une sélection déjà faite par l'utilisateur.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <select
      id={id}
      aria-label={label}
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value)}
      required={required}
      disabled={loading}
    >
      <option value="">{loading ? 'Chargement…' : 'Chantier…'}</option>
      {chantiers.map((c) => (
        <option key={c.id} value={c.id}>{chantierLabel(c)}</option>
      ))}
    </select>
  )
}
