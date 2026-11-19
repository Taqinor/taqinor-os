import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { Ligne } from './Sections'
import { LigneOs } from '../ui/ChargementTardif'
import { duree, jourCourt } from '../lib/textes'

/* ============================================================================
   TCH78 — « Proposé pour aujourd'hui » : ce qui presse puis le tour des projets, jusqu'à
   l'objectif (N = objectif − faites − gardées ouvertes, jamais négatif, calculé par le serveur :
   `propose.pour_objectif`). Chaque ligne DIT sa raison (« échéance jeudi », « prévue hier »,
   « prochaine action de Équipe ») ; la puce « Garder » à droite de la méta la garde seule ;
   « Garder ces N » (contour) les garde toutes (`journee/planifier/`, mode express) ; ★ jamais ici.
   Sous l'en-tête : « En tête : {raison de la 1re ligne}. » ; en surcharge, « {h} pour {disponible}
   de libre » à côté de Garder. R2-020 : rien à proposer (objectif couvert, ou sans objectif) → une
   seule ligne « Voir les tâches de mes projets » ; bilan fait → plus de Proposé.
   « Voir toutes les tâches de mes projets » déplie, groupé par projet (`?tout=1`) ; après
   « Alléger », l'en-tête est replié jusqu'au lendemain (`replie`).
   Maquettes : ecran-aujourdhui-matin.html, ecran-aujourdhui-retour.html, ecran-aujourdhui-15h.html.
   ========================================================================== */

/** « prévue lun. 23 » : une tâche du tour des projets déjà prévue plus tard le dit à la place de sa raison. */
function avecRaisonDatee(item, aujourdhui) {
  if (item.jour_prevu && item.jour_prevu > aujourdhui) {
    return { ...item, raison: { code: 'plus_tard', texte: `prévue ${jourCourt(item.jour_prevu, aujourdhui)}` } }
  }
  return item
}

/** « priorité haute » quand la tête de liste est la prochaine action d'un projet de priorité haute. */
function enTete(premiere) {
  if (!premiere?.raison?.texte) return ''
  if (premiere.raison.code === 'prochaine_action' && premiere.projet?.priorite === 3) return 'priorité haute'
  return premiere.raison.texte
}

/**
 * R2-020 — le chiffre est celui des lignes qui se DÉPLIENT : connu seulement quand la suite est lue (`?tout=1` ; sans
 * elle, `reste_nb` ne compte que les tâches sans jour alors que la suite montre aussi celles prévues plus tard — 16
 * lignes pour « (7) »). Inconnu, pas de chiffre.
 */
function VoirTout({ ouvert, libelle = 'Voir toutes les tâches de mes projets', lignes = null, onBasculer }) {
  return (
    <button type="button" className="lien-plus" aria-expanded={ouvert} onClick={onBasculer}>
      {ouvert ? 'Masquer' : `${libelle}${lignes ? ` (${lignes})` : ''}`}
      {ouvert ? <ChevronUp className="i i-16" aria-hidden="true" /> : <ChevronDown className="i i-16" aria-hidden="true" />}
    </button>
  )
}

