import { useEffect, useRef, useState } from 'react'
import { ArrowRight, Calendar, Check, Flag, Hourglass, Link as LienIcone, Lock, Plus, Repeat, Ellipsis } from 'lucide-react'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from '../../../ui/DropdownMenu'
import CaseRonde from './CaseRonde'
import Etoile from './Etoile'
import { aujourdhuiIso, duree, echeanceTexte, heure, jourCourt } from '../lib/textes'

/* ============================================================================
   TCH44 — LA ligne de tâche : une liste à PLAT (aucune boîte, aucun trait entre lignes),
   52 px mini (bureau 44), 65 px avec méta ; case ronde de 22 px dans 44 px ; colonne de fin =
   heure, ★ ou drapeau. Maquettes : composants-1.html, composants-2.html, composants-4.html.
   Forme lue : ITEM (api.md §1, `contract_samples/item.json`) — une tâche ET une activité ERP.

   Équivalents SANS geste (WCAG 2.5.1, 2.5.7) : chaque ligne a un bouton « Actions »,
   visible au focus (Tab, VoiceOver), qui ouvre le MÊME menu que l'appui long ; le balayage
   gauche (Reporter, Choisir un jour) et droite (Fait) n'est qu'un raccourci tactile.

   Le composant ne parle jamais au serveur : il appelle les rappels du parent
   (`onTerminer` rejette → la case revient en arrière), et annonce par `onAnnonce(texte)`
   (le parent le relie à `role=status`, textes.md §2.19).
   ========================================================================== */

const DUREE_APPUI_LONG_MS = 500
const SEUIL_OUVERT = 64
const LARGEUR_GAUCHE = 192
const LARGEUR_DROITE = 132

/** Balayage tactile : révèle des actions sous la ligne ; un balayage complet les déclenche. */
function useBalayage({ actif, cadre, onGauche, onDroite, onAppuiLong }) {
  const [dx, setDx] = useState(0)
  const [ouvert, setOuvert] = useState(null)
  const [glisse, setGlisse] = useState(false)
  const depart = useRef(null)
  const minuteur = useRef(null)

  const annulerAppui = () => { if (minuteur.current) { clearTimeout(minuteur.current); minuteur.current = null } }
  useEffect(() => annulerAppui, [])

  const fermer = () => { setOuvert(null); setDx(0) }

  const surDebut = (e) => {
    if (e.pointerType !== 'touch') return
    depart.current = { x: e.clientX, y: e.clientY, base: ouvert === 'gauche' ? -LARGEUR_GAUCHE : ouvert === 'droite' ? LARGEUR_DROITE : 0, horizontal: false }
    annulerAppui()
    minuteur.current = setTimeout(() => { minuteur.current = null; depart.current = null; onAppuiLong() }, DUREE_APPUI_LONG_MS)
  }
  const surMouvement = (e) => {
    const d = depart.current
    if (!d) return
    const ex = e.clientX - d.x
    const ey = e.clientY - d.y
    if (!d.horizontal) {
      if (Math.abs(ex) < 8 && Math.abs(ey) < 8) return
      annulerAppui()
      if (!actif || Math.abs(ey) > Math.abs(ex)) { depart.current = null; return }
      d.horizontal = true
      setGlisse(true)
      e.currentTarget.setPointerCapture?.(e.pointerId)
    }
    setDx(Math.max(-LARGEUR_GAUCHE - 40, Math.min(LARGEUR_DROITE + 40, d.base + ex)))
  }
  const surFin = () => {
    annulerAppui()
    const d = depart.current
    depart.current = null
    if (!d?.horizontal) return
    setGlisse(false)
    const largeur = cadre.current?.offsetWidth || 360
    const position = dx
    if (position <= -largeur * 0.5) { setOuvert(null); setDx(0); onGauche(); return }
    if (position >= largeur * 0.5) { setOuvert(null); setDx(0); onDroite(); return }
    if (position <= -SEUIL_OUVERT) { setOuvert('gauche'); setDx(0); return }
    if (position >= SEUIL_OUVERT) { setOuvert('droite'); setDx(0); return }
    fermer()
  }
  return {
    dx, ouvert, glisse, fermer,
    gestes: { onPointerDown: surDebut, onPointerMove: surMouvement, onPointerUp: surFin, onPointerCancel: surFin },
  }
}

function MetaProjet({ projet }) {
  return (
    <span data-p={projet.couleur}>
      <i className="point" />
      <span className="projet-nom">{projet.nom}</span>
    </span>
  )
}

