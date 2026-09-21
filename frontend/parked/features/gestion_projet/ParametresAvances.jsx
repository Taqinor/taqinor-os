import { useEffect, useMemo, useState } from 'react'

import gestionProjetApi from '../../api/gestionProjetApi'
import { formatDate } from '../../lib/format'
import { errMessage } from './constants'

/* ============================================================================
   PACT78 — Paramètres avancés du module Projet : trois ressources servies par
   le backend et qu'AUCUN écran ne pilotait.

   1. VERROUILLAGE D'UN MOIS sur les feuilles de temps (XPRJ1) — une période
      verrouillée interdit toute saisie/édition de `Timesheet` sur ce mois ;
      déverrouiller = supprimer la ligne. `verrouille_par` est posé par le
      serveur, jamais envoyé d'ici.
   2. LIEN DE PORTAIL PROJET (PROJ37) — le portail public FONCTIONNE déjà
      (`/gestion-projet/portail/<token>/`, sans login, aucun coût ni marge) ;
      il manquait la moitié administration : générer et révoquer le lien. Le
      `token` est généré CÔTÉ SERVEUR (jamais fabriqué ici) ; révoquer est un
      kill-switch (`actif: false`), pas une suppression.
   3. GABARITS DE TÂCHES RÉCURRENTES (XPRJ13) — cet écran définit le gabarit ;
      la GÉNÉRATION reste une commande serveur
      (`manage.py generer_taches_recurrentes`). Rien n'est généré ici, et
      `nb_generees` reste en lecture seule.
   ========================================================================== */

const REGLES = [
  ['hebdomadaire', 'Hebdomadaire'],
  ['mensuelle', 'Mensuelle'],
]

const RECURRENCE_VIDE = {
  projet: '', libelle: '', regle: 'hebdomadaire', intervalle: '1',
  prochaine_echeance: '',
}

function listeDe(reponse) {
  const charge = reponse?.data
  if (Array.isArray(charge)) return charge
  if (Array.isArray(charge?.results)) return charge.results
  return []
}

// SCA29 (marque blanche) : aucun domaine de marque en dur. Le site public du
// tenant se configure par `VITE_PUBLIC_SITE_URL` ; à défaut on retombe sur
// l'origine courante — le précédent du dépôt pour un lien public tokenisé
// (ECataloguePage, GedNavigator, EnqueteBuilder, DashboardSharePage…).
function lienPortail(token) {
  const base = (import.meta.env.VITE_PUBLIC_SITE_URL || window.location.origin)
    .replace(/\/+$/, '')
  return `${base}/gestion-projet/portail/${token}/`
}

