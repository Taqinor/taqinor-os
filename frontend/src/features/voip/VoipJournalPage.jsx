import { Fragment, useCallback, useEffect, useState } from 'react'

import voipApi from '../../api/voipApi'
import { formatDateTime } from '../../lib/format'

/* ============================================================================
   WIR160 — Journal d'appels + widget click-to-call. Composer un numéro et
   « Appeler » amorce un appel sortant (le backend refuse en 409 si le softphone
   n'est pas configuré/actif — message clair). Le journal liste les appels de la
   société (lecture seule ; la journalisation est orchestrée côté serveur).

   WIR271 — aucun appel n'était jamais CLÔTURABLE depuis l'écran : la durée et
   l'issue restaient à jamais vides, et l'entrée chatter que `terminer_appel`
   pose sur la fiche résolue ne partait donc jamais. Le bouton « Terminer »
   (appels EN_COURS) pré-remplit la durée depuis `started_at` → maintenant
   (l'utilisateur peut la corriger) ; l'issue est en texte libre, optionnelle.
   Le 400 du serveur (« Entier requis. » si `duree_secondes` n'est pas un
   entier) est affiché TEL QUEL — jamais un message français réinventé ici.
   ========================================================================== */

// Durée écoulée depuis `started_at` (secondes), pour pré-remplir le champ.
function dureeEcouleeSecondes(startedAt) {
  if (!startedAt) return 0
  const debut = new Date(startedAt).getTime()
  if (Number.isNaN(debut)) return 0
  return Math.max(0, Math.round((Date.now() - debut) / 1000))
}

export default function VoipJournalPage() {
  const [appels, setAppels] = useState([])
  const [loading, setLoading] = useState(true)
  const [numero, setNumero] = useState('')
  const [message, setMessage] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  // WIR271 — clôture d'appel : l'appel en cours de clôture, sa durée/issue
  // en cours d'édition, et l'erreur 400 propre à CETTE clôture (jamais
  // mélangée à l'erreur du composeur ci-dessus).
  const [cloture, setCloture] = useState(null) // { id, duree, issue }
  const [clotureErreur, setClotureErreur] = useState(null)
  const [clotureBusy, setClotureBusy] = useState(false)

  const charger = useCallback(() => {
    let alive = true
    voipApi
      .getAppels()
      .then((res) => {
        if (alive) setAppels(res.data?.results ?? res.data ?? [])
      })
      .catch(() => {
        if (alive) setError("Impossible de charger le journal d'appels.")
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [])

  useEffect(() => charger(), [charger])

  async function appeler(e) {
    e.preventDefault()
    const n = numero.trim()
    if (!n) { setError('Numéro requis.'); return }
    setBusy(true)
    setError(null)
    setMessage(null)
    try {
      await voipApi.appelSortant(n)
      setMessage(`Appel vers ${n} amorcé.`)
      setNumero('')
      charger()
    } catch (err) {
      if (err?.response?.status === 409) {
        setError('Softphone VoIP non configuré/actif — voir « Config société ».')
      } else {
        setError("Impossible d'amorcer l'appel.")
      }
    } finally {
      setBusy(false)
    }
  }

  const ouvrirCloture = (appel) => {
    setCloture({
      id: appel.id,
      duree: String(dureeEcouleeSecondes(appel.started_at)),
      issue: '',
    })
    setClotureErreur(null)
  }

  const annulerCloture = () => {
    setCloture(null)
    setClotureErreur(null)
  }

  async function terminer(e) {
    e.preventDefault()
    if (!cloture) return
    setClotureBusy(true)
    setClotureErreur(null)
    try {
      await voipApi.terminerAppel(cloture.id, {
        duree_secondes: cloture.duree,
        issue: cloture.issue || undefined,
      })
      setCloture(null)
      charger()
    } catch (err) {
      // WIR271 — 400 « Entier requis. » (ou tout autre motif serveur) affiché
      // tel quel, jamais un message français réinventé ici.
      const data = err?.response?.data
      const motif = data?.duree_secondes || data?.detail
        || "Clôture de l'appel impossible."
      setClotureErreur(Array.isArray(motif) ? motif[0] : motif)
    } finally {
      setClotureBusy(false)
    }
  }

  return (
    <div className="voip-journal" data-testid="voip-journal">
      <form className="voip-journal__dialer" onSubmit={appeler} noValidate>
        <input
          type="tel"
          value={numero}
          onChange={(e) => setNumero(e.target.value)}
          placeholder="Numéro à appeler"
          aria-label="Numéro à appeler"
        />
        <button type="submit" disabled={busy}>Appeler</button>
      </form>
      {message && <p className="voip-journal__ok" role="status">{message}</p>}
      {error && <p className="voip-journal__error" role="alert">{error}</p>}

      {loading ? (
        <p>Chargement…</p>
      ) : appels.length === 0 ? (
        <p>Aucun appel enregistré.</p>
      ) : (
        <table className="voip-journal__table">
          <thead>
            <tr>
              <th>Sens</th>
              <th>Numéro</th>
              <th>Contact</th>
              <th>Statut</th>
              <th>Début</th>
              <th>Durée</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {appels.map((a) => {
              const enCours = a.statut === 'en_cours'
              return (
                <Fragment key={a.id}>
                  <tr>
                    <td>{a.direction}</td>
                    <td>{a.numero}</td>
                    <td>{a.cible?.libelle || '—'}</td>
                    <td>{a.statut}{a.issue ? ` (${a.issue})` : ''}</td>
                    <td>{a.started_at ? formatDateTime(a.started_at) : '—'}</td>
                    <td>{a.duree_secondes != null ? `${a.duree_secondes}s` : '—'}</td>
                    <td>
                      {/* WIR271 — un appel EN_COURS est le SEUL à pouvoir être
                          clôturé depuis l'écran : un appel déjà terminé n'a
                          plus de bouton (test présence/absence). */}
                      {enCours && (
                        <button
                          type="button"
                          onClick={() => ouvrirCloture(a)}
                          disabled={cloture?.id === a.id}
                        >
                          Terminer
                        </button>
                      )}
                    </td>
                  </tr>
                  {cloture?.id === a.id && (
                    <tr>
                      <td colSpan={7}>
                        <form className="voip-journal__cloture" onSubmit={terminer} noValidate>
                          <label>
                            Durée (secondes)
                            <input
                              type="number"
                              min="0"
                              value={cloture.duree}
                              onChange={(e) => setCloture((c) => ({ ...c, duree: e.target.value }))}
                              aria-label={`Durée de l'appel ${a.numero}`}
                            />
                          </label>
                          <label>
                            Issue
                            <input
                              type="text"
                              value={cloture.issue}
                              onChange={(e) => setCloture((c) => ({ ...c, issue: e.target.value }))}
                              placeholder="Répondu, sans suite, injoignable…"
                              aria-label={`Issue de l'appel ${a.numero}`}
                            />
                          </label>
                          <button type="submit" disabled={clotureBusy}>Valider</button>
                          <button type="button" onClick={annulerCloture} disabled={clotureBusy}>Annuler</button>
                          {clotureErreur && (
                            <p className="voip-journal__error" role="alert">{clotureErreur}</p>
                          )}
                        </form>
                      </td>
                    </tr>
                  )}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}
