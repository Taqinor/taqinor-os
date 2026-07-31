import { useCallback, useEffect, useState } from 'react'
import { formatMAD } from '../../lib/format.js'
import immobilierApi from '../../api/immobilierApi'

/* ============================================================================
   WIR148 — Écran de gestion des Baux (`/immobilier/baux`).
   ----------------------------------------------------------------------------
   Tout le cycle de vie du bail (signature/révision/dépôt/échéancier/
   quittancement/impayés) est backend-only et déjà testé (NTPRO3-8) — cet
   écran est le SEUL client de ces endpoints. Même style volontairement
   minimal (HTML brut + data-testid, aucun composant @/ui) que les autres
   écrans immobilier existants (PatrimoineTree.jsx/ChargesPage.jsx) : ce
   module n'a pas encore été restylé sur le système de design.

   Créer un bail (`creer_bail`) le rend ``actif`` IMMÉDIATEMENT par défaut
   (services.py : « le cas d'usage courant : signer un bail le rend actif
   immédiatement ») — il n'existe pas de statut ``brouillon`` exposé par
   l'API en écriture. « Signer un nouveau bail » EST donc l'action de
   signature ; il n'y a pas de bouton « Signer » séparé.
   ========================================================================== */

function rowsFrom(data) {
  if (Array.isArray(data)) return data
  return data?.results ?? []
}

const BAIL_VIDE = {
  local: '', locataire: '', type_bail: 'habitation',
  date_debut: '', duree_mois: '12',
  loyer_mensuel_ht: '', charges_mensuelles_provisions: '0',
  depot_garantie: '0',
}

