import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { Plus } from 'lucide-react'

/* ============================================================================
   TCH45 — Sélecteur de projet : récents d'abord, recherche sans accents ni casse, et
   « + Nouveau projet » FIXE en bas (jamais perdu dans la liste). Frappe d'un nom qui n'existe
   pas : « Créer « nom » » (textes.md §2.3). Pattern listbox : la flèche bas/haut déplace
   l'option active, Entrée la choisit. Un projet = un point (la palette, `data-p`) puis son nom,
   toujours — la couleur n'est jamais seule. Se pose dans une FeuilleACrans ou un popover.
   F2 acceptation (P144.3, parcours 18 « `j m` Entrée ») : ouvert au clavier (`focusChamp`), le champ a le focus ;
   (jamais au doigt : le clavier virtuel de l'iPhone sortirait sans qu'on l'ait demandé) ; l'option active de
   départ est le premier projet AUTRE que celui de la tâche (Entrée déplace vraiment) ; une Entrée frappée pendant
   le chargement de la liste (`chargement`) est gardée et jouée dès qu'elle arrive.
   Maquette : docs/taches/maquettes/composants-5.html, composants-6.html.
   ========================================================================== */

const sansAccents = (texte) => String(texte ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()

export default function SelecteurProjet({
  projets = [],
  valeur = null,
  sansProjet = false,
  chargement = false,
  focusChamp = false,
  onChoisir,
  onNouveau,
}) {
  const [q, setQ] = useState('')
  const [actif, setActif] = useState(null)
  const entreeEnAttente = useRef(false)
  const idListe = useId()

  const options = useMemo(() => {
    const cherche = sansAccents(q.trim())
    const trouves = projets.filter((p) => !cherche || sansAccents(p.nom).includes(cherche))
    const liste = trouves.map((p) => ({ cle: `p${p.id}`, projet: p }))
    if (sansProjet && !cherche) liste.unshift({ cle: 'sans', projet: null })
    const exact = projets.some((p) => sansAccents(p.nom) === cherche)
    if (cherche && !exact) liste.push({ cle: 'creer', creer: q.trim() })
    return liste
  }, [projets, q, sansProjet])

  // tant que rien n'est tapé ni parcouru, l'option active est le premier projet qui n'est pas le sien
  const parDefaut = Math.max(options.findIndex((o) => !(o.projet && o.projet.id === valeur) && !(o.cle === 'sans' && valeur === null)), 0)
  const courant = Math.min(actif ?? parDefaut, Math.max(options.length - 1, 0))
  const choisir = (option) => {
    if (!option) return
    if (option.creer) onNouveau?.(option.creer)
    else onChoisir?.(option.projet ? option.projet.id : null)
  }
  useEffect(() => {
    if (chargement || !entreeEnAttente.current || options.length === 0) return
    entreeEnAttente.current = false
    choisir(options[courant])
  })
  const surTouche = (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setActif(Math.min(courant + 1, options.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActif(Math.max(courant - 1, 0)) }
    else if (e.key === 'Enter') {
      e.preventDefault()
      if (chargement) entreeEnAttente.current = true
      else choisir(options[courant])
    }
  }

  return (
    <div className="selecteur-projet">
      <input
        type="search"
        className="champ"
        role="combobox"
        aria-expanded="true"
        aria-controls={idListe}
        aria-activedescendant={options[courant] ? `${idListe}-${options[courant].cle}` : undefined}
        aria-label="Chercher un projet"
        placeholder="Chercher un projet"
        autoComplete="off"
        data-focus-initial={focusChamp ? '' : undefined}
        value={q}
        onChange={(e) => { setQ(e.target.value); setActif(0) }}
        onKeyDown={surTouche}
      />
      <div id={idListe} className="selecteur-projet-liste" role="listbox" aria-label="Projets">
        {options.map((option, i) => {
          const choisi = option.projet ? option.projet.id === valeur : (option.cle === 'sans' && valeur === null)
          return (
            <button
              key={option.cle}
              id={`${idListe}-${option.cle}`}
              type="button"
              role="option"
              aria-selected={i === courant}
              aria-checked={choisi}
              className="selecteur-projet-item"
              data-p={option.projet?.couleur}
              onMouseEnter={() => setActif(i)}
              onClick={() => choisir(option)}
            >
              {option.creer ? (
                <><Plus className="i i-16" aria-hidden="true" />Créer « {option.creer} »</>
              ) : option.projet ? (
                <><i className="point" aria-hidden="true" />{option.projet.nom}</>
              ) : 'Sans projet'}
            </button>
          )
        })}
      </div>
      <button
        type="button"
        className="selecteur-projet-item selecteur-projet-nouveau"
        onClick={() => onNouveau?.(q.trim())}
      >
        <Plus className="i i-16" aria-hidden="true" />Nouveau projet
      </button>
    </div>
  )
}
