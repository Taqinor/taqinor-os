import { useState } from 'react'
import { Hand, Lightbulb } from 'lucide-react'
import { duree, heureDite } from '../lib/textes'
import { lireTexte, ecrireTexte, viderALaDeconnexion } from '../lib/stockage'

/* ============================================================================
   TCH77 — LA carte du moment : UNE seule, en haut d'Aujourd'hui, sous la progression.
   Ordre (regles.md §4.10, spec-7 §4) : `retour` > brouillon (« Reprendre », posé par le
   navigateur, clé de TCH82) > le serveur (`bilan_hier`, `garder`, `alleger`, `faire_bilan`,
   `rythme`, `pause`) > astuce de geste (navigateur, une par jour, une fois chacune) >
   révélation (`mon_iphone`… « OK »). Le serveur choisit, l'écran ne recalcule rien.
   Les cartes à réponse (`retour`, `rythme`, `pause`, `revelation`) rendent le TEXTE et les
   BOUTONS de la PROPOSITION telle quelle et répondent par `onRepondre(proposition, reponse)`
   (→ `rythme/propositions/{id}/repondre/`). Carte écartée (« Passer », « Pas maintenant ») :
   rien n'est écrit au serveur ; R4-03 — elle ne revient pas ce jour-là, rechargement et réouverture de l'appli compris
   (retenue sur l'appareil, par compte et par jour : `lib/stockage`, vidée à la déconnexion).
   R4-05 — « Alléger » lit le compte VIVANT de la page (`faites`, la progression que suit chaque geste) et la charge
   servie (`charge.deborde_minutes`) : jamais un chiffre figé qui contredit l'en-tête.
   R4-06 — un seul dessin : chaque carte est une rangée compacte (`.carte.compacte`, comme le conseil), la phrase puis
   ses réponses en texte d'accent.
   Maquettes : ecran-aujourdhui-matin.html, ecran-aujourdhui-retour.html, ecran-aujourdhui-15h.html,
   etat-astuce.html. Textes : reference/textes.md §2.17, §2.18, §4.2.
   ========================================================================== */

/* R2-015 — une astuce n'est montrée que sur l'appareil où elle sert : le balayage et l'appui long n'existent qu'au doigt
   (`pointer: coarse`), les touches et le glisser vers l'agenda qu'à la souris et au clavier. Sans `matchMedia`
   (test, vieux navigateur), l'appareil est un bureau. */
const ASTUCES = [
  { cle: 'balayage', appareil: 'doigt', texte: 'Balaie une ligne vers la gauche pour la reporter, vers la droite pour la cocher.', demo: true },
  { cle: 'appui_long', appareil: 'doigt', texte: 'Garde le doigt sur une ligne pour voir toutes ses actions.' },
  { cle: 'touches', appareil: 'bureau', texte: 'Touche n pour ajouter, ? pour voir les touches.' },
  { cle: 'glisser_agenda', appareil: 'bureau', texte: "Glisse une tâche sur l'agenda pour lui donner une heure." },
  { cle: 'diese', texte: 'Tape #nom pour ranger dans un projet.' },
]

const auDoigt = () => (typeof window !== 'undefined' && typeof window.matchMedia === 'function'
  ? window.matchMedia('(pointer: coarse)').matches
  : false)

/** Pour chaque révélation : le bouton qui mène quelque part (en plus d'OK) et sa destination. */
const REVELATIONS = {
  mon_iphone: { libelle: 'Mon iPhone', vers: '/taches/reglages/iphone' },
  ranger_copilote: { libelle: 'Ranger avec le Copilote', copilote: 'Range ma liste' },
  planifier_projet: { libelle: 'Planifier le projet', vers: '/taches/projets' },
  revue: { libelle: 'Ouvrir la revue', vers: '/taches/revue' },
}

const CLE_STOCKAGE = 'taches:astuces'
/** R4-03 — les cartes écartées du jour, sur l'appareil : `{ jour, types }` sous une clé PAR COMPTE (un poste partagé ne
 *  prête jamais ses réponses à un autre compte), une seule journée gardée (la suivante remplace), vidée à la déconnexion. */