export default function BauxPage() {
  const [locaux, setLocaux] = useState([])
  const [locataires, setLocataires] = useState([])
  const [baux, setBaux] = useState([])
  const [loading, setLoading] = useState(true)
  const [erreur, setErreur] = useState(null)

  const [form, setForm] = useState(BAIL_VIDE)
  const [creating, setCreating] = useState(false)
  const [creerErreur, setCreerErreur] = useState(null)

  const [selectedId, setSelectedId] = useState(null)
  const [echeances, setEcheances] = useState([])

  const [revision, setRevision] = useState({ nouveau_loyer: '', date_effet: '', indice: '' })
  const [depotDate, setDepotDate] = useState('')
  const [restitution, setRestitution] = useState({ montant_retenu: '0', motif_retenue: '' })

  const [impayees, setImpayees] = useState([])

  // Fetch brut (sans reset synchrone loading/erreur) : partagé entre le
  // montage (effet ci-dessous — `loading` démarre déjà à `true`, donc aucun
  // setState synchrone n'est nécessaire avant le premier `await`,
  // react-hooks/set-state-in-effect) et `chargerListes` (rechargement après
  // mutation, appelé depuis les handlers d'événement signerBail/relancer).
  const fetchListes = useCallback(async () => {
    const [rLocaux, rLocataires, rBaux, rImpayees] = await Promise.all([
      immobilierApi.locaux.list(),
      immobilierApi.locataires.list(),
      immobilierApi.baux.list(),
      immobilierApi.echeancesLoyer.impayees(),
    ])
    setLocaux(rowsFrom(rLocaux.data))
    setLocataires(rowsFrom(rLocataires.data))
    setBaux(rowsFrom(rBaux.data))
    setImpayees(rowsFrom(rImpayees.data))
  }, [])

  const chargerListes = useCallback(async () => {
    setLoading(true)
    setErreur(null)
    try {
      await fetchListes()
    } catch {
      setErreur('Chargement des baux impossible.')
    } finally {
      setLoading(false)
    }
  }, [fetchListes])

  useEffect(() => {
    let annule = false
    fetchListes()
      .catch(() => { if (!annule) setErreur('Chargement des baux impossible.') })
      .finally(() => { if (!annule) setLoading(false) })
    return () => { annule = true }
  }, [fetchListes])

  const selected = baux.find((b) => b.id === selectedId) || null

  const chargerEcheances = useCallback(async (bailId) => {
    const res = await immobilierApi.echeancesLoyer.list({ bail: bailId })
    setEcheances(rowsFrom(res.data))
  }, [])

  const selectionner = useCallback((bail) => {
    setSelectedId(bail.id)
    setEcheances([])
    setRevision({ nouveau_loyer: '', date_effet: '', indice: '' })
    setDepotDate('')
    setRestitution({ montant_retenu: '0', motif_retenue: '' })
    chargerEcheances(bail.id)
  }, [chargerEcheances])

  const rafraichirBail = useCallback(async (bailId) => {
    const res = await immobilierApi.baux.get(bailId)
    setBaux((prev) => prev.map((b) => (b.id === bailId ? res.data : b)))
  }, [])

  const signerBail = useCallback(async (e) => {
    e.preventDefault()
    if (!form.local || !form.locataire || !form.date_debut) return
    setCreating(true)
    setCreerErreur(null)
    try {
      await immobilierApi.baux.create({
        ...form,
        duree_mois: Number(form.duree_mois),
        loyer_mensuel_ht: form.loyer_mensuel_ht,
        charges_mensuelles_provisions: form.charges_mensuelles_provisions,
        depot_garantie: form.depot_garantie,
      })
      setForm(BAIL_VIDE)
      await chargerListes()
    } catch (err) {
      setCreerErreur(err.response?.data?.detail || 'Signature du bail impossible.')
    } finally {
      setCreating(false)
    }
  }, [form, chargerListes])

  const reviser = useCallback(async (e) => {
    e.preventDefault()
    if (!selected || !revision.nouveau_loyer || !revision.date_effet) return
    await immobilierApi.baux.reviser(selected.id, revision)
    setRevision({ nouveau_loyer: '', date_effet: '', indice: '' })
    await rafraichirBail(selected.id)
  }, [selected, revision, rafraichirBail])

  const encaisserDepot = useCallback(async () => {
    if (!selected) return
    await immobilierApi.baux.encaisserDepot(
      selected.id, depotDate ? { date_reception: depotDate } : {})
    await rafraichirBail(selected.id)
  }, [selected, depotDate, rafraichirBail])

  const restituerDepot = useCallback(async (e) => {
    e.preventDefault()
    if (!selected) return
    await immobilierApi.baux.restituerDepot(selected.id, restitution)
    await rafraichirBail(selected.id)
  }, [selected, restitution, rafraichirBail])

  const genererEcheancier = useCallback(async () => {
    if (!selected) return
    await immobilierApi.baux.genererEcheancier(selected.id)
    await chargerEcheances(selected.id)
  }, [selected, chargerEcheances])

  const emettreQuittance = useCallback(async (echeanceId) => {
    await immobilierApi.echeancesLoyer.emettreQuittance(echeanceId)
    if (selected) await chargerEcheances(selected.id)
  }, [selected, chargerEcheances])

  const relancer = useCallback(async (echeanceId) => {
    await immobilierApi.echeancesLoyer.relancer(echeanceId, {})
    if (selected) await chargerEcheances(selected.id)
    await chargerListes()
  }, [selected, chargerEcheances, chargerListes])

  return (
    <div data-testid="baux-page" style={{ padding: 16 }}>
      <h1>Baux</h1>

      {loading && <p>Chargement…</p>}
      {erreur && <p role="alert">{erreur}</p>}

      {/* ── Signer un nouveau bail ── */}
      <h2>Signer un nouveau bail</h2>
      <form onSubmit={signerBail} data-testid="form-signer-bail" style={{ marginBottom: 24 }}>
        <select
          aria-label="Local" value={form.local}
          onChange={(e) => setForm((f) => ({ ...f, local: e.target.value }))}
        >
          <option value="">— Local —</option>
          {locaux.map((l) => (
            <option key={l.id} value={l.id}>{l.reference}</option>
          ))}
        </select>{' '}
        <select
          aria-label="Locataire" value={form.locataire}
          onChange={(e) => setForm((f) => ({ ...f, locataire: e.target.value }))}
        >
          <option value="">— Locataire —</option>
          {locataires.map((l) => (
            <option key={l.id} value={l.id}>{l.nom}</option>
          ))}
        </select>{' '}
        <select
          aria-label="Type de bail" value={form.type_bail}
          onChange={(e) => setForm((f) => ({ ...f, type_bail: e.target.value }))}
        >
          <option value="habitation">Habitation</option>
          <option value="commercial">Commercial</option>
        </select>{' '}
        <label>
          Début{' '}
          <input
            type="date" aria-label="Date de début" value={form.date_debut}
            onChange={(e) => setForm((f) => ({ ...f, date_debut: e.target.value }))}
          />
        </label>{' '}
        <label>
          Durée (mois){' '}
          <input
            type="number" aria-label="Durée en mois" value={form.duree_mois} style={{ width: 70 }}
            onChange={(e) => setForm((f) => ({ ...f, duree_mois: e.target.value }))}
          />
        </label>{' '}
        <label>
          Loyer mensuel HT{' '}
          <input
            type="number" step="any" aria-label="Loyer mensuel HT"
            value={form.loyer_mensuel_ht} style={{ width: 100 }}
            onChange={(e) => setForm((f) => ({ ...f, loyer_mensuel_ht: e.target.value }))}
          />
        </label>{' '}
        <label>
          Charges/mois{' '}
          <input
            type="number" step="any" aria-label="Charges mensuelles"
            value={form.charges_mensuelles_provisions} style={{ width: 90 }}
            onChange={(e) => setForm((f) => ({ ...f, charges_mensuelles_provisions: e.target.value }))}
          />
        </label>{' '}
        <label>
          Dépôt de garantie{' '}
          <input
            type="number" step="any" aria-label="Dépôt de garantie"
            value={form.depot_garantie} style={{ width: 90 }}
            onChange={(e) => setForm((f) => ({ ...f, depot_garantie: e.target.value }))}
          />
        </label>{' '}
        <button type="submit" disabled={creating}>Signer le bail</button>
        {creerErreur && <p role="alert">{creerErreur}</p>}
      </form>

      {/* ── Liste des baux ── */}
      <h2>Tous les baux</h2>
      <table data-testid="table-baux" style={{ marginBottom: 24 }}>
        <thead>
          <tr>
            <th>Local</th><th>Locataire</th><th>Type</th><th>Loyer HT</th>
            <th>Statut</th><th>Dépôt</th><th></th>
          </tr>
        </thead>
        <tbody>
          {baux.map((b) => (
            <tr key={b.id} data-testid={`ligne-bail-${b.id}`}>
              <td>{b.local_reference}</td>
              <td>{b.locataire_nom}</td>
              <td>{b.type_bail_display}</td>
              <td>{formatMAD(Number(b.loyer_mensuel_ht))}</td>
              <td>{b.statut_display}</td>
              <td>
                {b.depot_garantie_restitue ? 'Restitué'
                  : b.depot_garantie_recu ? 'Reçu' : 'À encaisser'}
              </td>
              <td>
                <button type="button" onClick={() => selectionner(b)}>Détails</button>
              </td>
            </tr>
          ))}
          {baux.length === 0 && !loading && (
            <tr><td colSpan={7}>Aucun bail.</td></tr>
          )}
        </tbody>
      </table>

      {/* ── Détail du bail sélectionné ── */}
      {selected && (
        <div data-testid="detail-bail" style={{ marginBottom: 24, border: '1px solid #ccc', padding: 12 }}>
          <h2>
            Bail — {selected.local_reference} / {selected.locataire_nom}
          </h2>
          <p>Loyer actuel : {formatMAD(Number(selected.loyer_mensuel_ht))}</p>

          <h3>Révision de loyer</h3>
          <form onSubmit={reviser} data-testid="form-reviser">
            <label>
              Nouveau loyer{' '}
              <input
                type="number" step="any" aria-label="Nouveau loyer"
                value={revision.nouveau_loyer}
                onChange={(e) => setRevision((r) => ({ ...r, nouveau_loyer: e.target.value }))}
              />
            </label>{' '}
            <label>
              Date d&apos;effet{' '}
              <input
                type="date" aria-label="Date d'effet de la révision"
                value={revision.date_effet}
                onChange={(e) => setRevision((r) => ({ ...r, date_effet: e.target.value }))}
              />
            </label>{' '}
            <button type="submit">Réviser</button>
          </form>
          {selected.revisions?.length > 0 && (
            <ul>
              {selected.revisions.map((r) => (
                <li key={r.id}>
                  {r.date_effet} : {formatMAD(Number(r.ancien_loyer))} → {formatMAD(Number(r.nouveau_loyer))}
                </li>
              ))}
            </ul>
          )}

          <h3>Dépôt de garantie</h3>
          {!selected.depot_garantie_recu ? (
            <p>
              <input
                type="date" aria-label="Date de réception du dépôt"
                value={depotDate}
                onChange={(e) => setDepotDate(e.target.value)}
              />{' '}
              <button type="button" onClick={encaisserDepot}>Encaisser le dépôt</button>
            </p>
          ) : !selected.depot_garantie_restitue ? (
            <form onSubmit={restituerDepot} data-testid="form-restituer-depot">
              <p>Dépôt reçu le {selected.date_reception_depot}.</p>
              <label>
                Montant retenu{' '}
                <input
                  type="number" step="any" aria-label="Montant retenu"
                  value={restitution.montant_retenu}
                  onChange={(e) => setRestitution((r) => ({ ...r, montant_retenu: e.target.value }))}
                />
              </label>{' '}
              <label>
                Motif{' '}
                <input
                  aria-label="Motif de la retenue"
                  value={restitution.motif_retenue}
                  onChange={(e) => setRestitution((r) => ({ ...r, motif_retenue: e.target.value }))}
                />
              </label>{' '}
              <button type="submit">Restituer le dépôt</button>
            </form>
          ) : (
            <p>Dépôt restitué le {selected.date_restitution}.</p>
          )}

          <h3>Échéancier</h3>
          <button type="button" onClick={genererEcheancier}>Générer l&apos;échéancier</button>
          <table data-testid="table-echeances">
            <thead>
              <tr><th>Période</th><th>Total</th><th>Statut</th><th></th></tr>
            </thead>
            <tbody>
              {echeances.map((ech) => (
                <tr key={ech.id}>
                  <td>{ech.periode_debut}</td>
                  <td>{formatMAD(Number(ech.montant_total))}</td>
                  <td>{ech.statut_display}</td>
                  <td>
                    {ech.statut === 'a_emettre' && (
                      <button type="button" onClick={() => emettreQuittance(ech.id)}>
                        Émettre quittance
                      </button>
                    )}
                    {ech.statut === 'emise' || ech.statut === 'payee' ? (
                      <a
                        href={immobilierApi.echeancesLoyer.quittancePdfUrl(ech.id)}
                        target="_blank" rel="noreferrer"
                      >
                        PDF
                      </a>
                    ) : null}
                    {(ech.statut === 'emise' || ech.statut === 'relancee') && (
                      <button type="button" onClick={() => relancer(ech.id)}>Relancer</button>
                    )}
                  </td>
                </tr>
              ))}
              {echeances.length === 0 && (
                <tr><td colSpan={4}>Aucune échéance générée.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Impayés (toutes échéances en retard, tous baux confondus) ── */}
      <h2>Impayés</h2>
      <table data-testid="table-impayees">
        <thead>
          <tr><th>Local</th><th>Locataire</th><th>Montant</th><th>Jours de retard</th><th></th></tr>
        </thead>
        <tbody>
          {impayees.map((it) => (
            <tr key={it.echeance_id}>
              <td>{it.local}</td>
              <td>{it.locataire}</td>
              <td>{formatMAD(Number(it.montant_total))}</td>
              <td>{it.jours_retard}</td>
              <td>
                <button type="button" onClick={() => relancer(it.echeance_id)}>Relancer</button>
              </td>
            </tr>
          ))}
          {impayees.length === 0 && !loading && (
            <tr><td colSpan={5}>Aucun impayé.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  )
}
