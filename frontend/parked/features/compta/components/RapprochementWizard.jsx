/* NTTRE24 — Assistant guidé « Nouveau rapprochement bancaire » (3 étapes).
   ----------------------------------------------------------------------------
   1. Compte + période  → crée le rapprochement (POST /compta/rapprochements/)
   2. Import du relevé  → format DÉTECTÉ automatiquement (extension/en-tête)
                          parmi CFONB120 / MT940 / camt.053 / CSV, puis
                          `import-releve` (NTTRE1-3) ou, pour le CSV, une ligne
                          `ligne-releve` par mouvement (aucune route nouvelle)
   3. Aperçu & pointage → suggestions pré-remplies (NTTRE4/XACC3), acceptation
                          des non ambiguës, puis clôture — sans jamais quitter
                          l'assistant.

   AUCUN nouveau modèle ni endpoint : l'assistant n'orchestre que des routes
   déjà en place. Toutes les erreurs serveur sont affichées telles quelles,
   en nommant le champ fautif quand le serveur le nomme. */
import { useEffect, useRef, useState } from 'react'
import { Upload, Wand2, CheckCircle2 } from 'lucide-react'
import {
  Button, Input, Label, EmptyState, toast,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '../../../ui'
import { formatMAD, formatDate } from '../../../lib/format'
import ComptaTable from '../ComptaTable'
import comptaApi from '../../../api/comptaApi'
import {
  detecterFormatReleve, LIBELLE_FORMAT, parserReleveCsv,
} from './bankFormatDetect'

const ETAPES = [
  { numero: 1, titre: 'Compte & période' },
  { numero: 2, titre: 'Import du relevé' },
  { numero: 3, titre: 'Aperçu & pointage' },
]

function messageErreur(err, repli) {
  const d = err?.response?.data
  if (typeof d === 'string') return d
  if (d?.detail) return d.detail
  // Erreur de validation par champ : on NOMME le champ fautif.
  if (d && typeof d === 'object') {
    const [champ, valeur] = Object.entries(d)[0] || []
    if (champ) {
      const texte = Array.isArray(valeur) ? valeur[0] : valeur
      return `${champ} : ${texte}`
    }
  }
  return repli
}

export default function RapprochementWizard({ onClose, onCreated }) {
  const [etape, setEtape] = useState(1)
  const [busy, setBusy] = useState(false)
  const [comptes, setComptes] = useState([])
  const [form, setForm] = useState({
    compte_tresorerie: '', date_debut: '', date_fin: '', solde_releve: '',
  })
  const [erreurChamp, setErreurChamp] = useState('')
  const [rapprochement, setRapprochement] = useState(null)
  const [importInfo, setImportInfo] = useState(null)
  const [suggestions, setSuggestions] = useState([])
  const [resume, setResume] = useState(null)
  const fileRef = useRef(null)

  useEffect(() => {
    let vivant = true
    comptaApi.tresorerie.list({ page_size: 200 })
      .then((res) => {
        if (!vivant) return
        const liste = Array.isArray(res.data) ? res.data : (res.data?.results || [])
        setComptes(liste)
      })
      .catch(() => { if (vivant) setComptes([]) })
    return () => { vivant = false }
  }, [])

  const set = (champ, valeur) => setForm((f) => ({ ...f, [champ]: valeur }))

  // ── Étape 1 : création du rapprochement ────────────────────────────────
  const creer = async () => {
    if (!form.compte_tresorerie) {
      setErreurChamp('compte_tresorerie')
      toast.error('Choisissez le compte de trésorerie à rapprocher.')
      return
    }
    if (!form.date_debut || !form.date_fin) {
      setErreurChamp(form.date_debut ? 'date_fin' : 'date_debut')
      toast.error('Renseignez le début et la fin de la période.')
      return
    }
    setErreurChamp('')
    setBusy(true)
    try {
      const res = await comptaApi.rapprochements.create({
        compte_tresorerie: form.compte_tresorerie,
        date_debut: form.date_debut,
        date_fin: form.date_fin,
        solde_releve: form.solde_releve === '' ? 0 : Number(form.solde_releve),
      })
      setRapprochement(res.data)
      setEtape(2)
      onCreated?.()
    } catch (err) {
      toast.error(messageErreur(err, 'Création du rapprochement impossible.'))
    } finally {
      setBusy(false)
    }
  }

  // ── Étape 2 : import du relevé, format détecté automatiquement ─────────
  const importer = async (event) => {
    const fichier = event.target.files?.[0]
    event.target.value = ''
    if (!fichier || !rapprochement) return
    setBusy(true)
    try {
      const entete = await fichier.slice(0, 2048).text()
      const format = detecterFormatReleve(fichier.name, entete)
      if (!format) {
        toast.error(
          'Format du relevé non reconnu : attendu CFONB120, MT940, '
          + 'camt.053 ou CSV.')
        return
      }
      if (format === 'csv') {
        const { lignes, ignorees } = parserReleveCsv(await fichier.text())
        if (!lignes.length) {
          toast.error('Aucune ligne exploitable dans ce fichier CSV.')
          return
        }
        for (const ligne of lignes) {
          await comptaApi.rapprochements.ajouterLigneReleve(
            rapprochement.id, ligne)
        }
        setImportInfo({ format, nombre: lignes.length, ignorees })
      } else {
        const fd = new FormData()
        fd.append('releve', fichier)
        const res = await comptaApi.rapprochements.importReleve(
          rapprochement.id, fd, format)
        setImportInfo({
          format, nombre: res.data?.nombre ?? 0, ignorees: 0,
        })
      }
      toast.success('Relevé importé.')
    } catch (err) {
      toast.error(messageErreur(err, 'Import du relevé impossible.'))
    } finally {
      setBusy(false)
    }
  }

  // ── Étape 3 : suggestions, pointage, clôture ───────────────────────────
  const chargerApercu = async () => {
    if (!rapprochement) return
    setBusy(true)
    try {
      const [sug, res] = await Promise.all([
        comptaApi.rapprochements.suggestions(rapprochement.id),
        comptaApi.rapprochements.resume(rapprochement.id),
      ])
      setSuggestions(Array.isArray(sug.data) ? sug.data : (sug.data?.suggestions || []))
      setResume(res.data)
      setEtape(3)
    } catch (err) {
      toast.error(messageErreur(err, 'Aperçu indisponible.'))
    } finally {
      setBusy(false)
    }
  }

  const accepterSuggestions = async () => {
    setBusy(true)
    try {
      const res = await comptaApi.rapprochements.accepterSuggestions(rapprochement.id)
      const n = res.data?.acceptees?.length ?? res.data?.pointees ?? 0
      toast.success(`${n} ligne(s) pointée(s) automatiquement.`)
      const [sug, resume2] = await Promise.all([
        comptaApi.rapprochements.suggestions(rapprochement.id),
        comptaApi.rapprochements.resume(rapprochement.id),
      ])
      setSuggestions(Array.isArray(sug.data) ? sug.data : (sug.data?.suggestions || []))
      setResume(resume2.data)
    } catch (err) {
      toast.error(messageErreur(err, 'Acceptation des suggestions impossible.'))
    } finally {
      setBusy(false)
    }
  }

  const cloturer = async () => {
    setBusy(true)
    try {
      await comptaApi.rapprochements.cloturer(rapprochement.id)
      toast.success('Rapprochement clôturé.')
      onCreated?.()
      onClose()
    } catch (err) {
      toast.error(messageErreur(err, 'Clôture impossible.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Assistant — nouveau rapprochement bancaire</DialogTitle>
        </DialogHeader>

        <ol className="mb-3 flex flex-wrap gap-2 text-xs" aria-label="Étapes de l'assistant">
          {ETAPES.map((e) => (
            <li
              key={e.numero}
              aria-current={etape === e.numero ? 'step' : undefined}
              className={`rounded-full border px-3 py-1 ${
                etape === e.numero
                  ? 'border-primary bg-primary/10 font-medium text-primary'
                  : 'text-muted-foreground'
              }`}
            >
              {e.numero}. {e.titre}
            </li>
          ))}
        </ol>

        {etape === 1 && (
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <Label htmlFor="rw-compte">Compte de trésorerie</Label>
              <select
                id="rw-compte"
                value={form.compte_tresorerie}
                onChange={(e) => set('compte_tresorerie', e.target.value)}
                className="h-9 rounded-md border border-border bg-card px-3 text-sm"
              >
                <option value="">Choisir un compte…</option>
                {comptes.map((c) => (
                  <option key={c.id} value={c.id}>{c.libelle}</option>
                ))}
              </select>
              {erreurChamp === 'compte_tresorerie' && (
                <span className="text-xs text-destructive">
                  Compte de trésorerie : champ obligatoire.
                </span>
              )}
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div className="flex flex-col gap-1">
                <Label htmlFor="rw-debut">Début de période</Label>
                <Input id="rw-debut" type="date" value={form.date_debut}
                       onChange={(e) => set('date_debut', e.target.value)} />
                {erreurChamp === 'date_debut' && (
                  <span className="text-xs text-destructive">
                    Début de période : champ obligatoire.
                  </span>
                )}
              </div>
              <div className="flex flex-col gap-1">
                <Label htmlFor="rw-fin">Fin de période</Label>
                <Input id="rw-fin" type="date" value={form.date_fin}
                       onChange={(e) => set('date_fin', e.target.value)} />
                {erreurChamp === 'date_fin' && (
                  <span className="text-xs text-destructive">
                    Fin de période : champ obligatoire.
                  </span>
                )}
              </div>
              <div className="flex flex-col gap-1">
                <Label htmlFor="rw-solde">Solde du relevé</Label>
                <Input id="rw-solde" type="number" step="any" value={form.solde_releve}
                       onChange={(e) => set('solde_releve', e.target.value)} />
              </div>
            </div>
          </div>
        )}

        {etape === 2 && (
          <div className="flex flex-col gap-3">
            <p className="text-sm text-muted-foreground">
              Déposez le relevé de banque : le format est reconnu tout seul
              (CFONB120, MT940, camt.053 ou CSV).
            </p>
            <div>
              <Button variant="outline" disabled={busy}
                      onClick={() => fileRef.current?.click()}>
                <Upload className="size-4" /> Choisir le fichier du relevé
              </Button>
              <input
                ref={fileRef} type="file" className="hidden"
                accept=".txt,.csv,.xml,.sta,.mt940,.cfonb,.cfonb120"
                onChange={importer}
              />
            </div>
            {importInfo && (
              <p className="text-sm">
                Format reconnu : <strong>{LIBELLE_FORMAT[importInfo.format]}</strong> —{' '}
                {importInfo.nombre} ligne(s) importée(s)
                {importInfo.ignorees > 0
                  ? `, ${importInfo.ignorees} ligne(s) ignorée(s) (date ou montant illisible).`
                  : '.'}
              </p>
            )}
          </div>
        )}

        {etape === 3 && (
          <div className="flex flex-col gap-3">
            {resume && (
              <div className="flex flex-wrap gap-4 rounded-lg border px-3 py-2 text-sm">
                <span>Solde relevé : <strong>{formatMAD(resume.solde_releve)}</strong></span>
                <span>Solde grand livre : <strong>{formatMAD(resume.solde_gl)}</strong></span>
                <span className={Number(resume.ecart) === 0 ? 'text-success' : 'text-destructive'}>
                  Écart : <strong>{formatMAD(resume.ecart)}</strong>
                </span>
                <span>{resume.lignes_non_pointees} ligne(s) non pointée(s)</span>
              </div>
            )}
            {!suggestions.length ? (
              <EmptyState
                title="Aucune suggestion"
                description="Toutes les lignes sont pointées, ou aucune écriture ne concorde."
              />
            ) : (
              <ComptaTable
                aria-label="Lignes importées et suggestions"
                rows={suggestions}
                getRowKey={(s) => s.ligne_releve_id}
                columns={[
                  { key: 'date', label: 'Date',
                    cell: (s) => formatDate(s.date_operation) },
                  { key: 'libelle', label: 'Libellé', cell: (s) => s.libelle || '—' },
                  { key: 'montant', label: 'Montant', align: 'right', numeric: true,
                    cell: (s) => formatMAD(s.montant) },
                  { key: 'suggestion', label: 'Suggestion pré-remplie',
                    cell: (s) => (s.candidats?.length
                      ? `${s.candidats[0].libelle || '—'} (${formatMAD(s.candidats[0].montant)})`
                      : 'Aucune') },
                  { key: 'ambigue', label: 'Ambiguë',
                    cell: (s) => (s.ambigue ? 'Oui — à arbitrer' : 'Non') },
                ]}
              />
            )}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Fermer</Button>
          {etape === 1 && (
            <Button onClick={creer} disabled={busy}>Créer et continuer</Button>
          )}
          {etape === 2 && (
            <Button onClick={chargerApercu} disabled={busy}>
              Voir l’aperçu et les suggestions
            </Button>
          )}
          {etape === 3 && (
            <>
              <Button variant="outline" onClick={accepterSuggestions} disabled={busy}>
                <Wand2 className="size-4" /> Accepter les suggestions non ambiguës
              </Button>
              <Button onClick={cloturer} disabled={busy}>
                <CheckCircle2 className="size-4" /> Terminer le rapprochement
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
