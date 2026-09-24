import { useEffect, useId, useState } from 'react'
import { Button, FormField, Input } from '../../../../ui'
import AssigneePicker from '../../../../components/AssigneePicker'
import crmApi from '../../../../api/crmApi'
import { toast, toastPromise } from '../../../../ui/confirm'
import { getApiError } from '../../../../lib/apiError'
import useCanaux from '../../useCanaux'
import { TYPE_INSTALLATION_LABELS, PRIORITE_LABELS } from '../../stages'
import { getField, isSuggested } from '../draftCore'
import CadenceFrise from './CadenceFrise'
// QJ-ARBRE — l'historique condensé du client, colonne droite du Suivi
// commercial (données déjà chargées par le shell — aucun appel réseau ici).
import ArbreHistorique from './ArbreHistorique'
// RLC2 — le journal « ce qui s'est passé » du PLAN DE RELANCE (avec la cause de
// chaque ligne) + l'état courant en une phrase. Lecture serveur dédiée.
import JournalRelance from './JournalRelance'

// Les trois cadences nommées du gabarit (MRY4) — jamais un libellé inventé.
const CADENCE_CHOICES = [
  { value: 'contact', label: 'Contact' },
  { value: 'apres_devis', label: 'Après devis' },
  { value: 'reveil', label: 'Réveil' },
]

