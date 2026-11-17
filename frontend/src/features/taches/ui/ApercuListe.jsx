import { Check } from 'lucide-react'

import { accord } from '../lib/textes'
import { PrioriteProjet, phraseAlerte } from './ChampSaisie'

/* ============================================================================
   TCH83 — « Aperçu de ta liste » : ce que le serveur a lu d'un collage (`saisie-rapide/` aperçu,
   `saisie_apercu.json`), AVANT toute création. Une liste = un projet commun (première ligne), une
   puce de priorité Haute · Moyenne · Basse (Moyenne par défaut) pour un projet qui n'existe pas ;
   par ligne : une case, le titre modifiable, les puces lues, et ce qui la décoche d'office
   (« Déjà faite », « En double dans cette liste »). Les points en retrait sont les points de la
   check-list de leur tâche (« En faire des sous-tâches » les rend à part entière).
   Composant d'AFFICHAGE : l'état (cases, titres) et la création vivent dans `ColleListes`.
   Maquettes : ecran-saisie-liste.html, premier-usage-1-apercu.html.
   ========================================================================== */

export const TITRE_APERCU = 'Aperçu de ta liste'

function CocheCarree({ coche, titre, onBasculer }) {
  return (
    <button
      type="button"
      className="coche-carree"
      role="checkbox"
      aria-checked={coche}
      aria-label={`${coche ? 'Garder' : 'Créer'} : ${titre}`}
      onClick={onBasculer}
    >
      <span>{coche ? <Check aria-hidden="true" /> : null}</span>
    </button>
  )
}

/** Ce qui explique qu'une ligne soit décochée d'office (textes.md §2.3). */
function noteDeLigne(ligne) {
  if (ligne.deja_faite) return 'Déjà faite'
  if (ligne.doublon_de != null) {
    // Raccord F2 — `doublon_projet` servi : « Déjà dans « {projet} » » ; sinon le repli sans nom
    const projet = typeof ligne.doublon_projet === 'string' ? ligne.doublon_projet : ligne.doublon_projet?.nom
    return projet ? `Déjà dans « ${projet} »` : 'Déjà dans tes tâches'
  }
  if (ligne.doublon_de_ligne != null) return 'En double dans cette liste'
  return ''
}

function LigneApercu({ ligne, coche, titre, onCocher, onTitre }) {
  const note = noteDeLigne(ligne)
  const alertes = (ligne.alertes ?? []).map(phraseAlerte).filter(Boolean)
  const jetons = (ligne.jetons ?? []).filter((j) => j.type !== 'projet' || !j.valeur?.nouveau)
  return (
    <div className={`apercu-ligne${coche ? '' : ' decochee'}`}>
      <CocheCarree coche={coche} titre={titre} onBasculer={onCocher} />
      <div>
        <input
          type="text"
          className="titre-ligne"
          aria-label={`Titre : ${ligne.titre}`}
          value={titre}
          onChange={(e) => onTitre(e.target.value)}
        />
        {note ? <p className="apercu-note">{note}</p> : null}
        {alertes.map((phrase) => <p key={phrase} className="apercu-note">{phrase}</p>)}
        {jetons.length > 0 ? (
          <div className="puces">
            {jetons.map((j) => <span key={`${j.type}:${j.debut}`} className="puce lue chiffres">{j.libelle}</span>)}
          </div>
        ) : null}
      </div>
    </div>
  )
}

function PointsDeListe({ points, sousTaches, titre, onSousTaches }) {
  return (
    <>
      <div className="apercu-ligne retrait">
        <span />
        <div>
          <ul className="apercu-note" aria-label={`Points de « ${titre} »`}>
            {points.map((p) => <li key={p.index}>{p.titre}</li>)}
          </ul>
          <button type="button" className="bouton discret" aria-pressed={sousTaches} onClick={onSousTaches}>
            En faire des sous-tâches
          </button>
        </div>
      </div>
    </>
  )
}

