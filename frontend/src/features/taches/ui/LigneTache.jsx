import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  AlignLeft, ArrowRight, Bell, Calendar, Check, Flag, Hourglass, Link as LienIcone, ListChecks, Lock, Repeat, Ellipsis,
} from 'lucide-react'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from '../../../ui/DropdownMenu'
import CaseRonde from './CaseRonde'
import Etoile from './Etoile'
import FeuilleACrans from './FeuilleACrans'
import { retenirApercu } from '../lib/fiche'
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
   TCH152 — `glissable` (bureau seulement : `{ onDebut(item), onFin() }`) : une tâche ouverte se glisse vers une
   heure de la colonne Agenda ; sans la prop, la ligne ne se glisse pas (iPhone : jamais de glisser, spec-7 §5).
   Passe visuelle n° 46 (recherche.html) — `surligne` (le texte cherché) : ses mots sont surlignés dans le titre ;
   `contexte="recherche"` : la méta commence par le statut du résultat. Sans ces props, la ligne ne change pas.
   R2-018 — `groupeTitre` : le nom du projet qui TITRE le groupe où la ligne est rendue (omis de sa méta).
   ========================================================================== */

const DUREE_APPUI_LONG_MS = 500
const SEUIL_OUVERT = 64
const LARGEUR_GAUCHE = 192
const LARGEUR_DROITE = 132

/** R2-032 — le toucher qui referme une ligne ouverte n'ouvre rien d'autre : son `click` est avalé, une fois. S'il n'y a
 *  pas de clic (c'était un défilement), le toucher suivant retire l'avaleur. Hors de React : la ligne, une fois fermée,
 *  démonte son effet, et l'avaleur doit lui survivre jusqu'au clic. */
function avalerProchainClic() {
  const retirer = () => {
    document.removeEventListener('click', avaler, true)
    document.removeEventListener('pointerdown', retirer, true)
  }
  const avaler = (c) => { c.stopPropagation(); c.preventDefault(); retirer() }
  document.addEventListener('click', avaler, true)
  document.addEventListener('pointerdown', retirer, true)
}

/** R2-032 — pendant le glissement, les actions se partagent exactement la largeur que le doigt a découverte (au repos,
 *  la feuille de style leur donne leur largeur pleine) : jamais une bande vide ou grise à côté de la ligne. */
const BOUTON_PROPORTIONNEL = { flexGrow: 1, flexShrink: 1, flexBasis: '0px', width: 'auto', minWidth: 0 }

