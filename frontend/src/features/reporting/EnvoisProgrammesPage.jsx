import { useCallback, useEffect, useState } from 'react'
import { Mail, Pencil, Plus, Trash2 } from 'lucide-react'
import reportingApi from '../../api/reportingApi'
import { getApiError } from '../../lib/apiError'
import { formatDateTime } from '../../lib/format'
import { lireToutesLesPages } from '../../utils/fetchAllPages'
import PageHeader from '../../components/layout/PageHeader'
import {
  Button, Card, CardContent, CardHeader, CardTitle, EmptyState, FormField,
  Input, StatusPill, Textarea,
} from '../../ui'
import { toast, useConfirmDialog } from '../../ui/confirm'
import { ChargementPage } from '../../ui/ChargementPage'
import {
  CANAUX, KINDS_AVEC_CIBLE, SCHEDULES, STATUTS, TARGET_KINDS,
} from './envoisProgrammesChoix'

/* ============================================================================
   AANA45 / D-AANA-036-BRANCHER (C-AANA-036) — « Envois programmés ».
   ----------------------------------------------------------------------------
   `reporting/envois-rapports/` (historique de diffusion, NTDATA40) n'avait
   aucun écran : le fondateur (30/10/2026) a tranché « brancher », pas retirer.
   Un envoi programmé EST un rapport sauvegardé (`reporting/saved-reports/`,
   CRUD existant, réservé responsable/admin) dont la cadence (`schedule`,
   `heure_envoi`, `jour_du_mois`), le canal et les destinataires pilotent
   l'envoi automatique ; l'historique (lecture seule) montre chaque tentative,
   échecs et motif compris.

   Rien n'est ajouté au serveur : l'écran n'utilise QUE les méthodes déjà
   exposées (liste / création / modification / suppression des rapports ;
   liste des envois). Les erreurs de validation arrivent par champ et sont
   affichées SOUS le champ fautif. Contrat partagé :
   `apps/reporting/contract_samples/rapports_programmes.json` et `envois_rapports.json` (les choix de envoisProgrammesChoix.js
   y sont égalés par le test).
   ========================================================================== */

const TON_STATUT = {
  envoye: 'success', echec: 'danger', non_configure: 'warning', sans_destinataire: 'warning',
}
const TAILLE_HISTORIQUE = 50

const FORM_VIDE = {
  name: '', target_kind: 'sales', cible_id: '', schedule: 'weekly',
  heure_envoi: '', jour_du_mois: '1', canal: 'email', recipients: '',
  destinataires_whatsapp: '',
}

const CLASSE_SELECT = 'flex h-[var(--control-h)] w-full rounded-md border border-input bg-card px-[var(--control-px)] '
  + 'text-base text-foreground shadow-ui-xs focus-ring aria-[invalid=true]:border-destructive sm:text-sm'

const libelle = (choix, valeur) => choix.find(([v]) => v === valeur)?.[1] ?? valeur

function versForm(rapport) {
  return {
    name: rapport.name ?? '',
    target_kind: rapport.target_kind ?? 'sales',
    cible_id: rapport.cible_id == null ? '' : String(rapport.cible_id),
    schedule: rapport.schedule ?? 'none',
    heure_envoi: rapport.heure_envoi == null ? '' : String(rapport.heure_envoi),
    jour_du_mois: String(rapport.jour_du_mois ?? 1),
    canal: rapport.canal ?? 'email',
    recipients: rapport.recipients ?? '',
    destinataires_whatsapp: rapport.destinataires_whatsapp ?? '',
  }
}

// Types STRICTS côté serveur (entiers, jamais « 8 » ni 8.0) : on convertit ici,
// et un texte non numérique est laissé tel quel pour que le serveur le refuse
// au bon champ plutôt que de le taire.
function entierOuNull(texte) {
  const t = String(texte ?? '').trim()
  if (t === '') return null
  return /^-?\d+$/.test(t) ? Number(t) : t
}

function versPayload(form) {
  return {
    name: form.name,
    target_kind: form.target_kind,
    cible_id: KINDS_AVEC_CIBLE.includes(form.target_kind) ? entierOuNull(form.cible_id) : null,
    schedule: form.schedule,
    heure_envoi: entierOuNull(form.heure_envoi),
    jour_du_mois: entierOuNull(form.jour_du_mois) ?? 1,
    canal: form.canal,
    recipients: form.recipients,
    destinataires_whatsapp: form.destinataires_whatsapp,
  }
}

