import { useEffect, useMemo, useState } from 'react'

import creditApi from '../../api/creditApi'
import { formatMAD, formatDate } from '../../lib/format'
import { frenchError } from '../../lib/frenchError'

/* ============================================================================
   PACT48 — Assurance-crédit : polices et encours garantis (NTCRD16/17/18).

   REGISTRE DÉCLARATIF : aucun appel à l'assureur. Allianz Trade, Coface,
   Atradius sont saisis à la main — ce que le serveur modélise déjà
   (`PoliceAssuranceCredit` / `EncoursGarantiClient`), sans qu'aucun écran ne
   l'ait jamais exposé. À NE PAS CONFONDRE avec l'écran « Polices » existant,
   qui gère les polices D'ENTREPRISE (RC pro, décennale) : autre modèle, autre
   backend, nom voisin seulement.

   LE POINT DUR — « non couvert » DIT, jamais supposé. Le serveur ne compte
   comme garanti qu'un encours `accorde` sous une police ACTIVE
   (`selectors.quota_assurance_utilise` → `garanti = None` sinon). Cet écran
   affiche donc `garantie_assurance: null` comme un état EXPLICITE
   (« Non couvert »), jamais comme un tiret ni un zéro qui laisserait croire à
   une couverture nulle mesurée.
   ========================================================================== */

const STATUTS = [
  ['accorde', 'Accordé'],
  ['refuse', 'Refusé'],
  ['en_attente', 'En attente'],
  ['reduit', 'Réduit'],
]
const LIBELLE_STATUT = Object.fromEntries(STATUTS)

const JOUR_MS = 24 * 60 * 60 * 1000

/** Jours restants avant `date_fin` (null si la police n'a pas d'échéance). */
function joursAvantEcheance(dateFin, maintenant = Date.now()) {
  if (!dateFin) return null
  const fin = new Date(dateFin).getTime()
  if (Number.isNaN(fin)) return null
  return Math.ceil((fin - maintenant) / JOUR_MS)
}

function EtatEcheance({ dateFin }) {
  const jours = joursAvantEcheance(dateFin)
  if (jours === null) return <span>Sans échéance</span>
  if (jours < 0) return <strong>Expirée</strong>
  if (jours <= 30) return <strong>Échéance proche ({jours} j)</strong>
  return <span>{formatDate(dateFin)}</span>
}

const POLICE_VIDE = {
  assureur: '', numero_police: '', date_debut: '', date_fin: '',
  taux_couverture_pct: '', plafond_global: '',
}
const ENCOURS_VIDE = {
  police: '', client: '', montant_garanti: '', statut_agrement: 'en_attente',
  date_agrement: '', reference_assureur: '',
}

function lignes(reponse) {
  const charge = reponse?.data
  if (Array.isArray(charge)) return charge
  if (Array.isArray(charge?.results)) return charge.results
  return []
}

