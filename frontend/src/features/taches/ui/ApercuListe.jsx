import { useState } from 'react'
import { Check, ChevronDown, X } from 'lucide-react'

import {
  DropdownMenu, DropdownMenuContent, DropdownMenuRadioGroup, DropdownMenuRadioItem, DropdownMenuTrigger,
} from '../../../ui/DropdownMenu'
import { accord } from '../lib/textes'
import { PRIORITES_PROJET, phraseAlerte } from './ChampSaisie'
import SelecteurProjet from './SelecteurProjet'

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

/** Ce qui explique qu'une ligne soit décochée d'office (textes.md §2.3). Partagé avec la carte de collage du
 *  Copilote (`cartes/CartesTaches.jsx`, relecture finale F3 n° 1). */
// eslint-disable-next-line react-refresh/only-export-components -- helper pur partagé avec la carte du Copilote
export function noteDeLigne(ligne) {
  if (ligne.deja_faite) return 'Déjà faite'
  if (ligne.doublon_de != null) {
    // Raccord F2 — `doublon_projet` servi : « Déjà dans « {projet} » » ; sinon le repli sans nom
    const projet = typeof ligne.doublon_projet === 'string' ? ligne.doublon_projet : ligne.doublon_projet?.nom
    return projet ? `Déjà dans « ${projet} »` : 'Déjà dans tes tâches'
  }
  if (ligne.doublon_de_ligne != null) return 'En double dans cette liste'
  return ''
}

/** Les puces lues d'une ligne (`jetons[].libelle` servis par le serveur), comme l'aperçu les montre. R2-005 — avec
 *  `onRetirer`, chaque puce a son « × » (« Retirer {libellé} ») : même effet que dans la saisie d'une phrase. */
export function PucesLues({ jetons, onRetirer }) {
  if (!jetons || jetons.length === 0) return null
  return (
    <div className="puces">
      {jetons.map((j) => (onRetirer ? (
        <span key={`${j.type}:${j.debut}`} className="puce lue" data-jeton={j.type}>
          <span className="chiffres">{j.libelle}</span>
          <button type="button" className="retirer" aria-label={`Retirer ${j.libelle}`} onClick={() => onRetirer(j)}>
            <X aria-hidden="true" />
          </button>
        </span>
      ) : <span key={`${j.type}:${j.debut}`} className="puce lue chiffres">{j.libelle}</span>))}
    </div>
  )
}

const cleNom = (nom) => String(nom ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[\s_-]+/g, '')

/** Le projet qu'une ligne REÇOIT de son titre de groupe (aucun `#projet` à elle) : `{ cle, nom?, id?, nouveau }`. */
function projetHerite(ligne) {
  if ((ligne.jetons ?? []).some((j) => j.type === 'projet')) return null
  const champs = ligne.champs ?? {}
  if (champs.nouveau_projet?.nom) return { cle: `n:${cleNom(champs.nouveau_projet.nom)}`, nom: champs.nouveau_projet.nom, nouveau: true }
  if (champs.projet_id != null) return { cle: `p:${champs.projet_id}`, id: champs.projet_id, nouveau: false }
  return null
}

/**
 * R2-004 — les groupes d'un collage, dans l'ordre : chaque suite de lignes qui reçoivent le MÊME projet de leur titre
 * (« Hôtel Atlas Marrakech » puis ses lignes à tiret) est un groupe, montré sous son en-tête. Le projet commun de la
 * première ligne (`projets_communs`) garde son en-tête à lui (`commun: true`). `projets` donne le nom d'un projet
 * existant ; sans lui, son groupe n'a pas d'en-tête (jamais un nom inventé).
 */
// eslint-disable-next-line react-refresh/only-export-components -- helper pur partagé avec ColleListes (D-ENF22)
export function groupesDuCollage(apercu, collage, projets = []) {
  const commun = (apercu?.projets_communs ?? []).find((p) => p.collage === collage)
  const cleCommun = commun ? (commun.nouveau ? `n:${cleNom(commun.nom)}` : `p:${commun.id}`) : null
  const groupes = []
  ;(apercu?.lignes ?? []).filter((l) => l.collage === collage && l.etape_de == null).forEach((ligne) => {
    const herite = projetHerite(ligne)
    const cle = herite?.cle ?? null
    const dernier = groupes.at(-1)
    // une ligne qui nomme son propre projet (`#Autre`) reste dans le groupe où elle est écrite
    if (dernier && (dernier.cle === cle || cle === null)) { dernier.lignes.push(ligne); return }
    const existant = herite && !herite.nouveau ? projets.find((p) => p.id === herite.id) : null
    groupes.push({
      cle,
      commun: cle !== null && cle === cleCommun,
      cleModif: `g${ligne.index}`,
      projet: herite ? { nom: herite.nouveau ? herite.nom : existant?.nom ?? '', nouveau: herite.nouveau, couleur: existant?.couleur } : null,
      lignes: [ligne],
    })
  })
  return groupes
}

