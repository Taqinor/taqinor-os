import { Ellipsis, TriangleAlert } from 'lucide-react'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '../../../ui/DropdownMenu'
import { aujourdhuiIso, echeanceTexte } from '../lib/textes'

/* ============================================================================
   TCH88 — Une ligne de la liste Projets. Forme lue : PROJET (api.md §1,
   `contract_samples/projets_liste.json`). Maquette : docs/taches/maquettes/projets-liste.html.
   Textes : reference/textes.md §2.6 (puce de priorité « Haute · Moyenne · Basse · — »,
   « {faites} sur {total} », « à surveiller », « À planifier », « Projet de la semaine »).
   La ligne ne parle jamais au serveur : elle appelle `onPriorite(projet, valeur)` et
   `onAction(code, projet)` ; le parent écrit, met à jour sans relire la liste et annule.
   ========================================================================== */

// eslint-disable-next-line react-refresh/only-export-components -- table de priorités partagée par les écrans Projets (TCH88-TCH93)
export const PRIORITES = [
  { valeur: 3, libelle: 'Haute', classe: '' },
  { valeur: 2, libelle: 'Moyenne', classe: 'moyenne' },
  { valeur: 1, libelle: 'Basse', classe: 'basse' },
  { valeur: 0, libelle: '—', classe: 'aucune' },
]

// eslint-disable-next-line react-refresh/only-export-components -- idem
export const prioriteDe = (valeur) => PRIORITES.find((p) => p.valeur === valeur) ?? PRIORITES[3]

/** « 12 sur 20 » : faites sur total (faites + ouvertes), jamais un chiffre inventé. */
// eslint-disable-next-line react-refresh/only-export-components -- idem
export function avancementDe(projet) {
  const faites = projet.compteurs?.faites ?? 0
  const total = faites + (projet.compteurs?.ouvertes ?? 0)
  return { faites, total, texte: `${faites} sur ${total}`, part: total > 0 ? faites / total : 0 }
}

/** La puce de priorité, touchable : « Priorité haute, changer » ouvre les quatre choix. */
export function PuchePriorite({ projet, onChoisir }) {
  const courante = prioriteDe(projet.priorite)
  const nom = courante.valeur === 0 ? 'aucune' : courante.libelle.toLowerCase()
  const barres = [3, 2, 1]
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button type="button" className={`ep-prio ${courante.classe}`.trim()} aria-label={`Priorité ${nom}, changer`}>
          <span className="barres" aria-hidden="true">
            {barres.map((n) => <i key={n} className={courante.valeur >= n ? '' : 'eteinte'} />)}
          </span>
          {courante.libelle}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {PRIORITES.map((p) => (
          <DropdownMenuItem key={p.valeur} onSelect={() => onChoisir?.(projet, p.valeur)}>{p.libelle}</DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export default function LigneProjet({ projet, aujourdhui = aujourdhuiIso(), onOuvrir, onPriorite, onAction, enPause = false }) {
  const { texte, part } = avancementDe(projet)
  const ech = projet.echeance ? echeanceTexte(projet.echeance, aujourdhui) : null
  const surveiller = Array.isArray(projet.sante) && projet.sante.length > 0
  return (
    <div className="ligne projet" role="listitem" data-p={projet.couleur} data-projet={projet.id}>
      <span className="point-projet" aria-hidden="true" />
      <div className="ligne-corps">
        <button type="button" className="ligne-corps-bouton ep-ouvrir" onClick={() => onOuvrir?.(projet)}>
          <span className="titre">{projet.nom}</span>
        </button>
        <div className="meta">
          <span className="chiffres">{texte}</span>
          {ech ? <span className={ech.ton === 'alerte' ? 'alerte chiffres' : 'chiffres'}>{ech.texte}</span> : null}
          {surveiller ? (
            <span className="ep-sante surveiller"><TriangleAlert className="i i-14" aria-hidden="true" />à surveiller</span>
          ) : null}
          {projet.a_planifier ? <span className="ep-aplanifier">À planifier</span> : null}
          {projet.focus_semaine ? <span className="fort">Projet de la semaine</span> : null}
        </div>
        <span className="barre-avance" style={{ '--avance': part.toFixed(3) }} role="img" aria-label={texte}><i /></span>
      </div>
      <div className="ligne-fin">
        {enPause ? null : <PuchePriorite projet={projet} onChoisir={onPriorite} />}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button type="button" className="ligne-actions" aria-label={`Actions pour « ${projet.nom} »`}>
              <Ellipsis className="i" aria-hidden="true" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {enPause ? (
              <DropdownMenuItem onSelect={() => onAction?.('reprendre', projet)}>Reprendre</DropdownMenuItem>
            ) : (
              <>
                <DropdownMenuItem onSelect={() => onAction?.('en_haut', projet)}>Mettre en haut</DropdownMenuItem>
                <DropdownMenuItem onSelect={() => onAction?.('pause', projet)}>Mettre en pause</DropdownMenuItem>
              </>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  )
}