export default function PolicesAssuranceCreditPage() {
  const [polices, setPolices] = useState([])
  const [encours, setEncours] = useState([])
  const [couverture, setCouverture] = useState([])
  const [erreur, setErreur] = useState(null)
  const [rechargement, setRechargement] = useState(0)
  const [formPolice, setFormPolice] = useState(POLICE_VIDE)
  const [formEncours, setFormEncours] = useState(ENCOURS_VIDE)
  const [occupe, setOccupe] = useState(false)

  useEffect(() => {
    let vivant = true
    Promise.all([
      creditApi.getPolicesAssurance(),
      creditApi.getEncoursGarantis(),
      creditApi.getExposition(),
    ])
      .then(([resPolices, resEncours, resExposition]) => {
        if (!vivant) return
        setPolices(lignes(resPolices))
        setEncours(lignes(resEncours))
        setCouverture(resExposition?.data?.resultats ?? [])
      })
      .catch((err) => {
        if (vivant) setErreur(frenchError(err, 'Chargement impossible.'))
      })
    return () => { vivant = false }
  }, [rechargement])

  const nomPolice = useMemo(() => {
    const table = {}
    polices.forEach((p) => {
      table[p.id] = `${p.assureur}${p.numero_police ? ` — ${p.numero_police}` : ''}`
    })
    return table
  }, [polices])

  async function creerPolice(event) {
    event.preventDefault()
    if (occupe) return
    setOccupe(true)
    setErreur(null)
    try {
      await creditApi.createPoliceAssurance({
        assureur: formPolice.assureur,
        numero_police: formPolice.numero_police,
        date_debut: formPolice.date_debut || null,
        date_fin: formPolice.date_fin || null,
        taux_couverture_pct: formPolice.taux_couverture_pct || null,
        plafond_global: formPolice.plafond_global || null,
      })
      setFormPolice(POLICE_VIDE)
      setRechargement((n) => n + 1)
    } catch (err) {
      setErreur(frenchError(err, "Enregistrement de la police impossible."))
    } finally {
      setOccupe(false)
    }
  }

  async function declarerEncours(event) {
    event.preventDefault()
    if (occupe) return
    setOccupe(true)
    setErreur(null)
    try {
      await creditApi.createEncoursGaranti({
        police: formEncours.police,
        client: formEncours.client,
        montant_garanti: formEncours.montant_garanti,
        statut_agrement: formEncours.statut_agrement,
        date_agrement: formEncours.date_agrement || null,
        reference_assureur: formEncours.reference_assureur,
      })
      setFormEncours({ ...ENCOURS_VIDE, police: formEncours.police })
      setRechargement((n) => n + 1)
    } catch (err) {
      setErreur(frenchError(err, "Déclaration de l'encours garanti impossible."))
    } finally {
      setOccupe(false)
    }
  }

  const nonCouverts = couverture.filter(
    (ligne) => ligne.garantie_assurance === null || ligne.garantie_assurance === undefined,
  )

  return (
    <div className="credit-assurance" data-testid="credit-assurance">
      <h3>Assurance-crédit — polices et encours garantis</h3>
      <p>
        Registre déclaratif : les polices et les agréments sont saisis à la main
        (aucune connexion assureur). Seul un encours « Accordé » sous une police
        active compte comme garanti.
      </p>
      {erreur && <p className="credit-assurance__error" role="alert">{erreur}</p>}

      <section data-testid="credit-assurance-polices">
        <h4>Polices</h4>
        {polices.length === 0 ? (
          <p>Aucune police déclarée.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Assureur</th>
                <th>N° de police</th>
                <th>Couverture</th>
                <th>Plafond global</th>
                <th>Échéance</th>
                <th>État</th>
              </tr>
            </thead>
            <tbody>
              {polices.map((p) => (
                <tr key={p.id}>
                  <td>{p.assureur}</td>
                  <td>{p.numero_police || '—'}</td>
                  <td>{p.taux_couverture_pct ? `${p.taux_couverture_pct} %` : '—'}</td>
                  <td>{p.plafond_global ? formatMAD(p.plafond_global) : '—'}</td>
                  <td><EtatEcheance dateFin={p.date_fin} /></td>
                  <td>{p.actif ? 'Active' : 'Inactive'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <form onSubmit={creerPolice}>
          <label htmlFor="police-assureur">Assureur</label>
          <input
            id="police-assureur"
            value={formPolice.assureur}
            onChange={(e) => setFormPolice({ ...formPolice, assureur: e.target.value })}
            required
          />
          <label htmlFor="police-numero">N° de police</label>
          <input
            id="police-numero"
            value={formPolice.numero_police}
            onChange={(e) => setFormPolice({ ...formPolice, numero_police: e.target.value })}
          />
          <label htmlFor="police-debut">Début</label>
          <input
            id="police-debut"
            type="date"
            value={formPolice.date_debut}
            onChange={(e) => setFormPolice({ ...formPolice, date_debut: e.target.value })}
          />
          <label htmlFor="police-fin">Échéance</label>
          <input
            id="police-fin"
            type="date"
            value={formPolice.date_fin}
            onChange={(e) => setFormPolice({ ...formPolice, date_fin: e.target.value })}
          />
          <label htmlFor="police-taux">Taux de couverture (%)</label>
          <input
            id="police-taux"
            type="number"
            step="any"
            value={formPolice.taux_couverture_pct}
            onChange={(e) => setFormPolice({ ...formPolice, taux_couverture_pct: e.target.value })}
          />
          <label htmlFor="police-plafond">Plafond global</label>
          <input
            id="police-plafond"
            type="number"
            step="any"
            value={formPolice.plafond_global}
            onChange={(e) => setFormPolice({ ...formPolice, plafond_global: e.target.value })}
          />
          <button type="submit" disabled={occupe}>Ajouter la police</button>
        </form>
      </section>

      <section data-testid="credit-assurance-encours">
        <h4>Encours garantis déclarés</h4>
        {encours.length === 0 ? (
          <p>Aucun encours garanti déclaré.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Police</th>
                <th>Client</th>
                <th>Montant garanti</th>
                <th>Agrément</th>
                <th>Date d’agrément</th>
                <th>Référence assureur</th>
              </tr>
            </thead>
            <tbody>
              {encours.map((e) => (
                <tr key={e.id}>
                  <td>{nomPolice[e.police] || `#${e.police}`}</td>
                  <td>{e.client}</td>
                  <td>{formatMAD(e.montant_garanti)}</td>
                  <td>{LIBELLE_STATUT[e.statut_agrement] || e.statut_agrement}</td>
                  <td>{e.date_agrement ? formatDate(e.date_agrement) : '—'}</td>
                  <td>{e.reference_assureur || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <form onSubmit={declarerEncours}>
          <label htmlFor="encours-police">Police</label>
          <select
            id="encours-police"
            value={formEncours.police}
            onChange={(e) => setFormEncours({ ...formEncours, police: e.target.value })}
            required
          >
            <option value="">Choisir une police</option>
            {polices.map((p) => (
              <option key={p.id} value={p.id}>{nomPolice[p.id]}</option>
            ))}
          </select>
          <label htmlFor="encours-client">Client</label>
          <select
            id="encours-client"
            value={formEncours.client}
            onChange={(e) => setFormEncours({ ...formEncours, client: e.target.value })}
            required
          >
            <option value="">Choisir un client</option>
            {couverture.map((ligne) => (
              <option key={ligne.client_id} value={ligne.client_id}>{ligne.client_nom}</option>
            ))}
          </select>
          <label htmlFor="encours-montant">Montant garanti</label>
          <input
            id="encours-montant"
            type="number"
            step="any"
            value={formEncours.montant_garanti}
            onChange={(e) => setFormEncours({ ...formEncours, montant_garanti: e.target.value })}
            required
          />
          <label htmlFor="encours-statut">Statut d’agrément</label>
          <select
            id="encours-statut"
            value={formEncours.statut_agrement}
            onChange={(e) => setFormEncours({ ...formEncours, statut_agrement: e.target.value })}
          >
            {STATUTS.map(([valeur, libelle]) => (
              <option key={valeur} value={valeur}>{libelle}</option>
            ))}
          </select>
          <label htmlFor="encours-date">Date d’agrément</label>
          <input
            id="encours-date"
            type="date"
            value={formEncours.date_agrement}
            onChange={(e) => setFormEncours({ ...formEncours, date_agrement: e.target.value })}
          />
          <label htmlFor="encours-reference">Référence assureur</label>
          <input
            id="encours-reference"
            value={formEncours.reference_assureur}
            onChange={(e) => setFormEncours({ ...formEncours, reference_assureur: e.target.value })}
          />
          <button type="submit" disabled={occupe}>Déclarer l’encours garanti</button>
        </form>
      </section>

      <section data-testid="credit-assurance-couverture">
        <h4>Couverture des clients</h4>
        <p>
          {nonCouverts.length} client(s) sans encours garanti déclaré — l’absence
          de couverture est un ÉTAT, pas une valeur nulle.
        </p>
        {couverture.length === 0 ? (
          <p>Aucun client à afficher.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Client</th>
                <th>Encours</th>
                <th>Garantie assureur</th>
                <th>Alerte</th>
              </tr>
            </thead>
            <tbody>
              {couverture.map((ligne) => {
                const couvert = ligne.garantie_assurance !== null
                  && ligne.garantie_assurance !== undefined
                return (
                  <tr key={ligne.client_id}>
                    <td>{ligne.client_nom}</td>
                    <td>{formatMAD(ligne.encours)}</td>
                    <td>
                      {couvert
                        ? formatMAD(ligne.garantie_assurance)
                        : <strong>Non couvert</strong>}
                    </td>
                    <td>
                      {ligne.depasse_garantie
                        ? 'Encours au-dessus de la garantie assureur'
                        : '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}
