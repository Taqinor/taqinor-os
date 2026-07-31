import { Wallet } from 'lucide-react'
import { Badge } from '../../ui'
import educationApi from '../../api/educationApi'
import useEducationResource from '../../features/education/useEducationResource'

/* ============================================================================
   WIR143 — Écran P1 « Échéancier scolarité » (NTEDU8). LECTURE SEULE :
   l'échéancier est généré exclusivement par le serveur à la validation d'une
   inscription — jamais créé/modifié depuis cet écran.
   ========================================================================== */

const STATUT_TONE = { a_venir: 'neutral', facturee: 'warning', payee: 'success', en_retard: 'danger' }

export default function EcheancierPage() {
  const { data: echeanciers, loading, error } = useEducationResource(educationApi.echeanciers.list)
  const { data: eleves } = useEducationResource(educationApi.eleves.list)

  const eleveNom = (id) => {
    const e = eleves.find((x) => x.id === Number(id))
    return e ? `${e.nom} ${e.prenom}` : `Élève #${id}`
  }

  if (loading) return <p>Chargement…</p>
  if (error) return <p role="alert">Impossible de charger l&apos;échéancier.</p>

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <Wallet size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Échéancier scolarité</h1>
      </div>
      <p style={{ color: '#64748b', marginBottom: 16 }}>
        Généré automatiquement à la validation de chaque inscription — lecture seule.
      </p>

      {echeanciers.map((ech) => (
        <div key={ech.id} style={{ border: '1px solid var(--border, #e5e7eb)', borderRadius: 8, padding: 12, marginBottom: 16 }}>
          <h2 style={{ fontSize: 15, fontWeight: 600, marginTop: 0 }}>
            {eleveNom(ech.eleve)} — Total {ech.montant_total} ({ech.nombre_echeances} échéance{ech.nombre_echeances > 1 ? 's' : ''})
          </h2>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr><th>Libellé</th><th>Montant</th><th>Échéance</th><th>Statut</th></tr>
            </thead>
            <tbody>
              {(ech.lignes || []).map((l) => (
                <tr key={l.id}>
                  <td>{l.libelle}</td>
                  <td>{l.montant}</td>
                  <td>{l.date_echeance}</td>
                  <td><Badge tone={STATUT_TONE[l.statut] || 'neutral'}>{l.statut}</Badge></td>
                </tr>
              ))}
              {(!ech.lignes || ech.lignes.length === 0) && (
                <tr><td colSpan={4} style={{ textAlign: 'center', color: '#64748b' }}>Aucune ligne</td></tr>
              )}
            </tbody>
          </table>
        </div>
      ))}
      {echeanciers.length === 0 && <p style={{ color: '#64748b' }}>Aucun échéancier généré.</p>}
    </div>
  )
}