function EnteteProjet({ commun, nbTaches, priorite, enTache, onPriorite, onEnTache }) {
  const nouveau = Boolean(commun.nouveau)
  return (
    <div className="apercu-projet">
      <span className="nom">
        {nouveau ? `Nouveau projet : ${commun.nom}` : `Projet : ${commun.nom}`}
        <small>{accord(nbTaches, 'tâche')}</small>
      </span>
      {nouveau && !enTache ? <PrioriteProjet nom={commun.nom} valeur={priorite} onChoisir={onPriorite} /> : null}
      <button
        type="button"
        className="bouton discret"
        aria-label={`En faire une tâche : ${commun.nom}`}
        aria-pressed={enTache}
        onClick={onEnTache}
      >
        En faire une tâche
      </button>
    </div>
  )
}

export default function ApercuListe({
  apercu, modifs, priorites = {}, onCocher, onTitre, onEnTache, onSousTaches, onPriorite, nbCreer, nbProjets,
}) {
  const lignes = apercu?.lignes ?? []
  const communs = apercu?.projets_communs ?? []
  if (lignes.length === 0 && communs.length === 0) {
    return <p className="vide-phrase">Aucune ligne lisible.</p>
  }
  const collages = [...new Set([...lignes.map((l) => l.collage), ...communs.map((c) => c.collage)])].sort((a, b) => a - b)
  return (
    <div className="apercu-liste" aria-label={TITRE_APERCU}>
      <div className="apercu-entete">
        <span className="feuille-titre">{TITRE_APERCU}</span>
        <span className="raccourci chiffres">{`${accord(nbCreer, 'tâche')} · ${accord(nbProjets, 'projet')}`}</span>
      </div>
      {collages.map((c) => {
        const commun = communs.find((p) => p.collage === c)
        const deCollage = lignes.filter((l) => l.collage === c)
        const taches = deCollage.filter((l) => l.etape_de == null)
        const enTache = Boolean(modifs.enTache[c])
        return (
          <div key={c} className="apercu-groupe" role="group" aria-label={commun ? commun.nom : `Liste ${c + 1}`}>
            {commun ? (
              <EnteteProjet
                commun={commun}
                nbTaches={taches.length}
                priorite={priorites[commun.nom] ?? commun.priorite ?? 2}
                enTache={enTache}
                onPriorite={onPriorite}
                onEnTache={() => onEnTache(c)}
              />
            ) : null}
            {commun && enTache ? (
              <LigneApercu
                ligne={{ titre: commun.nom, jetons: [], alertes: [] }}
                coche={modifs.cochees[`p${c}`] !== false}
                titre={modifs.titres[`p${c}`] ?? commun.nom}
                onCocher={() => onCocher(`p${c}`, modifs.cochees[`p${c}`] === false)}
                onTitre={(valeur) => onTitre(`p${c}`, valeur)}
              />
            ) : null}
            {taches.map((ligne) => {
              const points = deCollage.filter((l) => l.etape_de === ligne.index)
              const sousTaches = Boolean(modifs.sousTaches[ligne.index])
              return (
                <div key={ligne.index}>
                  <LigneApercu
                    ligne={ligne}
                    coche={modifs.cochees[ligne.index] ?? ligne.cochee !== false}
                    titre={modifs.titres[ligne.index] ?? ligne.titre}
                    onCocher={() => onCocher(ligne.index, !(modifs.cochees[ligne.index] ?? ligne.cochee !== false))}
                    onTitre={(valeur) => onTitre(ligne.index, valeur)}
                  />
                  {points.length > 0 && !sousTaches ? (
                    <PointsDeListe
                      points={points}
                      sousTaches={sousTaches}
                      titre={modifs.titres[ligne.index] ?? ligne.titre}
                      onSousTaches={() => onSousTaches(ligne.index)}
                    />
                  ) : null}
                  {points.length > 0 && sousTaches ? (
                    <>
                      {points.map((p) => (
                        <LigneApercu
                          key={p.index}
                          ligne={p}
                          coche={modifs.cochees[p.index] ?? p.cochee !== false}
                          titre={modifs.titres[p.index] ?? p.titre}
                          onCocher={() => onCocher(p.index, !(modifs.cochees[p.index] ?? p.cochee !== false))}
                          onTitre={(valeur) => onTitre(p.index, valeur)}
                        />
                      ))}
                      <button type="button" className="bouton discret" aria-pressed onClick={() => onSousTaches(ligne.index)}>
                        En faire des sous-tâches
                      </button>
                    </>
                  ) : null}
                </div>
              )
            })}
          </div>
        )
      })}
    </div>
  )
}
