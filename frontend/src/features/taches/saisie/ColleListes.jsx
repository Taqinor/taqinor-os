import { useMemo, useState } from 'react'

import { saisieRapide } from '../../../api/tachesApi'
import { frenchError } from '../../../lib/frenchError'
import { construireLigne } from '../horsligne/captureQueue'
import { accord } from '../lib/textes'
import ApercuListe, { groupesDuCollage } from '../ui/ApercuListe'

/* ============================================================================
   TCH83 — « Coller mes listes » : le corps de la feuille de saisie quand on colle plus d'une ligne
   (ou plusieurs listes). Reçoit l'aperçu du serveur (`saisie_apercu.json`) et tient ce que la
   personne change AVANT de créer : cases, titres, « En faire une tâche » (le projet de tête
   devient une tâche), « En faire des sous-tâches », priorité des nouveaux projets. Rien n'est
   écrit tant que « Créer N tâches » n'est pas touché ; la création = UN envoi `saisie-rapide/`
   (`apercu:false`) fait par la feuille, qui reçoit les LIGNES prêtes.
   Boutons (textes.md §2.3) : Créer {n} tâches · Coller encore.
   ========================================================================== */

const MODIFS_VIDES = { cochees: {}, titres: {}, enTache: {}, sousTaches: {} }
const SANS_PROJETS = []

// La ligne à créer (`construireLigne`) vit avec la file hors ligne, qui la refait au rejeu d'une phrase (R2-008a) ;
// elle est relue d'ici par FeuilleSaisie.
// eslint-disable-next-line react-refresh/only-export-components -- ré-export du helper pur de la file (D-ENF22)
export { construireLigne }

const aSonProjet = (ligne) => (ligne.jetons ?? []).some((j) => j.type === 'projet')

/**
 * R2-005 — une ligne relue par le serveur remplace titre, puces, alertes et champs lus ; le projet qu'elle RECEVAIT
 * de son titre de groupe (aucun `#projet` à elle) est gardé, comme le × d'une puce le fait côté serveur.
 */
function fusionner(ligne, lue) {
  const herite = aSonProjet(ligne) || aSonProjet(lue) ? {} : Object.fromEntries(
    ['projet_id', 'nouveau_projet', 'section_id'].filter((c) => ligne.champs?.[c] != null).map((c) => [c, ligne.champs[c]]))
  const { texte, ignorer, ...reste } = lue
  return {
    ...ligne, titre: reste.titre, jetons: reste.jetons ?? [], alertes: reste.alertes ?? [],
    champs: { ...(reste.champs ?? {}), ...herite }, erreurs: reste.erreurs, texte, ignorer,
    cochee: reste.erreurs ? false : ligne.cochee,
  }
}

/** Le texte d'une ligne de l'aperçu (le serveur ne le sert pas) : son titre, puis la source de chacun de ses jetons. */
function texteDeLigne(ligne) {
  return [ligne.titre, ...(ligne.jetons ?? []).map((j) => j.source)].filter(Boolean).join(' ')
}

const estCochee = (ligne, modifs) => modifs.cochees[ligne.index] ?? ligne.cochee !== false

/** Les lignes à envoyer, dans l'ordre de la liste : cochées seulement, points repliés dans la check-list. */
// eslint-disable-next-line react-refresh/only-export-components -- helper co-localisé, testé directement (D-ENF22)
export function lignesACreer(apercu, modifs, { cid, priorites, projets = [] }) {
  const lignes = apercu?.lignes ?? []
  const sorties = []
  const enTete = (apercu?.projets_communs ?? []).filter((c) => modifs.enTache[c.collage] && modifs.cochees[`p${c.collage}`] !== false)
  enTete.forEach((c) => {
    sorties.push({
      index: 10000 + c.collage, collage: c.collage, client_id: `${cid}:p${c.collage}`, titre: modifs.titres[`p${c.collage}`] ?? c.nom,
    })
  })
  // R2-004 — un titre de groupe « En faire une tâche » : il devient une tâche, ses lignes perdent le projet qu'il donnait
  const sansCommun = new Set(lignes.map((l) => l.collage).filter((c) => !(apercu?.projets_communs ?? []).some((p) => p.collage === c)))
  const groupeDe = new Map()
  sansCommun.forEach((c) => groupesDuCollage(apercu, c, projets).forEach((g) => {
    g.lignes.forEach((l, rang) => groupeDe.set(l.index, { g, premier: rang === 0 }))
  }))
  lignes.forEach((ligne) => {
    const groupe = groupeDe.get(ligne.index)
    const titreEnTache = groupe && modifs.enTache[groupe.g.cleModif]
    if (groupe?.premier && titreEnTache && modifs.cochees[`t${groupe.g.cleModif}`] !== false) {
      const premierIndex = groupe.g.lignes[0].index
      sorties.push({
        index: 20000 + premierIndex, collage: ligne.collage, client_id: `${cid}:g${premierIndex}`,
        titre: modifs.titres[`t${groupe.g.cleModif}`] ?? groupe.g.projet?.nom ?? '',
      })
    }
    const point = ligne.etape_de != null && !modifs.sousTaches[ligne.etape_de]
    if (point || !estCochee(ligne, modifs)) return
    const base = construireLigne({ ...ligne, titre: modifs.titres[ligne.index] ?? ligne.titre }, { cid, priorites })
    const heriteDuTitre = titreEnTache && !(ligne.jetons ?? []).some((j) => j.type === 'projet')
    if (modifs.enTache[ligne.collage] || heriteDuTitre) { delete base.nouveau_projet; delete base.projet_id }
    const points = lignes.filter((l) => l.etape_de === ligne.index)
    if (points.length > 0 && !modifs.sousTaches[ligne.index]) {
      base.checklist = points.map((p) => modifs.titres[p.index] ?? p.titre)
    }
    sorties.push(base)
  })
  return sorties
}

