// AGR613 — fiche de recette POMPAGE (IEC 62253) : remplace la fiche IEC 62446-1
// pour un chantier agricole. Niveaux / HMT / débit / électrique / essais, et
// le bloc de comparaison au devis (promesse FIGÉE, débit attendu, écart,
// seuil société). Tout le calcul vient du serveur (`record.comparaison`) :
// l'écran ne recalcule ni écart ni verdict. Aucun prix ici.
import { useState } from 'react'
import installationsApi from '../../api/installationsApi'
import {
  Button, Badge,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
  DialogFooter, Input, Textarea, Label,
} from '../../ui'

const TRI_ETAT = [
  { value: '', label: 'Non renseigné' },
  { value: 'true', label: 'Conforme' },
  { value: 'false', label: 'Non conforme' },
]

const RESULTATS = [
  { value: 'en_cours', label: 'En cours' },
  { value: 'conforme', label: 'Conforme' },
  { value: 'reserves', label: 'Conforme avec réserves' },
  { value: 'non_conforme', label: 'Non conforme' },
]

const METHODES = [
  { value: '', label: 'Non renseignée' },
  { value: 'compteur', label: 'Compteur' },
  { value: 'jaugeage', label: 'Jaugeage' },
]

const SOURCES_IRRADIANCE = [
  { value: '', label: 'Non renseignée' },
  { value: 'mesuree', label: 'Mesurée' },
  { value: 'estimee', label: 'Estimée' },
]

const SECTIONS = [
  {
    titre: 'Niveaux d’eau',
    mesures: [
      ['niveau_statique_m', 'Niveau statique (m)'],
      ['niveau_dynamique_m', 'Niveau dynamique (m)'],
    ],
  },
  {
    titre: 'Hauteur manométrique',
    mesures: [['hmt_mesuree_m', 'HMT mesurée (m)']],
  },
  {
    titre: 'Débit',
    mesures: [
      ['debit_mesure_m3h', 'Débit mesuré (m³/h)'],
      ['index_compteur_m3', 'Index du compteur (m³)'],
    ],
    choix: [['methode_debit', 'Méthode de mesure du débit', METHODES]],
  },
  {
    titre: 'Électrique',
    mesures: [
      ['courant_plaque_a', 'Courant de plaque (A)'],
      ['courant_phase_1_a', 'Courant phase 1 (A)'],
      ['courant_phase_2_a', 'Courant phase 2 (A) — vide en monophasé'],
      ['courant_phase_3_a', 'Courant phase 3 (A) — vide en monophasé'],
      ['tension_v', 'Tension (V)'],
      ['frequence_variateur_hz', 'Fréquence du variateur (Hz)'],
      ['irradiance_wm2', 'Irradiance (W/m²)'],
      ['isolement_moteur_mohm', 'Isolement du moteur (MΩ)'],
    ],
    choix: [['source_irradiance', 'Source de l’irradiance', SOURCES_IRRADIANCE]],
  },
  {
    titre: 'Essais',
    essais: [
      ['isolement_ok', 'Isolement du moteur'],
      ['sens_rotation_ok', 'Sens de rotation'],
      ['test_marche_a_sec_ok', 'Protection marche à sec'],
    ],
  },
]

const boolVersTexte = (v) => (v === true ? 'true' : v === false ? 'false' : '')
const texteVersBool = (v) => (v === 'true' ? true : v === 'false' ? false : null)
// Un nombre TAPÉ n'est jamais rogné ni arrondi : il part tel quel, ou null.
const nombreOuNull = (v) => (v === '' || v == null ? null : v)

const idChamp = (cle) => `recette-pompage-${cle}`

function etatDepuisRecord(record) {
  const etat = {
    date_essai: record?.date_essai ?? '',
    instrument_id: record?.instrument_id ?? '',
    resultat: record?.resultat ?? 'en_cours',
    observations: record?.observations ?? '',
    commentaire_ecart: record?.commentaire_ecart ?? '',
  }
  for (const s of SECTIONS) {
    for (const [cle] of s.mesures ?? []) etat[cle] = record?.[cle] ?? ''
    for (const [cle] of s.choix ?? []) etat[cle] = record?.[cle] ?? ''
    for (const [cle] of s.essais ?? []) etat[cle] = boolVersTexte(record?.[cle])
  }
  return etat
}

function payloadDepuisEtat(etat) {
  const payload = {
    date_essai: etat.date_essai || null,
    instrument_id: etat.instrument_id,
    resultat: etat.resultat,
    observations: etat.observations,
    commentaire_ecart: etat.commentaire_ecart,
  }
  for (const s of SECTIONS) {
    for (const [cle] of s.mesures ?? []) payload[cle] = nombreOuNull(etat[cle])
    for (const [cle] of s.choix ?? []) payload[cle] = etat[cle]
    for (const [cle] of s.essais ?? []) payload[cle] = texteVersBool(etat[cle])
  }
  return payload
}