// MRY15 — remplace l'ancien « Initialiser le plan de relance » (fondation
// relance du 24/08/2026, revue Fable finale) : le moteur démarre maintenant
// SEUL à l'arrivée d'un lead vivant (MRY6) — ce contrôle sert à RELANCER une
// cadence manuellement (choix contact/après devis/réveil, appel IDEMPOTENT
// par cadence, `apps/crm/views.py initialiser_relance`) ou à L'ARRÊTER
// (motif obligatoire, `arreter_relance` — MRY9). `onChanged` fait recharger
// la frise juste en dessous (CadenceFrise) sans dupliquer sa logique réseau.
function RelanceCadenceControls({ leadId, onChanged }) {
  const [cadence, setCadence] = useState('contact')
  const [busy, setBusy] = useState(false)
  const [arretOpen, setArretOpen] = useState(false)
  const [motif, setMotif] = useState('')
  // CAD51 — relancer une cadence PLUS prioritaire ARRÊTE celle en cours : le
  // serveur refuse (409) tant que ce n'est pas confirmé, et renvoie ce qui
  // serait perdu (`remplacement` : cadence(s) arrêtée(s), touches ouvertes).
  // L'écran le dit, demande un motif (comme « Arrêter la cadence ») et ne
  // relance qu'après. CAD55 — « Après devis » cite le devis envoyé du lead :
  // plusieurs → « lequel ? » en une ligne (`devis_a_choisir`, le plus récent
  // proposé) ; aucun → l'avertissement AVANT le lancement (`sans_devis`).
  // Toutes les questions arrivent dans UN 409 et repartent ensemble.
  // Contrat : apps/crm/contract_samples/lead_relance_initialiser.json.
  const [questions, setQuestions] = useState(null)
  const [motifRemplacement, setMotifRemplacement] = useState('')
  const [devisChoisi, setDevisChoisi] = useState('')
  const [erreurs, setErreurs] = useState({})
  // Champs de la CONFIRMATION de relance, pas des champs du lead : ids
  // générés (hors `fieldLabels`, qui ne cartographie que les colonnes du
  // lead) — leurs erreurs 400 s'affichent directement sous eux.
  const idMotif = useId()
  const idDevis = useId()

  if (leadId == null) return null

  const fermerQuestions = () => {
    setQuestions(null)
    setMotifRemplacement('')
    setDevisChoisi('')
    setErreurs({})
  }

  const relancer = async (reponses = {}) => {
    setBusy(true)
    setErreurs({})
    try {
      await crmApi.initialiserRelance(leadId, { cadence, ...reponses }, { suppressErrorToast: true })
      toast.success('Cadence relancée.')
      fermerQuestions()
      onChanged?.()
    } catch (err) {
      const data = err?.response?.data
      const aDesQuestions = !!(data && (data.remplacement || data.devis_a_choisir || data.sans_devis))
      if (err?.response?.status === 409 && aDesQuestions) {
        // Les textes qui NOMMENT ce qui se passera viennent du serveur.
        setQuestions({
          remplacement: data.remplacement ?? null,
          messageRemplacement: data.erreurs?.confirmer_remplacement?.[0] ?? '',
          devisAChoisir: data.devis_a_choisir ?? null,
          sansDevis: !!data.sans_devis,
          messageDevis: data.erreurs?.devis?.[0] ?? '',
        })
        if (data.devis_a_choisir) setDevisChoisi(String(data.devis_a_choisir.propose))
      } else if (data?.erreurs) {
        // 400 qui nomme le champ (motif, devis, cadence) : affiché dessous.
        setErreurs(data.erreurs)
      } else {
        toast.error(getApiError(err, 'Relance de la cadence impossible.').message)
      }
    } finally {
      setBusy(false)
    }
  }

  const confirmer = () => {
    const reponses = {}
    if (questions.remplacement) {
      reponses.confirmer_remplacement = true
      reponses.motif = motifRemplacement.trim()
    }
    if (questions.devisAChoisir) reponses.devis = Number(devisChoisi)
    if (questions.sansDevis) reponses.sans_devis_confirme = true
    relancer(reponses)
  }

  const erreurCadence = erreurs.cadence?.[0]
  const erreurMotif = erreurs.motif?.[0]
  const erreurDevis = erreurs.devis?.[0]
  const libelleConfirmer = !questions ? ''
    : questions.remplacement
      ? `Arrêter ${questions.remplacement.cadences_arretees_libelles.map((l) => `« ${l} »`).join(', ')} et relancer`
      : questions.sansDevis ? 'Lancer sans devis' : 'Relancer avec ce devis'
  const confirmationIncomplete = !!questions && (
    (!!questions.remplacement && !motifRemplacement.trim())
    || (!!questions.devisAChoisir && !devisChoisi))
  const dateFr = (iso) => (iso ? iso.split('-').reverse().join('/') : '')

  const arreter = async () => {
    const m = motif.trim()
    if (!m) return
    setBusy(true)
    try {
      await toastPromise(crmApi.arreterCadence(leadId, { motif: m }), {
        loading: 'Arrêt de la cadence…',
        success: 'Cadence arrêtée.',
        error: 'Arrêt de la cadence impossible.',
      })
      setArretOpen(false)
      setMotif('')
      onChanged?.()
    } catch {
      // toastPromise a déjà affiché l'erreur — rien de plus à faire ici.
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mt-1.5 flex flex-col gap-1.5">
      <div className="flex flex-wrap items-center gap-1.5">
        <select
          className={erreurCadence ? 'form-select is-invalid' : 'form-select'}
          aria-label="Cadence à relancer" value={cadence}
          aria-invalid={erreurCadence ? true : undefined}
          aria-describedby={erreurCadence ? 'lf-relance-cadence-erreur' : undefined}
          onChange={(e) => { setCadence(e.target.value); fermerQuestions() }} disabled={busy}
        >
          {CADENCE_CHOICES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>
        <Button
          type="button" size="sm" variant="outline" disabled={busy}
          data-testid="lf-relance-cadence" onClick={() => relancer()}
        >
          Relancer la cadence
        </Button>
        <Button
          type="button" size="sm" variant="outline" disabled={busy}
          data-testid="lf-arreter-cadence" onClick={() => setArretOpen((o) => !o)}
        >
          Arrêter la cadence
        </Button>
      </div>
      {erreurCadence && (
        <p id="lf-relance-cadence-erreur" role="alert" className="text-xs text-destructive">
          {erreurCadence}
        </p>
      )}
      {erreurDevis && !questions?.devisAChoisir && (
        <p role="alert" className="text-xs text-destructive">{erreurDevis}</p>
      )}
      {questions && (
        <div
          className="flex flex-col gap-1.5 rounded-md border border-warning/40 bg-warning/10 p-2"
          data-testid="lf-relance-confirmation" role="alertdialog"
          aria-label="Confirmer avant de relancer la cadence"
        >
          {questions.remplacement && (
            <div className="flex flex-col gap-1.5" data-testid="cad51-confirmer-remplacement">
              <p className="text-xs">{questions.messageRemplacement}</p>
              <FormField
                label="Motif d’arrêt de la cadence en cours" required
                htmlFor={idMotif} error={erreurMotif} errorKind="required"
              >
                <Input
                  id={idMotif} invalid={!!erreurMotif}
                  value={motifRemplacement}
                  onChange={(e) => setMotifRemplacement(e.target.value)}
                  data-testid="lf-remplacement-motif"
                />
              </FormField>
            </div>
          )}
          {questions.devisAChoisir && (
            <div className="flex flex-col gap-1.5" data-testid="cad55-choix-devis">
              <p className="text-xs">{questions.messageDevis}</p>
              <FormField label="Devis cité par le suivi" htmlFor={idDevis} error={erreurDevis}>
                <select
                  id={idDevis}
                  className={erreurDevis ? 'form-select is-invalid' : 'form-select'}
                  aria-invalid={erreurDevis ? true : undefined}
                  value={devisChoisi} onChange={(e) => setDevisChoisi(e.target.value)}
                >
                  {questions.devisAChoisir.choix.map((d) => (
                    <option key={d.id} value={String(d.id)}>
                      {d.reference}{d.date_envoi ? ` — envoyé le ${dateFr(d.date_envoi)}` : ''}
                    </option>
                  ))}
                </select>
              </FormField>
            </div>
          )}
          {questions.sansDevis && (
            <p className="text-xs" data-testid="cad55-sans-devis" role="status">
              {questions.messageDevis}
            </p>
          )}
          <div className="flex flex-wrap items-center gap-1.5">
            <Button
              type="button" size="sm" variant="outline" disabled={busy}
              onClick={fermerQuestions}
            >
              Annuler
            </Button>
            <Button
              type="button" size="sm" disabled={busy || confirmationIncomplete}
              data-testid="lf-relance-confirmer" onClick={confirmer}
            >
              {libelleConfirmer}
            </Button>
          </div>
        </div>
      )}
      {arretOpen && (
        <div className="flex flex-wrap items-center gap-1.5">
          <Input
            placeholder="Motif d'arrêt (obligatoire)" value={motif}
            onChange={(e) => setMotif(e.target.value)}
            data-testid="lf-arreter-cadence-motif"
          />
          <Button
            type="button" size="sm" variant="outline" disabled={busy}
            onClick={() => { setArretOpen(false); setMotif('') }}
          >
            Annuler
          </Button>
          <Button type="button" size="sm" disabled={busy || !motif.trim()} onClick={arreter}>
            Confirmer
          </Button>
        </div>
      )}
    </div>
  )
}

// Langue préférée du contact — pré-sélectionne la langue du message WhatsApp.
const LANGUES_PREFEREES = { fr: 'Français', darija: 'Darija' }

// CAD65 — civilité du client (FACULTATIVE) : elle décide de la salutation de
// tous les messages (« Bonjour Mme Salma » / « لالة »). Vide = salutation
// NEUTRE (le prénom seul), jamais un « M. » supposé.
// source-choix: crm.Lead.civilite
const CIVILITES = { 'M.': 'M.', Mme: 'Mme' }

// CAD150 — préférence de contact du CLIENT (vide = non renseignée).
// source-choix: crm.Lead.contact_preference
const CONTACT_PREFERENCES = { whatsapp_only: 'WhatsApp uniquement', phone_ok: 'Rappel téléphonique OK' }

const enumOptions = (labels) => [
  <option key="" value="">—</option>,
  ...Object.entries(labels).map(([k, l]) => <option key={k} value={k}>{l}</option>),
]

// LW11 — Suivi commercial SANS le select d'étape (remplacé par StageControl
// LW16, rail identité). Port 1:1 des autres champs pipeline + verrous perdu/motif.
export default function SectionPipeline({ state, setField, errors = {}, refData = {} }) {
  const v = (k) => getField(state, k) ?? ''
  // F4 — `relanceVersion` (LeadWorkspace, bumpé par les raccourcis « ⋯ » du
  // rail identité — hors de cette section) est COMBINÉ au compteur local
  // `friseReload` ci-dessous (propres boutons Relancer/Arrêter de CETTE
  // section) : les deux sources de rechargement de la frise coexistent sans
  // jamais s'écraser l'une l'autre.
  const { users = [], tagOptions = [], motifOptions = [], relanceVersion = 0, onRelanceChanged } = refData
  const { labels: canalLabels } = useCanaux()
  const perdu = !!getField(state, 'perdu')
  const neplusContacter = !!getField(state, 'ne_plus_contacter')
  // CAD144 — même règle que SectionContact : `pii_masked` vient du serveur.
  const piiMasked = !!(state.server && state.server.pii_masked)
  const ownerSuggested = isSuggested(state, 'owner')
  // MRY15 — bumped après « Relancer »/« Arrêter la cadence » pour forcer
  // CadenceFrise à recharger, sans dupliquer sa logique réseau ici.
  const [friseReload, setFriseReload] = useState(0)
  // MRY32 — la frise fait désormais elle-même Fait/Sauter/Reporter/WhatsApp
  // (touches compactes) : son propre `onChanged` doit à la fois recharger LA
  // FRISE (même compteur que ci-dessus) et LA FICHE entière (une touche
  // « Fait » peut avancer l'étape/les tags du lead — `refData.onRelanceChanged`,
  // posé par `LeadWorkspace.jsx`).
  const onFriseChanged = () => {
    setFriseReload((n) => n + 1)
    onRelanceChanged?.()
  }

  // CAD48 — le champ « Relance le » ci-dessous ment sur ce qu'il fait : sur
  // un lead à cadence active, son PATCH n'ajoute pas un rappel, il appelle
  // `reporter_prochaine_touche` (`apps/crm/views.py`) — il déplace la
  // PROCHAINE touche ET tout le reste du plan. Lu ici en LECTURE SEULE
  // (`getRelanceEtapesLead`, même appel que `CadenceFrise`) : une cadence est
  // « active » tant qu'au moins une étape reste `a_faire`. Recalculé après
  // chaque geste de cadence (mêmes jetons que la frise/le journal).
  const [cadenceLue, setCadenceActive] = useState(false)
  // Sans fiche (création), aucune cadence : dérivé au rendu plutôt qu'un
  // setState synchrone dans l'effet (règle react-hooks/set-state-in-effect).
  const cadenceActive = state.leadId != null && cadenceLue
  useEffect(() => {
    if (state.leadId == null) return undefined
    let actif = true
    crmApi.getRelanceEtapesLead(state.leadId)
      .then((r) => {
        if (!actif) return
        const etapes = r.data?.results ?? r.data ?? []
        setCadenceActive(etapes.some((e) => e.statut === 'a_faire'))
      })
      .catch(() => { if (actif) setCadenceActive(false) })
    return () => { actif = false }
  }, [state.leadId, friseReload, relanceVersion])

  return (
    <>
      <div className="form-row">
        <FormField label="Type d'installation" htmlFor="lf-type-installation" error={errors.type_installation}>
          <select
            id="lf-type-installation"
            className={errors.type_installation ? 'form-select is-invalid' : 'form-select'}
            aria-invalid={errors.type_installation ? true : undefined}
            value={v('type_installation')}
            onChange={(e) => setField('type_installation', e.target.value)}
          >
            {enumOptions(TYPE_INSTALLATION_LABELS)}
          </select>
        </FormField>
        {/* VX249(b) — owner : champ « suggéré » à la création tant qu'il n'est
            pas touché. AssigneePicker n'expose pas de className : le contour va
            sur le wrapper (label stable pour l'e2e). */}
        <div className="form-group">
          <label className="form-label">Responsable</label>
          <div className={ownerSuggested ? 'vx-suggested-field inline-block rounded-full' : undefined}>
            <AssigneePicker
              users={users}
              value={v('owner')}
              onChange={(id) => setField('owner', id ?? '')}
            />
          </div>
          {ownerSuggested && (
            <p className="mt-1 text-xs text-muted-foreground">Suggéré — modifiable</p>
          )}
        </div>
        <div className="form-group">
          <FormField label="Relance le" htmlFor="lf-relance-date" error={errors.relance_date}>
            <Input
              id="lf-relance-date" type="date" invalid={!!errors.relance_date}
              value={v('relance_date')} onChange={(e) => setField('relance_date', e.target.value)}
            />
          </FormField>
          {/* CAD48 — dit ce que le champ fait RÉELLEMENT sur un lead à
              cadence active, jamais un rappel libre en plus (contraire à
              MRY10, « un seul système de rappel ») : on dit la vérité sur le
              champ existant. */}
          {cadenceActive && (
            <p className="mt-1 text-xs text-muted-foreground" data-testid="cad48-relance-le-note">
              Une cadence est active : modifier cette date déplace la
              prochaine touche ET tout le reste du plan.
            </p>
          )}
        </div>
      </div>
      {/* QJ-ARBRE (fondateur 09/09/2026) — le Suivi commercial se scinde en
          deux : à GAUCHE la cadence (contrôles + frise des touches, DOM
          inchangé — mêmes composants, seul l'emplacement bouge), à DROITE
          l'arbre « Historique en un coup d'œil » (ce qui s'est passé avec ce
          client, condensé — recherche marché dans ArbreHistorique.jsx). Sur
          panneau étroit les deux colonnes s'empilent (auto-fit). */}
      {state.mode === 'edit' && (
        <div className="lw-suivi-split">
          <div className="lw-suivi-split-col">
            <RelanceCadenceControls
              leadId={state.leadId}
              onChanged={() => setFriseReload((n) => n + 1)}
            />
            <div className="mt-1.5">
              <CadenceFrise
                leadId={state.leadId} reloadToken={friseReload + relanceVersion}
                onChanged={onFriseChanged}
              />
            </div>
          </div>
          <div className="lw-suivi-split-col">
            <ArbreHistorique
              historique={refData.historique}
              chatterRecent={state.server?.chatter_recent}
            />
            {/* RLC2 — sous l'arbre du client, l'histoire du PLAN : chaque
                ligne dit sa cause. Même jeton de rechargement que la frise
                (un geste de relance change les deux). */}
            <JournalRelance
              leadId={state.leadId}
              reloadToken={friseReload + relanceVersion}
            />
          </div>
        </div>
      )}
      <div className="form-row">
        {/* XSAL7 — pipeline pondéré pré-devis. */}
        <FormField label="Montant estimé (MAD)" htmlFor="lf-montant-estime" error={errors.montant_estime}>
          <Input
            id="lf-montant-estime" type="number" step="any" invalid={!!errors.montant_estime}
            value={v('montant_estime')} onChange={(e) => setField('montant_estime', e.target.value)}
          />
        </FormField>
        <FormField label="Clôture prévue le" htmlFor="lf-date-cloture" error={errors.date_cloture_prevue}>
          <Input
            id="lf-date-cloture" type="date" invalid={!!errors.date_cloture_prevue}
            value={v('date_cloture_prevue')} onChange={(e) => setField('date_cloture_prevue', e.target.value)}
          />
        </FormField>
      </div>
      <div className="form-row">
        <FormField label="Priorité" htmlFor="lf-priorite" error={errors.priorite}>
          <select
            id="lf-priorite" className={errors.priorite ? 'form-select is-invalid' : 'form-select'}
            aria-invalid={errors.priorite ? true : undefined}
            value={v('priorite')} onChange={(e) => setField('priorite', e.target.value)}
          >
            {enumOptions(PRIORITE_LABELS)}
          </select>
        </FormField>
        <FormField label="Canal" htmlFor="lf-canal" error={errors.canal}>
          <select
            id="lf-canal" className={errors.canal ? 'form-select is-invalid' : 'form-select'}
            aria-invalid={errors.canal ? true : undefined}
            value={v('canal')} onChange={(e) => setField('canal', e.target.value)}
          >
            {enumOptions(canalLabels)}
          </select>
        </FormField>
        {/* CAD65 — la civilité est une DONNÉE, plus un « M. » codé en dur
            dans les textes : saisie au premier contact, facultative. */}
        <FormField
          label="Civilité" htmlFor="lf-civilite" error={errors.civilite}
          hint="Facultative — vide : « Bonjour [prénom] », jamais un genre supposé."
        >
          <select
            id="lf-civilite" className={errors.civilite ? 'form-select is-invalid' : 'form-select'}
            aria-invalid={errors.civilite ? true : undefined}
            value={v('civilite')} onChange={(e) => setField('civilite', e.target.value)}
          >
            {enumOptions(CIVILITES)}
          </select>
        </FormField>
        <FormField label="Langue préférée" htmlFor="lf-langue-preferee" error={errors.langue_preferee}>
          <select
            id="lf-langue-preferee" className={errors.langue_preferee ? 'form-select is-invalid' : 'form-select'}
            aria-invalid={errors.langue_preferee ? true : undefined}
            value={v('langue_preferee')} onChange={(e) => setField('langue_preferee', e.target.value)}
          >
            {enumOptions(LANGUES_PREFEREES)}
          </select>
        </FormField>
        <div className="form-group fg-grow">
          <FormField label="Tags (séparés par des virgules)" htmlFor="lf-tags" error={errors.tags}>
            <Input
              id="lf-tags" invalid={!!errors.tags} value={v('tags')} onChange={(e) => setField('tags', e.target.value)}
              placeholder="ex: Régularisation 82-21, VIP" list="ld-tags"
            />
          </FormField>
          <datalist id="ld-tags">
            {tagOptions.map((t) => <option key={t.id} value={t.nom} />)}
          </datalist>
        </div>
      </div>
      {/* CAD144 — coopérative, comité industriel : un SECOND interlocuteur
          (co-associé, technicien). Champ libre, rien d'automatique : aucune
          relance ne lui part — le joindre reste un geste manuel. Le numéro
          est une PII (verrouillé sans `client_pii_voir`, comme le principal). */}
      <div className="form-row" data-testid="contact-secondaire">
        <FormField
          label="Contact secondaire (nom)" htmlFor="lf-contact-secondaire-nom"
          error={errors.contact_secondaire_nom}
        >
          <Input
            id="lf-contact-secondaire-nom" invalid={!!errors.contact_secondaire_nom}
            value={v('contact_secondaire_nom')}
            placeholder="ex : co-associé, technicien d’usine"
            onChange={(e) => setField('contact_secondaire_nom', e.target.value)}
          />
        </FormField>
        <FormField
          label="Contact secondaire (téléphone)" htmlFor="lf-contact-secondaire-tel"
          error={errors.contact_secondaire_telephone}
        >
          <Input
            id="lf-contact-secondaire-tel" type="tel" invalid={!!errors.contact_secondaire_telephone}
            value={v('contact_secondaire_telephone')} disabled={piiMasked}
            title={piiMasked
              ? 'Coordonnées masquées — votre rôle ne permet pas de voir/modifier les données personnelles.'
              : undefined}
            onChange={(e) => setField('contact_secondaire_telephone', e.target.value)}
          />
        </FormField>
        <p className="w-full text-xs text-muted-foreground">
          Aucune relance automatique n’est adressée à ce contact : le joindre reste un geste manuel.
        </p>
      </div>
      {/* CAD150 — `contact_preference` était déjà suivie (TRACKED_KEYS,
          SECTION_FIELDS.pipeline) : il ne lui manquait que son contrôle. Posée
          par le site OU à l'appel (« ne m'appelez pas, écrivez-moi »), elle
          change le CANAL des touches (CAD32). */}
      <div className="form-row">
        <FormField label="Préférence de contact" htmlFor="lf-contact-preference" error={errors.contact_preference}>
          <select
            id="lf-contact-preference"
            className={errors.contact_preference ? 'form-select is-invalid' : 'form-select'}
            aria-invalid={errors.contact_preference ? true : undefined}
            value={v('contact_preference')} onChange={(e) => setField('contact_preference', e.target.value)}
          >
            {enumOptions(CONTACT_PREFERENCES)}
          </select>
        </FormField>
      </div>
      {/* QW3 — préférence de contact explicite (posée par le site/webhook). */}
      {getField(state, 'contact_preference') === 'phone_ok' && (
        <div className="form-row">
          <span
            className="kb-badge-rappel rounded-full bg-info/15 px-1.5 py-0.5 text-info"
            title="Le client a demandé à être rappelé par téléphone"
          >
            ☎ Rappel demandé
          </span>
        </div>
      )}
      <div className="form-row">
        {/* « Perdu ? » — drapeau indépendant de l'étape (perdu à n'importe
            quelle étape). */}
        <div className="form-group" style={{ alignSelf: 'flex-end' }}>
          <label className="pdf-toggle">
            <input type="checkbox" checked={perdu} onChange={(e) => setField('perdu', e.target.checked)} />
            <span>Perdu ?</span>
          </label>
        </div>
        {/* MRY9/MRY15 — distinct de `perdu` : une demande explicite de la
            personne, jamais une conséquence automatique d'un statut. Bloque
            tout futur démarrage/relance de cadence (garde MRY6/MRY9). */}
        <div className="form-group" style={{ alignSelf: 'flex-end' }}>
          <label className="pdf-toggle">
            <input
              type="checkbox" checked={neplusContacter}
              onChange={(e) => setField('ne_plus_contacter', e.target.checked)}
            />
            <span>Ne plus contacter</span>
          </label>
        </div>
        {perdu && (
          <div className="form-group fg-grow">
            <FormField
              label="Motif de perte" required htmlFor="lf-motif-perte"
              error={errors.motif_perte} errorKind="required"
            >
              <Input
                id="lf-motif-perte" invalid={!!errors.motif_perte}
                value={v('motif_perte')} onChange={(e) => setField('motif_perte', e.target.value)}
                list="ld-motifs"
              />
              <datalist id="ld-motifs">
                {motifOptions.map((m) => <option key={m.id} value={m.nom} />)}
              </datalist>
            </FormField>
          </div>
        )}
      </div>
    </>
  )
}