const PREFIXE_ECARTEES = 'taches:cartes-ecartees:'
const cleEcartees = (compte) => `${PREFIXE_ECARTEES}${compte ?? 'anonyme'}`

function lireEcartees(compte, jour) {
  try {
    const brut = JSON.parse(lireTexte(cleEcartees(compte)) || 'null')
    return new Set(brut?.jour === jour && Array.isArray(brut.types) ? brut.types : [])
  } catch {
    return new Set() // illisible : traité comme rien d'écarté (la carte revient, rien ne casse)
  }
}

function ecarterCarte(compte, jour, type) {
  viderALaDeconnexion(PREFIXE_ECARTEES)
  const types = [...lireEcartees(compte, jour), type]
  return ecrireTexte(cleEcartees(compte), JSON.stringify({ jour, types: [...new Set(types)] }))
}

function lireAstuces() {
  try {
    const brut = JSON.parse(window.localStorage.getItem(CLE_STOCKAGE) ?? 'null')
    return { vues: Array.isArray(brut?.vues) ? brut.vues : [], jour: typeof brut?.jour === 'string' ? brut.jour : '' }
  } catch {
    return { vues: [], jour: '' }
  }
}

/** `cle` : l'astuce vue (une seule fois chacune) ; `null` : seulement « ce jour est pris » (R2-014). */
function noterAstuce(cle, jour) {
  const { vues } = lireAstuces()
  try {
    window.localStorage.setItem(CLE_STOCKAGE, JSON.stringify({ vues: cle ? [...new Set([...vues, cle])] : vues, jour }))
    return true
  } catch {
    return false // stockage indisponible (navigation privée) : l'astuce ne sera pas retenue, rien d'autre
  }
}

/** La prochaine astuce à montrer aujourd'hui (une par jour, chacune une seule fois, propre à l'appareil), ou `null`. */
function prochaineAstuce(jour) {
  const { vues, jour: dernier } = lireAstuces()
  if (dernier === jour) return null
  const surDoigt = auDoigt()
  return ASTUCES.find((a) => !vues.includes(a.cle) && (!a.appareil || (a.appareil === 'doigt') === surDoigt)) ?? null
}

function Boutons({ boutons, onRepondre, desactive }) {
  return (
    <div className="carte-actions">
      {boutons.map((b, rang) => (
        <button
          key={b.reponse}
          type="button"
          className={rang === 0 ? 'bouton second' : 'bouton discret'}
          aria-disabled={desactive || undefined}
          onClick={() => onRepondre(b.reponse)}
        >
          {b.libelle}
        </button>
      ))}
    </div>
  )
}

function CarteRetour({ proposition, onRepondre, desactive }) {
  return (
    <div className="carte retour" role="region" aria-label="Retour">
      <p className="carte-texte">{proposition.texte}</p>
      <div className="carte-actions pile">
        {proposition.boutons.map((b, rang) => (
          <button
            key={b.reponse}
            type="button"
            className={rang === 0 ? 'bouton second' : 'bouton discret'}
            aria-disabled={desactive || undefined}
            onClick={() => onRepondre(b.reponse)}
          >
            {b.libelle}
          </button>
        ))}
      </div>
    </div>
  )
}

function CarteGarder({ donnees, onGarder, desactive }) {
  const n = Number(donnees.n) || 0
  return (
    <div className="moment" role="region" aria-label="Proposé pour aujourd'hui">
      <div className="moment-texte">
        <b>{n >= 2 ? `${n} tâches proposées` : '1 tâche proposée'}</b>
        <span>{`pour atteindre ${donnees.objectif}`}</span>
      </div>
      <button type="button" className="bouton second" aria-disabled={desactive || undefined} onClick={onGarder}>
        {n >= 2 ? `Garder ces ${n}` : 'Garder celle-ci'}
      </button>
    </div>
  )
}

/** R4-06 — LE dessin d'une carte liée à l'heure (Alléger, Bilan d'hier, Faire le bilan ; « Reprendre » d'Aujourd'hui
 *  le reprend) : la rangée compacte de la carte de conseil. */
