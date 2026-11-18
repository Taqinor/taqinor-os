import { ChartGantt, ChevronDown, Columns3, ListTodo } from 'lucide-react'
import { VUES_PROJET } from '../lib/projets'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '../../../ui/DropdownMenu'

/* ============================================================================
   TCH90 — Le sélecteur de vue d'un projet : Liste · Tableau · Chronologie (textes.md §2.6 « Vues »).
   Maquettes : projet-liste.html, projet-tableau.html, projet-chronologie.html. Deux formes pour UN seul état :
   iPhone, une puce « Vue : Tableau, changer » qui ouvre le menu des trois vues ; bureau, un segmenté
   (`role=radiogroup`). C'est CSS seul qui montre l'une ou l'autre (`styles/taches/projets.css`).
   Présentation seule : l'écran choisit, mémorise (`affichage.vue`) et rappelle `onChoisir(code)`.
   ========================================================================== */

const ICONES = { liste: ListTodo, tableau: Columns3, chronologie: ChartGantt }

export default function SelecteurVue({ vue, onChoisir }) {
  const [codeActif, nomActif] = VUES_PROJET.find(([code]) => code === vue) ?? VUES_PROJET[0]
  const IconeActive = ICONES[codeActif]
  return (
    <div className="ep-entre">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button type="button" className="ep-vue-puce mobile-seul" aria-label={`Vue : ${nomActif}, changer`}>
            <IconeActive aria-hidden="true" />{nomActif}<ChevronDown aria-hidden="true" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          {VUES_PROJET.map(([code, nom]) => (
            <DropdownMenuItem key={code} onSelect={() => onChoisir(code)}>{nom}</DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>
      <div className="ep-vues bureau-seul" role="radiogroup" aria-label="Vue">
        {VUES_PROJET.map(([code, nom]) => (
          <button key={code} type="button" role="radio" aria-checked={code === vue} onClick={() => onChoisir(code)}>{nom}</button>
        ))}
      </div>
    </div>
  )
}
