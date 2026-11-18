import { useState } from 'react'
import { Hand, Lightbulb } from 'lucide-react'
import { heureDite } from '../lib/textes'

/* ============================================================================
   TCH77 — LA carte du moment : UNE seule, en haut d'Aujourd'hui, sous la progression.
   Ordre (regles.md §4.10, spec-7 §4) : `retour` > brouillon (« Reprendre », posé par le
   navigateur, clé de TCH82) > le serveur (`bilan_hier`, `garder`, `alleger`, `faire_bilan`,
   `rythme`, `pause`) > astuce de geste (navigateur, une par jour, une fois chacune) >
   révélation (`mon_iphone`… « OK »). Le serveur choisit, l'écran ne recalcule rien.
   Les cartes à réponse (`retour`, `rythme`, `pause`, `revelation`) rendent le TEXTE et les
   BOUTONS de la PROPOSITION telle quelle et répondent par `onRepondre(proposition, reponse)`
   (→ `rythme/propositions/{id}/repondre/`). Carte écartée (« Passer », « Pas maintenant ») :
   rien n'est écrit, elle ne revient pas ce jour-là.
   Maquettes : ecran-aujourdhui-matin.html, ecran-aujourdhui-retour.html, ecran-aujourdhui-15h.html,
   etat-astuce.html. Textes : reference/textes.md §2.17, §2.18, §4.2.
   ========================================================================== */

const ASTUCES = [
  { cle: 'balayage', texte: 'Balaie une ligne vers la gauche pour la reporter, vers la droite pour la cocher.', demo: true },
  { cle: 'touches', texte: 'Touche n pour ajouter, ? pour voir les touches.' },
  { cle: 'diese', texte: 'Tape #nom pour ranger dans un projet.' },
]

/** Pour chaque révélation : le bouton qui mène quelque part (en plus d'OK) et sa destination. */
const REVELATIONS = {
  mon_iphone: { libelle: 'Mon iPhone', vers: '/taches/reglages/iphone' },
  ranger_copilote: { libelle: 'Ranger avec le Copilote', copilote: 'Range ma liste' },
  planifier_projet: { libelle: 'Planifier le projet', vers: '/taches/projets' },
  revue: { libelle: 'Ouvrir la revue', vers: '/taches/revue' },
}

const CLE_STOCKAGE = 'taches:astuces'
const ecartees = new Set()

function lireAstuces() {
  try {
    const brut = JSON.parse(window.localStorage.getItem(CLE_STOCKAGE) ?? 'null')
    return { vues: Array.isArray(brut?.vues) ? brut.vues : [], jour: typeof brut?.jour === 'string' ? brut.jour : '' }
  } catch {
    return { vues: [], jour: '' }
  }
}

function noterAstuce(cle, jour) {
  const { vues } = lireAstuces()
  try {
    window.localStorage.setItem(CLE_STOCKAGE, JSON.stringify({ vues: [...new Set([...vues, cle])], jour }))
    return true
  } catch {
    return false // stockage indisponible (navigation privée) : l'astuce ne sera pas retenue, rien d'autre
  }
}

/** La prochaine astuce à montrer aujourd'hui (une par jour, chacune une seule fois), ou `null`. */
function prochaineAstuce(jour) {
  const { vues, jour: dernier } = lireAstuces()
  if (dernier === jour) return null
  return ASTUCES.find((a) => !vues.includes(a.cle)) ?? null
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

function CarteSimple({ etiquette, texte, actions }) {
  return (
    <div className="carte" role="region" aria-label={etiquette}>
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

export default function CarteDuMoment({
  carte = null,
  jour = '',
  maintenant = '',
  objectif = 0,
  enLigne = true,
  avecAstuce = true,
  brouillon = null,
  onRepondre,
  onGarder,
  onAlleger,
  onBilan,
  onNaviguer,
  onCopilote,
}) {
  const [, relire] = useState(0)
  const desactive = !enLigne
  const ecarter = (cle) => { ecartees.add(`${cle}:${jour}`); relire((v) => v + 1) }
  const repondre = (proposition) => (reponse) => onRepondre(proposition, reponse)
  const type = carte?.type

  if (type === 'retour' && carte.proposition) {
    return <CarteRetour proposition={carte.proposition} onRepondre={repondre(carte.proposition)} desactive={desactive} />
  }
  if (brouillon) return brouillon
  if (type === 'bilan_hier' && !ecartees.has(`bilan_hier:${jour}`)) {
    return (
      <CarteSimple
        etiquette="Bilan d'hier"
        texte="Le bilan d'hier n'est pas fait : il reste possible jusqu'à midi."
        actions={[
          { libelle: "Faire le bilan d'hier", principal: true, onClick: () => onBilan(carte.donnees?.jour), desactive },
          { libelle: 'Passer', onClick: () => ecarter('bilan_hier') },
        ]}
      />
    )
  }
  if (type === 'garder') return <CarteGarder donnees={carte.donnees ?? {}} onGarder={onGarder} desactive={desactive} />
  if (type === 'alleger' && !ecartees.has(`alleger:${jour}`)) {
    const { faites = 0 } = carte.donnees ?? {}
    return (
      <CarteSimple
        etiquette="Alléger ma journée"
        texte={`${faites} sur ${objectif} à ${heureDite(String(maintenant).slice(11, 16))}`}
        actions={[
          { libelle: 'Alléger ma journée', principal: true, onClick: onAlleger, desactive },
          { libelle: 'Pas maintenant', onClick: () => ecarter('alleger') },
        ]}
      />
    )
  }
  if (type === 'faire_bilan') {
    return (
      <CarteSimple
        etiquette="Bilan du soir"
        texte="Ta journée se termine."
        actions={[{ libelle: 'Faire le bilan', principal: true, onClick: () => onBilan(null), desactive }]}
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
