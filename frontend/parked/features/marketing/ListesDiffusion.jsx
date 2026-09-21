import { useEffect, useState, useCallback } from 'react'
import marketingApi from '../../api/marketingApi'
import { parseCsv, buildLignesImport } from './csvImport'

/* ============================================================================
   NTMKT5 — Listes de diffusion (XMKT5) : CRUD + import CSV avec mapping +
   vue détail (abonnés, statut inscrit/désinscrit, historique d'adhésion).
   ----------------------------------------------------------------------------
   `marketing/listes-diffusion/` (CRUD), `<id>/importer/` (rapport
   ajoutés/doublons/ignorés-supprimés — dédoublonnage + respect de la
   suppression XMKT3 côté serveur, `apps.compta.services.
   importer_abonnements_liste`), `<id>/abonnes/?statut=` pour la vue détail.
   Un contact désinscrit n'est JAMAIS réactivé par un ré-import (comportement
   serveur — le rapport le montre en « ignorés/supprimés »).
   ========================================================================== */

const STATUTS_ABONNE = [
  { key: '', label: 'Tous' },
  { key: 'inscrit', label: 'Inscrit' },
  { key: 'desinscrit', label: 'Désinscrit' },
]

export default function ListesDiffusion() {
  const [listes, setListes] = useState([])
  const [loading, setLoading] = useState(true)
  const [nom, setNom] = useState('')
  const [description, setDescription] = useState('')
  const [err, setErr] = useState('')

  const [selectedId, setSelectedId] = useState(null)
  const [abonnes, setAbonnes] = useState([])
  const [statutFiltre, setStatutFiltre] = useState('')

  const [csv, setCsv] = useState(null) // { headers, rows }
  const [mapping, setMapping] = useState({ destinataire: '', contact_ref: '' })
  const [rapport, setRapport] = useState(null)
  const [importing, setImporting] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    marketingApi.listes.list()
      .then(r => setListes(marketingApi.unwrapList(r)))
      .catch(() => setListes([]))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  const creerListe = async (e) => {
    e.preventDefault()
    setErr('')
    try {
      await marketingApi.listes.create({ nom, description })
      setNom(''); setDescription('')
      load()
    } catch {
      setErr('Création impossible.')
    }
  }

  const ouvrirListe = (id) => {
    setSelectedId(id)
    setCsv(null); setRapport(null)
  }

  useEffect(() => {
    if (!selectedId) return
    marketingApi.listes.abonnes(selectedId, statutFiltre ? { statut: statutFiltre } : undefined)
      .then(r => setAbonnes(marketingApi.unwrapList(r)))
      .catch(() => setAbonnes([]))
  }, [selectedId, statutFiltre])

  const onFichier = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => {
      const parsed = parseCsv(String(reader.result))
      setCsv(parsed)
      setMapping({ destinataire: '', contact_ref: '' })
      setRapport(null)
    }
    reader.readAsText(file)
  }

  const lancerImport = async () => {
    if (!csv || !selectedId) return
    const lignes = buildLignesImport(csv.rows, mapping)
    setImporting(true)
    setErr('')
    try {
      const r = await marketingApi.listes.importer(selectedId, lignes)
      setRapport(r.data)
      // Recharge la table d'abonnés (statut courant) SANS effacer le rapport
      // qu'on vient d'afficher — `ouvrirListe` réinitialiserait `rapport`.
      const abonnesRes = await marketingApi.listes.abonnes(
        selectedId, statutFiltre ? { statut: statutFiltre } : undefined)
      setAbonnes(marketingApi.unwrapList(abonnesRes))
      load()
    } catch {
      setErr("Import impossible.")
    } finally {
      setImporting(false)
    }
  }

  const listeCourante = listes.find(l => l.id === selectedId)

  return (
    <div className="page">
      <div className="page-header"><h2>Listes de diffusion</h2></div>

      <form onSubmit={creerListe} style={{ display: 'flex', gap: '0.5rem',
        flexWrap: 'wrap', marginBottom: '1rem' }}>
        <input className="form-input" data-testid="liste-nom" placeholder="Nom"
          required value={nom} onChange={e => setNom(e.target.value)}
          style={{ flex: '1 1 200px' }} />
        <input className="form-input" data-testid="liste-description"
          placeholder="Description" value={description}
          onChange={e => setDescription(e.target.value)}
          style={{ flex: '2 1 260px' }} />
        <button type="submit" className="btn btn-primary" data-testid="liste-creer">
          Créer
        </button>
      </form>

      {err && <p style={{ color: '#dc2626' }}>{err}</p>}

      {loading
        ? <p className="page-loading">Chargement…</p>
        : (
          <table className="data-table" data-testid="listes-table">
            <thead><tr><th>Nom</th><th>Abonnés</th><th /></tr></thead>
            <tbody>
              {listes.map(l => (
                <tr key={l.id} data-testid="liste-row">
                  <td>{l.nom}</td>
                  <td>{l.nb_abonnes ?? 0}</td>
                  <td>
                    <button className="btn btn-light" type="button"
                      data-testid="liste-ouvrir" onClick={() => ouvrirListe(l.id)}>
                      Ouvrir
                    </button>
                  </td>
                </tr>
              ))}
              {listes.length === 0 && (
                <tr><td colSpan={3} style={{ textAlign: 'center', color: '#64748b' }}>
                  Aucune liste
                </td></tr>
              )}
            </tbody>
          </table>
        )}

      {listeCourante && (
        <section data-testid="liste-detail" style={{ marginTop: '1.5rem' }}>
          <h3>{listeCourante.nom} — abonnés</h3>
          <select className="form-input" data-testid="liste-filtre-statut"
            value={statutFiltre} onChange={e => setStatutFiltre(e.target.value)}
            style={{ marginBottom: 8 }}>
            {STATUTS_ABONNE.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
          </select>
          <table className="data-table" data-testid="abonnes-table">
            <thead><tr><th>Destinataire</th><th>Statut</th><th>Depuis</th></tr></thead>
            <tbody>
              {abonnes.map(a => (
                <tr key={a.id} data-testid="abonne-row">
                  <td>{a.destinataire}</td>
                  <td>{a.statut_display || a.statut}</td>
                  <td>{a.date_creation ? new Date(a.date_creation).toLocaleDateString('fr-FR') : '—'}</td>
                </tr>
              ))}
              {abonnes.length === 0 && (
                <tr><td colSpan={3} style={{ textAlign: 'center', color: '#64748b' }}>
                  Aucun abonné
                </td></tr>
              )}
            </tbody>
          </table>

          <h4 style={{ marginTop: '1rem' }}>Importer un fichier CSV</h4>
          <input type="file" accept=".csv,text/csv" data-testid="liste-import-fichier"
            onChange={onFichier} />
          {csv && (
            <div style={{ marginTop: 8 }}>
              <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
                <label style={{ fontSize: '0.82rem' }}>
                  Colonne destinataire
                  <select className="form-input" data-testid="liste-mapping-destinataire"
                    value={mapping.destinataire}
                    onChange={e => setMapping(m => ({ ...m, destinataire: e.target.value }))}>
                    <option value="">—</option>
                    {csv.headers.map((h, i) => <option key={i} value={i}>{h}</option>)}
                  </select>
                </label>
                <label style={{ fontSize: '0.82rem' }}>
                  Colonne référence contact (optionnel)
                  <select className="form-input" data-testid="liste-mapping-contact-ref"
                    value={mapping.contact_ref}
                    onChange={e => setMapping(m => ({ ...m, contact_ref: e.target.value }))}>
                    <option value="">—</option>
                    {csv.headers.map((h, i) => <option key={i} value={i}>{h}</option>)}
                  </select>
                </label>
              </div>
              <p style={{ fontSize: '0.8rem', color: '#64748b' }}>
                {csv.rows.length} ligne(s) détectée(s) dans le fichier.
              </p>
              <button className="btn btn-primary" type="button"
                data-testid="liste-lancer-import"
                disabled={importing || mapping.destinataire === ''}
                onClick={lancerImport}>
                {importing ? 'Import…' : 'Importer'}
              </button>
            </div>
          )}
          {rapport && (
            <p data-testid="liste-import-rapport" style={{ marginTop: 8 }}>
              Ajoutés : {rapport.ajoutes ?? 0} · Doublons : {rapport.doublons ?? 0} ·
              {' '}Ignorés/supprimés : {rapport.ignores_supprimes ?? 0}
            </p>
          )}
        </section>
      )}
    </div>
  )
}
