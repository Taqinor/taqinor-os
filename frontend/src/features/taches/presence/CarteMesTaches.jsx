import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Star } from 'lucide-react'
import { annulerGeste, lireAujourdhui, rouvrirTache, terminerTache } from '../../../api/tachesApi'
import { useHasPermission } from '../../../hooks/useHasPermission'
import { ROUTE } from '../../../lib/search/entityRoutes'
import { proposerAnnuler } from '../lib/gestes'
import CaseRonde from '../ui/CaseRonde'

/* ============================================================================
   TCH103 — Carte du cockpit « Tâches · Aujourd'hui » (spec-6a-erp.md « Écrans », textes.md §2.1 « Carte
   cockpit »). Maquette qui fait foi : docs/taches/maquettes/cockpit-carte.html. Montée dans le tableau de
   bord et l'accueil mobile par TCH125/TCH126 ; ici elle n'est que construite et exportée.

   Tout vient de `GET taches/aujourdhui/` (`aujourdhui.json`) : « {faites} sur {objectif} » (`progression`,
   `objectif` — mode `libre` : « {faites} faites »), « {n} à faire » (les tâches gardées encore ouvertes),
   TROIS lignes cochables, l'essentiel d'abord, puis le reste de la journée, puis les faites. Rien gardé :
   « Rien de gardé ». « Ouvrir Aujourd'hui » mène à l'écran. Sans `taches_voir` : aucune carte. Une relecture
   en échec ne vide jamais la carte déjà affichée ; aucun chiffre n'est écrit ici.
   ========================================================================== */

const NB_LIGNES = 3

const estTache = (item) => item?.type === 'tache'

/** Les tâches gardées, sans doublon, dans l'ordre de l'écran : l'essentiel, le prévu, « Ce soir », puis les faites.
 *  `etats` : ce que l'utilisateur vient de cocher ou décocher (id → fait ?), avant que le serveur ne soit relu. */
function lignesDeLaCarte(donnees, etats) {
  const vues = new Set()
  const fait = (t) => (etats.has(t.id) ? etats.get(t.id) : t.statut === 'fait')
  const toutes = [...(donnees.essentiel ?? []), ...(donnees.journee ?? []), ...(donnees.ce_soir ?? []), ...(donnees.faites ?? [])]
    .filter(estTache)
    .filter((t) => (vues.has(t.id) ? false : vues.add(t.id)))
  const ouvertes = toutes.filter((t) => !fait(t))
  const faites = toutes.filter(fait)
  return { lignes: [...ouvertes, ...faites].slice(0, NB_LIGNES), fait }
}

/** « {n} à faire » : les éléments ouverts GARDÉS d'Aujourd'hui, comme la pastille (regles.md §4.9) — `prevues − faites`
 *  de la progression SERVIE ; sans ce chiffre, rien n'est affiché (jamais un compte refait ici). */
function aFaire(progression) {
  const { prevues, faites } = progression ?? {}
  return Number.isInteger(prevues) && Number.isInteger(faites) ? Math.max(0, prevues - faites) : 0
}

function Compte({ donnees, ouvertes }) {
  const { objectif = {}, progression = {} } = donnees
  const faites = progression.faites ?? 0
  const libre = objectif.mode === 'libre' || !objectif.nb
  const segments = libre ? 0 : objectif.nb
  const texte = libre ? `${faites} ${faites >= 2 ? 'faites' : 'faite'}` : `${faites} sur ${objectif.nb}`
  return (
    <span className="ep-cc-compte">
      {segments > 0 ? (
        <span className="segments" aria-hidden="true">
          {Array.from({ length: segments }, (_, i) => <i key={i} className={i < faites ? 'fait' : ''} />)}
        </span>
      ) : null}
      <span className="chiffres"><span className="fort">{texte}</span>{ouvertes > 0 ? ` · ${ouvertes} à faire` : ''}</span>
    </span>
  )
}