/** Balayage tactile : révèle des actions sous la ligne ; un balayage complet les déclenche. */
function useBalayage({ actif, cadre, onGauche, onDroite, onAppuiLong }) {
  const [dx, setDx] = useState(0)
  const [ouvert, setOuvert] = useState(null)
  const [glisse, setGlisse] = useState(false)
  const depart = useRef(null)
  const minuteur = useRef(null)
  // où est le DOIGT (non plafonné) : l'affichage s'arrête à la largeur des actions, le seuil du balayage complet non
  const doigt = useRef(0)

  const annulerAppui = () => { if (minuteur.current) { clearTimeout(minuteur.current); minuteur.current = null } }
  useEffect(() => annulerAppui, [])

  const fermer = () => { setOuvert(null); setDx(0) }

  // R2-032 — un toucher AILLEURS referme d'abord la ligne ouverte (et n'ouvre rien d'autre)
  useEffect(() => {
    if (!ouvert) return undefined
    const dehors = (e) => {
      if (cadre.current?.contains(e.target)) return
      setOuvert(null)
      setDx(0)
      avalerProchainClic()
    }
    document.addEventListener('pointerdown', dehors, true)
    return () => document.removeEventListener('pointerdown', dehors, true)
  }, [ouvert, cadre])

  const surDebut = (e) => {
    if (e.pointerType !== 'touch') return
    depart.current = { x: e.clientX, y: e.clientY, base: ouvert === 'gauche' ? -LARGEUR_GAUCHE : ouvert === 'droite' ? LARGEUR_DROITE : 0, horizontal: false }
    annulerAppui()
    minuteur.current = setTimeout(() => {
      minuteur.current = null
      depart.current = null
      // R4-21 — le doigt est ENCORE posé : son relâcher (pointerup, touchend, puis le click que le navigateur envoie à
      // ce qui est passé sous lui — « Choisir un jour », « Priorité », le voile —, dans un ordre qui varie, parfois sans
      // click) ne doit rien déclencher. Le prochain click est avalé ; un NOUVEAU toucher (pointerdown) retire l'avaleur,
      // et lui seul agit. Aucun minuteur de protection : c'est le geste suivant qui décide.
      avalerProchainClic()
      onAppuiLong()
    }, DUREE_APPUI_LONG_MS)
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
    doigt.current = d.base + ex
    setDx(Math.max(-LARGEUR_GAUCHE - 40, Math.min(LARGEUR_DROITE + 40, doigt.current)))
  }
  const surFin = () => {
    annulerAppui()
    const d = depart.current
    depart.current = null
    if (!d?.horizontal) return
    setGlisse(false)
    const largeur = cadre.current?.offsetWidth || 360
    const position = doigt.current
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

/* Passe visuelle n° 46 — le mot cherché, surligné dans le titre (recherche.html : `<b class="es-trouve">`).
   Casse et accents ignorés ; le titre est DÉCOUPÉ en fragments de texte (jamais de HTML interprété). */
const sansAccent = (texte) => texte.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase()

/** Les plages `[début, fin[` du titre où tombe un des mots, fusionnées quand elles se touchent. */
function plagesTrouvees(titre, mots) {
  const caracteres = Array.from(titre)
  const carte = [] // position dans le texte normalisé → indice du caractère d'origine
  let plat = ''
  caracteres.forEach((car, i) => {
    const n = sansAccent(car)
    for (let k = 0; k < n.length; k += 1) carte.push(i)
    plat += n
  })
  const plages = []
  for (const mot of mots) {
    for (let pos = plat.indexOf(mot); pos >= 0 && mot; pos = plat.indexOf(mot, pos + mot.length)) {
      let fin = carte[pos + mot.length - 1] + 1
      while (fin < caracteres.length && !sansAccent(caracteres[fin])) fin += 1 // un accent décomposé reste avec sa lettre
      plages.push([carte[pos], fin])
    }
  }
  plages.sort((a, b) => a[0] - b[0])
  const fusion = []
  for (const p of plages) {
    const der = fusion[fusion.length - 1]
    if (der && p[0] <= der[1]) der[1] = Math.max(der[1], p[1])
    else fusion.push([...p])
  }
  return { caracteres, plages: fusion }
}

function TitreSurligne({ titre, surligne }) {
  const mots = sansAccent(surligne).split(/\s+/).filter(Boolean)
  if (mots.length === 0) return titre
  const { caracteres, plages } = plagesTrouvees(titre, mots)
  if (plages.length === 0) return titre
  const fragments = []
  let curseur = 0
  plages.forEach(([debut, fin]) => {
    if (debut > curseur) fragments.push(caracteres.slice(curseur, debut).join(''))
    fragments.push(<b key={debut} className="es-trouve">{caracteres.slice(debut, fin).join('')}</b>)
    curseur = fin
  })
  if (curseur < caracteres.length) fragments.push(caracteres.slice(curseur).join(''))
  return fragments
}

/** La méta de STATUT d'un résultat de recherche (recherche.html), lue des données servies : son jour, sinon, pour une
 *  tâche ouverte, « Plus tard » ou « À trier » (ni jour, ni réserve, ni projet) ; puis « Suggéré par l'ERP ». */
function statutRecherche(item, aujourdhui) {
  if (item.type !== 'tache') return []
  const puces = []
  const ouverte = item.statut !== 'fait' && item.statut !== 'annule'
  if (item.jour_prevu) puces.push(<span key="statut" className="chiffres">{jourCourt(item.jour_prevu, aujourdhui)}</span>)
  else if (ouverte && item.quelque_jour) puces.push(<span key="statut">Plus tard</span>)
  else if (ouverte && !item.projet) puces.push(<span key="statut">À trier</span>)
  if (item.source === 'suggestion') puces.push(<span key="suggestion">Suggéré par l'ERP</span>)
  return puces
}

/** R2-018 — les puces BRÈVES : une méta qui n'en compte que deux au plus peut tenir sur la ligne du titre
 *  (`.ligne-corps.meta-courte`, la règle CSS est celle de la coquille) ; un lien, une raison ou une attente, jamais. */
const PUCES_BREVES = new Set(['statut', 'jour', 'ech', 'duree', 'projet'])
const INDICES = new Set(['note', 'check', 'rappel']) // R2-028 : de petites icônes, jamais comptées dans la méta brève
const metaCourte = (meta) => {
  const puces = meta.filter((p) => !INDICES.has(p.key))
  return puces.length > 0 && puces.length <= 2 && puces.every((p) => PUCES_BREVES.has(p.key))
}

/** Les puces de méta d'une ligne, dans l'ordre des maquettes. */
function metaDe(item, { contexte, aujourdhui, propose, groupeTitre }) {
  const puces = contexte === 'recherche' ? statutRecherche(item, aujourdhui) : []
  if (item.type === 'activite') puces.push(<span key="erp">Activité ERP</span>)
  if (contexte === 'projet' && item.jour_prevu) {
    puces.push(<span key="jour" className="fort chiffres">{jourCourt(item.jour_prevu, aujourdhui)}</span>)
  }
  // TCH78 — une ligne proposée DIT sa raison (« échéance jeudi », « prévue hier ») ; elle remplace la puce d'échéance
  const raison = propose ? item.raison?.texte : ''
  if (raison) puces.push(<span key="raison" className="explique">{raison}</span>)
  const ech = item.echeance && !raison ? echeanceTexte(item.echeance, aujourdhui) : null
  if (ech) puces.push(<span key="ech" className={ech.ton === 'alerte' ? 'alerte chiffres' : 'fort chiffres'}>{ech.texte}</span>)
  const d = duree(item.estimation_minutes)
  // R2-018 — « 2 h » nu se lisait « à 2 h » : la durée porte son sablier (et « Durée : » pour la lecture d'écran)
  if (d && item.heure_debut) {
    puces.push(
      <span key="duree" className="chiffres"><Hourglass className="i i-14" aria-hidden="true" /><span className="sr">Durée : </span>{d}</span>,
    )
  }
  // R2-028 — ce que la ligne ne montrait pas : une note, une check-list, un rappel (petites icônes discrètes, comme Things).
  // Les notes ne sont servies que par la fiche ; une liste peut porter `a_notes` : l'indice n'apparaît que si la donnée le dit.
  if (item.notes || item.a_notes) {
    puces.push(<span key="note" className="indice"><AlignLeft className="i i-14" aria-hidden="true" /><span className="sr">Note</span></span>)
  }
  if (item.checklist?.total > 0) {
    puces.push(
      <span key="check" className="indice chiffres">
        <ListChecks className="i i-14" aria-hidden="true" /><span className="sr">Check-list : </span>{item.checklist.faits}/{item.checklist.total}
      </span>,
    )
  }
  if (item.rappel?.heure && item.statut !== 'fait') {
    const quand = item.rappel.jour && item.rappel.jour !== aujourdhui ? `${jourCourt(item.rappel.jour, aujourdhui)} ` : ''
    puces.push(
      <span key="rappel" className="indice chiffres">
        <Bell className="i i-14" aria-hidden="true" /><span className="sr">{`Rappel ${quand}à ${heure(item.rappel.heure)}`}</span>
      </span>,
    )
  }
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
  // R2-018 — le nom du projet n'est pas répété sous un groupe qui le porte déjà en titre
  if (contexte !== 'projet' && item.projet && item.projet.nom !== groupeTitre) puces.push(<MetaProjet key="projet" projet={item.projet} />)
  return puces
}

export default function LigneTache({
  item,
  contexte = 'jour',
  // couture r2 — `none` quand un parent porte déjà le rôle `listitem` (ligne réordonnable d'une vue Liste)
  roleCadre = 'listitem',
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
  glissable = null,
  surligne = '',
  groupeTitre = '',
}) {
  const cadre = useRef(null)
  const [menuOuvert, setMenuOuvert] = useState(false)
  // R3-061 — ce que la ligne sait de sa tâche est l'aperçu de la fiche : elle s'ouvre dessus, sans « Chargement… »
  useEffect(() => { retenirApercu(item) }, [item])
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
  // R3-063 (choix C-23) — l'appui long au doigt ouvre une FEUILLE DU BAS titrée de la tâche (rangées de 48 px, la ligne
  // surlignée tant qu'elle est ouverte) ; le menu ⋯ du bureau (souris, clic droit, clavier) ne change pas
  const [feuilleActions, setFeuilleActions] = useState(false)
  const [hote, setHote] = useState(null) // `.tch` : la feuille est rendue hors de la ligne (ni listitem, ni overflow)
  const geste = useRef(null) // le geste choisi dans la feuille : il part une fois la feuille fermée
  const dernierToucher = useRef(false)
  const ouvrirFeuilleActions = () => {
    setHote(cadre.current?.closest('.tch') ?? document.body)
    setFeuilleActions(true)
  }
  const balayage = useBalayage({
    actif: balayable,
    cadre,
    onGauche: reporter,
    onDroite: () => { terminer(true).catch(() => {}) },
    onAppuiLong: ouvrirFeuilleActions,
  })

  const ouvrir = () => {
    if (balayage.ouvert) { balayage.fermer(); return }
    onOuvrir?.(item)
  }
  const action = (code) => () => onAction?.(code, item)

  /** Les actions de la ligne : les MÊMES dans le menu ⋯ (bureau) et la feuille de l'appui long (doigt). */
  const actions = activite
    ? [{ cle: 'lier', libelle: 'Lier une tâche', faire: action('lier') }]
    : [
      ...(reporterLibelle ? [{ cle: 'reporter', libelle: `Reporter à ${reporterLibelle}`, faire: reporter }] : []),
      { cle: 'choisir_jour', libelle: 'Choisir un jour', faire: action('choisir_jour') },
      ...(item.quelque_jour ? [] : [{ cle: 'reserve', libelle: 'Plus tard', faire: action('reserve') }]),
      { cle: 'deplacer', libelle: 'Changer de projet…', faire: action('deplacer') },
      { cle: 'essentiel', libelle: item.essentielle ? 'Plus essentielle' : 'Essentielle', faire: action('essentiel') },
      { cle: 'attente', libelle: 'En attente de…', faire: action('attente') },
      { cle: 'priorite', libelle: 'Priorité', faire: action('priorite') },
      { cle: 'supprimer', libelle: 'Supprimer', faire: action('supprimer'), destructive: true, separe: true },
    ]
  const choisirDansLaFeuille = (faire) => { geste.current = faire; setFeuilleActions(false) }
  const apresFeuilleActions = () => { const faire = geste.current; geste.current = null; faire?.() }

  const classes = ['ligne']
  if (fait) classes.push('faite')
  if (estampille) classes.push('estampillee')
  if (selection?.selectionnee) classes.push('selectionnee')
  if (feuilleActions) classes.push('en-actions')
  if (balayage.ouvert === 'gauche') classes.push('glisse-gauche')
  if (balayage.ouvert === 'droite') classes.push('glisse-droite')
  const style = balayage.glisse ? { transform: `translateX(${balayage.dx}px)`, transition: 'none' } : undefined

  const meta = metaDe(item, { contexte, aujourdhui, propose, groupeTitre })
  const aRevelation = balayage.glisse || balayage.ouvert

  return (
    <div
      ref={cadre}
      className="ligne-cadre"
      role={roleCadre}
      aria-selected={selection?.actif ? Boolean(selection.selectionnee) : undefined}
      data-ligne={`${item.type}:${item.id}`}
      draggable={glissable && item.type === 'tache' && !fait ? true : undefined}
      onDragStart={glissable && item.type === 'tache' && !fait ? (e) => {
        e.dataTransfer?.setData('text/plain', `tache:${item.id}`)
        if (e.dataTransfer) e.dataTransfer.effectAllowed = 'move'
        glissable.onDebut(item)
      } : undefined}
      onDragEnd={glissable ? () => glissable.onFin() : undefined}
    >
      {aRevelation && (balayage.ouvert === 'droite' || balayage.dx > 0) ? (
        <div className="actions" style={balayage.glisse ? { right: 'auto', width: Math.max(0, balayage.dx), overflow: 'hidden' } : undefined}>
          <button type="button" className="action fait" aria-label={`Fait : ${item.titre}`} style={balayage.glisse ? BOUTON_PROPORTIONNEL : undefined}
            onClick={() => { balayage.fermer(); terminer(true).catch(() => {}) }}>
            <Check className="i" aria-hidden="true" />Fait
          </button>
        </div>
      ) : null}
      {aRevelation && (balayage.ouvert === 'gauche' || balayage.dx < 0) ? (
        <div className="actions droite" style={balayage.glisse ? { left: 'auto', width: Math.max(0, -balayage.dx), overflow: 'hidden' } : undefined}>
          <button type="button" className="action choisir" aria-label="Choisir un jour" style={balayage.glisse ? BOUTON_PROPORTIONNEL : undefined}
            onClick={() => { balayage.fermer(); onChoisirJour?.(item) }}>
            <Calendar className="i" aria-hidden="true" />Choisir<br />un jour
          </button>
          <button type="button" className="action reporter" aria-label={reporterLibelle ? `Reporter à ${reporterLibelle}` : 'Reporter'}
            style={balayage.glisse ? BOUTON_PROPORTIONNEL : undefined}
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
        // au doigt, Android envoie aussi `contextmenu` à l'appui long : la feuille suffit, jamais le menu en plus
        onContextMenu={(e) => { e.preventDefault(); if (!dernierToucher.current) setMenuOuvert(true) }}
        {...balayage.gestes}
        onPointerDown={(e) => { dernierToucher.current = e.pointerType === 'touch'; balayage.gestes.onPointerDown(e) }}
      >
        {selection?.actif ? (
          <CaseRonde coche={Boolean(selection.selectionnee)} selection titre={item.titre} onBasculer={() => selection.onBasculer?.(item)} />
        ) : cochable ? (
          <CaseRonde coche={fait} attente={attente} titre={item.titre} onBasculer={terminer} />
        ) : (
          <span className="case vide"><span className="pastille-erp"><LienIcone className="i" aria-hidden="true" /></span></span>
        )}

        <div className={!propose && metaCourte(meta) ? 'ligne-corps meta-courte' : 'ligne-corps'}>
          <button type="button" className="ligne-corps-bouton" onClick={ouvrir}>
            <span className="titre">{surligne ? <TitreSurligne titre={item.titre} surligne={surligne} /> : item.titre}</span>
          </button>
          {meta.length > 0 || propose ? (
            <div className="meta">
              {propose ? (
                <button type="button" className="garder" aria-label={`Mettre « ${item.titre} » aujourd'hui`}
                  onClick={() => onGarder?.(item)}>Aujourd&apos;hui</button>
              ) : null}
              {meta}
            </div>
          ) : null}
        </div>

        <div className="ligne-fin">
          {estampille ? <span className="estampille chiffres">{estampille}</span> : null}
          {/* spec-8 §2 « heure, ★ ou drapeau » : l'étoile d'une essentielle tient lieu du drapeau ; drapeau AVANT l'heure
              (maquettes ecran-aujourdhui-15h.html, ecran-bilan.html) */}
          {/* R2-017 — la pastille « → ven. 20 » se POSE sur la colonne (R3-086) le temps que la ligne s'efface ; couture L7 :
              l'heure, le drapeau et l'étoile restent à leur place, CACHÉS (`visibility: hidden`, inertes) au lieu d'être
              retirés — les retirer changeait la largeur de la colonne, donc la hauteur de la ligne (bureau : 80 → 58) */}
          <span className={estampille ? 'ligne-fin-masque masquee' : 'ligne-fin-masque'}
            aria-hidden={estampille ? 'true' : undefined} inert={Boolean(estampille)}>
            {item.priorite === 3 && !item.essentielle ? <Flag className="i i-16 drapeau" role="img" aria-label="Priorité haute" /> : null}
            {item.heure_debut ? <span className="heure chiffres">{heure(item.heure_debut)}</span> : null}
            <Etoile
              active={Boolean(item.essentielle)}
              onBasculer={onEssentiel ? (suivant) => onEssentiel(item, suivant) : undefined}
              nbEssentielles={nbEssentielles}
              onRefus={onRefusEssentiel}
              titre={item.titre}
            />
          </span>
        </div>

        <DropdownMenu open={menuOuvert} onOpenChange={setMenuOuvert}>
          <DropdownMenuTrigger asChild>
            <button type="button" className="ligne-actions" aria-label={`Actions pour « ${item.titre} »`}>
              <Ellipsis className="i" aria-hidden="true" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {actions.map((a) => [
              a.separe ? <DropdownMenuSeparator key={`${a.cle}-sep`} /> : null,
              <DropdownMenuItem key={a.cle} destructive={a.destructive} onSelect={a.faire}>{a.libelle}</DropdownMenuItem>,
            ])}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      {hote ? createPortal(
        // cran 85 : la feuille épouse ses 8 rangées (`cran-auto`) — au cran 50, « Supprimer » restait sous le bord
        <FeuilleACrans ouverte={feuilleActions} onFermer={() => setFeuilleActions(false)} titre={item.titre} cranInitial="85" apresFermeture={apresFeuilleActions}>
          <div className="actions-ligne-feuille">
            {actions.map((a) => (
              <button
                key={a.cle}
                type="button"
                className={[a.destructive ? 'action-ligne destructif' : 'action-ligne', a.separe ? 'separee' : ''].join(' ').trim()}
                onClick={() => choisirDansLaFeuille(a.faire)}
              >
                {a.libelle}
              </button>
            ))}
          </div>
        </FeuilleACrans>,
        hote,
      ) : null}
    </div>
  )
}
