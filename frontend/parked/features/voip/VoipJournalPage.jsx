import { useCallback, useEffect, useState } from 'react'

import voipApi from '../../api/voipApi'
import { formatDateTime } from '../../lib/format'

/* ============================================================================
   WIR160 — Journal d'appels + widget click-to-call. Composer un numéro et
   « Appeler » amorce un appel sortant (le backend refuse en 409 si le softphone
   n'est pas configuré/actif — message clair). Le journal liste les appels de la
   société (lecture seule ; la journalisation est orchestrée côté serveur).
   WIR271 — un appel OUVERT (initié/sonnant/en cours) porte un bouton
   « Terminer » : formulaire inline avec la durée pré-remplie (écoulée depuis
   `started_at`, éditable) + l'issue (texte libre, comme les autres modules
   « issue » du dépôt) → `voipApi.terminerAppel`. Un 400 serveur (durée non
   entière) s'affiche tel quel, en français.
   ========================================================================== */

// Statuts encore ouverts (terminables) — cf. apps/voip/models.py Appel.Statut.
const STATUTS_OUVERTS = ['initie', 'sonnant', 'en_cours']

export default function VoipJournalPage() {
  const [appels, setAppels] = useState([])
  const [loading, setLoading] = useState(true)
  const [numero, setNumero] = useState('')
  const [message, setMessage] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  // WIR271 — clôture d'un appel ouvert (un seul formulaire inline à la fois).
  const [terminantId, setTerminantId] = useState(null)
  const [dureeSaisie, setDureeSaisie] = useState('')
  const [issueSaisie, setIssueSaisie] = useState('')
  const [terminerBusy, setTerminerBusy] = useState(false)
  const [terminerError, setTerminerError] = useState(null)

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

  // WIR271 — ouvre le formulaire de clôture, durée PRÉ-REMPLIE avec le temps
  // écoulé depuis `started_at` (éditable ensuite — jamais figée). `maintenant`
  // (Date.now()) est lu par l'APPELANT, dans le gestionnaire de clic
  // lui-même (react-hooks/purity : un impur comme Date.now() ne doit jamais
  // s'exécuter dans une fonction atteignable depuis le rendu — seul le corps
  // direct d'un event handler JSX l'est).
  function ouvrirTerminer(appel, maintenant) {
    const ecoulees = appel.started_at
      ? Math.max(
        0, Math.round((maintenant - new Date(appel.started_at).getTime()) / 1000))
      : 0
    setTerminantId(appel.id)
    setDureeSaisie(String(ecoulees))
    setIssueSaisie('')
    setTerminerError(null)
  }

  function annulerTerminer() {
    setTerminantId(null)
    setTerminerError(null)
  }

  async function confirmerTerminer(appel) {
    setTerminerBusy(true)
    setTerminerError(null)
    try {
      await voipApi.terminerAppel(appel.id, {
        duree_secondes: dureeSaisie,
        issue: issueSaisie.trim(),
      })
      setTerminantId(null)
      charger()
    } catch (err) {
      // Le 400 serveur (durée non entière) est déjà en français — affiché tel quel.
      setTerminerError(
        err?.response?.data?.duree_secondes || "Impossible de clôturer l'appel.")
    } finally {
      setTerminerBusy(false)
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
            {appels.map((a) => (
              <tr key={a.id}>
                <td>{a.direction}</td>
                <td>{a.numero}</td>
                <td>{a.cible?.libelle || '—'}</td>
                <td>{a.statut}{a.issue ? ` (${a.issue})` : ''}</td>
                <td>{a.started_at ? formatDateTime(a.started_at) : '—'}</td>
                <td>{a.duree_secondes != null ? `${a.duree_secondes}s` : '—'}</td>
                <td>
                  {!STATUTS_OUVERTS.includes(a.statut) ? '—'
                    : terminantId === a.id ? (
                      <div className="voip-journal__terminer">
                        <input
                          type="number"
                          aria-label="Durée (secondes)"
                          value={dureeSaisie}
                          onChange={(e) => setDureeSaisie(e.target.value)}
                        />
                        <input
                          type="text"
                          aria-label="Issue"
                          placeholder="répondu, sans réponse, messagerie…"
                          value={issueSaisie}
                          onChange={(e) => setIssueSaisie(e.target.value)}
                        />
                        <button type="button" disabled={terminerBusy}
                          onClick={() => confirmerTerminer(a)}>
                          Confirmer
                        </button>
                        <button type="button" disabled={terminerBusy}
                          onClick={annulerTerminer}>
                          Annuler
                        </button>
                        {terminerError && (
                          <p className="voip-journal__error" role="alert">
                            {terminerError}
                          </p>
                        )}
                      </div>
                    ) : (
                      <button type="button"
                        onClick={() => ouvrirTerminer(a, Date.now())}>
                        Terminer
                      </button>
                    )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
