import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ChevronDown, ChevronLeft, Diamond, TriangleAlert } from 'lucide-react'
import {
  classerErreur, creerTache, lireVueProjet, modifierProjet, nouvelleCle, rouvrirTache, supprimerTache,
  restaurerTache, terminerTache,
} from '../../api/tachesApi'
import { frenchError } from '../../lib/frenchError'
import CoquilleTaches from '../../features/taches/coquille/CoquilleTaches'
import { PuchePriorite, avancementDe } from '../../features/taches/projets/LigneProjet'
import VueListe from '../../features/taches/projets/VueListe'
import { annoncer, proposerAnnuler } from '../../features/taches/lib/gestes'
import { aujourdhuiIso, jourCourt } from '../../features/taches/lib/textes'

/* ============================================================================
   TCH89 — Écran « Un projet », vue Liste (`/taches/projets/:id`). Maquette : docs/taches/maquettes/projet-liste.html.
   Textes : reference/textes.md §2.6 (« {faites} sur {total} · échéance {jj/mm} », « Prochain jalon : {titre} · {jour} »,
   santé si signal, Détails « Fini quand : {objectif} » · « dernière faite le {jj/mm} »). Contrat : `projet_vue.json`.
   Tableau, Chronologie, Modèle et Dupliquer sont de la fusion F4 : ils n'apparaissent pas ici.
   Un geste (cocher, ajouter, priorité, pause) met l'écran à jour sur place et ne relit jamais la vue entière.
   ========================================================================== */

const jjmm = (iso) => {
  const m = /^\d{4}-(\d{2})-(\d{2})/.exec(String(iso ?? ''))
  return m ? `${m[2]}/${m[1]}` : ''
}

/** Remplace une tâche partout dans la vue (sections et « Sans étape »). */
function remplacerTache(vue, tache) {
  const maj = (liste) => (liste ?? []).map((t) => (t.id === tache.id ? { ...t, ...tache } : t))
  return { ...vue, sections: (vue.sections ?? []).map((s) => ({ ...s, taches: maj(s.taches) })), sans_section: maj(vue.sans_section) }
}

function Entete({ vue, aujourdhui, onPriorite }) {
  const [details, setDetails] = useState(false)
  const { projet, avancement, prochain_jalon: jalon } = vue
  const { texte, part } = avancementDe({ compteurs: { faites: avancement.faites, ouvertes: avancement.total - avancement.faites } })
  const sante = projet.sante?.[0]?.phrase
  const jalonJour = jalon ? (jalon.jour_prevu ?? jalon.echeance) : null
  return (
    <div className="ep-tete" data-p={projet.couleur}>
      <div className="ep-ligne-info">
        <PuchePriorite projet={projet} onChoisir={onPriorite} />
        <span className="chiffres">{`${texte}${projet.echeance ? ` · échéance ${jjmm(projet.echeance)}` : ''}`}</span>
      </div>
      <div className="ep-avance">
        <div className="ep-barre-avance" role="img" aria-label={texte}><i style={{ '--avance': part.toFixed(3) }} /></div>
        {jalon ? (
          <span className="ep-jalon-proche">
            <Diamond className="i i-14 ep-losange" aria-hidden="true" />
            {`Prochain jalon : ${jalon.titre}${jalonJour ? ` · ${jourCourt(jalonJour, aujourdhui)}` : ''}`}
          </span>
        ) : null}
      </div>
      {sante ? (
        <p className="ep-sante-ligne surveiller">
          <TriangleAlert className="i i-14" aria-hidden="true" /><span>{sante}</span>
        </p>
      ) : null}
      <button type="button" className="ep-details" aria-expanded={details} onClick={() => setDetails((o) => !o)}>
        <b>Détails</b>
        <ChevronDown className="i i-16" aria-hidden="true" />
      </button>
      {details ? (
        <div className="ep-details-corps">
          {projet.objectif ? (
            <p>{/^fini quand/i.test(projet.objectif) ? projet.objectif : `Fini quand : ${projet.objectif}`}</p>
          ) : null}
          {avancement.derniere_faite_le ? <p className="chiffres">{`dernière faite le ${jjmm(avancement.derniere_faite_le)}`}</p> : null}
        </div>
      ) : null}
    </div>
  )
}

