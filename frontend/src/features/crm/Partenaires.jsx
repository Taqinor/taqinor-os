import { useEffect, useState } from 'react'
import { Handshake } from 'lucide-react'
import { Badge, Button, toast } from '../../ui'
import crmApi from '../../api/crmApi'
import { frenchError } from '../../lib/frenchError'

/* ============================================================================
   PACT102 — Partenaires : fiche, soumissions, commissions (FG234/235/237).
   Le portail externe montre déjà ce résumé EN LECTURE au partenaire ; cet
   écran est le côté INTERNE — agréer un partenaire, qualifier ses
   soumissions, régler ses commissions — qui n'existait nulle part.
   ========================================================================== */

const TYPE_LABEL = {
  apporteur: "Apporteur d'affaires", sous_revendeur: 'Sous-revendeur',
  installateur: 'Installateur',
}
const ONBOARDING_LABEL = {
  prospect: 'Prospect', en_cours: "En cours d'agrément",
  agree: 'Agréé', suspendu: 'Suspendu',
}
const ONBOARDING_TONE = {
  prospect: 'neutral', en_cours: 'warning', agree: 'success', suspendu: 'danger',
}
const SOUMISSION_LABEL = {
  soumis: 'Soumis', qualifie: 'Qualifié', converti: 'Converti', rejete: 'Rejeté',
}
const COMMISSION_LABEL = { due: 'Due', payee: 'Payée', annulee: 'Annulée' }
const COMMISSION_TONE = { due: 'warning', payee: 'success', annulee: 'neutral' }