function CarteSimple({ etiquette, texte, actions }) {
  return (
    <div className="carte compacte" role="region" aria-label={etiquette}>
      <p className="carte-texte">{texte}</p>
      <div className="carte-actions">
        {actions.map(({ libelle, onClick, principal, desactive }) => (
          <button
            key={libelle}
            type="button"
            className={principal ? 'bouton second' : 'bouton discret'}
            aria-disabled={desactive || undefined}
            onClick={onClick}
          >
            {libelle}
          </button>
        ))}
      </div>
    </div>
  )
}

function CarteRevelation({ proposition, onRepondre, onNaviguer, onCopilote, desactive }) {
  const destination = REVELATIONS[proposition.cle]
  const aller = () => {
    onRepondre('ok')
    if (destination?.vers) onNaviguer(destination.vers)
    else if (destination?.copilote) onCopilote(destination.copilote)
  }
  return (
    <div className="moment revelation" role="region" aria-label="Astuce">
      <span className="bandeau-icone"><Lightbulb className="i i-16" aria-hidden="true" /></span>
      <div className="moment-texte">
        <b>{proposition.texte}</b>
        <div className="carte-actions">
          {destination ? (
            <button type="button" className="bouton second" aria-disabled={desactive || undefined} onClick={aller}>
              {destination.libelle}
            </button>
          ) : null}
          <button type="button" className="bouton second" aria-disabled={desactive || undefined} onClick={() => onRepondre('ok')}>OK</button>
        </div>
      </div>
    </div>
  )
}

function CarteAstuce({ astuce, onOk }) {
  return (
    <div className="moment revelation" role="region" aria-label="Astuce">
      <span className="bandeau-icone"><Hand className="i i-16" aria-hidden="true" /></span>
      <div className="moment-texte">
        <b>{astuce.texte}</b>
        {astuce.demo ? (
          <div className="demo-balayage" aria-hidden="true"><span><i />Imprimer les kakémonos</span><b>Reporter</b></div>
        ) : null}
        <div className="carte-actions">
          <button type="button" className="bouton second" onClick={onOk}>OK</button>
        </div>
      </div>
    </div>
  )
}

/** R4-05 — « 1 faite sur 5 à 15 h » sur le compte VIVANT de la page ; la charge du jour quand elle déborde (« · 2 h de
 *  trop ») ; sans objectif chiffré, jamais « 0 sur 5 » (le serveur ne sert alors pas la carte, R4-04). */
function texteAlleger({ faites, objectif, maintenant, charge }) {
  const fait = `${faites} ${faites >= 2 ? 'faites' : 'faite'}`
  const compte = objectif ? `${fait} sur ${objectif}` : fait
  const trop = charge?.deborde_minutes > 0 ? ` · ${duree(charge.deborde_minutes)} de trop` : ''
  return `${compte} à ${heureDite(String(maintenant).slice(11, 16))}${trop}`
}