// Les erreurs DRF `{champ: [msg]}` s'affichent sous LEUR champ ; le reste
// (detail, verrouillee, réseau) en bandeau.
function erreursDepuis(err) {
  const data = err?.response?.data
  const champs = {}
  let general = null
  if (data && typeof data === 'object') {
    for (const [cle, val] of Object.entries(data)) {
      const msg = Array.isArray(val) ? val.join(' ') : String(val)
      if (cle === 'detail' || cle === 'non_field_errors' || cle === 'verrouillee') {
        general = msg
      } else {
        champs[cle] = msg
      }
    }
  }
  if (!general && Object.keys(champs).length === 0) {
    general = "L'enregistrement de la fiche a échoué — vérifiez les valeurs saisies."
  }
  return { champs, general }
}

const fmt = (v, unite = '') => (v == null ? '—' : `${v}${unite}`)

function Erreur({ cle, erreurs }) {
  const msg = erreurs.champs[cle]
  if (!msg) return null
  return (
    <p className="form-error text-xs" role="alert" data-testid={`erreur-${cle}`}>{msg}</p>
  )
}

function Comparaison({ comparaison }) {
  if (!comparaison) return null
  const { promesse = {}, omissions = [] } = comparaison
  const seuil = comparaison.seuil_ecart_pct
  return (
    <section className="flex flex-col gap-2 rounded-lg border border-border p-3"
             data-testid="recette-pompage-comparaison">
      <h4 className="text-sm font-semibold">Comparaison au devis</h4>
      <dl className="grid gap-x-4 gap-y-1 text-sm sm:grid-cols-2">
        <dt className="text-muted-foreground">Devis de référence</dt>
        <dd>
          {fmt(promesse.devis_reference)}
          {promesse.figee_le ? ` (figé le ${promesse.figee_le})` : ''}
        </dd>
        <dt className="text-muted-foreground">Débit promis à la HMT du devis</dt>
        <dd data-testid="cmp-promis">
          {fmt(promesse.debit_hmt_m3h, ' m³/h')} à {fmt(promesse.hmt_m, ' m')}
        </dd>
        <dt className="text-muted-foreground">Débit attendu à la HMT mesurée</dt>
        <dd data-testid="cmp-attendu">
          {fmt(comparaison.debit_attendu_a_hmt_mesuree_m3h, ' m³/h')}
        </dd>
        <dt className="text-muted-foreground">Écart au débit promis</dt>
        <dd data-testid="cmp-ecart">{fmt(comparaison.ecart_debit_pct, ' %')}</dd>
        <dt className="text-muted-foreground">Seuil de la société</dt>
        <dd data-testid="cmp-seuil">
          {seuil == null ? 'seuil non saisi en Paramètres' : `${seuil} %`}
        </dd>
      </dl>
      {comparaison.hors_seuil === true && (
        <Badge tone="danger">Écart hors seuil</Badge>
      )}
      {omissions.length > 0 && (
        <ul className="flex flex-col gap-0.5 text-xs text-muted-foreground"
            data-testid="cmp-omissions">
          {omissions.map((o) => <li key={o.cle}>• {o.motif}</li>)}
        </ul>
      )}
      {comparaison.note_formule && (
        <p className="text-xs text-muted-foreground">{comparaison.note_formule}</p>
      )}
    </section>
  )
}

