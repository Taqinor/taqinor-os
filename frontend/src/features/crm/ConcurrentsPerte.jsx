import { useEffect, useState } from 'react'
import { Swords } from 'lucide-react'
import { Badge, Button, toast } from '../../ui'
import crmApi from '../../api/crmApi'
import { frenchError } from '../../lib/frenchError'

/* ============================================================================
   PACT103 — Concurrents sur affaires perdues (FG242). `crm.ConcurrentPerte`
   capture, sur un lead marqué perdu, le concurrent gagnant et son prix —
   aucun écran ne l'appelait, y compris le popover « perdu » existant.

   `litiges.Reclamation.concurrent_nom/concurrent_prix` capture le MÊME
   besoin métier sur un autre objet, sans unification (dette distincte,
   trou (c), HORS PÉRIMÈTRE ici) : cet écran construit `crm.ConcurrentPerte`
   tel qu'il existe aujourd'hui.
   ========================================================================== */

export default function ConcurrentsPerte() {
  const [recherche, setRecherche] = useState('')
  const [leads, setLeads] = useState([])
  const [chargementLeads, setChargementLeads] = useState(false)
  const leadsAffiches = recherche.trim() ? leads : []

  useEffect(() => {
    if (!recherche.trim()) return
    let cancelled = false
    crmApi.getLeads({ search: recherche })
      .then((res) => {
        if (cancelled) return
        const rows = res.data?.results ?? res.data ?? []
        setLeads(rows.filter((l) => l.perdu))
      })
      .catch(() => { if (!cancelled) setLeads([]) })
      .finally(() => { if (!cancelled) setChargementLeads(false) })
    return () => { cancelled = true }
  }, [recherche])

  const [leadSelectionne, setLeadSelectionne] = useState(null)
  const [concurrents, setConcurrents] = useState([])
  const [chargementConcurrents, setChargementConcurrents] = useState(false)

  const chargerConcurrents = (leadId) => {
    setChargementConcurrents(true)
    crmApi.getConcurrentsPerte({ lead: leadId })
      .then((res) => setConcurrents(res.data?.results ?? res.data ?? []))
      .catch(() => setConcurrents([]))
      .finally(() => setChargementConcurrents(false))
  }

  const choisirLead = (lead) => {
    setLeadSelectionne(lead)
    chargerConcurrents(lead.id)
  }

  const [form, setForm] = useState({
    concurrent_nom: '', concurrent_prix: '', devise: 'MAD', motif: '', notes: '',
  })
  const [saving, setSaving] = useState(false)

  const creer = async (event) => {
    event.preventDefault()
    if (!leadSelectionne || !form.concurrent_nom) return
    setSaving(true)
    try {
      await crmApi.createConcurrentPerte({
        lead: leadSelectionne.id,
        concurrent_nom: form.concurrent_nom,
        concurrent_prix: form.concurrent_prix || undefined,
        devise: form.devise,
        motif: form.motif,
        notes: form.notes,
      })
      toast.success('Concurrent enregistré.')
      setForm({ concurrent_nom: '', concurrent_prix: '', devise: 'MAD', motif: '', notes: '' })
      chargerConcurrents(leadSelectionne.id)
    } catch (err) {
      toast.error(frenchError(err, "Impossible d'enregistrer ce concurrent."))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <Swords size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Concurrents sur affaires perdues</h1>
      </div>

      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        <div style={{ minWidth: 260 }}>
          <input
            placeholder="Rechercher un lead perdu (nom, société…)"
            value={recherche}
            onChange={(e) => {
              const valeur = e.target.value
              if (valeur.trim()) setChargementLeads(true)
              setRecherche(valeur)
            }}
            aria-label="Rechercher un lead perdu"
            style={{ width: '100%', marginBottom: 8 }}
          />
          {chargementLeads && <p>Recherche…</p>}
          <ul style={{ listStyle: 'none', padding: 0 }}>
            {leadsAffiches.map((l) => (
              <li key={l.id}>
                <Button
                  type="button"
                  variant={leadSelectionne?.id === l.id ? 'default' : 'ghost'}
                  onClick={() => choisirLead(l)}
                  style={{ width: '100%', justifyContent: 'flex-start' }}
                >
                  {l.nom} {l.societe ? `— ${l.societe}` : ''}
                </Button>
              </li>
            ))}
            {!chargementLeads && recherche.trim() && leadsAffiches.length === 0 && (
              <li style={{ color: '#64748b' }}>Aucun lead perdu trouvé.</li>
            )}
          </ul>
        </div>

        <div style={{ flex: 1, minWidth: 300 }}>
          {!leadSelectionne && <p style={{ color: '#64748b' }}>Choisissez un lead perdu pour voir son analyse concurrentielle.</p>}
          {leadSelectionne && (
            <>
              <h2 style={{ fontSize: 15, fontWeight: 600 }}>
                {leadSelectionne.nom} <Badge tone="danger">Perdu</Badge>
              </h2>

              <form onSubmit={creer} style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
                <input
                  placeholder="Concurrent gagnant"
                  value={form.concurrent_nom}
                  onChange={(e) => setForm({ ...form, concurrent_nom: e.target.value })}
                  aria-label="Concurrent gagnant"
                  required
                />
                <input
                  type="number" step="0.01"
                  placeholder="Prix du concurrent"
                  value={form.concurrent_prix}
                  onChange={(e) => setForm({ ...form, concurrent_prix: e.target.value })}
                  aria-label="Prix du concurrent"
                  style={{ width: 130 }}
                />
                <input
                  placeholder="Motif"
                  value={form.motif}
                  onChange={(e) => setForm({ ...form, motif: e.target.value })}
                  aria-label="Motif de la perte"
                />
                <input
                  placeholder="Notes"
                  value={form.notes}
                  onChange={(e) => setForm({ ...form, notes: e.target.value })}
                  aria-label="Notes"
                />
                <Button type="submit" disabled={saving}>{saving ? 'Enregistrement…' : 'Enregistrer'}</Button>
              </form>

              {chargementConcurrents && <p>Chargement…</p>}
              {!chargementConcurrents && (
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr><th>Concurrent</th><th>Prix</th><th>Motif</th><th>Saisi par</th></tr>
                  </thead>
                  <tbody>
                    {concurrents.map((c) => (
                      <tr key={c.id}>
                        <td>{c.concurrent_nom}</td>
                        <td>{c.concurrent_prix != null ? `${c.concurrent_prix} ${c.devise}` : '—'}</td>
                        <td>{c.motif || '—'}</td>
                        <td>{c.saisi_par_nom || '—'}</td>
                      </tr>
                    ))}
                    {concurrents.length === 0 && (
                      <tr><td colSpan={4} style={{ textAlign: 'center', color: '#64748b' }}>Aucun concurrent saisi</td></tr>
                    )}
                  </tbody>
                </table>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