export default function CarteDuMoment({
  carte = null,
  jour = '',
  maintenant = '',
  objectif = 0,
  faites = null,
  charge = null,
  compte = null,
  conseilDonne = false,
  enLigne = true,
  avecAstuce = true,
  bilanFait = false,
  brouillon = null,
  onRepondre,
  onGarder,
  onAlleger,
  onBilan,
  onNaviguer,
  onCopilote,
}) {
  const [, relire] = useState(0)
  // repli quand l'appareil refuse de garder quoi que ce soit (navigation privée stricte) : écartée pour cet écran
  const [ecarteesIci, setEcarteesIci] = useState(() => new Set())
  const desactive = !enLigne
  // R2-014 — UNE carte au plus par matin : dès qu'une carte est répondue, écartée ou agie, la journée est « prise » et
  // aucune astuce ne vient prendre sa place (ni maintenant, ni au rechargement : `taches:astuces`)
  const prise = (rappel) => (...args) => { noterAstuce(null, jour); return rappel?.(...args) }
  // R4-03 — « Pas maintenant » / « Passer » TIENNENT la journée : gardés sur l'appareil, par compte et par jour
  const ecartees = lireEcartees(compte, jour)
  const ecartee = (cle) => ecartees.has(cle) || ecarteesIci.has(`${cle}:${jour}`)
  const ecarter = (cle) => {
    ecarterCarte(compte, jour, cle)
    setEcarteesIci((s) => new Set(s).add(`${cle}:${jour}`))
    noterAstuce(null, jour)
    relire((v) => v + 1)
  }
  const repondre = (proposition) => prise((reponse) => onRepondre(proposition, reponse))
  const type = carte?.type
  const constatApresBilan = bilanFait && carte?.proposition?.type === 'constat' // la carte « 57 % » ne remonte pas après le bilan

  if (type === 'retour' && carte.proposition) {
    return <CarteRetour proposition={carte.proposition} onRepondre={repondre(carte.proposition)} desactive={desactive} />
  }
  if (brouillon) return brouillon
  if (constatApresBilan) return null
  if (type === 'bilan_hier' && !ecartee('bilan_hier')) {
    return (
      <CarteSimple
        etiquette="Bilan d'hier"
        texte="Le bilan d'hier n'est pas fait : il reste possible jusqu'à midi."
        actions={[
          { libelle: "Faire le bilan d'hier", principal: true, onClick: prise(() => onBilan(carte.donnees?.jour)), desactive },
          { libelle: 'Passer', onClick: () => ecarter('bilan_hier') },
        ]}
      />
    )
  }
  if (type === 'garder') return <CarteGarder donnees={carte.donnees ?? {}} onGarder={prise(onGarder)} desactive={desactive} />
  // R4-04 — après « Bilan enregistré », plus jamais « Alléger » (même si une lecture d'avant le servait encore)
  if (type === 'alleger' && !ecartee('alleger') && !bilanFait) {
    const servies = Number(carte.donnees?.faites) || 0
    return (
      <CarteSimple
        etiquette="Alléger ma journée"
        texte={texteAlleger({ faites: Number.isFinite(faites) ? faites : servies, objectif, maintenant, charge })}
        actions={[
          { libelle: 'Alléger ma journée', principal: true, onClick: prise(onAlleger), desactive },
          { libelle: 'Pas maintenant', onClick: () => ecarter('alleger') },
        ]}
      />
    )
  }
  if (type === 'faire_bilan' && !bilanFait) {
    return (
      <CarteSimple
        etiquette="Bilan du soir"
        texte="Ta journée se termine."
        actions={[{ libelle: 'Faire le bilan', principal: true, onClick: prise(() => onBilan(null)), desactive }]}
      />
    )
  }
  if ((type === 'rythme' || type === 'pause') && carte.proposition) {
    return (
      <div className="carte rythme" role="region" aria-label="Mon rythme">
        <p className="carte-texte">{carte.proposition.texte}</p>
        <Boutons boutons={carte.proposition.boutons} onRepondre={repondre(carte.proposition)} desactive={desactive} />
      </div>
    )
  }
  // R3-022 (C-17) — au plus UNE carte de conseil par jour : une fois la journée « prise » (une carte répondue, écartée
  // ou suivie — astuce comprise), ni astuce ni révélation ne viennent prendre sa place, ni au rechargement ; R4-10 —
  // ni sur un AUTRE appareil : le serveur dit qu'un conseil a déjà été répondu aujourd'hui (`conseil_donne`)
  if (lireAstuces().jour === jour || conseilDonne) return null
  const astuce = avecAstuce ? prochaineAstuce(jour) : null
  if (astuce) {
    return <CarteAstuce astuce={astuce} onOk={() => { noterAstuce(astuce.cle, jour); relire((v) => v + 1) }} />
  }
  if (type === 'revelation' && carte.proposition) {
    return (
      <CarteRevelation
        proposition={carte.proposition}
        onRepondre={repondre(carte.proposition)}
        onNaviguer={onNaviguer}
        onCopilote={onCopilote}
        desactive={desactive}
      />
    )
  }
  return null
}
