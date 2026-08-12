import { useEffect, useRef, useState } from 'react'
import { Download, Upload } from 'lucide-react'
import { Button, Card, Combobox, Label, EmptyState, toast } from '../../../ui'
import { formatMAD } from '../../../lib/format'
import { stampedFilename } from '../../../utils/downloadBlob'
import { store } from '../../../store'
import ComptaTable from '../ComptaTable'
import comptaApi from '../../../api/comptaApi'
import { unwrap } from '../components/useComptaList.js'

/* ============================================================================
   PACT35 — Import guidé de la balance d'ouverture.
   ----------------------------------------------------------------------------
   COMPTA3 : télécharge un gabarit CSV, puis importe la balance d'ouverture en
   une écriture « À-Nouveaux » unique et équilibrée — l'outil dont a besoin
   toute société qui migre sa comptabilité vers l'ERP en cours d'exercice.
   IDEMPOTENT par exercice : un second import sur le même exercice ne
   duplique rien, `services.importer_balance_ouverture` renvoie l'écriture
   déjà postée (`deja_importee: true`) — affiché ici distinctement d'un
   import neuf, jamais présenté comme un second succès silencieux. Un
   fichier invalide renvoie le détail ligne à ligne (400), jamais un 500.
   Endpoints /compta/balance-ouverture/gabarit/, /importer/.
   ========================================================================== */

export default function BalanceOuverturePage() {
  const [exercice, setExercice] = useState(null)
  const [exercices, setExercices] = useState([])
  const [fichier, setFichier] = useState(null)
  const [erreurs, setErreurs] = useState([])
  const [resultat, setResultat] = useState(null)
  const [telechargement, setTelechargement] = useState(false)
  const [important, setImportant] = useState(false)
  const fileRef = useRef(null)

  useEffect(() => {
    comptaApi.exercices.list()
      .then((res) => setExercices(unwrap(res).map((e) => ({ value: e.id, label: e.libelle }))))
      .catch(() => toast.error('Chargement des exercices impossible.'))
  }, [])

  const telechargerGabarit = async () => {
    setTelechargement(true)
    try {
      const res = await comptaApi.balanceOuverture.gabarit()
      const blob = res.data instanceof Blob ? res.data : new Blob([res.data])
      const societe = store.getState().parametres?.profile?.nom
      comptaApi.downloadBlob(blob, stampedFilename('gabarit-balance-ouverture', 'csv', societe))
    } catch {
      toast.error('Téléchargement du gabarit impossible.')
    } finally {
      setTelechargement(false)
    }
  }

  const importer = async () => {
    if (!exercice || !fichier) {
      toast.error('Choisissez un exercice et un fichier CSV.')
      return
    }
    setImportant(true)
    setErreurs([])
    setResultat(null)
    try {
      const res = await comptaApi.balanceOuverture.importer(fichier, exercice)
      setResultat(res.data)
      if (res.data?.deja_importee) {
        toast('Balance déjà importée pour cet exercice — écriture existante affichée ci-dessous.')
      } else {
        toast.success(`Balance importée : écriture ${res.data?.reference || ''}.`)
      }
      setFichier(null)
      if (fileRef.current) fileRef.current.value = ''
    } catch (err) {
      const d = err?.response?.data
      if (Array.isArray(d?.erreurs)) {
        setErreurs(d.erreurs)
        toast.error(d?.detail || 'Fichier invalide — voir le détail ligne à ligne.')
      } else {
        toast.error(typeof d === 'string' ? d : (d?.detail || 'Import impossible.'))
      }
    } finally {
      setImportant(false)
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <h2>Balance d'ouverture</h2>
      </div>

      <Card className="flex flex-col gap-4 p-4 sm:p-5">
        <p className="text-sm text-muted-foreground">
          Téléchargez le gabarit CSV, remplissez une ligne par compte (numéro, libellé,
          débit, crédit — et le tiers pour les comptes auxiliaires), puis importez-le sur
          l'exercice cible. Une seule écriture « À-Nouveaux » équilibrée est postée.
        </p>
        <div>
          <Button variant="outline" onClick={telechargerGabarit} disabled={telechargement}>
            <Download className="size-4" /> {telechargement ? 'Téléchargement…' : 'Télécharger le gabarit CSV'}
          </Button>
        </div>

        <div className="flex flex-wrap items-end gap-3 border-t pt-4">
          <div className="flex min-w-56 flex-col gap-1">
            <Label htmlFor="bo-exercice" required>Exercice</Label>
            <Combobox id="bo-exercice" options={exercices} value={exercice} onChange={setExercice} />
          </div>
          <div className="flex flex-1 min-w-56 flex-col gap-1">
            <Label htmlFor="bo-fichier" required>Fichier CSV</Label>
            <input
              ref={fileRef}
              id="bo-fichier"
              type="file"
              accept=".csv"
              onChange={(e) => setFichier(e.target.files?.[0] || null)}
              className="text-sm"
            />
          </div>
          <Button onClick={importer} disabled={important || !exercice || !fichier}>
            <Upload className="size-4" /> {important ? 'Import…' : 'Importer'}
          </Button>
        </div>

        {resultat && !erreurs.length && (
          <div className={`rounded-md border p-3 text-sm ${resultat.deja_importee ? 'border-border' : 'border-success/40 bg-success/5'}`}>
            {resultat.deja_importee
              ? `Cette balance a déjà été importée pour cet exercice — écriture existante : ${resultat.reference || '—'}.`
              : `Écriture postée : ${resultat.reference || '—'} (total ${formatMAD(resultat.total)}).`}
          </div>
        )}

        {erreurs.length > 0 && (
          <div className="flex flex-col gap-2">
            <p className="text-sm font-medium text-destructive">
              Fichier invalide — {erreurs.length} ligne(s) rejetée(s), rien n'a été écrit.
            </p>
            <ComptaTable
              aria-label="Erreurs d'import de la balance d'ouverture"
              rows={erreurs}
              getRowKey={(e, i) => i}
              columns={[
                { key: 'ligne', label: 'Ligne', cell: (e) => e.ligne },
                { key: 'raison', label: 'Raison', cell: (e) => e.raison },
              ]}
            />
          </div>
        )}

        {!resultat && !erreurs.length && (
          <EmptyState
            title="Aucun import effectué"
            description="Le résultat de l'import (écriture postée ou détail des erreurs) s'affichera ici."
          />
        )}
      </Card>
    </div>
  )
}
