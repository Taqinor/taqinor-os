import { useCallback, useEffect, useMemo, useState } from 'react'
import { listerProjets, listerTousLesProjets, rouvrirProjet } from '../../api/tachesApi'
import { frenchError } from '../../lib/frenchError'
import BarreRetourProjets from '../../features/taches/ui/BarreRetourProjets'
import CoquilleTaches from '../../features/taches/coquille/CoquilleTaches'
import { avancementDe } from '../../features/taches/projets/LigneProjet'
import { annoncer } from '../../features/taches/lib/gestes'
import { aujourdhuiIso, jourCourt } from '../../features/taches/lib/textes'

/* ============================================================================
   TCH92 — Écran Archive (`/taches/projets/archive`) : les projets terminés ou archivés, une recherche, « Rouvrir ».
   Maquette : docs/taches/maquettes/projets-archive.html. Textes : reference/textes.md §2.6 (« Chercher un projet
   archivé », « Rouvrir », vide « Aucun projet archivé »). Contrat : `projets_liste.json` (`?statut=archive`).
   « Rouvrir » retire la ligne sur place, remet la ligne si le serveur refuse, et ne relit pas la liste.
   ========================================================================== */

const sansAccents = (t) => String(t ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
const ISSUES = { atteint: 'Atteint', abandonne: 'Abandonné' }

export default function ProjetsArchive() {
  const aujourdhui = useMemo(() => aujourdhuiIso(), [])
  const [projets, setProjets] = useState([])
  const [charge, setCharge] = useState(false)
  const [q, setQ] = useState('')
  const [erreur, setErreur] = useState('')

  const lire = useCallback(async () => {
    try {
      // Liste paginée (50) : la page 1 suffit tant que `next` est vide, sinon on lit tout (api.md §0).
      const premiere = await listerProjets({ statut: 'archive' })
      const data = premiere.data?.next ? await listerTousLesProjets({ statut: 'archive' }) : premiere.data
      setProjets(Array.isArray(data) ? data : (data?.results ?? []))
      setErreur('')
    } catch (err) {
      setErreur(frenchError(err, 'L\'archive n\'a pas pu être lue. Réessaie.'))
    } finally {
      setCharge(true)
    }
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement à l'ouverture de l'écran (D-ENF22)
  useEffect(() => { lire() }, [lire])

  const rouvrir = async (projet) => {
    setProjets((l) => l.filter((p) => p.id !== projet.id))
    try {
      await rouvrirProjet(projet.id)
      annoncer(`« ${projet.nom} » rouvert`)
    } catch (err) {
      setProjets((l) => [projet, ...l])
      setErreur(frenchError(err, 'Le projet n\'a pas été rouvert. Réessaie.'))
    }
  }

  const cherche = sansAccents(q.trim())
  const visibles = projets.filter((p) => !cherche || sansAccents(p.nom).includes(cherche))
  return (
    <CoquilleTaches ecran="projets-archive" titre="Archive">
      <BarreRetourProjets />
      {erreur ? <p className="ep-alerte-ligne" role="alert">{erreur}</p> : null}
      {projets.length > 0 ? (
        <div className="ep-recherche">
          <label className="sr" htmlFor="ep-archive-q">Chercher un projet archivé</label>
          <input id="ep-archive-q" className="champ" type="search" placeholder="Chercher un projet archivé" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      ) : null}
      {charge && projets.length === 0 && !erreur ? <p className="ep-constat">Aucun projet archivé</p> : null}
      {visibles.length > 0 ? (
        <section className="section" aria-label="Projets archivés">
          <div className="liste" role="list">
            {visibles.map((p) => {
              const { texte } = avancementDe(p)
              return (
                <div key={p.id} className="ligne projet ep-archive-ligne" role="listitem" data-p={p.couleur}>
                  <span className="point-projet" aria-hidden="true" />
                  <div className="ligne-corps">
                    <div className="titre">{p.nom}</div>
                    <div className="meta">
                      {p.issue ? <span className="issue">{ISSUES[p.issue] ?? p.issue}</span> : null}
                      {p.termine_le ? <span className="chiffres">{jourCourt(p.termine_le.slice(0, 10), aujourdhui)}</span> : null}
                      <span className="chiffres">{texte}</span>
                    </div>
                    {p.bilan ? <p className="ep-bilan">{p.bilan}</p> : null}
                  </div>
                  <div className="ligne-fin">
                    <button type="button" className="bouton second" aria-label={`Rouvrir « ${p.nom} »`} onClick={() => rouvrir(p)}>Rouvrir</button>
                  </div>
                </div>
              )
            })}
          </div>
        </section>
      ) : null}
    </CoquilleTaches>
  )
}