function Ligne({ tache, fait, onTerminer, onOuvrir }) {
  return (
    <div className={fait ? 'ligne faite' : 'ligne'} role="listitem">
      <CaseRonde coche={fait} titre={tache.titre} onBasculer={(suivant) => onTerminer(tache, suivant)} />
      <div className="ligne-corps">
        <button type="button" className="ligne-corps-bouton" onClick={() => onOuvrir(tache)}>
          <span className="titre">{tache.titre}</span>
        </button>
        {tache.projet ? (
          <div className="meta">
            <span data-p={tache.projet.couleur}><i className="point" /><span className="projet-nom">{tache.projet.nom}</span></span>
          </div>
        ) : null}
      </div>
      <div className="ligne-fin">
        {tache.essentielle ? <Star className="i i-16 etoile" role="img" aria-label="Essentielle" /> : null}
      </div>
    </div>
  )
}

function CarteActive() {
  const navigate = useNavigate()
  const [donnees, setDonnees] = useState(null)
  const [etats, setEtats] = useState(() => new Map())

  useEffect(() => {
    let vivant = true
    lireAujourdhui()
      .then(({ data }) => { if (vivant) setDonnees(data) })
      .catch(() => { /* jamais de carte vidée ni de faux chiffre : sans lecture, la carte reste absente */ })
    return () => { vivant = false }
  }, [])

  if (!donnees) return null
  const { lignes, fait } = lignesDeLaCarte(donnees, etats)
  const poserEtat = (id, oui) => setEtats((s) => new Map(s).set(id, oui))
  /** La progression servie par le geste (`tache_ecrite.progression`, `geste_annuler.progression`) ; sans elle, Aujourd'hui
   *  est relu UNE fois (la carte entière, jamais une liste) et ses lignes redeviennent celles du serveur. */
  const reconcilier = async (progression) => {
    if (progression && typeof progression.faites === 'number') { setDonnees((d) => (d ? { ...d, progression } : d)); return true }
    try {
      const { data } = await lireAujourdhui()
      setDonnees(data)
      setEtats(new Map())
      return true
    } catch {
      return false // relecture en échec : la carte garde ses lignes et le dernier relevé du serveur, jamais un faux chiffre
    }
  }

  const terminer = async (tache, suivant) => {
    const { data } = suivant ? await terminerTache(tache.id) : await rouvrirTache(tache.id)
    poserEtat(tache.id, suivant)
    await reconcilier(data?.progression)
    if (!suivant) return
    proposerAnnuler({
      message: 'Faite',
      annonce: `Fait : ${tache.titre}`,
      onAnnuler: async () => {
        const bilan = await annulerGeste(data?.geste_id)
        poserEtat(tache.id, false)
        await reconcilier(bilan?.data?.progression)
      },
    })
  }

  return (
    <div className="tch">
      <section className="ep-carte-cockpit" aria-label="Tâches, aujourd'hui">
        <div className="ep-cc-tete">
          <div className="ep-cc-titre"><b>Tâches · Aujourd'hui</b><Compte donnees={donnees} ouvertes={aFaire(donnees.progression)} /></div>
        </div>
        {lignes.length > 0 ? (
          <div className="liste" role="list">
            {lignes.map((t) => (
              <Ligne key={t.id} tache={t} fait={fait(t)} onTerminer={terminer} onOuvrir={(x) => navigate(ROUTE.tache(x.id))} />
            ))}
          </div>
        ) : <p className="ep-cc-vide">Rien de gardé</p>}
        <div className="ep-cc-pied">
          <button type="button" className="lien-plus" onClick={() => navigate('/taches/aujourdhui')}>
            Ouvrir Aujourd'hui<ArrowRight className="i i-16" aria-hidden="true" />
          </button>
        </div>
      </section>
    </div>
  )
}

/** La carte : rien du tout sans `taches_voir`. */
export default function CarteMesTaches() {
  const peutVoir = useHasPermission('taches_voir')
  return peutVoir ? <CarteActive /> : null
}
