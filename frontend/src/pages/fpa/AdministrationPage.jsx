import { useEffect, useState } from 'react'
import fpaApi from '../../api/fpaApi'
import { Button, Card, toast } from '../../ui'
import PageHeader from '../../components/layout/PageHeader'
import { downloadBlob } from '../../utils/downloadBlob'

/* ============================================================================
   WIR199 — Écran « Administration FP&A » (`/fpa/administration`, responsable/
   admin, comme le reste du module).
   ----------------------------------------------------------------------------
   L'écran de saisie budgétaire (SaisiePage) exigeait un cycle ET un
   département EXISTANTS — mais AUCUN écran ne permettait d'en créer : les
   deux devaient être ajoutés en admin Django. Cet écran ferme ce trou : arbre
   des départements (CRUD, hiérarchie via `parent`), cycles budgétaires
   (création, ouvrir-saisie/clore/dupliquer/export XLSX blob).
   ========================================================================== */

const TYPE_CYCLE = [['annuel', 'Annuel'], ['trimestriel', 'Trimestriel']]
const STATUT_CYCLE_LABELS = {
  brouillon: 'Brouillon', ouvert_saisie: 'Ouvert à la saisie',
  en_validation: 'En validation', clos: 'Clos',
}

function messageErreurAdmin(err, repli) {
  const data = err?.response?.data
  if (typeof data?.detail === 'string') return data.detail
  if (typeof data === 'string' && data) return data
  return repli
}

function listeDe(data) {
  if (Array.isArray(data)) return data
  if (data && Array.isArray(data.results)) return data.results
  return []
}

// Aplati l'arbre des départements en une liste plate { id, nom, profondeur }
// pour le sélecteur « Parent » (chaque niveau visuellement indenté).
function aplatirArbre(noeuds, profondeur = 0, out = []) {
  for (const n of noeuds) {
    out.push({ id: n.id, nom: n.nom, profondeur })
    if (n.enfants?.length) aplatirArbre(n.enfants, profondeur + 1, out)
  }
  return out
}

