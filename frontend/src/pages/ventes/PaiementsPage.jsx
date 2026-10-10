import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { Ban, Upload, Wallet, Undo2, Shuffle } from 'lucide-react'
import ventesApi from '../../api/ventesApi'
// AFAC18 — gestes de correction d'un paiement (réaffecter / annuler la saisie) :
// client `api` partagé, comme RemisesEncaissementPage (aucune méthode ventesApi neuve).
import api from '../../api/axios'
import fetchAllPages from '../../utils/fetchAllPages'
import { formatMAD } from '../../lib/format'
import {
  Card, CardContent, Skeleton, EmptyState, Input, Button, Badge, Label,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '../../ui'
import { Table } from '../reporting/Table'
// AUD132 — le rejet est une écriture réservée au palier responsable/admin
// (même garde que le serveur : `get_permissions` → IsResponsableOrAdmin).
import { useIsAdminOrResponsable } from '../../hooks/useHasPermission'
// APX11 — en-tête unique VX28 + accent de module (identité Ventes).
import { PageHeader } from '../../ui/PageHeader'
import { VENTES_ACCENT_STYLE } from '../../features/ventes/accent'

const dh = (v) => formatMAD(v, { decimals: 2 })

/* WIR265/FG42 — Statuts de ligne d'un relevé bancaire, tels que le SERVEUR les
   calcule (`paiement_import.dry_run`). Rien n'est recalculé ici : l'écran ne
   fait que nommer et colorer ce que le serveur a décidé. */
const STATUTS_RELEVE = {
  a_importer: { label: 'À importer', tone: 'success' },
  non_trouve: { label: 'Facture non trouvée', tone: 'neutral' },
  deja_regle: { label: 'Déjà réglée', tone: 'info' },
  surpaiement: { label: 'Sur-paiement', tone: 'warning' },
  montant_invalide: { label: 'Montant invalide', tone: 'danger' },
  // AFAC7 — les 4 statuts de revue/idempotence (contrat releve_import_dry_run.json).
  ambigu: { label: 'Plusieurs factures possibles', tone: 'warning' },
  client_non_identifie: { label: 'Donneur d’ordre inconnu', tone: 'warning' },
  doublon_import: { label: 'Déjà importée', tone: 'info' },
  date_invalide: { label: 'Date illisible', tone: 'danger' },
  // Statuts propres au bilan du commit (contrat releve_import_commit.json).
  non_selectionnee: { label: 'Non sélectionnée', tone: 'neutral' },
  created: { label: 'Créée', tone: 'success' },
  erreur: { label: 'Erreur', tone: 'danger' },
}
const LIGNES_PAR_PAGE = 50

// AUD132 / AFAC18 — un paiement rejeté OU annulé (erreur de saisie) sort du payé.
const estRejete = (p) => p.statut === 'rejete'
const estAnnuleSaisie = (p) => p.statut === 'annule_saisie'
const estNonCompte = (p) => estRejete(p) || estAnnuleSaisie(p)

// Modes de paiement. Le modele vit dans `facturation` (pas `ventes`) ;
// `all` est la sentinelle du FILTRE, jamais un mode enregistre.
// source-choix: facturation.Paiement.mode +all
const MODES = [
  { value: 'all', label: 'Tous les modes' },
  { value: 'especes', label: 'Espèces' },
  { value: 'virement', label: 'Virement' },
  { value: 'cheque', label: 'Chèque' },
  { value: 'carte', label: 'Carte bancaire' },
  { value: 'prelevement', label: 'Prélèvement' },
  { value: 'autre', label: 'Autre' },
]

// Encaissements (L512) : liste lecture seule de TOUS les paiements de la
// société (PaiementViewSet), avec filtre par mode/date et lien vers la facture.
export default function PaiementsPage() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  // Filtres d'AFFICHAGE (sur les données déjà chargées — pas d'appel API).
  const [mode, setMode] = useState('all')
  const [du, setDu] = useState('')
  const [au, setAu] = useState('')
  // VX231(b) — filtre client local, reflété dans l'URL (?client=<id>) : cliquer
  // le nom d'un client dans le tableau restreint la liste à ses encaissements
  // (id, jamais de donnée personnelle en clair dans l'URL). Le nom affiché reste
  // la seule info exposée à l'écran.
  const [searchParams, setSearchParams] = useSearchParams()
  const clientFilter = searchParams.get('client') || ''
  const clientFilterNom = useMemo(() => {
    if (!clientFilter) return ''
    const hit = rows.find(p => String(p.client) === clientFilter)
    return hit?.client_nom || ''
  }, [rows, clientFilter])
  const setClientFilter = (id) => {
    setSearchParams(prev => {
      const p = new URLSearchParams(prev)
      if (id) p.set('client', String(id))
      else p.delete('client')
      return p
    }, { replace: true })
  }

  const chargerPaiements = () => fetchAllPages((page) => ventesApi.getPaiements({ ordering: '-date_paiement', page, page_size: 200 }).then((r) => r.data))
    .then((res) => setRows(Array.isArray(res) ? res : (res?.results ?? [])))
    .catch(() => setError('Impossible de charger les encaissements. Réessayez.'))
    .finally(() => setLoading(false))

  useEffect(() => {
    chargerPaiements()
  }, [])

  /* ── WIR265/FG42 — Assistant « Import de relevé bancaire » ────────────────
     Le couple d'endpoints multipart (dry-run puis commit) existait et était
     testé depuis FG42 SANS aucun consommateur : rapprocher un relevé se
     faisait donc paiement par paiement, à la main.

     DEUX ÉTAPES, jamais une seule : le dry-run n'écrit RIEN et renvoie le
     mapping de colonnes, le statut de chaque ligne et les totaux ; l'import
     n'est déclenchable qu'APRÈS avoir vu cet aperçu. Les statuts viennent
     intégralement du serveur. */
  const location = useLocation()
  const navigate = useNavigate()
  const importOuvert = location.pathname.endsWith('/import-releve')
  const [fichier, setFichier] = useState(null)
  const [apercu, setApercu] = useState(null)
  const [bilan, setBilan] = useState(null)
  const [importBusy, setImportBusy] = useState(false)
  // AFAC7 — sélection des lignes (numéros cochés), candidat choisi par ligne
  // ambiguë ({ligne: facture_reference}) et page courante de l'aperçu.
  const [cochees, setCochees] = useState(() => new Set())
  const [choix, setChoix] = useState({})
  const [pageApercu, setPageApercu] = useState(1)
  const [importErreur, setImportErreur] = useState('')

  const fermerImport = () => {
    setFichier(null); setApercu(null); setBilan(null); setImportErreur('')
    setCochees(new Set()); setChoix({}); setPageApercu(1)
    navigate('/ventes/paiements', { replace: true })
  }

  const choisirFichier = (f) => {
    setFichier(f || null)
    setApercu(null)
    setBilan(null)
    setImportErreur('')
  }

  const lancerApercu = async () => {
    if (!fichier) return
    setImportBusy(true); setImportErreur(''); setBilan(null)
    try {
      const r = await ventesApi.importReleveDryRun(fichier)
      setApercu(r.data)
      // Seules les lignes que le serveur dit importables sont cochées d'office :
      // une ligne `doublon_import` (ou en revue) reste décochée.
      setCochees(new Set((r.data?.preview || [])
        .filter((l) => l.statut === 'a_importer').map((l) => l.ligne)))
      setChoix({}); setPageApercu(1)
    } catch (err) {
      // Le serveur nomme la cause (fichier trop gros, format illisible,
      // colonnes absentes) : on l'affiche TEL QUEL.
      setImportErreur(err?.response?.data?.detail || 'Lecture du relevé impossible.')
    } finally { setImportBusy(false) }
  }

  const lancerImport = async () => {
    // AUD121 — l'import rejoue les décisions de l'aperçu : sans jeton de
    // dry-run il n'y a rien à valider (le serveur refuserait en 400).
    if (!apercu?.token) return
    setImportBusy(true); setImportErreur('')
    try {
      // Les lignes cochées partent par numéro ; une ligne ambiguë résolue part
      // en `{ligne, facture_reference}` (contrat releve_import_commit.json).
      const lignes = (apercu.preview || [])
        .filter((l) => cochees.has(l.ligne))
        .map((l) => (choix[l.ligne]
          ? { ligne: l.ligne, facture_reference: choix[l.ligne] }
          : l.ligne))
      const r = await ventesApi.importReleveCommit(apercu.token, lignes)
      setBilan(r.data)
      // Les paiements créés doivent être VISIBLES sans recharger la page.
      setLoading(true)
      await chargerPaiements()
    } catch (err) {
      setImportErreur(err?.response?.data?.detail || "L'import a échoué.")
    } finally { setImportBusy(false) }
  }

  const basculerLigne = (ligne) => setCochees((prev) => {
    const n = new Set(prev)
    if (n.has(ligne)) n.delete(ligne); else n.add(ligne)
    return n
  })
  const choisirCandidat = (ligne, ref) => {
    setChoix((prev) => ({ ...prev, [ligne]: ref }))
    setCochees((prev) => {
      const n = new Set(prev)
      if (ref) n.add(ligne); else n.delete(ligne)
      return n
    })
  }

  const filtered = useMemo(() => {
    return rows.filter(p => {
      if (mode !== 'all' && p.mode !== mode) return false
      if (clientFilter && String(p.client) !== clientFilter) return false
      const d = p.date_paiement || ''
      if (du && d < du) return false
      if (au && d > au) return false
      return true
    })
  }, [rows, mode, du, au, clientFilter])

  // AUD132 (PAY-10) — un paiement REJETÉ (chèque impayé) sort du total affiché,
  // exactement comme il sort de `Facture.montant_paye` côté serveur. Il reste
  // VISIBLE dans la liste, badgé « Rejeté » : c'est une piste d'audit, pas un
  // encaissement.
  const total = useMemo(
    () => filtered.reduce(
      (s, p) => (estNonCompte(p) ? s : s + Number(p.montant || 0)), 0),
    [filtered],
  )

  /* ── AUD132 (PAY-10) — « Chèque impayé » ────────────────────────────────
     L'action serveur `POST /ventes/paiements/{id}/rejeter/` (YLEDG5) existait
     sans AUCUN appelant : grep `rejeter` dans `ventesApi.js` ne trouvait que
     `rejeterEtapeDevis`. Un chèque revenu impayé était donc ingérable depuis
     le produit — et l'écran, sans colonne statut, affichait de toute façon un
     paiement rejeté comme un encaissement valide. Le motif est OBLIGATOIRE
     (le serveur refuse en 400 sans lui) ; le message d'erreur serveur est
     affiché TEL QUEL. */
  const peutRejeter = useIsAdminOrResponsable()
  const [rejetCible, setRejetCible] = useState(null)
  const [rejetMotif, setRejetMotif] = useState('')
  const [rejetFrais, setRejetFrais] = useState('')
  const [rejetDate, setRejetDate] = useState('')
  const [rejetBusy, setRejetBusy] = useState(false)
  const [rejetErreur, setRejetErreur] = useState('')

  const ouvrirRejet = (p) => {
    setRejetCible(p)
    setRejetMotif(''); setRejetFrais(''); setRejetDate(''); setRejetErreur('')
  }

  const confirmerRejet = async () => {
    if (!rejetCible || !rejetMotif.trim()) return
    setRejetBusy(true); setRejetErreur('')
    try {
      await ventesApi.rejeterPaiement(rejetCible.id, {
        motif: rejetMotif.trim(),
        frais: rejetFrais || undefined,
        date_rejet: rejetDate || undefined,
      })
      setRejetCible(null)
      setLoading(true)
      await chargerPaiements()
    } catch (err) {
      setRejetErreur(
        err?.response?.data?.detail || 'Le rejet a échoué. Réessayez.')
    } finally { setRejetBusy(false) }
  }

  /* ── AFAC18 — correction d'un paiement mal saisi ─────────────────────────
     Deux gestes serveur (AFAC17, formes AFAC4 `paiement_reaffecter.json` /
     `paiement_annuler_saisie.json`) à côté de « Rejeter » : réaffecter vers une
     autre facture ENCAISSABLE du même client, ou annuler la saisie (motif
     obligatoire). Le serveur reste seul juge ; son `detail` s'affiche sous le
     champ concerné, jamais en toast seul. */
  const [reafCible, setReafCible] = useState(null)
  const [reafFactures, setReafFactures] = useState([])
  const [reafChoix, setReafChoix] = useState('')
  const [reafBusy, setReafBusy] = useState(false)
  const [reafErreur, setReafErreur] = useState('')

  const ouvrirReaffecter = async (p) => {
    setReafCible(p); setReafChoix(''); setReafErreur(''); setReafFactures([])
    try {
      const data = await fetchAllPages((page) => api.get('/ventes/factures/',
        { params: { client: p.client, page, page_size: 200 } }).then((r) => r.data))
      const liste = Array.isArray(data) ? data : (data?.results || [])
      setReafFactures(liste.filter((f) => String(f.client) === String(p.client)
        && f.id !== p.facture && f.encaissable !== false
        && ['emise', 'en_retard'].includes(f.statut)))
    } catch {
      setReafErreur('Impossible de charger les factures du client.')
    }
  }

  const confirmerReaffecter = async () => {
    if (!reafCible || !reafChoix) return
    setReafBusy(true); setReafErreur('')
    try {
      await api.post(`/ventes/paiements/${reafCible.id}/reaffecter/`,
        { facture_cible: Number(reafChoix) })
      setReafCible(null)
      setLoading(true)
      await chargerPaiements()
    } catch (err) {
      setReafErreur(err?.response?.data?.detail || 'La réaffectation a échoué. Réessayez.')
    } finally { setReafBusy(false) }
  }

  const [annulCible, setAnnulCible] = useState(null)
  const [annulMotif, setAnnulMotif] = useState('')
  const [annulBusy, setAnnulBusy] = useState(false)
  const [annulErreur, setAnnulErreur] = useState('')
  const ouvrirAnnulSaisie = (p) => { setAnnulCible(p); setAnnulMotif(''); setAnnulErreur('') }

  const confirmerAnnulSaisie = async () => {
    if (!annulCible || !annulMotif.trim()) return
    setAnnulBusy(true); setAnnulErreur('')
    try {
      await api.post(`/ventes/paiements/${annulCible.id}/annuler-saisie/`,
        { motif: annulMotif.trim() })
      setAnnulCible(null)
      setLoading(true)
      await chargerPaiements()
    } catch (err) {
      setAnnulErreur(err?.response?.data?.detail || 'L’annulation a échoué. Réessayez.')
    } finally { setAnnulBusy(false) }
  }

  return (
    <div className="ui-root page">
      {/* APX11 — en-tête unique VX28 + accent Ventes. */}
      <PageHeader
        style={VENTES_ACCENT_STYLE}
        className="app-accent-rail"
        icon={Wallet}
        title="Encaissements"
        subtitle="Tous les paiements reçus, par facture et par mode"
        actions={(
          <Button size="sm" variant="outline"
                  onClick={() => navigate('/ventes/paiements/import-releve')}>
            <Upload className="size-4" /> Importer un relevé bancaire
          </Button>
        )}
      />

      {/* ── WIR265/FG42 — Assistant d'import en DEUX étapes ─────────────── */}
      <Dialog open={importOuvert} onOpenChange={(o) => { if (!o) fermerImport() }}>
        <DialogContent className="sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>Importer un relevé bancaire</DialogTitle>
            <DialogDescription>
              Étape 1 — l’aperçu n’écrit RIEN : il montre les colonnes
              reconnues, le statut de chaque ligne et les totaux. Étape 2 —
              l’import crée les encaissements manquants. Fichier XLSX ou CSV,
              5 Mo maximum.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4">
            <div className="grid gap-1.5">
              <label htmlFor="imp-fichier" className="text-sm font-medium">
                Fichier du relevé
              </label>
              <Input id="imp-fichier" type="file"
                     accept=".xlsx,.csv,text/csv"
                     onChange={(e) => choisirFichier(e.target.files?.[0])} />
            </div>

            {importErreur && (
              <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                {importErreur}
              </div>
            )}

            {/* ── Étape 1 : l'aperçu (aucune écriture) ─────────────────── */}
            {apercu && (
              <div className="grid gap-3">
                {apercu.deja_importe && (
                  <div role="alert" className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
                    Ce fichier a déjà été importé : le serveur refusera un nouvel import.
                  </div>
                )}
                <div className="flex flex-wrap items-center gap-3 text-sm">
                  <span><strong>{apercu.total_rows}</strong> ligne(s) lue(s)</span>
                  <span><strong>{apercu.matched}</strong> rapprochée(s)</span>
                  <span><strong>{apercu.already_paid}</strong> déjà réglée(s)</span>
                </div>
                <div className="text-sm">
                  <p className="mb-1 font-medium">Colonnes reconnues</p>
                  {Object.keys(apercu.columns || {}).length === 0 ? (
                    <p className="text-muted-foreground">
                      Aucune colonne reconnue — vérifiez les en-têtes du fichier.
                    </p>
                  ) : (
                    <ul className="flex flex-wrap gap-1.5">
                      {Object.entries(apercu.columns).map(([entete, champ]) => (
                        <li key={entete}>
                          <Badge tone="info">{entete} → {champ}</Badge>
                        </li>
                      ))}
                    </ul>
                  )}
                  {(apercu.unmapped || []).length > 0 && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      Ignorées : {apercu.unmapped.join(', ')}
                    </p>
                  )}
                </div>
                {(apercu.preview || []).length > 0 && (
                  <div className="overflow-x-auto">
                    {apercu.preview.length > LIGNES_PAR_PAGE && (
                      <div className="mt-2 flex items-center gap-2 text-sm">
                        <Button type="button" size="sm" variant="outline"
                                disabled={pageApercu <= 1}
                                onClick={() => setPageApercu((p) => p - 1)}>Précédent</Button>
                        <span>Page {pageApercu} / {Math.ceil(apercu.preview.length / LIGNES_PAR_PAGE)}</span>
                        <Button type="button" size="sm" variant="outline"
                                disabled={pageApercu >= Math.ceil(apercu.preview.length / LIGNES_PAR_PAGE)}
                                onClick={() => setPageApercu((p) => p + 1)}>Suivant</Button>
                      </div>
                    )}
                    <table className="w-full border-collapse text-sm"
                           aria-label="Aperçu du relevé bancaire">
                      <thead>
                        <tr className="border-b border-border">
                          <th className="px-2 py-1 text-left text-xs uppercase text-muted-foreground">Ligne</th>
                          <th className="px-2 py-1 text-left text-xs uppercase text-muted-foreground">Date</th>
                          <th className="px-2 py-1 text-left text-xs uppercase text-muted-foreground">Référence</th>
                          <th className="px-2 py-1 text-right text-xs uppercase text-muted-foreground">Montant</th>
                          <th className="px-2 py-1 text-left text-xs uppercase text-muted-foreground">Facture</th>
                          <th className="px-2 py-1 text-left text-xs uppercase text-muted-foreground">Importer</th>
                          <th className="px-2 py-1 text-left text-xs uppercase text-muted-foreground">Imputer à</th>
                          <th className="px-2 py-1 text-left text-xs uppercase text-muted-foreground">Statut</th>
                        </tr>
                      </thead>
                      <tbody>
                        {apercu.preview
                          .slice((pageApercu - 1) * LIGNES_PAR_PAGE, pageApercu * LIGNES_PAR_PAGE)
                          .map((l) => (
                          <tr key={l.ligne} className="border-b border-border/60 last:border-b-0">
                            <td className="px-2 py-1 tabular-nums">{l.ligne}</td>
                            <td className="px-2 py-1">{l.date || '—'}</td>
                            <td className="px-2 py-1">{l.reference || '—'}</td>
                            <td className="px-2 py-1 text-right tabular-nums">
                              {l.montant != null ? dh(l.montant) : '—'}
                            </td>
                            <td className="px-2 py-1">{l.facture_reference || '—'}</td>
                            <td className="px-2 py-1">
                              <input type="checkbox"
                                     aria-label={`Importer la ligne ${l.ligne}`}
                                     checked={cochees.has(l.ligne)}
                                     disabled={l.statut === 'ambigu' ? !choix[l.ligne] : l.statut !== 'a_importer'}
                                     onChange={() => basculerLigne(l.ligne)} />
                            </td>
                            <td className="px-2 py-1">
                              {l.statut === 'ambigu' && (l.candidats || []).length > 0 ? (
                                <select aria-label={`Facture de la ligne ${l.ligne}`}
                                        className="rounded border border-border bg-background px-1 py-0.5 text-sm"
                                        value={choix[l.ligne] || ''}
                                        onChange={(e) => choisirCandidat(l.ligne, e.target.value)}>
                                  <option value="">Choisir la facture…</option>
                                  {l.candidats.map((c) => <option key={c} value={c}>{c}</option>)}
                                </select>
                              ) : null}
                            </td>
                            <td className="px-2 py-1">
                              <Badge tone={STATUTS_RELEVE[l.statut]?.tone ?? 'neutral'}>
                                {STATUTS_RELEVE[l.statut]?.label ?? l.statut}
                              </Badge>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {/* ── Étape 2 : le bilan de l'import ───────────────────────── */}
            {bilan && (
              <div className="rounded-lg border border-border p-3 text-sm">
                <p className="m-0">
                  <strong>{bilan.created}</strong> encaissement(s) créé(s),{' '}
                  <strong>{bilan.skipped}</strong> ignoré(s),{' '}
                  <strong>{bilan.errors}</strong> en erreur.
                </p>
                <p className="m-0 mt-1 text-muted-foreground">
                  La liste ci-dessous a été rechargée.
                </p>
                {(bilan.results || []).filter((x) => x.statut !== 'created').length > 0 && (
                  <ul aria-label="Lignes ignorées" className="mt-2 list-disc pl-5">
                    {bilan.results.filter((x) => x.statut !== 'created').map((x) => (
                      <li key={x.ligne}>
                        Ligne {x.ligne} : {STATUTS_RELEVE[x.statut]?.label ?? x.statut}
                        {x.detail ? ` — ${x.detail}` : ''}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={fermerImport}>
              {bilan ? 'Fermer' : 'Annuler'}
            </Button>
            {!bilan && (
              <Button type="button" variant="outline" disabled={!fichier}
                      loading={importBusy && !apercu}
                      onClick={lancerApercu}>
                Aperçu (sans écrire)
              </Button>
            )}
            {!bilan && (
              // L'import n'est possible qu'APRÈS l'aperçu : jamais d'écriture
              // à l'aveugle sur un fichier qu'on n'a pas regardé.
              <Button type="button" disabled={!apercu || cochees.size === 0} loading={importBusy && !!apercu}
                      onClick={lancerImport}>
                Importer
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* VX231(b) — chip du filtre client actif (depuis un clic sur un nom). */}
      {clientFilter && (
        <div className="mb-3 flex items-center gap-2 text-sm">
          <span className="rounded-md border border-border bg-muted/40 px-2 py-1">
            Filtré sur {clientFilterNom || 'un client'}
          </span>
          <Button variant="outline" size="sm" onClick={() => setClientFilter('')}>
            Effacer le filtre client
          </Button>
        </div>
      )}

      {error && (
        <div className="mb-3 rounded border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      {!loading && rows.length > 0 && (
        <div className="mb-3 flex flex-wrap items-end gap-3">
          <label className="text-sm">
            <span className="mb-1 block text-xs text-muted-foreground">Mode</span>
            <Select value={mode} onValueChange={setMode}>
              <SelectTrigger className="w-44">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {MODES.map(m => (
                  <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </label>
          <label className="text-sm">
            <span className="mb-1 block text-xs text-muted-foreground">Du</span>
            <Input type="date" value={du} onChange={e => setDu(e.target.value)} />
          </label>
          <label className="text-sm">
            <span className="mb-1 block text-xs text-muted-foreground">Au</span>
            <Input type="date" value={au} onChange={e => setAu(e.target.value)} />
          </label>
          {(mode !== 'all' || du || au) && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => { setMode('all'); setDu(''); setAu('') }}
            >
              Effacer les filtres
            </Button>
          )}
        </div>
      )}

      {loading ? (
        <Card>
          <CardContent className="space-y-2 pt-5">
            {Array.from({ length: 5 }).map((unused, i) => (
              <Skeleton key={i} className="h-9 w-full" />
            ))}
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0 sm:p-0">
            {/* P167 — migré vers le moteur de tableau partagé. */}
            <Table
              aria-label="Encaissements"
              getRowKey={(p) => p.id}
              columns={[
                {
                  key: 'facture',
                  header: 'Facture',
                  cell: (p) => (p.facture ? (
                    <Link
                      className="font-medium text-info hover:underline"
                      to={`/ventes/factures?facture=${p.facture}`}
                    >
                      {p.facture_reference || `Facture #${p.facture}`}
                    </Link>
                  ) : '—'),
                },
                {
                  key: 'client',
                  header: 'Client',
                  // VX231(b) — nom cliquable → filtre local ?client=<id>.
                  cell: (p) => (p.client && p.client_nom ? (
                    <button
                      type="button"
                      className="font-medium text-info hover:underline"
                      onClick={() => setClientFilter(p.client)}
                      title={`Filtrer les encaissements de ${p.client_nom}`}
                    >
                      {p.client_nom}
                    </button>
                  ) : (p.client_nom || '—')),
                },
                {
                  key: 'montant',
                  header: 'Montant',
                  align: 'right',
                  cell: (p) => (estNonCompte(p)
                    ? <s className="text-muted-foreground">{dh(p.montant)}</s>
                    : <strong>{dh(p.montant)}</strong>),
                },
                { key: 'date', header: 'Date', cell: (p) => p.date_paiement || '—' },
                { key: 'mode', header: 'Mode', cell: (p) => p.mode_display || p.mode },
                // AUD132 — la colonne qui manquait : sans elle, un chèque
                // impayé se lisait comme un encaissement valide.
                {
                  key: 'statut',
                  header: 'Statut',
                  cell: (p) => (estAnnuleSaisie(p) ? (
                    <Badge tone="neutral"
                           title={p.motif_annulation || 'Saisie annulée'}>
                      Annulé (saisie)
                    </Badge>
                  ) : estRejete(p) ? (
                    <Badge tone="danger"
                           title={p.motif_rejet || 'Règlement rejeté'}>
                      Rejeté
                    </Badge>
                  ) : (
                    <Badge tone="success">Encaissé</Badge>
                  )),
                },
                { key: 'par_qui', header: 'Par qui', cell: (p) => p.created_by_username || '—' },
                {
                  key: 'actions',
                  header: '',
                  align: 'right',
                  cell: (p) => (peutRejeter && !estNonCompte(p) ? (
                    <div className="flex flex-wrap justify-end gap-1">
                      <Button size="sm" variant="outline"
                              onClick={() => ouvrirRejet(p)}
                              title="Chèque impayé / virement rejeté">
                        <Ban className="size-4" /> Rejeter
                      </Button>
                      <Button size="sm" variant="outline"
                              onClick={() => ouvrirReaffecter(p)}
                              title="Rapproché sur la mauvaise facture">
                        <Shuffle className="size-4" /> Réaffecter
                      </Button>
                      <Button size="sm" variant="outline"
                              onClick={() => ouvrirAnnulSaisie(p)}
                              title="Erreur de saisie : le paiement sort du payé">
                        <Undo2 className="size-4" /> Annuler (erreur de saisie)
                      </Button>
                    </div>
                  ) : null),
                },
              ]}
              rows={filtered}
              empty={(
                <EmptyState
                  icon={Wallet}
                  title="Aucun encaissement"
                  description={rows.length === 0
                    ? 'Aucun paiement n’a encore été enregistré.'
                    : 'Aucun encaissement ne correspond à ces filtres.'}
                  className="border-0 py-6"
                />
              )}
              footer={filtered.length > 0 && (
                <tr className="border-t border-border font-bold">
                  <td className="px-3 py-2" colSpan={2} data-label="Total">
                    Total encaissé ({filtered.filter(p => !estNonCompte(p)).length})
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums" data-label="Montant">{dh(total)}</td>
                  <td className="px-3 py-2" colSpan={6} />
                </tr>
              )}
            />
          </CardContent>
        </Card>
      )}

      {/* ── AFAC18 — Réaffecter un paiement à une autre facture ─────────── */}
      <Dialog open={!!reafCible}
              onOpenChange={(o) => { if (!o) setReafCible(null) }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Réaffecter le paiement de {dh(reafCible?.montant)}
            </DialogTitle>
            <DialogDescription>
              Le paiement passe sur une autre facture ouverte du même client ;
              les deux factures sont recalculées. Rien n’est supprimé.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="reaf-facture">Facture cible</Label>
              <select id="reaf-facture" value={reafChoix}
                      onChange={(e) => setReafChoix(e.target.value)}
                      className="rounded border border-border bg-background px-2 py-1 text-sm">
                <option value="">Choisir une facture ouverte…</option>
                {reafFactures.map((f) => (
                  <option key={f.id} value={f.id}>{f.reference}</option>
                ))}
              </select>
              {reafErreur && (
                <p role="alert" data-testid="reaffecter-erreur"
                   className="text-sm text-destructive">{reafErreur}</p>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setReafCible(null)}>
              Annuler
            </Button>
            <Button type="button" disabled={!reafChoix} loading={reafBusy}
                    onClick={confirmerReaffecter}>
              Réaffecter
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── AFAC18 — Annuler la saisie d'un paiement (erreur de saisie) ──── */}
      <Dialog open={!!annulCible}
              onOpenChange={(o) => { if (!o) setAnnulCible(null) }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Annuler la saisie du paiement de {dh(annulCible?.montant)}
            </DialogTitle>
            <DialogDescription>
              Le paiement sort du payé et reste tracé « Annulé (saisie) » avec
              son motif — différent d’un rejet bancaire.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-1.5">
            <Label htmlFor="annul-motif">Motif (obligatoire)</Label>
            <Input id="annul-motif" value={annulMotif}
                   placeholder="Montant saisi 5 000 au lieu de 500"
                   onChange={(e) => setAnnulMotif(e.target.value)} />
            {annulErreur && (
              <p role="alert" data-testid="annulation-saisie-erreur"
                 className="text-sm text-destructive">{annulErreur}</p>
            )}
          </div>
          <DialogFooter>
            <Button type="button" variant="ghost" onClick={() => setAnnulCible(null)}>
              Retour
            </Button>
            <Button type="button" variant="destructive" disabled={!annulMotif.trim()}
                    loading={annulBusy} onClick={confirmerAnnulSaisie}>
              Annuler la saisie
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── AUD132 (PAY-10) — Rejeter un règlement (chèque impayé) ───────── */}
      <Dialog open={!!rejetCible}
              onOpenChange={(o) => { if (!o) setRejetCible(null) }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Rejeter le règlement de {dh(rejetCible?.montant)}
            </DialogTitle>
            <DialogDescription>
              Le paiement n’est jamais supprimé : il passe « Rejeté », sort des
              totaux, la facture rouvre et les relances se ré-arment.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="rejet-motif">Motif du rejet</Label>
              <Input id="rejet-motif" value={rejetMotif}
                     placeholder="Chèque sans provision"
                     onChange={(e) => setRejetMotif(e.target.value)} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="rejet-frais">Frais bancaires (optionnel)</Label>
              <Input id="rejet-frais" type="number" step="any"
                     value={rejetFrais}
                     onChange={(e) => setRejetFrais(e.target.value)} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="rejet-date">Date du rejet (optionnel)</Label>
              <Input id="rejet-date" type="date" value={rejetDate}
                     onChange={(e) => setRejetDate(e.target.value)} />
            </div>
            {rejetErreur && (
              <div role="alert"
                   className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                {rejetErreur}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="ghost" onClick={() => setRejetCible(null)}>
              Annuler
            </Button>
            <Button variant="destructive" loading={rejetBusy}
                    disabled={!rejetMotif.trim()} onClick={confirmerRejet}>
              Confirmer le rejet
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
