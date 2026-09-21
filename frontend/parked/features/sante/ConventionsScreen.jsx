import { useEffect, useState } from 'react'
import { Handshake, Plus } from 'lucide-react'
import { Badge, Button, toast } from '../../ui'
import santeApi from '../../api/santeApi'

/* ============================================================================
   WIR142 — Écran d'administration « Conventions & grilles tarifaires »
   (NTSAN8/NTSAN9). Deux listes : conventions (mutuelle/CNOPS/CNSS/cash) et
   leurs lignes de grille tarifaire par acte — consommées par la facturation
   (`selectors.tarif_applicable`).
   ========================================================================== */

const TYPE_OPTIONS = [
  { value: 'cnops', label: 'CNOPS' },
  { value: 'cnss', label: 'CNSS' },
  { value: 'mutuelle_privee', label: 'Mutuelle privée' },
  { value: 'cash', label: 'Cash' },
  { value: 'autre', label: 'Autre' },
]

const CONVENTION_VIDE = { nom: '', type: 'autre', taux_tiers_payant_pct: '0' }
const GRILLE_VIDE = { convention: '', acte: '', tarif_convention_ttc: '0', taux_prise_charge_pct: '0' }

export default function ConventionsScreen() {
  const [conventions, setConventions] = useState([])
  const [grilles, setGrilles] = useState([])
  const [actes, setActes] = useState([])
  const [loading, setLoading] = useState(true)
  const [formConvention, setFormConvention] = useState(CONVENTION_VIDE)
  const [formGrille, setFormGrille] = useState(GRILLE_VIDE)
  const [saving, setSaving] = useState(false)

  const load = () => {
    setLoading(true)
    Promise.all([
      santeApi.conventions.list(),
      santeApi.grillesTarifaires.list(),
      santeApi.actesMedicaux.list(),
    ])
      .then(([convRes, grillesRes, actesRes]) => {
        setConventions(convRes.data?.results ?? convRes.data ?? [])
        setGrilles(grillesRes.data?.results ?? grillesRes.data ?? [])
        setActes(actesRes.data?.results ?? actesRes.data ?? [])
      })
      .catch(() => toast.error('Impossible de charger les conventions.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
    load()
  }, [])

  const conventionNom = (id) => {
    const c = conventions.find((x) => x.id === Number(id))
    return c ? c.nom : `Convention #${id}`
  }
  const acteNom = (id) => {
    const a = actes.find((x) => x.id === Number(id))
    return a ? a.libelle : `Acte #${id}`
  }

  const creerConvention = async (e) => {
    e.preventDefault()
    if (!formConvention.nom.trim()) return
    setSaving(true)
    try {
      await santeApi.conventions.create(formConvention)
      toast.success('Convention créée.')
      setFormConvention(CONVENTION_VIDE)
      load()
    } catch {
      toast.error('Impossible de créer la convention.')
    } finally {
      setSaving(false)
    }
  }

  const creerGrille = async (e) => {
    e.preventDefault()
    if (!formGrille.convention || !formGrille.acte) return
    setSaving(true)
    try {
      await santeApi.grillesTarifaires.create(formGrille)
      toast.success('Ligne de grille ajoutée.')
      setFormGrille(GRILLE_VIDE)
      load()
    } catch {
      toast.error("Impossible d'ajouter la ligne de grille.")
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <Handshake size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Conventions &amp; grilles tarifaires</h1>
      </div>

      <h2 style={{ fontSize: 15, fontWeight: 600 }}>Conventions</h2>
      <form onSubmit={creerConvention} style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <input
          placeholder="Nom"
          value={formConvention.nom}
          onChange={(e) => setFormConvention({ ...formConvention, nom: e.target.value })}
          aria-label="Nom de la convention"
        />
        <select
          value={formConvention.type}
          onChange={(e) => setFormConvention({ ...formConvention, type: e.target.value })}
          aria-label="Type de convention"
        >
          {TYPE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <input
          type="number" step="any"
          placeholder="Taux tiers payant %"
          value={formConvention.taux_tiers_payant_pct}
          onChange={(e) => setFormConvention({ ...formConvention, taux_tiers_payant_pct: e.target.value })}
          aria-label="Taux tiers payant par défaut"
        />
        <Button type="submit" disabled={saving}>
          <Plus size={16} strokeWidth={1.75} aria-hidden="true" /> Ajouter
        </Button>
      </form>

      {loading && <p>Chargement…</p>}
      {!loading && (
        <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: 24 }}>
          <thead>
            <tr><th>Nom</th><th>Type</th><th>Taux tiers payant</th><th>Statut</th></tr>
          </thead>
          <tbody>
            {conventions.map((c) => (
              <tr key={c.id}>
                <td>{c.nom}</td>
                <td>{c.type_display || c.type}</td>
                <td>{c.taux_tiers_payant_pct}%</td>
                <td><Badge tone={c.actif ? 'success' : 'neutral'}>{c.actif ? 'Actif' : 'Inactif'}</Badge></td>
              </tr>
            ))}
            {conventions.length === 0 && (
              <tr><td colSpan={4} style={{ textAlign: 'center', color: '#64748b' }}>Aucune convention</td></tr>
            )}
          </tbody>
        </table>
      )}

      <h2 style={{ fontSize: 15, fontWeight: 600 }}>Grille tarifaire</h2>
      <form onSubmit={creerGrille} style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <select
          value={formGrille.convention}
          onChange={(e) => setFormGrille({ ...formGrille, convention: e.target.value })}
          aria-label="Convention"
        >
          <option value="">Convention…</option>
          {conventions.map((c) => <option key={c.id} value={c.id}>{c.nom}</option>)}
        </select>
        <select
          value={formGrille.acte}
          onChange={(e) => setFormGrille({ ...formGrille, acte: e.target.value })}
          aria-label="Acte médical"
        >
          <option value="">Acte…</option>
          {actes.map((a) => <option key={a.id} value={a.id}>{a.libelle}</option>)}
        </select>
        <input
          type="number" step="any"
          placeholder="Tarif convention TTC"
          value={formGrille.tarif_convention_ttc}
          onChange={(e) => setFormGrille({ ...formGrille, tarif_convention_ttc: e.target.value })}
          aria-label="Tarif convention TTC"
        />
        <input
          type="number" step="any"
          placeholder="Taux prise en charge %"
          value={formGrille.taux_prise_charge_pct}
          onChange={(e) => setFormGrille({ ...formGrille, taux_prise_charge_pct: e.target.value })}
          aria-label="Taux de prise en charge"
        />
        <Button type="submit" disabled={saving}>
          <Plus size={16} strokeWidth={1.75} aria-hidden="true" /> Ajouter
        </Button>
      </form>

      {!loading && (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr><th>Convention</th><th>Acte</th><th>Tarif convention TTC</th><th>Prise en charge</th></tr>
          </thead>
          <tbody>
            {grilles.map((g) => (
              <tr key={g.id}>
                <td>{conventionNom(g.convention)}</td>
                <td>{acteNom(g.acte)}</td>
                <td>{g.tarif_convention_ttc}</td>
                <td>{g.taux_prise_charge_pct}%</td>
              </tr>
            ))}
            {grilles.length === 0 && (
              <tr><td colSpan={4} style={{ textAlign: 'center', color: '#64748b' }}>Aucune ligne de grille</td></tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  )
}