function NoeudDepartement({ noeud, profondeur, onToggleActif, onDelete }) {
  return (
    <>
      <li style={{ paddingLeft: profondeur * 20, display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0' }}>
        <span style={{ flex: 1 }}>
          {noeud.code ? `${noeud.code} — ` : ''}{noeud.nom}
          {!noeud.actif && <em style={{ marginLeft: 8, fontSize: 12 }}>(inactif)</em>}
        </span>
        <Button variant="ghost" size="sm" onClick={() => onToggleActif(noeud)}>
          {noeud.actif ? 'Désactiver' : 'Activer'}
        </Button>
        <Button variant="ghost" size="sm" onClick={() => onDelete(noeud)}>
          Supprimer
        </Button>
      </li>
      {(noeud.enfants ?? []).map((e) => (
        <NoeudDepartement key={e.id} noeud={e} profondeur={profondeur + 1}
          onToggleActif={onToggleActif} onDelete={onDelete} />
      ))}
    </>
  )
}

export default function AdministrationPage() {
  // ── Départements (arbre CRUD) ──────────────────────────────────────────
  const [arbre, setArbre] = useState([])
  const [chargementDept, setChargementDept] = useState(true)
  const [deptForm, setDeptForm] = useState({ code: '', nom: '', parent: '' })
  const [creantDept, setCreantDept] = useState(false)

  const chargerDepartements = () => {
    setChargementDept(true)
    return fpaApi.getDepartementsTree()
      .then((res) => setArbre(listeDe(res?.data)))
      .catch(() => toast.error('Impossible de charger les départements.'))
      .finally(() => setChargementDept(false))
  }

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { chargerDepartements() }, [])

  const departementsPlats = aplatirArbre(arbre)

  const creerDepartement = async () => {
    if (!deptForm.code.trim() || !deptForm.nom.trim()) return
    setCreantDept(true)
    try {
      await fpaApi.createDepartement({
        code: deptForm.code.trim(),
        nom: deptForm.nom.trim(),
        parent: deptForm.parent || undefined,
      })
      toast.success('Département créé.')
      setDeptForm({ code: '', nom: '', parent: '' })
      chargerDepartements()
    } catch (err) {
      toast.error(messageErreurAdmin(err, 'Création du département impossible.'))
    } finally {
      setCreantDept(false)
    }
  }

  const toggleActifDepartement = async (dept) => {
    try {
      await fpaApi.updateDepartement(dept.id, { actif: !dept.actif })
      chargerDepartements()
    } catch (err) {
      toast.error(messageErreurAdmin(err, 'Mise à jour impossible.'))
    }
  }

  const supprimerDepartement = async (dept) => {
    if (!window.confirm(`Supprimer le département « ${dept.nom} » ?`)) return
    try {
      await fpaApi.deleteDepartement(dept.id)
      toast.success('Département supprimé.')
      chargerDepartements()
    } catch (err) {
      toast.error(messageErreurAdmin(err, 'Suppression impossible (des lignes de budget y sont peut-être rattachées).'))
    }
  }

  // ── Cycles budgétaires (création + actions) ────────────────────────────
  const [cycles, setCycles] = useState([])
  const [chargementCycles, setChargementCycles] = useState(true)
  const [cycleForm, setCycleForm] = useState({ nom: '', date_debut: '', date_fin: '', type_cycle: 'annuel' })
  const [creantCycle, setCreantCycle] = useState(false)
  const [busyCycleId, setBusyCycleId] = useState(null)
  const [dupliquerNoms, setDupliquerNoms] = useState({}) // { [cycleId]: nouveau_nom }

  const chargerCycles = () => {
    setChargementCycles(true)
    return fpaApi.getCycles()
      .then((res) => setCycles(listeDe(res?.data)))
      .catch(() => toast.error('Impossible de charger les cycles.'))
      .finally(() => setChargementCycles(false))
  }

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { chargerCycles() }, [])

  const creerCycle = async () => {
    if (!cycleForm.nom.trim() || !cycleForm.date_debut || !cycleForm.date_fin) return
    setCreantCycle(true)
    try {
      await fpaApi.createCycle({
        nom: cycleForm.nom.trim(),
        date_debut: cycleForm.date_debut,
        date_fin: cycleForm.date_fin,
        type_cycle: cycleForm.type_cycle,
      })
      toast.success('Cycle créé.')
      setCycleForm({ nom: '', date_debut: '', date_fin: '', type_cycle: 'annuel' })
      chargerCycles()
    } catch (err) {
      toast.error(messageErreurAdmin(err, 'Création du cycle impossible.'))
    } finally {
      setCreantCycle(false)
    }
  }

  const ouvrirSaisieCycle = async (cycle) => {
    setBusyCycleId(cycle.id)
    try {
      await fpaApi.ouvrirSaisie(cycle.id)
      toast.success('Cycle ouvert à la saisie.')
      chargerCycles()
    } catch (err) {
      toast.error(messageErreurAdmin(err, 'Ouverture de la saisie impossible.'))
    } finally {
      setBusyCycleId(null)
    }
  }

  const clore = async (cycle) => {
    setBusyCycleId(cycle.id)
    try {
      await fpaApi.cloreCycle(cycle.id)
      toast.success('Cycle clos.')
      chargerCycles()
    } catch (err) {
      toast.error(messageErreurAdmin(err, 'Clôture impossible.'))
    } finally {
      setBusyCycleId(null)
    }
  }

  const dupliquer = async (cycle) => {
    const nouveauNom = (dupliquerNoms[cycle.id] || `${cycle.nom} (copie)`).trim()
    if (!nouveauNom) return
    setBusyCycleId(cycle.id)
    try {
      await fpaApi.dupliquerCycle(cycle.id, nouveauNom)
      toast.success('Cycle dupliqué.')
      setDupliquerNoms((n) => ({ ...n, [cycle.id]: '' }))
      chargerCycles()
    } catch (err) {
      toast.error(messageErreurAdmin(err, 'Duplication impossible.'))
    } finally {
      setBusyCycleId(null)
    }
  }

  const exporter = async (cycle) => {
    setBusyCycleId(cycle.id)
    try {
      const res = await fpaApi.exportCycle(cycle.id)
      downloadBlob(res.data, `budget-${cycle.nom}.xlsx`)
    } catch (err) {
      toast.error(messageErreurAdmin(err, 'Export impossible.'))
    } finally {
      setBusyCycleId(null)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Administration FP&A"
        subtitle="Départements (arbre) et cycles budgétaires — création, ouverture à la saisie, clôture, duplication, export"
      />

      <Card className="p-4 sm:p-5">
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>Départements</h3>
        {chargementDept && <p className="text-sm text-muted-foreground">Chargement…</p>}
        {!chargementDept && (
          <ul style={{ listStyle: 'none', padding: 0 }} data-testid="fpa-admin-departements">
            {arbre.map((n) => (
              <NoeudDepartement key={n.id} noeud={n} profondeur={0}
                onToggleActif={toggleActifDepartement} onDelete={supprimerDepartement} />
            ))}
            {arbre.length === 0 && (
              <li style={{ color: 'var(--muted-foreground, #64748b)' }}>Aucun département.</li>
            )}
          </ul>
        )}
        <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap', alignItems: 'center' }}>
          <input
            placeholder="Code"
            aria-label="Code du département"
            value={deptForm.code}
            onChange={(e) => setDeptForm((f) => ({ ...f, code: e.target.value }))}
            style={{ width: 100 }}
          />
          <input
            placeholder="Nom"
            aria-label="Nom du département"
            value={deptForm.nom}
            onChange={(e) => setDeptForm((f) => ({ ...f, nom: e.target.value }))}
          />
          <select
            aria-label="Département parent"
            value={deptForm.parent}
            onChange={(e) => setDeptForm((f) => ({ ...f, parent: e.target.value }))}
          >
            <option value="">— Aucun parent (racine) —</option>
            {departementsPlats.map((d) => (
              <option key={d.id} value={d.id}>{'—'.repeat(d.profondeur)} {d.nom}</option>
            ))}
          </select>
          <Button onClick={creerDepartement} disabled={creantDept || !deptForm.code.trim() || !deptForm.nom.trim()}>
            {creantDept ? 'Création…' : 'Créer le département'}
          </Button>
        </div>
      </Card>

      <Card className="p-4 sm:p-5">
        <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 8 }}>Cycles budgétaires</h3>
        {chargementCycles && <p className="text-sm text-muted-foreground">Chargement…</p>}
        {!chargementCycles && (
          <ul style={{ listStyle: 'none', padding: 0 }} data-testid="fpa-admin-cycles">
            {cycles.map((c) => (
              <li key={c.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 0', flexWrap: 'wrap' }}>
                <span style={{ flex: 1 }}>
                  {c.nom} — <em>{STATUT_CYCLE_LABELS[c.statut] || c.statut}</em>
                </span>
                <Button variant="ghost" size="sm" disabled={busyCycleId === c.id}
                        onClick={() => ouvrirSaisieCycle(c)}>
                  Ouvrir la saisie
                </Button>
                <Button variant="ghost" size="sm" disabled={busyCycleId === c.id}
                        onClick={() => clore(c)}>
                  Clore
                </Button>
                <input
                  placeholder="Nom de la copie"
                  aria-label={`Nom de la copie de ${c.nom}`}
                  value={dupliquerNoms[c.id] ?? ''}
                  onChange={(e) => setDupliquerNoms((n) => ({ ...n, [c.id]: e.target.value }))}
                  style={{ width: 140 }}
                />
                <Button variant="ghost" size="sm" disabled={busyCycleId === c.id}
                        onClick={() => dupliquer(c)}>
                  Dupliquer
                </Button>
                <Button variant="ghost" size="sm" disabled={busyCycleId === c.id}
                        onClick={() => exporter(c)}>
                  Exporter XLSX
                </Button>
              </li>
            ))}
            {cycles.length === 0 && (
              <li style={{ color: 'var(--muted-foreground, #64748b)' }}>Aucun cycle.</li>
            )}
          </ul>
        )}
        <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap', alignItems: 'center' }}>
          <input
            placeholder="Nom (ex. Budget 2027)"
            aria-label="Nom du cycle"
            value={cycleForm.nom}
            onChange={(e) => setCycleForm((f) => ({ ...f, nom: e.target.value }))}
          />
          <input
            type="date"
            aria-label="Date de début du cycle"
            value={cycleForm.date_debut}
            onChange={(e) => setCycleForm((f) => ({ ...f, date_debut: e.target.value }))}
          />
          <input
            type="date"
            aria-label="Date de fin du cycle"
            value={cycleForm.date_fin}
            onChange={(e) => setCycleForm((f) => ({ ...f, date_fin: e.target.value }))}
          />
          <select
            aria-label="Type de cycle"
            value={cycleForm.type_cycle}
            onChange={(e) => setCycleForm((f) => ({ ...f, type_cycle: e.target.value }))}
          >
            {TYPE_CYCLE.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <Button onClick={creerCycle}
                  disabled={creantCycle || !cycleForm.nom.trim() || !cycleForm.date_debut || !cycleForm.date_fin}>
            {creantCycle ? 'Création…' : 'Créer le cycle'}
          </Button>
        </div>
      </Card>
    </div>
  )
}
