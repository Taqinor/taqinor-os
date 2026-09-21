import { useState } from 'react'

import creditApi from '../../api/creditApi'
import { frenchError } from '../../lib/frenchError'

/* ============================================================================
   PACT47 — Import en masse des limites de crédit (endpoint NTCRD39
   `POST /credit/import-limites/`, qui n'avait AUCUN écran : initialiser les
   limites de tout un portefeuille se faisait client par client).

   Les deux garde-fous du serveur sont rendus VISIBLES ici, jamais réimplémentés :

   * `apercu=true` — le serveur NE PEUT RIEN ÉCRIRE et renvoie le rapport ligne
     à ligne (erreurs + conflits). C'est le seul bouton disponible tant qu'aucun
     aperçu n'a été demandé : on ne confirme jamais ce qu'on n'a pas vu.
   * `ecraser` — OPT-IN explicite. Le défaut sûr (remplissage seul) ne remplace
     jamais un champ déjà rempli. La confirmation rejoue EXACTEMENT le couple
     (fichier, écrasement) FIGÉ par l'aperçu — changer l'un des deux invalide
     l'aperçu et en redemande un.
   ========================================================================== */

function Erreurs({ lignes }) {
  if (!lignes?.length) return <p>Aucune erreur de lecture.</p>
  return (
    <table className="credit-import__erreurs" data-testid="credit-import-erreurs">
      <thead>
        <tr>
          <th>Ligne</th>
          <th>Motif du refus</th>
        </tr>
      </thead>
      <tbody>
        {lignes.map((e) => (
          <tr key={`err-${e.ligne}-${e.motif}`}>
            <td>Ligne {e.ligne}</td>
            <td>{e.motif}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default function ImportLimitesCreditPage() {
  const [fichier, setFichier] = useState(null)
  const [ecraser, setEcraser] = useState(false)
  // `apercu` FIGE le couple (fichier, écrasement) prévisualisé : c'est lui,
  // jamais l'état courant du formulaire, qui sera rejoué à la confirmation.
  const [apercu, setApercu] = useState(null)
  const [rapport, setRapport] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [occupe, setOccupe] = useState(false)

  const apercuAJour = Boolean(
    apercu && apercu.fichier === fichier && apercu.ecraser === ecraser,
  )

  function choisirFichier(event) {
    setFichier(event.target.files?.[0] ?? null)
    setRapport(null)
    setErreur(null)
  }

  async function demanderApercu(event) {
    event.preventDefault()
    if (!fichier || occupe) return
    setOccupe(true)
    setErreur(null)
    setRapport(null)
    try {
      const res = await creditApi.importerLimites(fichier, {
        apercu: true, ecraser,
      })
      setApercu({ fichier, ecraser, donnees: res.data })
    } catch (err) {
      setApercu(null)
      setErreur(frenchError(err, "Aperçu impossible (droits Directeur/Administrateur requis)."))
    } finally {
      setOccupe(false)
    }
  }

  async function confirmer() {
    if (!apercuAJour || occupe) return
    setOccupe(true)
    setErreur(null)
    try {
      const res = await creditApi.importerLimites(apercu.fichier, {
        apercu: false, ecraser: apercu.ecraser,
      })
      setRapport(res.data)
      setApercu(null)
    } catch (err) {
      setErreur(frenchError(err, 'Import impossible.'))
    } finally {
      setOccupe(false)
    }
  }

  // Un aperçu périmé (fichier ou option changés depuis) n'est PLUS affichable :
  // sinon on confirmerait un rapport qui ne décrit plus ce qui serait écrit.
  const vue = apercuAJour ? apercu.donnees : null

  return (
    <div className="credit-import" data-testid="credit-import-limites">
      <h3>Import en masse des limites de crédit</h3>
      <p>
        Colonnes attendues : <code>client</code> (identifiant ou e-mail),{' '}
        <code>montant_limite</code>, <code>mode_hold</code> (facultatif).
        Formats acceptés : CSV ou XLSX.
      </p>

      {erreur && (
        <p className="credit-import__error" role="alert">{erreur}</p>
      )}

      <form onSubmit={demanderApercu} className="credit-import__form">
        <label htmlFor="credit-import-fichier">Fichier CSV ou XLSX</label>
        <input
          id="credit-import-fichier"
          type="file"
          accept=".csv,.xlsx"
          onChange={choisirFichier}
        />
        <label>
          <input
            type="checkbox"
            checked={ecraser}
            onChange={(e) => setEcraser(e.target.checked)}
          />
          Remplacer les valeurs déjà renseignées (sinon : remplissage seul)
        </label>
        <button type="submit" disabled={!fichier || occupe}>
          Aperçu (n’écrit rien)
        </button>
      </form>

      {vue && (
        <section className="credit-import__apercu" data-testid="credit-import-apercu">
          <h4>Aperçu — rien n’a été écrit en base</h4>
          <ul>
            <li>{vue.total_lignes} ligne(s) lue(s)</li>
            <li>{vue.creations} fiche(s) à créer</li>
            <li>{vue.maj} fiche(s) existante(s) concernée(s)</li>
            <li>
              {apercu.ecraser
                ? 'Mode : remplacement des valeurs déjà renseignées'
                : 'Mode : remplissage seul (aucune valeur existante remplacée)'}
            </li>
          </ul>

          <h5>Erreurs ligne à ligne</h5>
          <Erreurs lignes={vue.erreurs} />

          <h5>Valeurs déjà renseignées concernées</h5>
          {vue.conflits?.length ? (
            <table data-testid="credit-import-conflits">
              <thead>
                <tr>
                  <th>Ligne</th>
                  <th>Client</th>
                  <th>Remplacements</th>
                  <th>Remplissages</th>
                </tr>
              </thead>
              <tbody>
                {vue.conflits.map((c) => (
                  <tr key={`conflit-${c.ligne}`}>
                    <td>Ligne {c.ligne}</td>
                    <td>{c.client}</td>
                    <td>
                      {c.ecrasements?.length
                        ? c.ecrasements.map((m) => (
                          <span key={`${c.ligne}-${m.champ}`}>
                            {m.champ} : {m.ancienne} → {m.nouvelle}{' '}
                          </span>
                        ))
                        : '—'}
                    </td>
                    <td>
                      {c.remplissages?.length ? c.remplissages.join(', ') : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p>Aucune valeur existante ne serait remplacée.</p>
          )}

          <button type="button" onClick={confirmer} disabled={occupe}>
            Confirmer l’import
          </button>
        </section>
      )}

      {!vue && fichier && !rapport && (
        <p className="credit-import__hint">
          Demandez l’aperçu avant de pouvoir confirmer l’import.
        </p>
      )}

      {rapport && (
        <section className="credit-import__rapport" data-testid="credit-import-rapport">
          <h4>Import appliqué</h4>
          <ul>
            <li>{rapport.crees} fiche(s) créée(s)</li>
            <li>{rapport.maj} fiche(s) mise(s) à jour</li>
            <li>{rapport.ecrasements?.length ?? 0} valeur(s) remplacée(s)</li>
            <li>{rapport.refuses?.length ?? 0} valeur(s) refusée(s) (remplissage seul)</li>
            <li>Journal d’import n° {rapport.job_id}</li>
          </ul>
          <h5>Erreurs ligne à ligne</h5>
          <Erreurs lignes={rapport.erreurs} />
        </section>
      )}
    </div>
  )
}
