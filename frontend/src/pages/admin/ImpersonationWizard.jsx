import { useCallback, useEffect, useState } from 'react'
import adminopsApi from '../../api/adminopsApi'

/**
 * NTADM32 — assistant « Demander une impersonation » (2 étapes).
 *
 * Réservé au staff support de l'éditeur : le SERVEUR porte la garde
 * (`is_taqinor_support`, sinon 403) — cet écran ne fait qu'afficher ce que
 * l'API autorise.
 *
 * Étape 1 : motif libre OBLIGATOIRE — impossible de passer à l'étape suivante
 * sans lui, et le serveur le revalide de toute façon (400 si vide).
 * Étape 2 : société + utilisateur cible, puis envoi de la demande.
 *
 * Envoyer NE DONNE AUCUN ACCÈS : la demande part en attente du consentement
 * explicite de l'Administrateur du tenant, qui voit ce motif tel quel.
 */
export default function ImpersonationWizard() {
  const [etape, setEtape] = useState(1)
  const [motif, setMotif] = useState('')
  const [societeId, setSocieteId] = useState('')
  const [cibleId, setCibleId] = useState('')
  const [societes, setSocietes] = useState([])
  const [utilisateurs, setUtilisateurs] = useState([])
  const [erreur, setErreur] = useState('')
  const [succes, setSucces] = useState('')
  const [envoi, setEnvoi] = useState(false)

  const chargerCibles = useCallback((societe) => (
    adminopsApi.ciblesImpersonation(societe ? { societe } : undefined)
      .then(({ data }) => {
        setSocietes(data.societes || [])
        setUtilisateurs(data.utilisateurs || [])
        setErreur('')
      })
      .catch((e) => {
        setErreur(
          e?.response?.status === 403
            ? "Réservé au staff support de l'éditeur."
            : 'Impossible de charger les cibles.'
        )
      })
  ), [])

  useEffect(() => { chargerCibles('') }, [chargerCibles])

  const motifValide = motif.trim().length > 0

  const allerEtape2 = () => {
    if (!motifValide) {
      setErreur('Le motif est obligatoire.')
      return
    }
    setErreur('')
    setEtape(2)
  }

  const changerSociete = (valeur) => {
    setSocieteId(valeur)
    setCibleId('')
    chargerCibles(valeur)
  }

  const envoyer = async () => {
    if (!motifValide) {
      setErreur('Le motif est obligatoire.')
      return
    }
    if (!cibleId) {
      setErreur('Choisissez un utilisateur à assister.')
      return
    }
    setEnvoi(true)
    try {
      await adminopsApi.demanderImpersonation({
        utilisateur_cible: Number(cibleId),
        motif: motif.trim(),
      })
      setSucces(
        "Demande envoyée. Aucune session n'est ouverte tant que "
        + "l'Administrateur du tenant ne l'a pas autorisée."
      )
      setErreur('')
      setMotif('')
      setCibleId('')
      setEtape(1)
    } catch (e) {
      setErreur(
        e?.response?.data?.detail || "Échec de l'envoi de la demande."
      )
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <div className="page-pad">
      <h2>Demander une session support</h2>
      <p className="text-muted">
        Une session d&apos;assistance n&apos;existe qu&apos;après le
        consentement explicite de l&apos;Administrateur du tenant. Le motif
        saisi ici lui est présenté tel quel.
      </p>

      {erreur && <div role="alert" className="text-danger">{erreur}</div>}
      {succes && <div role="status" className="text-success">{succes}</div>}

      <ol className="text-muted" data-testid="impersonation-etapes">
        <li aria-current={etape === 1 ? 'step' : undefined}>
          Étape 1 — Motif
        </li>
        <li aria-current={etape === 2 ? 'step' : undefined}>
          Étape 2 — Utilisateur à assister
        </li>
      </ol>

      {etape === 1 && (
        <div data-testid="impersonation-etape-1">
          <label htmlFor="imp-motif">Motif de la demande</label>
          <textarea
            id="imp-motif"
            rows={4}
            value={motif}
            onChange={(e) => setMotif(e.target.value)}
            placeholder="Ex. : diagnostic d'un devis bloqué (ticket #123)"
          />
          <div>
            <button
              type="button"
              onClick={allerEtape2}
              disabled={!motifValide}
            >
              Continuer
            </button>
          </div>
        </div>
      )}

      {etape === 2 && (
        <div data-testid="impersonation-etape-2">
          <div>
            <label htmlFor="imp-societe">Société</label>
            <select
              id="imp-societe"
              value={societeId}
              onChange={(e) => changerSociete(e.target.value)}
            >
              <option value="">Toutes les sociétés</option>
              {societes.map((s) => (
                <option key={s.id} value={s.id}>{s.nom}</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="imp-cible">Utilisateur à assister</label>
            <select
              id="imp-cible"
              value={cibleId}
              onChange={(e) => setCibleId(e.target.value)}
            >
              <option value="">Choisir…</option>
              {utilisateurs.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.username} — {u.societe_nom}
                </option>
              ))}
            </select>
          </div>
          <div>
            <button type="button" onClick={() => setEtape(1)}>
              Retour
            </button>
            <button type="button" onClick={envoyer} disabled={envoi}>
              Envoyer la demande
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