function resume(rapport) {
  if (rapport.schedule === 'none') return 'Non programmé'
  const parts = [rapport.schedule_label || libelle(SCHEDULES, rapport.schedule)]
  if (rapport.schedule === 'monthly') parts.push(`le ${rapport.jour_du_mois}`)
  if (rapport.heure_envoi != null) parts.push(`à ${rapport.heure_envoi} h`)
  return parts.join(' · ')
}

function destinataires(rapport) {
  const valeur = rapport.canal === 'whatsapp' ? rapport.destinataires_whatsapp : rapport.recipients
  return valeur || '—'
}

function dateFr(iso) {
  return iso ? formatDateTime(iso) : '—'
}

export default function EnvoisProgrammesPage() {
  const { confirmDelete } = useConfirmDialog()
  const [rapports, setRapports] = useState([])
  const [envois, setEnvois] = useState({ lignes: [], total: 0 })
  const [chargement, setChargement] = useState(true)
  const [erreurChargement, setErreurChargement] = useState(false)
  const [filtreEchecs, setFiltreEchecs] = useState(false)
  const [form, setForm] = useState(null) // null = formulaire fermé
  const [editionId, setEditionId] = useState(null)
  const [erreurs, setErreurs] = useState({})
  const [erreurGlobale, setErreurGlobale] = useState('')
  const [occupe, setOccupe] = useState(false)
  const [rechargement, setRechargement] = useState(0)

  useEffect(() => {
    let vivant = true
    Promise.all([
      lireToutesLesPages((p) => reportingApi.listSavedReports(p)),
      // Historique : les N derniers envois (plus récent d'abord) — on lit
      // `count`/`next` pour dire s'il y en a davantage, jamais une page 1 muette.
      reportingApi.listEnvoisRapports({
        page_size: TAILLE_HISTORIQUE,
        ...(filtreEchecs ? { statut: 'echec' } : {}),
      }),
    ])
      .then(([listeRapports, reponseEnvois]) => {
        if (!vivant) return
        const page = reponseEnvois?.data
        const lignes = Array.isArray(page) ? page : (page?.results ?? [])
        setRapports(listeRapports)
        setErreurChargement(false)
        setEnvois({ lignes, total: page?.count ?? lignes.length, suite: !!page?.next })
      })
      .catch(() => { if (vivant) setErreurChargement(true) })
      .finally(() => { if (vivant) setChargement(false) })
    return () => { vivant = false }
  }, [rechargement, filtreEchecs])

  const recharger = useCallback(() => setRechargement((n) => n + 1), [])
  const reessayer = () => { setChargement(true); recharger() }

  const ouvrirCreation = () => {
    setEditionId(null)
    setForm({ ...FORM_VIDE })
    setErreurs({})
    setErreurGlobale('')
  }
  const ouvrirEdition = (rapport) => {
    setEditionId(rapport.id)
    setForm(versForm(rapport))
    setErreurs({})
    setErreurGlobale('')
  }
  const fermer = () => { setForm(null); setEditionId(null); setErreurs({}); setErreurGlobale('') }
  const maj = (champ) => (e) => setForm((f) => ({ ...f, [champ]: e.target.value }))

  const enregistrer = async (event) => {
    event.preventDefault()
    if (occupe || !form) return
    setOccupe(true)
    setErreurs({})
    setErreurGlobale('')
    try {
      const payload = versPayload(form)
      if (editionId) await reportingApi.updateSavedReport(editionId, payload)
      else await reportingApi.createSavedReport(payload)
      toast.success(editionId ? 'Envoi programmé modifié.' : 'Envoi programmé créé.')
      fermer()
      recharger()
    } catch (err) {
      const { message, fieldErrors } = getApiError(err, "Enregistrement impossible.")
      setErreurs(fieldErrors ?? {})
      setErreurGlobale(fieldErrors ? '' : message)
    } finally {
      setOccupe(false)
    }
  }

  const supprimer = async (rapport) => {
    const ok = await confirmDelete({
      title: 'Supprimer cet envoi programmé ?',
      description: `Le rapport « ${rapport.name} » et son historique d'envois seront supprimés.`,
    })
    if (!ok) return
    try {
      await reportingApi.deleteSavedReport(rapport.id)
      toast.success('Envoi programmé supprimé.')
      recharger()
    } catch (err) {
      toast.error(getApiError(err, 'Suppression impossible.').message)
    }
  }

  const avecCible = form && KINDS_AVEC_CIBLE.includes(form.target_kind)

  return (
    <div className="page" data-testid="envois-programmes">
      <PageHeader
        title="Envois programmés"
        subtitle="Rapports envoyés automatiquement par email ou WhatsApp, et historique de diffusion."
        actions={<Button onClick={ouvrirCreation}><Plus /> Nouvel envoi</Button>}
      />

      {chargement ? (
        <ChargementPage />
      ) : erreurChargement ? (
        <EmptyState
          tone="error"
          title="Chargement impossible"
          description="Les envois programmés n'ont pas pu être chargés."
          action={<Button variant="outline" onClick={reessayer}>Réessayer</Button>}
          className="my-6"
        />
      ) : (
        <div className="flex flex-col gap-5">
          {form && (
            <Card data-testid="envoi-form-carte">
              <CardHeader>
                <CardTitle>{editionId ? "Modifier l'envoi programmé" : 'Nouvel envoi programmé'}</CardTitle>
              </CardHeader>
              <CardContent>
                <form onSubmit={enregistrer} noValidate className="grid gap-4 sm:grid-cols-2">
                  {erreurGlobale && (
                    <p role="alert" className="text-sm text-destructive sm:col-span-2">{erreurGlobale}</p>
                  )}
                  <FormField label="Nom du rapport" required htmlFor="ep-name" error={erreurs.name} fullWidth>
                    <Input
                      id="ep-name"
                      value={form.name}
                      onChange={maj('name')}
                      invalid={!!erreurs.name}
                      autoFocus
                    />
                  </FormField>

                  <FormField label="Rapport à envoyer" htmlFor="ep-kind" error={erreurs.target_kind}>
                    <select
                      id="ep-kind"
                      className={CLASSE_SELECT}
                      value={form.target_kind}
                      onChange={maj('target_kind')}
                      aria-invalid={erreurs.target_kind ? true : undefined}
                    >
                      {TARGET_KINDS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                    </select>
                  </FormField>

                  {avecCible && (
                    <FormField
                      label={form.target_kind === 'dashboard'
                        ? 'Identifiant du tableau de bord'
                        : 'Identifiant de la requête sauvegardée'}
                      htmlFor="ep-cible"
                      error={erreurs.cible_id}
                    >
                      <Input
                        id="ep-cible"
                        inputMode="numeric"
                        value={form.cible_id}
                        onChange={maj('cible_id')}
                        invalid={!!erreurs.cible_id}
                      />
                    </FormField>
                  )}

                  <FormField label="Cadence" htmlFor="ep-schedule" error={erreurs.schedule}>
                    <select
                      id="ep-schedule"
                      className={CLASSE_SELECT}
                      value={form.schedule}
                      onChange={maj('schedule')}
                      aria-invalid={erreurs.schedule ? true : undefined}
                    >
                      {SCHEDULES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                    </select>
                  </FormField>

                  <FormField
                    label="Heure d'envoi (0-23, heure de Casablanca)"
                    htmlFor="ep-heure"
                    hint="Vide : à l'heure de passage du planificateur."
                    error={erreurs.heure_envoi}
                  >
                    <Input
                      id="ep-heure"
                      inputMode="numeric"
                      value={form.heure_envoi}
                      onChange={maj('heure_envoi')}
                      invalid={!!erreurs.heure_envoi}
                    />
                  </FormField>

                  {form.schedule === 'monthly' && (
                    <FormField label="Jour du mois (1-28)" htmlFor="ep-jour" error={erreurs.jour_du_mois}>
                      <Input
                        id="ep-jour"
                        inputMode="numeric"
                        value={form.jour_du_mois}
                        onChange={maj('jour_du_mois')}
                        invalid={!!erreurs.jour_du_mois}
                      />
                    </FormField>
                  )}

                  <FormField label="Canal" htmlFor="ep-canal" error={erreurs.canal}>
                    <select
                      id="ep-canal"
                      className={CLASSE_SELECT}
                      value={form.canal}
                      onChange={maj('canal')}
                      aria-invalid={erreurs.canal ? true : undefined}
                    >
                      {CANAUX.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                    </select>
                  </FormField>

                  {form.canal === 'email' ? (
                    <FormField
                      label="Destinataires (emails)"
                      htmlFor="ep-recipients"
                      hint="Séparés par une virgule, un point-virgule ou un retour à la ligne."
                      error={erreurs.recipients}
                      fullWidth
                    >
                      <Textarea
                        id="ep-recipients"
                        value={form.recipients}
                        onChange={maj('recipients')}
                        invalid={!!erreurs.recipients}
                      />
                    </FormField>
                  ) : (
                    <FormField
                      label="Numéros WhatsApp"
                      htmlFor="ep-whatsapp"
                      hint="Séparés par une virgule, un point-virgule ou un retour à la ligne."
                      error={erreurs.destinataires_whatsapp}
                      fullWidth
                    >
                      <Textarea
                        id="ep-whatsapp"
                        value={form.destinataires_whatsapp}
                        onChange={maj('destinataires_whatsapp')}
                        invalid={!!erreurs.destinataires_whatsapp}
                      />
                    </FormField>
                  )}

                  <div className="flex justify-end gap-2 sm:col-span-2">
                    <Button type="button" variant="outline" onClick={fermer}>Annuler</Button>
                    <Button type="submit" disabled={occupe}>
                      {editionId ? 'Enregistrer' : 'Créer'}
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader><CardTitle>Rapports programmés</CardTitle></CardHeader>
            <CardContent>
              {rapports.length === 0 ? (
                <EmptyState
                  icon={Mail}
                  title="Aucun envoi programmé"
                  description="Créez un envoi pour recevoir un rapport par email ou WhatsApp à intervalle régulier."
                  className="my-2"
                />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm" aria-label="Rapports programmés">
                    <thead>
                      <tr className="text-left text-xs uppercase text-muted-foreground">
                        <th className="py-2 pr-3">Rapport</th>
                        <th className="py-2 pr-3">Contenu</th>
                        <th className="py-2 pr-3">Cadence</th>
                        <th className="py-2 pr-3">Canal</th>
                        <th className="py-2 pr-3">Destinataires</th>
                        <th className="py-2 pr-3">Dernier envoi</th>
                        <th className="py-2 pr-3"><span className="sr-only">Actions</span></th>
                      </tr>
                    </thead>
                    <tbody>
                      {rapports.map((r) => (
                        <tr key={r.id} className="border-t" data-testid={`envoi-programme-${r.id}`}>
                          <td className="py-2 pr-3 font-medium">{r.name}</td>
                          <td className="py-2 pr-3">{r.target_kind_label || libelle(TARGET_KINDS, r.target_kind)}</td>
                          <td className="py-2 pr-3">{resume(r)}</td>
                          <td className="py-2 pr-3">{libelle(CANAUX, r.canal)}</td>
                          <td className="py-2 pr-3">{destinataires(r)}</td>
                          <td className="py-2 pr-3">{dateFr(r.last_sent_at)}</td>
                          <td className="py-2 pr-3">
                            <div className="flex justify-end gap-1">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => ouvrirEdition(r)}
                                aria-label={`Modifier ${r.name}`}
                              >
                                <Pencil />
                              </Button>
                              <Button variant="ghost" size="sm" onClick={() => supprimer(r)} aria-label={`Supprimer ${r.name}`}><Trash2 /></Button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex-row items-center justify-between gap-3">
              <CardTitle>Historique des envois</CardTitle>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={filtreEchecs}
                  onChange={(e) => setFiltreEchecs(e.target.checked)}
                />
                Échecs seulement
              </label>
            </CardHeader>
            <CardContent>
              {envois.lignes.length === 0 ? (
                <p className="text-sm text-muted-foreground" data-testid="envois-vide">
                  Aucun envoi enregistré.
                </p>
              ) : (
                <>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm" aria-label="Historique des envois">
                      <thead>
                        <tr className="text-left text-xs uppercase text-muted-foreground">
                          <th className="py-2 pr-3">Date</th>
                          <th className="py-2 pr-3">Rapport</th>
                          <th className="py-2 pr-3">Canal</th>
                          <th className="py-2 pr-3">Destinataires</th>
                          <th className="py-2 pr-3">Statut</th>
                          <th className="py-2 pr-3">Motif</th>
                        </tr>
                      </thead>
                      <tbody>
                        {envois.lignes.map((e) => (
                          <tr key={e.id} className="border-t" data-testid={`envoi-${e.id}`}>
                            <td className="py-2 pr-3">{dateFr(e.envoye_le)}</td>
                            <td className="py-2 pr-3">{e.rapport_nom}</td>
                            <td className="py-2 pr-3">{e.canal_label || libelle(CANAUX, e.canal)}</td>
                            <td className="py-2 pr-3">{e.destinataires || '—'}</td>
                            <td className="py-2 pr-3">
                              <StatusPill
                                tone={TON_STATUT[e.statut] ?? 'neutral'}
                                label={e.statut_label || libelle(STATUTS, e.statut)}
                              />
                            </td>
                            <td className="py-2 pr-3 text-muted-foreground">{e.erreur || '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {envois.suite && (
                    <p className="mt-2 text-xs text-muted-foreground" data-testid="envois-suite">
                      {`Les ${envois.lignes.length} envois les plus récents sur ${envois.total}.`}
                    </p>
                  )}
                </>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