export default function ParametresAvances() {
  const [projets, setProjets] = useState([])
  const [periodes, setPeriodes] = useState([])
  const [tokens, setTokens] = useState([])
  const [recurrences, setRecurrences] = useState([])
  const [erreur, setErreur] = useState(null)
  const [rechargement, setRechargement] = useState(0)
  const [mois, setMois] = useState('')
  const [projetPortail, setProjetPortail] = useState('')
  const [formRecurrence, setFormRecurrence] = useState(RECURRENCE_VIDE)
  const [occupe, setOccupe] = useState(false)

  useEffect(() => {
    let vivant = true
    Promise.all([
      gestionProjetApi.getProjets(),
      gestionProjetApi.getPeriodesVerrouillees(),
      gestionProjetApi.getPortailTokens(),
      gestionProjetApi.getRecurrencesTache(),
    ])
      .then(([resProjets, resPeriodes, resTokens, resRecurrences]) => {
        if (!vivant) return
        setProjets(listeDe(resProjets))
        setPeriodes(listeDe(resPeriodes))
        setTokens(listeDe(resTokens))
        setRecurrences(listeDe(resRecurrences))
      })
      .catch((err) => {
        if (vivant) setErreur(errMessage(err, 'Chargement impossible.'))
      })
    return () => { vivant = false }
  }, [rechargement])

  const nomProjet = useMemo(() => {
    const table = {}
    projets.forEach((p) => {
      table[p.id] = p.code ? `${p.code} — ${p.nom || ''}`.trim() : (p.nom || `#${p.id}`)
    })
    return table
  }, [projets])

  async function agir(action, messageErreur) {
    if (occupe) return
    setOccupe(true)
    setErreur(null)
    try {
      await action()
      setRechargement((n) => n + 1)
    } catch (err) {
      setErreur(errMessage(err, messageErreur))
    } finally {
      setOccupe(false)
    }
  }

  async function verrouillerMois(event) {
    event.preventDefault()
    if (!mois) return
    // Le serveur attend le 1er jour du mois (`PeriodeVerrouilleeTemps.mois`).
    await agir(
      () => gestionProjetApi.createPeriodeVerrouillee({ mois: `${mois}-01` }),
      'Verrouillage impossible.',
    )
    setMois('')
  }

  async function genererLienPortail(event) {
    event.preventDefault()
    if (!projetPortail) return
    await agir(
      () => gestionProjetApi.createPortailToken({ projet: projetPortail }),
      'Génération du lien impossible.',
    )
  }

  async function creerRecurrence(event) {
    event.preventDefault()
    await agir(
      () => gestionProjetApi.createRecurrenceTache({
        projet: formRecurrence.projet,
        libelle: formRecurrence.libelle,
        regle: formRecurrence.regle,
        intervalle: Number(formRecurrence.intervalle) || 1,
        prochaine_echeance: formRecurrence.prochaine_echeance,
      }),
      'Création du gabarit impossible.',
    )
    setFormRecurrence(RECURRENCE_VIDE)
  }

  return (
    <div className="projet-parametres" data-testid="projet-parametres-avances">
      <h3>Paramètres avancés du module Projet</h3>
      {erreur && <p className="projet-parametres__error" role="alert">{erreur}</p>}

      <section data-testid="projet-parametres-verrous">
        <h4>Verrouillage des feuilles de temps</h4>
        <p>
          Un mois verrouillé interdit toute saisie ou modification de temps sur
          cette période. Déverrouiller retire le verrou.
        </p>
        {periodes.length === 0 ? (
          <p>Aucun mois verrouillé.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Mois</th>
                <th>Verrouillé par</th>
                <th>Depuis</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {periodes.map((p) => (
                <tr key={p.id} data-testid={`periode-verrouillee-${p.id}`}>
                  <td>{formatDate(p.mois)}</td>
                  <td>{p.verrouille_par_nom || '—'}</td>
                  <td>{p.date_creation ? formatDate(p.date_creation) : '—'}</td>
                  <td>
                    <button
                      type="button"
                      disabled={occupe}
                      onClick={() => agir(
                        () => gestionProjetApi.deletePeriodeVerrouillee(p.id),
                        'Déverrouillage impossible.',
                      )}
                    >
                      Déverrouiller
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <form onSubmit={verrouillerMois}>
          <label htmlFor="verrou-mois">Mois à verrouiller</label>
          <input
            id="verrou-mois"
            type="month"
            value={mois}
            onChange={(e) => setMois(e.target.value)}
            required
          />
          <button type="submit" disabled={occupe || !mois}>
            Verrouiller le mois
          </button>
        </form>
      </section>

      <section data-testid="projet-parametres-portail">
        <h4>Lien de portail projet</h4>
        <p>
          Le portail client est public et en lecture seule (aucun coût, aucune
          marge). Le lien est généré par le serveur ; le révoquer le coupe
          immédiatement sans supprimer l’historique.
        </p>
        {tokens.length === 0 ? (
          <p>Aucun lien de portail généré.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Projet</th>
                <th>Lien public</th>
                <th>État</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {tokens.map((t) => (
                <tr key={t.id} data-testid={`portail-token-${t.id}`}>
                  <td>{t.projet_code || nomProjet[t.projet] || `#${t.projet}`}</td>
                  <td><code>{lienPortail(t.token)}</code></td>
                  <td>{t.actif ? 'Actif' : 'Révoqué'}</td>
                  <td>
                    {t.actif ? (
                      <button
                        type="button"
                        disabled={occupe}
                        onClick={() => agir(
                          () => gestionProjetApi.updatePortailToken(t.id, { actif: false }),
                          'Révocation impossible.',
                        )}
                      >
                        Révoquer
                      </button>
                    ) : (
                      <button
                        type="button"
                        disabled={occupe}
                        onClick={() => agir(
                          () => gestionProjetApi.updatePortailToken(t.id, { actif: true }),
                          'Réactivation impossible.',
                        )}
                      >
                        Réactiver
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <form onSubmit={genererLienPortail}>
          <label htmlFor="portail-projet">Projet</label>
          <select
            id="portail-projet"
            value={projetPortail}
            onChange={(e) => setProjetPortail(e.target.value)}
            required
          >
            <option value="">Choisir un projet…</option>
            {projets.map((p) => (
              <option key={p.id} value={p.id}>{nomProjet[p.id]}</option>
            ))}
          </select>
          <button type="submit" disabled={occupe || !projetPortail}>
            Générer le lien
          </button>
        </form>
      </section>

      <section data-testid="projet-parametres-recurrences">
        <h4>Gabarits de tâches récurrentes</h4>
        <p>
          Un gabarit décrit la tâche à créer et son rythme. La génération reste
          une commande serveur : cet écran ne crée aucune tâche.
        </p>
        {recurrences.length === 0 ? (
          <p>Aucun gabarit de tâche récurrente.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Libellé</th>
                <th>Projet</th>
                <th>Rythme</th>
                <th>Prochaine échéance</th>
                <th>Générées</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {recurrences.map((r) => (
                <tr key={r.id} data-testid={`recurrence-tache-${r.id}`}>
                  <td>{r.libelle}</td>
                  <td>{r.projet_code || nomProjet[r.projet] || `#${r.projet}`}</td>
                  <td>
                    {r.regle_display || r.regle}
                    {r.intervalle > 1 ? ` (tous les ${r.intervalle})` : ''}
                  </td>
                  <td>{r.prochaine_echeance ? formatDate(r.prochaine_echeance) : '—'}</td>
                  <td>{r.nb_generees ?? 0}</td>
                  <td>
                    <button
                      type="button"
                      disabled={occupe}
                      onClick={() => agir(
                        () => gestionProjetApi.deleteRecurrenceTache(r.id),
                        'Suppression impossible.',
                      )}
                    >
                      Supprimer
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <form onSubmit={creerRecurrence}>
          <label htmlFor="recurrence-projet">Projet du gabarit</label>
          <select
            id="recurrence-projet"
            value={formRecurrence.projet}
            onChange={(e) => setFormRecurrence({ ...formRecurrence, projet: e.target.value })}
            required
          >
            <option value="">Choisir un projet…</option>
            {projets.map((p) => (
              <option key={p.id} value={p.id}>{nomProjet[p.id]}</option>
            ))}
          </select>
          <label htmlFor="recurrence-libelle">Libellé de la tâche</label>
          <input
            id="recurrence-libelle"
            value={formRecurrence.libelle}
            onChange={(e) => setFormRecurrence({ ...formRecurrence, libelle: e.target.value })}
            required
          />
          <label htmlFor="recurrence-regle">Règle</label>
          <select
            id="recurrence-regle"
            value={formRecurrence.regle}
            onChange={(e) => setFormRecurrence({ ...formRecurrence, regle: e.target.value })}
          >
            {REGLES.map(([valeur, libelle]) => (
              <option key={valeur} value={valeur}>{libelle}</option>
            ))}
          </select>
          <label htmlFor="recurrence-intervalle">Intervalle</label>
          <input
            id="recurrence-intervalle"
            type="number"
            min="1"
            step="1"
            value={formRecurrence.intervalle}
            onChange={(e) => setFormRecurrence({ ...formRecurrence, intervalle: e.target.value })}
          />
          <label htmlFor="recurrence-echeance">Prochaine échéance</label>
          <input
            id="recurrence-echeance"
            type="date"
            value={formRecurrence.prochaine_echeance}
            onChange={(e) => setFormRecurrence({
              ...formRecurrence, prochaine_echeance: e.target.value,
            })}
            required
          />
          <button type="submit" disabled={occupe}>Créer le gabarit</button>
        </form>
      </section>
    </div>
  )
}