export default function RecettePompageDialog({
  installationId, record: recordInitial, onClose, onSaved,
}) {
  const [record, setRecord] = useState(recordInitial ?? null)
  const [etat, setEtat] = useState(() => etatDepuisRecord(recordInitial))
  const [busy, setBusy] = useState(false)
  const [erreurs, setErreurs] = useState({ champs: {}, general: null })

  const verrouillee = Boolean(record?.verrouillee)
  const comparaison = record?.comparaison ?? null
  const commentaireRequis = Boolean(comparaison?.commentaire_requis)
  const champ = (cle) => (valeur) => setEtat((p) => ({ ...p, [cle]: valeur }))

  const enregistrer = async () => {
    setBusy(true)
    setErreurs({ champs: {}, general: null })
    try {
      let id = record?.id
      // La fiche n'est créée qu'à la PREMIÈRE sauvegarde.
      if (!id) {
        const cree = await installationsApi.ouvrirRecettePompage(installationId)
        id = cree.data?.record?.id
        if (cree.data?.record) setRecord(cree.data.record)
      }
      const r = await installationsApi.updateRecettePompage(id, payloadDepuisEtat(etat))
      setRecord(r.data?.record ?? null)
      onSaved?.(r.data)
    } catch (err) {
      setErreurs(erreursDepuis(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="max-h-[92vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Recette de pompage (IEC 62253)</DialogTitle>
          <DialogDescription>
            Essai de mise en service de la pompe. Un champ laissé vide reste
            « non renseigné » — jamais présumé conforme.
            {verrouillee && ' Fiche verrouillée : le PV de réception est signé, lecture seule.'}
          </DialogDescription>
        </DialogHeader>

        {/* Les nombres tapés ne sont NI rognés NI rejetés : `noValidate`,
            chaque champ numérique en `step="any"`. */}
        <form noValidate className="flex flex-col gap-5" onSubmit={(e) => e.preventDefault()}>
          <fieldset disabled={verrouillee} className="flex flex-col gap-5 border-0 p-0">
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor={idChamp('date_essai')}>Date d’essai</Label>
                <Input id={idChamp('date_essai')} type="date" value={etat.date_essai}
                       onChange={(e) => champ('date_essai')(e.target.value)} />
                <Erreur cle="date_essai" erreurs={erreurs} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor={idChamp('instrument_id')}>Instrument de mesure</Label>
                <Input id={idChamp('instrument_id')} value={etat.instrument_id}
                       onChange={(e) => champ('instrument_id')(e.target.value)} />
                <Erreur cle="instrument_id" erreurs={erreurs} />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor={idChamp('resultat')}>Résultat</Label>
                <select id={idChamp('resultat')} className="form-control"
                        value={etat.resultat}
                        onChange={(e) => champ('resultat')(e.target.value)}>
                  {RESULTATS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
                <Erreur cle="resultat" erreurs={erreurs} />
              </div>
            </div>

            {SECTIONS.map((s) => (
              <section key={s.titre} className="flex flex-col gap-2">
                <h4 className="text-sm font-semibold">{s.titre}</h4>
                <div className="grid gap-3 sm:grid-cols-3">
                  {(s.mesures ?? []).map(([cle, libelle]) => (
                    <div key={cle} className="flex flex-col gap-1.5">
                      <Label htmlFor={idChamp(cle)}>{libelle}</Label>
                      <Input id={idChamp(cle)} type="number" step="any"
                             value={etat[cle]}
                             onChange={(e) => champ(cle)(e.target.value)} />
                      <Erreur cle={cle} erreurs={erreurs} />
                    </div>
                  ))}
                  {(s.choix ?? []).map(([cle, libelle, options]) => (
                    <div key={cle} className="flex flex-col gap-1.5">
                      <Label htmlFor={idChamp(cle)}>{libelle}</Label>
                      <select id={idChamp(cle)} className="form-control"
                              value={etat[cle]}
                              onChange={(e) => champ(cle)(e.target.value)}>
                        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                      </select>
                      <Erreur cle={cle} erreurs={erreurs} />
                    </div>
                  ))}
                  {(s.essais ?? []).map(([cle, libelle]) => (
                    <div key={cle} className="flex flex-col gap-1.5">
                      <Label htmlFor={idChamp(cle)}>{libelle}</Label>
                      <select id={idChamp(cle)} className="form-control"
                              value={etat[cle]}
                              onChange={(e) => champ(cle)(e.target.value)}>
                        {TRI_ETAT.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                      </select>
                      <Erreur cle={cle} erreurs={erreurs} />
                    </div>
                  ))}
                </div>
              </section>
            ))}

            <Comparaison comparaison={comparaison} />

            <div className="flex flex-col gap-1.5">
              <Label htmlFor={idChamp('commentaire_ecart')}>
                Commentaire sur l’écart
                {commentaireRequis && (
                  <span className="ml-1 font-semibold text-destructive">(obligatoire)</span>
                )}
              </Label>
              <Textarea id={idChamp('commentaire_ecart')} rows={2}
                        value={etat.commentaire_ecart}
                        onChange={(e) => champ('commentaire_ecart')(e.target.value)} />
              {commentaireRequis && (
                <p className="text-xs text-destructive" data-testid="commentaire-requis">
                  L’écart dépasse le seuil de la société : ce commentaire est obligatoire.
                </p>
              )}
              <Erreur cle="commentaire_ecart" erreurs={erreurs} />
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor={idChamp('observations')}>Observations</Label>
              <Textarea id={idChamp('observations')} rows={3} value={etat.observations}
                        onChange={(e) => champ('observations')(e.target.value)} />
              <Erreur cle="observations" erreurs={erreurs} />
            </div>
          </fieldset>

          {erreurs.general && (
            <p className="form-error" role="alert">{erreurs.general}</p>
          )}
        </form>

        <DialogFooter className="flex-wrap">
          <Button type="button" variant="ghost" onClick={onClose}>Fermer</Button>
          {!verrouillee && (
            <Button type="button" loading={busy} onClick={enregistrer}>
              Enregistrer la fiche
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