export default function Partenaires() {
  const [partenaires, setPartenaires] = useState([])
  const [loading, setLoading] = useState(true)

  const chargerPartenaires = () => {
    setLoading(true)
    crmApi.getPartenaires()
      .then((res) => setPartenaires(res.data?.results ?? res.data ?? []))
      .catch(() => toast.error('Impossible de charger les partenaires.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { chargerPartenaires() }, [])

  const [form, setForm] = useState({
    nom: '', type_partenaire: 'apporteur', email: '', telephone: '', taux_commission: '',
  })
  const [saving, setSaving] = useState(false)

  const creerPartenaire = async (event) => {
    event.preventDefault()
    if (!form.nom) return
    setSaving(true)
    try {
      await crmApi.createPartenaire({
        nom: form.nom,
        type_partenaire: form.type_partenaire,
        email: form.email,
        telephone: form.telephone,
        taux_commission: form.taux_commission || 0,
      })
      toast.success('Partenaire créé.')
      setForm({ nom: '', type_partenaire: 'apporteur', email: '', telephone: '', taux_commission: '' })
      chargerPartenaires()
    } catch (err) {
      toast.error(frenchError(err, 'Impossible de créer ce partenaire.'))
    } finally {
      setSaving(false)
    }
  }

  // ── Partenaire sélectionné : agrément + soumissions + commissions ──────
  const [selectedId, setSelectedId] = useState(null)
  const selected = partenaires.find((p) => p.id === selectedId) || null
  const [soumissions, setSoumissions] = useState([])
  const [commissions, setCommissions] = useState([])
  const [acting, setActing] = useState(false)

  useEffect(() => {
    if (!selectedId) {
      setSoumissions([])
      setCommissions([])
      return
    }
    crmApi.getSoumissionsLeadPartenaire({ partenaire: selectedId })
      .then((res) => setSoumissions(res.data?.results ?? res.data ?? []))
      .catch(() => setSoumissions([]))
    crmApi.getCommissionsPartenaire({ partenaire: selectedId })
      .then((res) => setCommissions(res.data?.results ?? res.data ?? []))
      .catch(() => setCommissions([]))
  }, [selectedId])

  const agreer = async () => {
    if (!selected) return
    setActing(true)
    try {
      await crmApi.activerPartenaire(selected.id)
      toast.success('Partenaire agréé.')
      chargerPartenaires()
    } catch (err) {
      toast.error(frenchError(err, "Impossible d'agréer ce partenaire."))
    } finally {
      setActing(false)
    }
  }

  const qualifier = async (soumission) => {
    setActing(true)
    try {
      const res = await crmApi.qualifierSoumissionLeadPartenaire(soumission.id)
      const lead = res?.data
      if (lead?.lead_id) toast.success(`Soumission qualifiée — lead #${lead.lead_id}.`)
      else toast.success('Soumission qualifiée.')
      setSoumissions((list) => list.map((s) => (s.id === soumission.id ? lead : s)))
    } catch (err) {
      toast.error(frenchError(err, 'Impossible de qualifier cette soumission.'))
    } finally {
      setActing(false)
    }
  }

  const marquerPayee = async (commission) => {
    setActing(true)
    try {
      const res = await crmApi.marquerPayeeCommissionPartenaire(commission.id)
      toast.success('Commission marquée payée.')
      setCommissions((list) => list.map((c) => (c.id === commission.id ? res.data : c)))
    } catch (err) {
      toast.error(frenchError(err, 'Impossible de régler cette commission.'))
    } finally {
      setActing(false)
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <Handshake size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Partenaires</h1>
      </div>

      <form onSubmit={creerPartenaire} style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        <input
          placeholder="Nom / raison sociale"
          value={form.nom}
          onChange={(e) => setForm({ ...form, nom: e.target.value })}
          aria-label="Nom du partenaire"
          required
        />
        <select
          value={form.type_partenaire}
          onChange={(e) => setForm({ ...form, type_partenaire: e.target.value })}
          aria-label="Type de partenaire"
        >
          {Object.entries(TYPE_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <input
          placeholder="Email"
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
          aria-label="Email du partenaire"
        />
        <input
          placeholder="Téléphone"
          value={form.telephone}
          onChange={(e) => setForm({ ...form, telephone: e.target.value })}
          aria-label="Téléphone du partenaire"
        />
        <input
          type="number" step="0.01"
          placeholder="Taux de commission (%)"
          value={form.taux_commission}
          onChange={(e) => setForm({ ...form, taux_commission: e.target.value })}
          aria-label="Taux de commission"
          style={{ width: 90 }}
        />
        <Button type="submit" disabled={saving}>{saving ? 'Création…' : 'Créer le partenaire'}</Button>
      </form>

      {loading && <p>Chargement…</p>}
      {!loading && (
        <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 16 }}>
          <thead>
            <tr><th>Nom</th><th>Type</th><th>Taux</th><th>Statut</th><th /></tr>
          </thead>
          <tbody>
            {partenaires.map((p) => (
              <tr key={p.id}>
                <td>{p.nom}</td>
                <td>{TYPE_LABEL[p.type_partenaire] || p.type_partenaire}</td>
                <td>{p.taux_commission}%</td>
                <td>
                  <Badge tone={ONBOARDING_TONE[p.statut_onboarding] || 'neutral'}>
                    {ONBOARDING_LABEL[p.statut_onboarding] || p.statut_onboarding}
                  </Badge>
                </td>
                <td><Button variant="ghost" onClick={() => setSelectedId(p.id)}>Détails</Button></td>
              </tr>
            ))}
            {partenaires.length === 0 && (
              <tr><td colSpan={5} style={{ textAlign: 'center', color: '#64748b' }}>Aucun partenaire</td></tr>
            )}
          </tbody>
        </table>
      )}

      {selected && (
        <div style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: 16 }}>
          <h2 style={{ fontSize: 15, fontWeight: 600, marginTop: 0 }}>
            {selected.nom}{' '}
            <Badge tone={ONBOARDING_TONE[selected.statut_onboarding] || 'neutral'}>
              {ONBOARDING_LABEL[selected.statut_onboarding] || selected.statut_onboarding}
            </Badge>
          </h2>
          {selected.statut_onboarding !== 'agree' && (
            <Button type="button" onClick={agreer} disabled={acting} style={{ marginBottom: 16 }}>
              Agréer ce partenaire
            </Button>
          )}

          <h3 style={{ fontSize: 13, fontWeight: 600 }}>Soumissions de leads</h3>
          <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 16 }}>
            <thead><tr><th>Prospect</th><th>Ville</th><th>Statut</th><th /></tr></thead>
            <tbody>
              {soumissions.map((s) => (
                <tr key={s.id}>
                  <td>{s.nom_prospect}</td>
                  <td>{s.ville || '—'}</td>
                  <td>{SOUMISSION_LABEL[s.statut] || s.statut}{s.lead_id ? ` (lead #${s.lead_id})` : ''}</td>
                  <td>
                    {s.statut === 'soumis' && (
                      <Button variant="outline" size="sm" onClick={() => qualifier(s)} disabled={acting}>
                        Qualifier
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
              {soumissions.length === 0 && (
                <tr><td colSpan={4} style={{ textAlign: 'center', color: '#64748b' }}>Aucune soumission</td></tr>
              )}
            </tbody>
          </table>

          <h3 style={{ fontSize: 13, fontWeight: 600 }}>Commissions</h3>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead><tr><th>Base HT</th><th>Taux</th><th>Montant</th><th>Statut</th><th /></tr></thead>
            <tbody>
              {commissions.map((c) => (
                <tr key={c.id}>
                  <td>{c.base_ht}</td>
                  <td>{c.taux}%</td>
                  <td>{c.montant}</td>
                  <td><Badge tone={COMMISSION_TONE[c.statut] || 'neutral'}>{COMMISSION_LABEL[c.statut] || c.statut}</Badge></td>
                  <td>
                    {c.statut === 'due' && (
                      <Button variant="outline" size="sm" onClick={() => marquerPayee(c)} disabled={acting}>
                        Marquer payée
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
              {commissions.length === 0 && (
                <tr><td colSpan={5} style={{ textAlign: 'center', color: '#64748b' }}>Aucune commission</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