/** Les projets que l'envoi touche (nouveaux par nom, existants par id), lus sur les lignes qui partent. */
function compterProjets(aEnvoyer) {
  const cles = new Set()
  aEnvoyer.forEach((l) => {
    if (l.nouveau_projet?.nom) cles.add(`n:${l.nouveau_projet.nom.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()}`)
    else if (l.projet_id != null) cles.add(`p:${l.projet_id}`)
  })
  return cles.size
}

export default function ColleListes({
  apercu, cid, priorites = {}, projets = SANS_PROJETS, onPriorite, onCreer, onCollerEncore, envoi = false, erreur = '',
}) {
  const [modifs, setModifs] = useState(MODIFS_VIDES)
  const maj = (cle, index, valeur) => setModifs((m) => ({ ...m, [cle]: { ...m[cle], [index]: valeur } }))
  // R2-005 — les lignes relues par le serveur après une correction (titre ou puce retirée), par index
  const [relues, setRelues] = useState({})
  const [erreurRelecture, setErreurRelecture] = useState('')
  const vu = useMemo(() => (Object.keys(relues).length === 0 ? apercu
    : { ...apercu, lignes: (apercu?.lignes ?? []).map((l) => (relues[l.index] ? fusionner(l, relues[l.index]) : l)) }),
  [apercu, relues])

  /** Relit UNE ligne : `texte` sans les jetons de `ignorer` ; le titre tapé est remplacé par le titre relu. */
  const relire = (index, texte, ignorer = []) => {
    saisieRapide({ texte, ignorer, apercu: true }, { cle: null, erreurSousLeChamp: true })
      .then(({ data }) => {
        const lue = data?.lignes?.[0]
        if (!lue) return
        setRelues((r) => ({ ...r, [index]: { ...lue, texte, ignorer } }))
        setModifs((m) => {
          const titres = { ...m.titres }
          delete titres[index]
          return { ...m, titres }
        })
      })
      // sans relecture (réseau, refus), le titre tapé reste tel quel et part ainsi : rien n'est perdu, l'échec est dit
      .catch((err) => setErreurRelecture(frenchError(err)))
    setErreurRelecture('')
  }
  const surRelire = (index) => {
    const tape = modifs.titres[index]
    const ligne = vu?.lignes?.find((l) => l.index === index)
    if (tape === undefined || !ligne || tape.trim() === '' || tape === ligne.titre) return
    relire(index, tape)
  }
  const surRetirer = (index, jeton) => {
    const ligne = vu?.lignes?.find((l) => l.index === index)
    if (!ligne) return
    const deja = relues[index]
    const texte = deja?.texte ?? texteDeLigne({ ...ligne, titre: modifs.titres[index] ?? ligne.titre })
    relire(index, texte, [...(deja?.ignorer ?? []), { type: jeton.type, source: jeton.source }])
  }

  const aEnvoyer = useMemo(() => lignesACreer(vu, modifs, { cid, priorites, projets }), [vu, modifs, cid, priorites, projets])
  const nbProjets = compterProjets(aEnvoyer)
  const vide = aEnvoyer.length === 0

  return (
    <div className="colle-listes">
      <ApercuListe
        apercu={vu}
        modifs={modifs}
        priorites={priorites}
        projets={projets}
        nbCreer={aEnvoyer.length}
        nbProjets={nbProjets}
        onCocher={(index, valeur) => maj('cochees', index, valeur)}
        onTitre={(index, valeur) => maj('titres', index, valeur)}
        onRelire={surRelire}
        onRetirer={surRetirer}
        onEnTache={(collage) => maj('enTache', collage, !modifs.enTache[collage])}
        onSousTaches={(index) => maj('sousTaches', index, !modifs.sousTaches[index])}
        onPriorite={onPriorite}
      />
      {erreur || erreurRelecture ? <p className="erreur-champ" role="alert">{erreur || erreurRelecture}</p> : null}
      <div className="feuille-pied">
        <button type="button" className="bouton second" onClick={onCollerEncore}>Coller encore</button>
        <button
          type="button"
          className="bouton plein large"
          aria-disabled={vide || envoi || undefined}
          onClick={() => { if (!vide && !envoi) onCreer?.(aEnvoyer) }}
        >
          {`Créer ${accord(aEnvoyer.length, 'tâche')}`}
        </button>
      </div>
    </div>
  )
}
