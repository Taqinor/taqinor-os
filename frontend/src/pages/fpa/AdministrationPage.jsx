import { useCallback, useEffect, useState } from 'react'
import { useSelector } from 'react-redux'
import fpaApi from '../../api/fpaApi'
import { downloadXlsx } from '../../api/importApi'
import { Button, Card, EmptyState, toast } from '../../ui'
import PageHeader from '../../components/layout/PageHeader'
import { peutEcrireFpa, peutAdministrerFpa } from '../../features/fpa/permissions'

/* ============================================================================
   WIR199 — Écran « Administration FP&A » (`/fpa/administration`).
   ----------------------------------------------------------------------------
   Le module FP&A était INAMORÇABLE sans l'admin Django : ni cycle ni
   département créable depuis l'UI. Deux blocs :

   1. Départements — arbre CRUD (créer/renommer/désactiver-réactiver), gardé
      par `peutEcrireFpa` (même tuple que `DepartementViewSet.write_permission`
      = FPA_ECRITURE : n'importe quel rôle FP&A écrivant, pas seulement
      l'administrateur — la garde serveur ne distingue pas plus finement ici).
   2. Cycles budgétaires — création + gouvernance (ouvrir-saisie/clore/
      dupliquer/export XLSX). La CRÉATION suit la même garde `peutEcrireFpa`
      (create standard du ViewSet), mais les 4 actions de gouvernance exigent
      spécifiquement `fpa_administrer` côté serveur (`ExigeFpaPermission`,
      WIR173) — reflété ici par `peutAdministrerFpa`.
   ========================================================================== */

const TYPE_CYCLE_LABELS = { annuel: 'Annuel', trimestriel: 'Trimestriel' }
const STATUT_LABELS = {
  brouillon: 'Brouillon',
  ouvert_saisie: 'Ouvert à la saisie',
  en_validation: 'En validation',
  clos: 'Clos',
}

function listeDe(data) {
  if (Array.isArray(data)) return data
  if (data && Array.isArray(data.results)) return data.results
  return []
}

function messageErreur(err, repli) {
  const data = err?.response?.data
  if (typeof data?.detail === 'string') return data.detail
  return repli
}

function DepartementNode({ node, depth, canEcrire, onRenommer, onBasculerActif }) {
  return (
    <>
      <div
        style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          borderBottom: '1px solid var(--border, #e5e7eb)', padding: '8px 0',
          paddingLeft: depth * 24,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontFamily: 'monospace', fontSize: 12, opacity: 0.7 }}>{node.code}</span>
          <span>{node.nom}</span>
          {!node.actif && <span style={{ fontSize: 11, opacity: 0.6 }}>(inactif)</span>}
        </div>
        {canEcrire && (
          <div style={{ display: 'flex', gap: 8 }}>
            <Button size="sm" variant="ghost" onClick={() => onRenommer(node)}>
              Renommer
            </Button>
            <Button size="sm" variant="ghost" onClick={() => onBasculerActif(node)}>
              {node.actif ? 'Désactiver' : 'Réactiver'}
            </Button>
          </div>
        )}
      </div>
      {node.enfants?.map((enfant) => (
        <DepartementNode
          key={enfant.id}
          node={enfant}
          depth={depth + 1}
          canEcrire={canEcrire}
          onRenommer={onRenommer}
          onBasculerActif={onBasculerActif}
        />
      ))}
    </>
  )
}