/** Les lignes de la suite, une fois lues ; pendant la lecture de « Voir tout », un squelette (jamais un vide). */
function SuiteParProjet({ groupes, contexte, geste, aujourdhui }) {
  if (!Array.isArray(groupes)) {
    return (
      <div className="suite-projets" role="status" aria-label="Chargement">
        <LigneOs l1="64%" l2="40%" /><LigneOs l1="72%" /><LigneOs l1="58%" l2="36%" />
      </div>
    )
  }
  return (
    <div className="suite-projets">
      {groupes.map((groupe) => (
        <div key={groupe.projet?.id ?? 'sans'} role="group" aria-label={groupe.projet?.nom ?? 'Sans projet'}>
          <p className="section-sous groupe-projet">
            {groupe.projet ? (
              <span data-p={groupe.projet.couleur}><i className="point" /><span className="projet-nom">{groupe.projet.nom}</span></span>
            ) : 'Sans projet'}
          </p>
          <div className="liste" role="list">
            {groupe.items.map((item) => (
              <Ligne key={`${item.type}:${item.id}`} item={avecRaisonDatee(item, aujourdhui)} contexte={contexte} geste={geste}
                extra={{ propose: true, onGarder: (it) => geste.garder([it]) }} />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

export default function Propose({ donnees, contexte, geste, enLigne, tout, carteGarder = false }) {
  const [ouvertReplie, setOuvertReplie] = useState(false)
  const propose = donnees.propose
  // R2-020 — journée close par le bilan : plus rien à proposer ni à garder pour aujourd'hui
  if (!propose || donnees.plan?.cloture_le) return null
  const lignes = propose.pour_objectif ?? []
  const suite = propose.suite_par_projet // nul tant que « Voir tout » n'a pas été lu
  const nbSuite = Array.isArray(suite) ? suite.reduce((total, groupe) => total + (groupe.items?.length ?? 0), 0) : null
  const reste = propose.reste_nb ?? 0
  const charge = propose.charge
  const n = lignes.length

  if (propose.replie) {
    return (
      <section className="section" aria-label="Proposé pour aujourd'hui">
        <button type="button" className="replie" aria-expanded={ouvertReplie} onClick={() => setOuvertReplie((v) => !v)}>
          <span>Proposé pour aujourd&apos;hui</span>
          <span className="indice">· revient demain</span>
          <ChevronDown className="i i-16" aria-hidden="true" />
        </button>
        {ouvertReplie ? <VoirTout ouvert={tout} lignes={nbSuite} onBasculer={() => geste.voirTout(!tout)} /> : null}
        {ouvertReplie && tout ? <SuiteParProjet groupes={suite} contexte={contexte} geste={geste} aujourdhui={donnees.jour} /> : null}
      </section>
    )
  }
  if (n === 0 && reste === 0 && !nbSuite) return null
  // R2-020 — rien à proposer pour l'objectif (couvert, ou sans objectif) : pas de titre ni de phrase, UNE ligne qui
  // déplie les tâches des projets
  if (n === 0) {
    return (
      <section className="section propose-replie" aria-label="Proposé pour aujourd'hui">
        <VoirTout ouvert={tout} libelle="Voir les tâches de mes projets" lignes={nbSuite} onBasculer={() => geste.voirTout(!tout)} />
        {tout ? <SuiteParProjet groupes={suite} contexte={contexte} geste={geste} aujourdhui={donnees.jour} /> : null}
      </section>
    )
  }

  const sous = `En tête : ${enTete(lignes[0])}.`
  return (
    <section className="section" aria-label="Proposé pour aujourd'hui">
      <h2 className="section-titre"><span>Proposé pour aujourd&apos;hui</span></h2>
      <p className="section-sous">{sous}</p>
      <div className="liste" role="list">
        {lignes.map((item) => (
          <Ligne key={`${item.type}:${item.id}`} item={item} contexte={contexte} geste={geste}
            extra={{ propose: true, onGarder: (it) => geste.garder([it]) }} />
        ))}
      </div>
      <div className="propose-actions">
        {!carteGarder ? (
          <button
            type="button"
            className="bouton second"
            data-necessite-reseau="" aria-disabled={!enLigne || undefined}
            onClick={() => geste.garder(lignes)}
          >
            {n >= 2 ? `Garder ces ${n}` : 'Garder celle-ci'}
          </button>
        ) : null}
        {charge?.surcharge ? (
          <span className="charge-surcharge chiffres">
            {`${duree(charge.minutes_estimees)} pour ${duree(charge.disponible_minutes)} de libre`}
          </span>
        ) : null}
        <button
          type="button"
          className="bouton lien"
          data-necessite-reseau="" aria-disabled={!enLigne || undefined}
          onClick={() => geste.copilote('Planifie ma journée')}
        >
          Planifier avec le Copilote
        </button>
      </div>
      <VoirTout ouvert={tout} lignes={nbSuite} onBasculer={() => geste.voirTout(!tout)} />
      {tout ? <SuiteParProjet groupes={suite} contexte={contexte} geste={geste} aujourdhui={donnees.jour} /> : null}
    </section>
  )
}