function LigneApercu({ ligne, coche, titre, onCocher, onTitre, onRelire, onRetirer }) {
  const note = noteDeLigne(ligne)
  const alertes = (ligne.alertes ?? []).map(phraseAlerte).filter(Boolean)
  // R2-004 — la puce du projet lu sur la ligne se voit, projet existant OU nouveau
  const jetons = ligne.jetons ?? []
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
          // R2-005 — à la sortie du champ, un titre corrigé est relu (« … mardi » devient la puce « mar. »)
          onBlur={onRelire}
        />
        {note ? <p className="apercu-note">{note}</p> : null}
        {alertes.map((phrase) => <p key={phrase} className="apercu-note">{phrase}</p>)}
        <PucesLues jetons={jetons} onRetirer={onRetirer} />
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

/** La priorité d'un nouveau projet en UNE puce « Moyenne ⌄ » (premier-usage-1-apercu.html, `puce prio`) : un toucher
 *  ouvre Haute · Moyenne · Basse ; l'en-tête du projet tient ainsi sur une ligne, même sur iPhone. */
function PucePriorite({ nom, valeur, onChoisir }) {
  const libelle = PRIORITES_PROJET.find(([, niveau]) => niveau === valeur)?.[0] ?? 'Moyenne'
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button type="button" className="puce prio" aria-label={`Priorité du projet ${nom} : ${libelle.toLowerCase()}`}>
          {libelle}
          <ChevronDown className="i i-16" aria-hidden="true" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuRadioGroup value={String(valeur)} onValueChange={(v) => onChoisir?.(nom, Number(v))}>
          {PRIORITES_PROJET.map(([texte, niveau]) => (
            <DropdownMenuRadioItem key={niveau} value={String(niveau)}>{texte}</DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/**
 * R3-043 — le projet d'un groupe tel qu'il est montré et envoyé : celui que le serveur a lu (`defaut`), ou celui que
 * la personne a choisi dans l'en-tête (`choix` : `{ id }` projet existant, `{ sans: true }`, `{ nom }` nouveau).
 */
// eslint-disable-next-line react-refresh/only-export-components -- helper pur partagé avec ColleListes (D-ENF22)
export function projetDuGroupe(defaut, choix, projets = []) {
  if (!choix) return defaut
  if (choix.sans) return { nom: '', sans: true, nouveau: false }
  if (choix.id != null) {
    const existant = projets.find((p) => p.id === choix.id)
    return { id: choix.id, nom: existant?.nom ?? '', nouveau: false, couleur: existant?.couleur }
  }
  return { nom: choix.nom, nouveau: true }
}

function EnteteProjet({ commun, nbTaches, priorite, enTache, ouvert, onPriorite, onEnTache, onChanger }) {
  const nouveau = Boolean(commun.nouveau)
  const libelle = commun.sans ? 'Sans projet' : nouveau ? `Nouveau projet : ${commun.nom}` : `Projet : ${commun.nom}`
  const nom = commun.sans ? 'Sans projet' : commun.nom
  return (
    <div className="apercu-projet" data-p={commun.couleur || undefined}>
      {/* la couleur d'un projet n'est servie que pour un projet existant : sans elle, pas de point muet */}
      {commun.couleur ? <i className="point" aria-hidden="true" /> : null}
      <span className="nom">
        <span className="nom-projet">{libelle}</span>
        <small>
          {accord(nbTaches, 'tâche')}
          {commun.sans ? null : (
            <>
              {' · '}
              <button
                type="button"
                className="apercu-bascule"
                aria-label={`En faire une tâche : ${commun.nom}`}
                aria-pressed={enTache}
                onClick={onEnTache}
              >
                En faire une tâche
              </button>
            </>
          )}
          {enTache || !onChanger ? null : (
            <>
              {' · '}
              {/* R3-043 — le projet lu se change avant « Créer » : un existant, « Sans projet » ou un nouveau */}
              <button
                type="button"
                className="apercu-bascule"
                aria-label={`Changer le projet : ${nom}`}
                aria-expanded={ouvert}
                onClick={onChanger}
              >
                Changer
              </button>
            </>
          )}
        </small>
      </span>
      {nouveau && !enTache ? <PucePriorite nom={commun.nom} valeur={priorite} onChoisir={onPriorite} /> : null}
    </div>
  )
}

/** Le sélecteur de l'en-tête ouvert (R3-043) : `valeur` = l'id montré, `null` pour « Sans projet » ; un projet nouveau
 *  n'est aucune des options (`-1`, jamais un id). */
function ChoixDuProjet({ projet, projets, onChoisir }) {
  return (
    <SelecteurProjet
      projets={projets}
      valeur={projet.sans ? null : projet.id ?? -1}
      sansProjet
      onChoisir={(id) => onChoisir(id == null ? { sans: true } : { id })}
      onNouveau={(nom) => { if (nom.trim()) onChoisir({ nom: nom.trim() }) }}
    />
  )
}

/** La ligne « titre devenu tâche » (« En faire une tâche ») : `cle` = `p{collage}` (projet commun) ou `g{index}`. */
function LigneTitreEnTache({ cle, nom, modifs, onCocher, onTitre }) {
  return (
    <LigneApercu
      ligne={{ titre: nom, jetons: [], alertes: [] }}
      coche={modifs.cochees[cle] !== false}
      titre={modifs.titres[cle] ?? nom}
      onCocher={() => onCocher(cle, modifs.cochees[cle] === false)}
      onTitre={(valeur) => onTitre(cle, valeur)}
    />
  )
}

export default function ApercuListe({
  apercu, modifs, priorites = {}, projets = [], onCocher, onTitre, onRelire, onRetirer, onEnTache, onSousTaches, onPriorite,
  onProjet, nbCreer, nbProjets,
}) {
  // R3-043 — l'en-tête dont le sélecteur de projet est ouvert (une clé de groupe), un seul à la fois
  const [changeant, setChangeant] = useState(null)
  const changer = (cle) => (onProjet ? () => setChangeant((c) => (c === cle ? null : cle)) : undefined)
  const choisir = (cle) => (choix) => { onProjet?.(cle, choix); setChangeant(null) }
  const lignes = apercu?.lignes ?? []
  const communs = apercu?.projets_communs ?? []
  if (lignes.length === 0 && communs.length === 0) {
    return <p className="vide-phrase">Aucune ligne lisible.</p>
  }
  const collages = [...new Set([...lignes.map((l) => l.collage), ...communs.map((c) => c.collage)])].sort((a, b) => a - b)
  const titreDeLigne = { modifs, onCocher, onTitre }
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
        const rendreTache = (ligne) => {
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
                onRelire={onRelire ? () => onRelire(ligne.index) : undefined}
                onRetirer={onRetirer ? (jeton) => onRetirer(ligne.index, jeton) : undefined}
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
                      onRelire={onRelire ? () => onRelire(p.index) : undefined}
                      onRetirer={onRetirer ? (jeton) => onRetirer(p.index, jeton) : undefined}
                    />
                  ))}
                  <button type="button" className="bouton discret" aria-pressed onClick={() => onSousTaches(ligne.index)}>
                    En faire des sous-tâches
                  </button>
                </>
              ) : null}
            </div>
          )
        }
        if (commun) {
          const cle = `p${c}`
          const choix = modifs.projets?.[cle]
          const vu = projetDuGroupe(commun, choix, projets)
          return (
            <div key={c} className="apercu-groupe" role="group" aria-label={vu.sans ? 'Sans projet' : vu.nom}>
              <EnteteProjet
                commun={vu}
                nbTaches={taches.length}
                priorite={priorites[vu.nom] ?? (choix ? 2 : commun.priorite ?? 2)}
                enTache={enTache}
                ouvert={changeant === cle}
                onPriorite={onPriorite}
                onEnTache={() => onEnTache(c)}
                onChanger={changer(cle)}
              />
              {changeant === cle ? <ChoixDuProjet projet={vu} projets={projets} onChoisir={choisir(cle)} /> : null}
              {enTache ? <LigneTitreEnTache cle={`p${c}`} nom={commun.nom} {...titreDeLigne} /> : null}
              {taches.map(rendreTache)}
            </div>
          )
        }
        // R2-004 — sans projet commun : un groupe par titre (« Hôtel Atlas Marrakech »), chacun sous son en-tête
        const groupes = groupesDuCollage(apercu, c, projets)
        if (groupes.length === 0) return <div key={c} className="apercu-groupe" role="group" aria-label={`Liste ${c + 1}`} />
        return groupes.map((g) => {
          const nom = g.projet?.nom ?? ''
          const gEnTache = Boolean(modifs.enTache[g.cleModif])
          const vu = g.projet ? projetDuGroupe(g.projet, modifs.projets?.[g.cleModif], projets) : null
          const titreVu = vu?.sans ? 'Sans projet' : vu?.nom
          return (
            <div key={`${c}:${g.cleModif}`} className="apercu-groupe" role="group" aria-label={(nom && titreVu) || `Liste ${c + 1}`}>
              {nom ? (
                <EnteteProjet
                  commun={vu}
                  nbTaches={g.lignes.length}
                  priorite={priorites[vu.nom] ?? 2}
                  enTache={gEnTache}
                  ouvert={changeant === g.cleModif}
                  onPriorite={onPriorite}
                  onEnTache={() => onEnTache(g.cleModif)}
                  onChanger={changer(g.cleModif)}
                />
              ) : null}
              {nom && changeant === g.cleModif ? (
                <ChoixDuProjet projet={vu} projets={projets} onChoisir={choisir(g.cleModif)} />
              ) : null}
              {nom && gEnTache ? <LigneTitreEnTache cle={`t${g.cleModif}`} nom={nom} {...titreDeLigne} /> : null}
              {g.lignes.map(rendreTache)}
            </div>
          )
        })
      })}
    </div>
  )
}
