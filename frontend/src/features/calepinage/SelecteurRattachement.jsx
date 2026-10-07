import { useMemo, useRef } from 'react'
import crmApi from '../../api/crmApi'
import { unwrapList } from '../../api/resource'
import { Combobox } from '../../ui'

/* ============================================================================
   ACAL181 — LE SÉLECTEUR LEAD / CLIENT PARTAGÉ.
   ----------------------------------------------------------------------------
   Extrait des deux Combobox de `CalepinageNouveau.jsx` : un seul composant,
   réutilisé par la fiche (changer le rattachement) et, ensuite, par l'écran de
   création. La recherche part au SERVEUR à chaque saisie (jamais une liste
   pré-chargée filtrée ici : un lead d'une autre société n'apparaît donc
   jamais). Le composant ne décide de rien : il rend l'identifiant choisi à
   `onChange(id, ligne)` et laisse l'appelant écrire — et relire.

   Props :
     genre    'lead' | 'client'
     valeur   identifiant courant (ou '' / null)
     libelle  libellé à afficher pour `valeur` tant qu'aucune recherche n'a eu
              lieu (le nom servi par le détail) ; sans lui l'identifiant seul
              serait connu et le champ afficherait le placeholder.
     onChange (id | null, ligneServeur | null) => void
   ========================================================================== */

const nomComplet = (ligne, repli) =>
  [ligne.nom, ligne.prenom].filter(Boolean).join(' ') || repli

export default function SelecteurRattachement({
  genre,
  valeur = null,
  libelle = '',
  onChange,
  onSearch: rechercheExterne,
  disabled = false,
  invalid = false,
  id,
  placeholder,
}) {
  const surLead = genre === 'lead'
  const lignes = useRef([])

  const chercher = useMemo(() => rechercheExterne || (async (q) => {
    const res = surLead
      ? await crmApi.getLeads({ search: q, page_size: 20 })
      : await crmApi.searchClients(q)
    const trouvees = unwrapList(res)
    lignes.current = trouvees
    return trouvees.map((l) => ({
      value: String(l.id),
      label: nomComplet(l, `${surLead ? 'Lead' : 'Client'} ${l.id}`),
      description: (surLead ? l.ville : l.adresse) || undefined,
    }))
  }), [rechercheExterne, surLead])

  const options = useMemo(() => (
    valeur && libelle ? [{ value: String(valeur), label: libelle }] : []
  ), [valeur, libelle])

  return (
    <Combobox
      id={id}
      value={valeur ? String(valeur) : null}
      options={options}
      onSearch={chercher}
      onChange={(v) => onChange?.(
        v ?? null,
        lignes.current.find((l) => String(l.id) === String(v)) || null,
      )}
      disabled={disabled}
      invalid={invalid}
      placeholder={placeholder
        || (surLead ? 'Rechercher un lead…' : 'Rechercher un client…')}
    />
  )
}
