import { useEffect, useState } from 'react'
import { ClipboardList, Plus } from 'lucide-react'
import { Button, Badge, toast } from '../../ui'
import santeApi from '../../api/santeApi'

/* ============================================================================
   NTSAN7 — Paramétrage « Nomenclature des actes » : CRUD ActeMedical, soft-
   disable uniquement (jamais de suppression physique une fois l'acte
   utilisé — la désactivation passe par l'action serveur `desactiver`).
   ========================================================================== */

const CHAMPS_VIDES = {
  code_ngap: '', libelle: '', categorie: '', tarif_base_ttc: '0',
  cotation_lettre_cle: '',
}

export default function NomenclatureActesScreen() {
  const [actes, setActes] = useState([])
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState(CHAMPS_VIDES)
  const [saving, setSaving] = useState(false)

  const load = () => {
    setLoading(true)
    santeApi.actesMedicaux.list()
      .then((res) => setActes(res.data?.results ?? res.data ?? []))
      .catch(() => toast.error('Impossible de charger la nomenclature.'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const creer = async (e) => {
    e.preventDefault()
    if (!form.libelle.trim()) return
    setSaving(true)
    try {
      await santeApi.actesMedicaux.create(form)
      toast.success('Acte créé.')
      setForm(CHAMPS_VIDES)
      load()
    } catch {
      toast.error("Impossible de créer l'acte.")
    } finally {
      setSaving(false)
    }
  }

  const basculer = async (acte) => {
    try {
      if (acte.actif) await santeApi.actesMedicaux.desactiver(acte.id)
      else await santeApi.actesMedicaux.activer(acte.id)
      load()
    } catch {
      toast.error('Action impossible.')
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <ClipboardList size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>
          Nomenclature des actes
        </h1>
      </div>

      <form onSubmit={creer} style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <input
          placeholder="Libellé"
          value={form.libelle}
          onChange={(e) => setForm({ ...form, libelle: e.target.value })}
          aria-label="Libellé de l'acte"
        />
        <input
          placeholder="Code NGAP"
          value={form.code_ngap}
          onChange={(e) => setForm({ ...form, code_ngap: e.target.value })}
          aria-label="Code NGAP"
        />
        <input
          placeholder="Cotation (ex. C, K, Z)"
          value={form.cotation_lettre_cle}
          onChange={(e) => setForm({ ...form, cotation_lettre_cle: e.target.value })}
          aria-label="Cotation lettre clé"
        />
        <input
          type="number" step="any"
          placeholder="Tarif TTC"
          value={form.tarif_base_ttc}
          onChange={(e) => setForm({ ...form, tarif_base_ttc: e.target.value })}
          aria-label="Tarif de base TTC"
        />
        <Button type="submit" disabled={saving}>
          <Plus size={16} strokeWidth={1.75} aria-hidden="true" /> Ajouter
        </Button>
      </form>

      {loading && <p>Chargement…</p>}
      {!loading && (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th>Libellé</th>
              <th>Code NGAP</th>
              <th>Cotation</th>
              <th>Tarif TTC</th>
              <th>Statut</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {actes.map((acte) => (
              <tr key={acte.id}>
                <td>{acte.libelle}</td>
                <td>{acte.code_ngap}</td>
                <td>{acte.cotation_lettre_cle}</td>
                <td>{acte.tarif_base_ttc}</td>
                <td>
                  <Badge tone={acte.actif ? 'success' : 'neutral'}>
                    {acte.actif ? 'Actif' : 'Désactivé'}
                  </Badge>
                </td>
                <td>
                  <Button variant="ghost" onClick={() => basculer(acte)}>
                    {acte.actif ? 'Désactiver' : 'Réactiver'}
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