export default function Projet() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [, setParams] = useSearchParams()
  const aujourdhui = useMemo(() => aujourdhuiIso(), [])
  const [vue, setVue] = useState(null)
  const [erreur, setErreur] = useState('')
  const [introuvable, setIntrouvable] = useState(false)

  const charger = useCallback(async () => {
    try {
      const { data } = await lireVueProjet(id, { vue: 'liste' })
      setVue(data)
      setErreur('')
      setIntrouvable(false)
    } catch (err) {
      if (classerErreur(err).code === 'introuvable') setIntrouvable(true)
      else setErreur(frenchError(err, 'Le projet n\'a pas pu être chargé. Réessaie.'))
    }
  }, [id])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement à l'ouverture de l'écran (D-ENF22)
  useEffect(() => { charger() }, [charger])

  const majTache = (tache) => setVue((v) => (v ? remplacerTache(v, tache) : v))
  const ajusterFaites = (delta) => setVue((v) => (v ? { ...v, avancement: { ...v.avancement, faites: v.avancement.faites + delta } } : v))

  const terminer = async (item, suivant) => {
    const { data } = suivant ? await terminerTache(item.id) : await rouvrirTache(item.id)
    majTache(data.tache ?? { ...item, statut: suivant ? 'fait' : 'a_faire' })
    ajusterFaites(suivant ? 1 : -1)
    if (suivant) {
      proposerAnnuler({
        message: 'Faite',
        annonce: `Fait : ${item.titre}`,
        onAnnuler: async () => {
          const retour = await rouvrirTache(item.id)
          majTache(retour.data.tache ?? { ...item, statut: 'a_faire' })
          ajusterFaites(-1)
        },
      })
    }
  }

  const ajouter = async (sectionId, titre) => {
    try {
      const { data } = await creerTache({ titre, projet_id: vue.projet.id, section_id: sectionId, client_id: nouvelleCle() })
      const tache = data.tache ?? data
      setVue((v) => {
        const ajout = (liste) => [...(liste ?? []), tache]
        if (sectionId == null) return { ...v, sans_section: ajout(v.sans_section), avancement: { ...v.avancement, total: v.avancement.total + 1 } }
        return {
          ...v,
          sections: v.sections.map((s) => (s.id === sectionId ? { ...s, taches: ajout(s.taches) } : s)),
          avancement: { ...v.avancement, total: v.avancement.total + 1 },
        }
      })
      annoncer(`Ajoutée : ${titre}`)
    } catch (err) {
      throw new Error(err?.response?.data?.titre?.[0] ?? frenchError(err, 'La tâche n\'a pas été ajoutée. Réessaie.'))
    }
  }

  const supprimer = async (item) => {
    await supprimerTache(item.id)
    setVue((v) => ({
      ...v,
      sections: v.sections.map((s) => ({ ...s, taches: s.taches.filter((t) => t.id !== item.id) })),
      sans_section: (v.sans_section ?? []).filter((t) => t.id !== item.id),
    }))
    proposerAnnuler({
      message: 'Supprimée',
      onAnnuler: async () => { await restaurerTache(item.id); await charger() },
    })
  }

  const surAction = (code, item) => {
    if (code === 'supprimer') supprimer(item).catch((err) => setErreur(frenchError(err, 'La tâche n\'a pas été supprimée. Réessaie.')))
  }

  const poserPriorite = async (projet, valeur) => {
    if (valeur === projet.priorite) return
    setVue((v) => ({ ...v, projet: { ...v.projet, priorite: valeur } }))
    try {
      const { data } = await modifierProjet(projet.id, { priorite: valeur, lock_version: projet.lock_version })
      setVue((v) => ({ ...v, projet: { ...v.projet, ...data } }))
    } catch (err) {
      setVue((v) => ({ ...v, projet }))
      setErreur(frenchError(err, 'La priorité n\'a pas été changée. Réessaie.'))
    }
  }

  const mettreEnPause = async () => {
    const projet = vue.projet
    try {
      const { data } = await modifierProjet(projet.id, { statut: 'en_pause', lock_version: projet.lock_version })
      setVue((v) => ({ ...v, projet: { ...v.projet, ...data } }))
      proposerAnnuler({
        message: `« ${projet.nom} » en pause`,
        onAnnuler: async () => {
          const retour = await modifierProjet(projet.id, { statut: 'actif', lock_version: data.lock_version })
          setVue((v) => ({ ...v, projet: { ...v.projet, ...retour.data } }))
        },
      })
    } catch (err) {
      setErreur(frenchError(err, 'Le projet n\'a pas été mis en pause. Réessaie.'))
    }
  }

  const projet = vue?.projet
  const actionsEcran = projet ? [
    { libelle: 'Planifier le projet', onSelect: () => setParams((p) => { const s = new URLSearchParams(p); s.set('planifier', '1'); return s }) },
    { libelle: "Voir dans l'agenda", onSelect: () => navigate(`/taches/agenda?projet=${projet.id}`) },
    ...(projet.statut === 'actif' ? [{ libelle: 'Mettre en pause', onSelect: mettreEnPause }] : []),
  ] : []

  return (
    <CoquilleTaches ecran="projet" titre={projet?.nom ?? 'Projet'} actionsEcran={actionsEcran}>
      <div className="ep-barre">
        <button type="button" className="ep-retour" onClick={() => navigate('/taches/projets')}>
          <ChevronLeft className="i" aria-hidden="true" />Projets
        </button>
      </div>
      {erreur ? <p className="ep-alerte-ligne" role="alert">{erreur}</p> : null}
      {introuvable ? <p className="ep-alerte-ligne" role="alert">Ce projet n'existe plus.</p> : null}
      {vue ? (
        <>
          {projet.statut === 'en_pause' ? <p className="ep-constat">En pause</p> : null}
          <Entete vue={vue} aujourdhui={aujourdhui} onPriorite={poserPriorite} />
          <VueListe
            vue={vue}
            aujourdhui={aujourdhui}
            onTerminer={terminer}
            onOuvrir={(t) => setParams((p) => { const s = new URLSearchParams(p); s.set('tache', String(t.id)); return s })}
            onAction={surAction}
            onAjouter={ajouter}
            onAnnonce={annoncer}
          />
        </>
      ) : null}
    </CoquilleTaches>
  )
}
