import { useState } from 'react'
import { ClipboardCheck, Plus } from 'lucide-react'
import { Badge, Button, toast } from '../../ui'
import educationApi from '../../api/educationApi'
import useEducationResource from '../../features/education/useEducationResource'

/* ============================================================================
   WIR143 — Écran P1 « Inscriptions » (NTEDU3/4/5). Workflow
   valider/refuser/affecter-classe/désinscrire/promouvoir passe TOUJOURS par
   les actions serveur dédiées — jamais une mutation directe de statut côté
   client. La liste d'attente FIFO est recalculée côté serveur.
   ========================================================================== */

const STATUT_TONE = {
  en_attente: 'neutral', validee: 'success', refusee: 'danger', liste_attente: 'warning',
}

export default function InscriptionsPage() {
  const { data: inscriptions, loading, reload } = useEducationResource(educationApi.inscriptions.list)
  const { data: eleves } = useEducationResource(educationApi.eleves.list)
  const { data: annees } = useEducationResource(educationApi.anneesScolaires.list)
  const { data: classes } = useEducationResource(educationApi.classes.list)

  const [form, setForm] = useState({ eleve: '', annee_scolaire: '', classe_demandee: '' })
  const [saving, setSaving] = useState(false)

  const eleveNom = (id) => {
    const e = eleves.find((x) => x.id === Number(id))
    return e ? `${e.nom} ${e.prenom}` : `Élève #${id}`
  }
  const anneeNom = (id) => annees.find((a) => a.id === Number(id))?.libelle || `Année #${id}`
  const classeNom = (id) => (id ? (classes.find((c) => c.id === Number(id))?.nom || `Classe #${id}`) : '—')

  const creer = async (e) => {
    e.preventDefault()
    if (!form.eleve || !form.annee_scolaire) return
    setSaving(true)
    try {
      await educationApi.inscriptions.create(form)
      toast.success('Inscription créée.')
      setForm({ eleve: '', annee_scolaire: form.annee_scolaire, classe_demandee: '' })
      reload()
    } catch {
      toast.error("Impossible de créer l'inscription.")
    } finally {
      setSaving(false)
    }
  }

  const agir = async (action, inscription) => {
    try {
      if (action === 'valider') await educationApi.inscriptions.valider(inscription.id)
      else if (action === 'refuser') await educationApi.inscriptions.refuser(inscription.id)
      else if (action === 'desinscrire') await educationApi.inscriptions.desinscrire(inscription.id)
      else if (action === 'affecter') {
        if (!inscription.classe_demandee) {
          toast.error('Aucune classe demandée à affecter.')
          return
        }
        await educationApi.inscriptions.affecterClasse(inscription.id, inscription.classe_demandee)
      }
      toast.success('Action effectuée.')
      reload()
    } catch {
      toast.error('Action impossible.')
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <ClipboardCheck size={20} strokeWidth={1.75} aria-hidden="true" />
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>Inscriptions</h1>
      </div>

      <form onSubmit={creer} style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <select value={form.eleve} onChange={(e) => setForm({ ...form, eleve: e.target.value })} aria-label="Élève">
          <option value="">Élève…</option>
          {eleves.map((el) => <option key={el.id} value={el.id}>{el.nom} {el.prenom}</option>)}
        </select>
        <select value={form.annee_scolaire} onChange={(e) => setForm({ ...form, annee_scolaire: e.target.value })} aria-label="Année scolaire">
          <option value="">Année scolaire…</option>
          {annees.map((a) => <option key={a.id} value={a.id}>{a.libelle}</option>)}
        </select>
        <select value={form.classe_demandee} onChange={(e) => setForm({ ...form, classe_demandee: e.target.value })} aria-label="Classe demandée">
          <option value="">Classe demandée (option.)…</option>
          {classes.map((c) => <option key={c.id} value={c.id}>{c.nom}</option>)}
        </select>
        <Button type="submit" disabled={saving}><Plus size={16} strokeWidth={1.75} aria-hidden="true" /> Créer</Button>
      </form>

      {loading && <p>Chargement…</p>}
      {!loading && (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr><th>Élève</th><th>Année</th><th>Classe demandée</th><th>Classe affectée</th><th>Statut</th><th /></tr>
          </thead>
          <tbody>
            {inscriptions.map((i) => (
              <tr key={i.id}>
                <td>{eleveNom(i.eleve)}</td>
                <td>{anneeNom(i.annee_scolaire)}</td>
                <td>{classeNom(i.classe_demandee)}</td>
                <td>{classeNom(i.classe_affectee)}</td>
                <td><Badge tone={STATUT_TONE[i.statut] || 'neutral'}>{i.statut}</Badge></td>
                <td style={{ display: 'flex', gap: 4 }}>
                  {i.statut === 'en_attente' && (
                    <>
                      <Button variant="ghost" onClick={() => agir('valider', i)}>Valider</Button>
                      <Button variant="ghost" onClick={() => agir('refuser', i)}>Refuser</Button>
                    </>
                  )}
                  {i.statut === 'validee' && !i.classe_affectee && (
                    <Button variant="ghost" onClick={() => agir('affecter', i)}>Affecter la classe</Button>
                  )}
                  {(i.statut === 'validee' || i.statut === 'liste_attente') && (
                    <Button variant="ghost" onClick={() => agir('desinscrire', i)}>Désinscrire</Button>
                  )}
                </td>
              </tr>
            ))}
            {inscriptions.length === 0 && (
              <tr><td colSpan={6} style={{ textAlign: 'center', color: '#64748b' }}>Aucune inscription</td></tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  )
}