/** Les puces de méta d'une ligne, dans l'ordre des maquettes. */
function metaDe(item, { contexte, aujourdhui }) {
  const puces = []
  if (item.type === 'activite') puces.push(<span key="erp">Activité ERP</span>)
  if (contexte === 'projet' && item.jour_prevu) {
    puces.push(<span key="jour" className="fort chiffres">{jourCourt(item.jour_prevu, aujourdhui)}</span>)
  }
  const ech = item.echeance ? echeanceTexte(item.echeance, aujourdhui) : null
  if (ech) puces.push(<span key="ech" className={ech.ton === 'alerte' ? 'alerte chiffres' : 'fort chiffres'}>{ech.texte}</span>)
  const d = duree(item.estimation_minutes)
  if (d && item.heure_debut) puces.push(<span key="duree" className="chiffres">{d}</span>)
  if (item.lien?.libelle) {
    puces.push(
      <span key="lien"><LienIcone className="i i-14" aria-hidden="true" /><span className="sr">Lié à : </span>{item.lien.libelle}</span>,
    )
  }
  if (item.recurrente) puces.push(<span key="rec"><Repeat className="i i-14" aria-hidden="true" /><span className="sr">Répétée</span></span>)
  if (item.bloquee_par?.titre) {
    puces.push(<span key="bloc"><Hourglass className="i i-14" aria-hidden="true" />attend : {item.bloquee_par.titre}</span>)
  } else if (item.en_attente_de) {
    puces.push(<span key="att"><Hourglass className="i i-14" aria-hidden="true" />En attente de : {item.en_attente_de}</span>)
  }
  if (item.confidentielle) puces.push(<span key="conf"><Lock className="i i-14" aria-hidden="true" />Confidentielle</span>)
  if (contexte !== 'projet' && item.projet) puces.push(<MetaProjet key="projet" projet={item.projet} />)
  return puces
}

