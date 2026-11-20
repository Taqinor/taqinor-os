import { useEffect, useRef, useState } from 'react'
import { Ellipsis, TriangleAlert } from 'lucide-react'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger,
} from '../../../ui/DropdownMenu'
import { ABR_JOURS, ABR_MOIS, aujourdhuiIso, ecartJours, echeanceTexte, jourCourt } from '../lib/textes'

/* ============================================================================
   TCH88 — Une ligne de la liste Projets. Forme lue : PROJET (api.md §1,
   `contract_samples/projets_liste.json`). Maquette : docs/taches/maquettes/projets-liste.html.
   Textes : reference/textes.md §2.6 (puce de priorité « Haute · Moyenne · Basse · — »,
   « {faites} sur {total} », « à surveiller », « À planifier », « Projet de la semaine »).
   R2-067 — `ouvert` : le projet affiché à droite au bureau (maître-détail), surligné, `aria-current` sur son nom.
   La ligne ne parle jamais au serveur : elle appelle `onPriorite(projet, valeur)` et
   `onAction(code, projet)` ; le parent écrit, met à jour sans relire la liste et annule.
   ========================================================================== */

// eslint-disable-next-line react-refresh/only-export-components -- table de priorités partagée par les écrans Projets (TCH88-TCH93)
export const PRIORITES = [
  { valeur: 3, libelle: 'Haute', classe: '' },
  { valeur: 2, libelle: 'Moyenne', classe: 'moyenne' },
  { valeur: 1, libelle: 'Basse', classe: 'basse' },
  { valeur: 0, libelle: 'Aucune', classe: 'aucune' }, // R2-071 : écrit, jamais « — »
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

/**
 * Passe visuelle n° 40 — la date d'un projet, UNE forme pour la liste, la vue d'un projet et la revue
 * (projets-liste.html, projet-liste.html, revue-semaine.html) : « aujourd'hui » · « demain » · « ven. 4 déc. »
 * (jour, quantième ET mois, même à moins de 13 jours) ; à 12 mois ou plus, l'année : « ven. 15 janv. 2028 ». R4-44 — le
 * passé a la MÊME forme (« jeu. 12 nov. ») : « jeu. 12/11 » était une 4e façon d'écrire une date à l'écran.
 */
// eslint-disable-next-line react-refresh/only-export-components -- idem
export function jourProjet(iso, aujourdhui = aujourdhuiIso()) {
  const ecart = ecartJours(iso, aujourdhui)
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso ?? ''))
  if (ecart === null || !m) return ''
  if (ecart === 0 || ecart === 1) return jourCourt(iso, aujourdhui)
  const [annee, mois, jour] = [Number(m[1]), Number(m[2]), Number(m[3])]
  const texte = `${ABR_JOURS[new Date(Date.UTC(annee, mois - 1, jour)).getUTCDay()]} ${jour} ${ABR_MOIS[mois - 1]}`
  return Math.abs(ecart) >= 365 ? `${texte} ${annee}` : texte
}

/** « échéance ven. 4 déc. » (`ton` fort) ; aujourd'hui et dépassée gardent la forme d'`echeanceTexte` (`ton` alerte). */
// eslint-disable-next-line react-refresh/only-export-components -- idem
export function echeanceProjet(echeance, aujourdhui = aujourdhuiIso()) {
  const base = echeanceTexte(echeance, aujourdhui)
  if (!base || base.ton === 'alerte') return base
  return { texte: `échéance ${jourProjet(echeance, aujourdhui)}`, ton: base.ton }
}

/** La puce de priorité, touchable : « Priorité haute, changer » ouvre les quatre choix. */
export function PuchePriorite({ projet, onChoisir }) {
  const courante = prioriteDe(projet.priorite)
  const nom = courante.valeur === 0 ? 'aucune' : courante.libelle.toLowerCase()
  // trois barres croissantes, allumées depuis la gauche (« Moyenne » : deux allumées, la plus haute éteinte)
  const barres = [1, 2, 3]
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

const DUREE_APPUI_LONG_MS = 500
const DEPLACEMENT_MAX = 8

/** R2-060 — l'appui long (500 ms, doigt immobile) sur la ligne ouvre le menu ⋯ ; le clic qui suit est avalé. */
function useAppuiLong(ouvrir) {
  const minuteur = useRef(null)
  const depart = useRef(null)
  const avale = useRef(false)
  const arreter = () => { if (minuteur.current) { clearTimeout(minuteur.current); minuteur.current = null } }
  useEffect(() => arreter, [])
  return {
    surClic: (e) => { if (avale.current) { avale.current = false; e.preventDefault(); e.stopPropagation() } },
    gestes: {
      onPointerDown: (e) => {
        if (e.pointerType !== 'touch') return
        avale.current = false
        depart.current = { x: e.clientX, y: e.clientY }
        arreter()
        minuteur.current = setTimeout(() => { minuteur.current = null; avale.current = true; ouvrir() }, DUREE_APPUI_LONG_MS)
      },
      onPointerMove: (e) => {
        const d = depart.current
        if (d && (Math.abs(e.clientX - d.x) > DEPLACEMENT_MAX || Math.abs(e.clientY - d.y) > DEPLACEMENT_MAX)) arreter()
      },
      onPointerUp: arreter,
      onPointerCancel: arreter,
      onContextMenu: (e) => { e.preventDefault(); ouvrir() },
    },
  }
}

export default function LigneProjet({ projet, aujourdhui = aujourdhuiIso(), onOuvrir, onPriorite, onAction, enPause = false, ouvert = false }) {
  const { texte, part } = avancementDe(projet)
  const ech = projet.echeance ? echeanceProjet(projet.echeance, aujourdhui) : null
  const surveiller = Array.isArray(projet.sante) && projet.sante.length > 0
  const [menuOuvert, setMenuOuvert] = useState(false)
  const appui = useAppuiLong(() => setMenuOuvert(true))
  return (
    <div className={`ligne projet${ouvert ? ' ouvert-bureau' : ''}`} role="listitem" data-p={projet.couleur} data-projet={projet.id} {...appui.gestes}>
      <span className="point-projet" aria-hidden="true" />
      <div className="ligne-corps">
        <button type="button" className="ligne-corps-bouton ep-ouvrir" aria-current={ouvert ? 'true' : undefined} onClickCapture={appui.surClic} onClick={() => onOuvrir?.(projet)}>
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
        <DropdownMenu open={menuOuvert} onOpenChange={setMenuOuvert}>
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
            <DropdownMenuItem destructive onSelect={() => onAction?.('supprimer', projet)}>Supprimer</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  )
}