export default function AdministrationPage() {
  const permissions = useSelector((s) => s.auth.permissions)
  const canEcrire = peutEcrireFpa(permissions)
  const canAdministrer = peutAdministrerFpa(permissions)

  const [arbre, setArbre] = useState([])
  const [departements, setDepartements] = useState([])
  const [chargementDept, setChargementDept] = useState(true)
  const [codeDept, setCodeDept] = useState('')
  const [nomDept, setNomDept] = useState('')
  const [parentDept, setParentDept] = useState('')

  const [cycles, setCycles] = useState([])
  const [chargementCycles, setChargementCycles] = useState(true)
  const [nomCycle, setNomCycle] = useState('')
  const [dateDebutCycle, setDateDebutCycle] = useState('')
  const [dateFinCycle, setDateFinCycle] = useState('')
  const [typeCycle, setTypeCycle] = useState('annuel')
  const [occupe, setOccupe] = useState(false)

  const chargerDepartements = useCallback(() => {
    setChargementDept(true)
    return Promise.all([fpaApi.getDepartementsTree(), fpaApi.getDepartements()])
      .then(([arbreRes, listeRes]) => {
        setArbre(listeDe(arbreRes?.data))
        setDepartements(listeDe(listeRes?.data))
      })
      .catch(() => toast.error('Impossible de charger les départements.'))
      .finally(() => setChargementDept(false))
  }, [])

  const chargerCycles = useCallback(() => {
    setChargementCycles(true)
    return fpaApi.getCycles()
      .then((res) => setCycles(listeDe(res?.data)))
      .catch(() => toast.error('Impossible de charger les cycles.'))
      .finally(() => setChargementCycles(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { chargerDepartements() }, [chargerDepartements])
  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { chargerCycles() }, [chargerCycles])

  async function creerDepartement() {
    if (!codeDept.trim() || !nomDept.trim() || occupe) return
    setOccupe(true)
    try {
      await fpaApi.createDepartement({
        code: codeDept.trim(), nom: nomDept.trim(),
        parent: parentDept || null,
      })
      setCodeDept(''); setNomDept(''); setParentDept('')
      toast.success('Département créé.')
      await chargerDepartements()
    } catch (err) {
      toast.error(messageErreur(err, 'La création a échoué.'))
    } finally {
      setOccupe(false)
    }
  }

  async function renommerDepartement(node) {
    const nom = window.prompt('Nouveau nom :', node.nom)
    if (!nom || nom === node.nom) return
    try {
      await fpaApi.updateDepartement(node.id, { nom })
      toast.success('Département renommé.')
      chargerDepartements()
    } catch (err) {
      toast.error(messageErreur(err, 'Le renommage a échoué.'))
    }
  }

  async function basculerActifDepartement(node) {
    try {
      await fpaApi.updateDepartement(node.id, { actif: !node.actif })
      toast.success(node.actif ? 'Département désactivé.' : 'Département réactivé.')
      chargerDepartements()
    } catch (err) {
      toast.error(messageErreur(err, "L'opération a échoué."))
    }
  }

  async function creerCycle() {
    if (!nomCycle.trim() || !dateDebutCycle || !dateFinCycle || occupe) return
    setOccupe(true)
    try {
      await fpaApi.createCycle({
        nom: nomCycle.trim(), date_debut: dateDebutCycle,
        date_fin: dateFinCycle, type_cycle: typeCycle,
      })
      setNomCycle(''); setDateDebutCycle(''); setDateFinCycle('')
      toast.success('Cycle créé.')
      await chargerCycles()
    } catch (err) {
      toast.error(messageErreur(err, 'La création du cycle a échoué.'))
    } finally {
      setOccupe(false)
    }
  }

  async function ouvrirSaisie(cycle) {
    try {
      await fpaApi.ouvrirSaisie(cycle.id)
      toast.success('Cycle ouvert à la saisie.')
      chargerCycles()
    } catch (err) {
      toast.error(messageErreur(err, "L'ouverture a échoué."))
    }
  }

  async function clore(cycle) {
    try {
      await fpaApi.cloreCycle(cycle.id)
      toast.success('Cycle clôturé.')
      chargerCycles()
    } catch (err) {
      toast.error(messageErreur(err, 'La clôture a échoué.'))
    }
  }

  async function dupliquer(cycle) {
    const nouveauNom = window.prompt('Nom du nouveau cycle :', `${cycle.nom} (copie)`)
    if (!nouveauNom) return
    try {
      await fpaApi.dupliquerCycle(cycle.id, nouveauNom)
      toast.success('Cycle dupliqué.')
      chargerCycles()
    } catch (err) {
      toast.error(messageErreur(err, 'La duplication a échoué.'))
    }
  }

  async function exporter(cycle) {
    try {
      const res = await fpaApi.exportCycle(cycle.id)
      downloadXlsx(res.data, `synthese_fpa_${cycle.id}.xlsx`)
    } catch (err) {
      toast.error(messageErreur(err, "L'export a échoué."))
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <PageHeader
        title="Administration FP&A"
        subtitle="Départements et cycles budgétaires — sans passer par l'admin Django"
      />

      <Card>
        <h3 style={{ marginBottom: 8 }}>Départements</h3>
        {chargementDept ? (
          <p>Chargement…</p>
        ) : arbre.length === 0 ? (
          <EmptyState
            title="Aucun département"
            description="Créez le premier département pour amorcer le module FP&A."
          />
        ) : (
          arbre.map((node) => (
            <DepartementNode
              key={node.id}
              node={node}
              depth={0}
              canEcrire={canEcrire}
              onRenommer={renommerDepartement}
              onBasculerActif={basculerActifDepartement}
            />
          ))
        )}
        {canEcrire && (
          <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
            <input
              aria-label="Code du département"
              placeholder="Code"
              value={codeDept}
              onChange={(e) => setCodeDept(e.target.value)}
              style={{ width: 100 }}
            />
            <input
              aria-label="Nom du département"
              placeholder="Nom"
              value={nomDept}
              onChange={(e) => setNomDept(e.target.value)}
            />
            <select
              aria-label="Département parent"
              value={parentDept}
              onChange={(e) => setParentDept(e.target.value)}
            >
              <option value="">— Aucun (racine) —</option>
              {departements.map((d) => (
                <option key={d.id} value={d.id}>{d.nom}</option>
              ))}
            </select>
            <Button
              onClick={creerDepartement}
              disabled={occupe || !codeDept.trim() || !nomDept.trim()}
            >
              Ajouter un département
            </Button>
          </div>
        )}
      </Card>

      <Card>
        <h3 style={{ marginBottom: 8 }}>Cycles budgétaires</h3>
        {chargementCycles ? (
          <p>Chargement…</p>
        ) : cycles.length === 0 ? (
          <EmptyState
            title="Aucun cycle"
            description="Créez le premier cycle budgétaire pour commencer la saisie."
          />
        ) : (
          <table style={{ borderCollapse: 'collapse', width: '100%', marginBottom: 12 }}>
            <thead>
              <tr>
                <th style={{ textAlign: 'left', padding: 8 }}>Nom</th>
                <th style={{ padding: 8 }}>Période</th>
                <th style={{ padding: 8 }}>Type</th>
                <th style={{ padding: 8 }}>Statut</th>
                {canAdministrer && <th style={{ padding: 8 }}>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {cycles.map((c) => (
                <tr key={c.id}>
                  <td style={{ padding: 8 }}>{c.nom}</td>
                  <td style={{ padding: 8 }}>{c.date_debut} → {c.date_fin}</td>
                  <td style={{ padding: 8 }}>{TYPE_CYCLE_LABELS[c.type_cycle] || c.type_cycle}</td>
                  <td style={{ padding: 8 }}>{STATUT_LABELS[c.statut] || c.statut}</td>
                  {canAdministrer && (
                    <td style={{ padding: 8, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                      {c.statut === 'brouillon' && (
                        <Button size="sm" variant="secondary" onClick={() => ouvrirSaisie(c)}>
                          Ouvrir la saisie
                        </Button>
                      )}
                      {(c.statut === 'ouvert_saisie' || c.statut === 'en_validation') && (
                        <Button size="sm" variant="secondary" onClick={() => clore(c)}>
                          Clore
                        </Button>
                      )}
                      <Button size="sm" variant="ghost" onClick={() => dupliquer(c)}>
                        Dupliquer
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => exporter(c)}>
                        Exporter XLSX
                      </Button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {canEcrire && (
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <input
              aria-label="Nom du cycle"
              placeholder="Nom (ex. Budget 2027)"
              value={nomCycle}
              onChange={(e) => setNomCycle(e.target.value)}
            />
            <input
              type="date"
              aria-label="Début du cycle"
              value={dateDebutCycle}
              onChange={(e) => setDateDebutCycle(e.target.value)}
            />
            <input
              type="date"
              aria-label="Fin du cycle"
              value={dateFinCycle}
              onChange={(e) => setDateFinCycle(e.target.value)}
            />
            <select
              aria-label="Type de cycle"
              value={typeCycle}
              onChange={(e) => setTypeCycle(e.target.value)}
            >
              <option value="annuel">Annuel</option>
              <option value="trimestriel">Trimestriel</option>
            </select>
            <Button
              onClick={creerCycle}
              disabled={occupe || !nomCycle.trim() || !dateDebutCycle || !dateFinCycle}
            >
              Créer le cycle
            </Button>
          </div>
        )}
      </Card>
    </div>
  )
}