export default function LigneTache({
  item,
  contexte = 'jour',
  aujourdhui = aujourdhuiIso(),
  reporterLibelle = '',
  estampille = '',
  propose = false,
  selection = null,
  nbEssentielles = 0,
  onEssentiel,
  onRefusEssentiel,
  onTerminer,
  onReporter,
  onChoisirJour,
  onOuvrir,
  onGarder,
  onAction,
  onAnnonce,
}) {
  const cadre = useRef(null)
  const [menuOuvert, setMenuOuvert] = useState(false)
  const activite = item.type === 'activite'
  const fait = item.statut === 'fait'
  const attente = item.statut === 'en_attente' || Boolean(item.bloquee_par) || Boolean(item.en_attente_de)
  const cochable = !activite || item.peut_cloturer
  const balayable = !selection?.actif && !activite

  const reporter = () => { onReporter?.(item); if (reporterLibelle) onAnnonce?.(`Reportée à ${reporterLibelle}`) }
  const terminer = async (suivant) => {
    await onTerminer?.(item, suivant)
    onAnnonce?.(suivant ? `Fait : ${item.titre}` : `Rouverte : ${item.titre}`)
  }
  const balayage = useBalayage({
    actif: balayable,
    cadre,
    onGauche: reporter,
    onDroite: () => { terminer(true).catch(() => {}) },
    onAppuiLong: () => setMenuOuvert(true),
  })

  const ouvrir = () => {
    if (balayage.ouvert) { balayage.fermer(); return }
    onOuvrir?.(item)
  }
  const action = (code) => () => onAction?.(code, item)

  const classes = ['ligne']
  if (fait) classes.push('faite')
  if (estampille) classes.push('estampillee')
  if (selection?.selectionnee) classes.push('selectionnee')
  if (balayage.ouvert === 'gauche') classes.push('glisse-gauche')
  if (balayage.ouvert === 'droite') classes.push('glisse-droite')
  const style = balayage.glisse ? { transform: `translateX(${balayage.dx}px)`, transition: 'none' } : undefined

  const meta = metaDe(item, { contexte, aujourdhui })
  const aRevelation = balayage.glisse || balayage.ouvert

  return (
    <div
      ref={cadre}
      className="ligne-cadre"
      role="listitem"
      aria-selected={selection?.actif ? Boolean(selection.selectionnee) : undefined}
      data-ligne={`${item.type}:${item.id}`}
    >
      {aRevelation && (balayage.ouvert === 'droite' || balayage.dx > 0) ? (
        <div className="actions">
          <button type="button" className="action fait" aria-label={`Fait : ${item.titre}`}
            onClick={() => { balayage.fermer(); terminer(true).catch(() => {}) }}>
            <Check className="i" aria-hidden="true" />Fait
          </button>
        </div>
      ) : null}
      {aRevelation && (balayage.ouvert === 'gauche' || balayage.dx < 0) ? (
        <div className="actions droite">
          <button type="button" className="action choisir" aria-label="Choisir un jour"
            onClick={() => { balayage.fermer(); onChoisirJour?.(item) }}>
            <Calendar className="i" aria-hidden="true" />Choisir<br />un jour
          </button>
          <button type="button" className="action reporter" aria-label={reporterLibelle ? `Reporter à ${reporterLibelle}` : 'Reporter'}
            onClick={() => { balayage.fermer(); reporter() }}>
            <ArrowRight className="i" aria-hidden="true" />Reporter
            {reporterLibelle ? <small className="chiffres">{reporterLibelle}</small> : null}
          </button>
        </div>
      ) : null}

      <div
        className={classes.join(' ')}
        style={style}
        aria-live={estampille ? 'polite' : undefined}
        onContextMenu={(e) => { e.preventDefault(); setMenuOuvert(true) }}
        {...balayage.gestes}
      >
        {selection?.actif ? (
          <CaseRonde coche={Boolean(selection.selectionnee)} selection titre={item.titre} onBasculer={() => selection.onBasculer?.(item)} />
        ) : cochable ? (
          <CaseRonde coche={fait} attente={attente} titre={item.titre} onBasculer={terminer} />
        ) : (
          <span className="case vide"><span className="pastille-erp"><LienIcone className="i" aria-hidden="true" /></span></span>
        )}

        <div className="ligne-corps">
          <button type="button" className="ligne-corps-bouton" onClick={ouvrir}>
            <span className="titre">{item.titre}</span>
          </button>
          {meta.length > 0 || propose ? (
            <div className="meta">
              {propose ? (
                <button type="button" className="garder" onClick={() => onGarder?.(item)}>
                  <Plus className="i i-14" aria-hidden="true" />Garder
                </button>
              ) : null}
              {meta}
            </div>
          ) : null}
        </div>

        <div className="ligne-fin">
          {estampille ? <span className="estampille chiffres">{estampille}</span> : null}
          {item.heure_debut ? <span className="heure chiffres">{heure(item.heure_debut)}</span> : null}
          <Etoile
            active={Boolean(item.essentielle)}
            onBasculer={onEssentiel ? (suivant) => onEssentiel(item, suivant) : undefined}
            nbEssentielles={nbEssentielles}
            onRefus={onRefusEssentiel}
            titre={item.titre}
          />
          {item.priorite === 3 ? <Flag className="i i-16 drapeau" role="img" aria-label="Priorité haute" /> : null}
        </div>

        <DropdownMenu open={menuOuvert} onOpenChange={setMenuOuvert}>
          <DropdownMenuTrigger asChild>
            <button type="button" className="ligne-actions" aria-label={`Actions pour « ${item.titre} »`}>
              <Ellipsis className="i" aria-hidden="true" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {!activite && reporterLibelle ? (
              <DropdownMenuItem onSelect={reporter}>Reporter à {reporterLibelle}</DropdownMenuItem>
            ) : null}
            {!activite ? <DropdownMenuItem onSelect={action('choisir_jour')}>Choisir un jour</DropdownMenuItem> : null}
            {!activite ? <DropdownMenuItem onSelect={action('deplacer')}>Déplacer…</DropdownMenuItem> : null}
            {!activite ? (
              <DropdownMenuItem onSelect={action('essentiel')}>
                {item.essentielle ? 'Plus essentielle' : 'Essentielle'}
              </DropdownMenuItem>
            ) : null}
            {!activite ? <DropdownMenuItem onSelect={action('attente')}>En attente de…</DropdownMenuItem> : null}
            {!activite ? <DropdownMenuItem onSelect={action('priorite')}>Priorité</DropdownMenuItem> : null}
            {activite ? <DropdownMenuItem onSelect={action('lier')}>Lier une tâche</DropdownMenuItem> : null}
            {!activite ? <DropdownMenuSeparator /> : null}
            {!activite ? <DropdownMenuItem destructive onSelect={action('supprimer')}>Supprimer</DropdownMenuItem> : null}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  )
}
