// CIQ125 — LE BLOC « PROFIL DÉCLARÉ » C&I (commercial ET industriel), UNE
// SEULE saisie de consommation : 12 kWh mensuels, OU un total annuel, OU les
// factures en MAD ; jours ouverts (aucun week-end pré-coché), plages horaires
// par type de jour, fermetures datées, talon (« je ne sais pas » possible),
// toit, raccordement (tension, phases, puissance souscrite), revente
// (MT seulement) et taille explicite. Ces champs forment le corps du contrat
// `etude_ci_preview.json` (voir `features/ventes/quote/profilCi.js`).
//
// QJR637 — monté UNE fois par les deux panneaux (PanneauIndustriel,
// PanneauCommercial), mêmes props. AUCUNE LOGIQUE NI AUCUN CALCUL ICI : l'état
// et les gestes arrivent en props ; sous chaque champ, la valeur RETENUE par
// le serveur (`entrees_resolues`) avec sa provenance. Saisie 100 % libre :
// chaque `<input type="number">` porte `step="any"` et `min="0"`, rien n'est
// arrondi ni rejeté (le `noValidate` reste sur le formulaire porteur).
import { Zap } from 'lucide-react'
import { Card, CardContent, Input, Label, Button } from '../../../ui'
import { formatNumber } from '../../../lib/format'
import { MONTHS_FR } from '../../../features/ventes/solar'
import { libelleProvenance } from '../../../features/ventes/etudeCiPreview'
import { inclinaisonRetenue, tailleLimiteeToit } from '../../../features/ventes/etudeCiPreviewPur'
import {
  JOURS_SEMAINE, TYPES_JOUR, LIBELLE_REPRIS_LEAD,
} from '../../../features/ventes/quote/profilCi'
import { GenCardHeader } from './CarteMetrique'
import CarteResultatCi from './CarteResultatCi'

/**
 * CIQ125 — LA carte C&I commune aux panneaux industriel et commercial : le
 * profil déclaré (UNE seule saisie de consommation — les factures hiver/été
 * et la facture réelle résidentielles n'y sont pas montées) puis le résultat
 * du moteur serveur tel quel. `children` = contenu propre au panneau
 * (catégorie commerciale).
 */
export function CarteProfilCi({
  profilCi, setChampCi, apercuCi, errors, children,
  tarifSaisie = null, setTarifChamp = null, reprisLead = [],
}) {
  const erreursTarif = errors?.tarifDeclare || {}
  const resolues = apercuCi?.donnees?.entrees_resolues || null
  // ADEV102 — le contrat suit la consommation (question 2), le détail du tarif
  // se range sous « Affiner » ; une erreur serveur sur ce détail l'ouvre.
  const tarif = (partie) => setTarifChamp && (
    <CarteTarifFacture partie={partie} tarif={tarifSaisie} setTarifChamp={setTarifChamp}
                       tension={profilCi?.tension} erreurs={erreursTarif}
                       repris={reprisLead} resolues={resolues} />
  )
  return (
    <Card>
      <GenCardHeader icon={Zap} title="Profil de consommation du site" />
      <CardContent className="pt-4">
        <BlocEtudeReseau
          profil={profilCi} setChamp={setChampCi}
          resolues={resolues}
          repris={reprisLead}
          erreurConso={errors?.conso}
          inclinaisonRetenue={inclinaisonRetenue(apercuCi?.donnees)}
          tailleLimiteeToit={tailleLimiteeToit(apercuCi?.donnees)}
          mentionReventeServeur={apercuCi?.donnees?.economie_ci?.revente?.statut === 'absente_bt'
            ? apercuCi.donnees.economie_ci.revente.mentions?.[0] : null}
          contrat={tarif('contrat')} affiner={tarif('affiner')} activite={children}
          affinerOuvert={Object.keys(erreursTarif).some((k) => k === 'base_tarifs' || k.startsWith('mt.'))}
        />
        <CarteResultatCi {...(apercuCi || {})} />
      </CardContent>
    </Card>
  )
}

export const MENTION_REVENTE_BT = 'Revente du surplus non ouverte en basse tension — ANRE décision 04/26.'
export const LIBELLE_REVENTE_MT = 'Revente du surplus (MT, plafond légal 20 %, tarif ANRE 04/26 HT)'

const CONTRATS = [
  { value: 'bt_domestique', label: 'BT domestique' },
  { value: 'bt_patente', label: 'BT patenté' },
  { value: 'bt_force_motrice', label: 'BT force motrice' },
  { value: 'mt_general', label: 'MT (Tarif Général)' },
]

function ErreurChamp({ erreurs, champ }) {
  if (!erreurs || !erreurs[champ]) return null
  return <p className="text-xs text-destructive" data-testid={`erreur-tarif-${champ}`}>{erreurs[champ]}</p>
}

/**
 * CIQ222 — LE TARIF DE SA FACTURE (contrat `tarifs_ci.json`, `tarif_declare`) :
 * contrat, base HT/TTC telle qu'imprimée, postes MT + prime fixe + puissance
 * souscrite, option bi-horaire (force motrice seulement), date de la facture.
 * Vide ⇒ la grille ONEE sert en repli (annoncé). Chaque nombre tel que tapé,
 * jamais corrigé ; les 400 du serveur s'affichent SOUS le champ nommé.
 *
 * ADEV102 — `partie` coupe la carte en deux : `'contrat'` = la question de
 * l'appel (le contrat d'électricité, option bi-horaire, repli annoncé),
 * `'affiner'` = le détail d'analyste (prix imprimés HT/TTC, source des prix,
 * date de la facture, postes MT), replié sous « Affiner l'étude ». Sans
 * `partie`, la carte entière.
 */
export function CarteTarifFacture({
  tarif, setTarifChamp, tension, erreurs = {}, resolues = null, repris = [], partie = null,
}) {
  const t = tarif || {}
  const mt = t.contrat === 'mt_general'
  const vide = !t.contrat && !t.pointe && !t.pleines && !t.creuses && !t.primeFixe
  const puissanceLead = resolues?.puissance_souscrite_kva?.valeur
  const question = (
    <>
      <AideAppel id="contrat">
        « Quel est votre contrat d&apos;électricité : basse tension patenté, force motrice, domestique,
        ou moyenne tension ? Il est écrit sur votre facture. »
      </AideAppel>
      <div className="grid gap-1.5 sm:max-w-xs">
        <Label htmlFor="gen-tarif-contrat">Contrat<BadgeRepris cle="contrat" repris={repris} /></Label>
        <select id="gen-tarif-contrat" className={SELECT} value={t.contrat || ''}
                onChange={(e) => setTarifChamp('contrat', e.target.value)}>
          <option value="">—</option>
          {CONTRATS.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>
        <ErreurChamp erreurs={erreurs} champ="contrat" />
      </div>
      {t.contrat === 'bt_force_motrice' && (
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input type="checkbox" data-testid="gen-tarif-bi-horaire"
                 checked={Boolean(t.optionBiHoraire)}
                 onChange={(e) => setTarifChamp('optionBiHoraire', e.target.checked)} />
          Option bi-horaire
        </label>
      )}
      {vide && (
        <p className="text-xs text-muted-foreground" data-testid="ci-tarif-repli">
          Aucun tarif saisi : la grille ONEE officielle sert en repli
          {tension === 'mt' ? ' (Tarif Général MT)' : ''}.
        </p>
      )}
    </>
  )
  const detail = (
    <>
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="grid gap-1.5">
          <Label htmlFor="gen-tarif-base">Prix imprimés</Label>
          <select id="gen-tarif-base" className={SELECT} value={t.baseTarifs || ''}
                  onChange={(e) => setTarifChamp('baseTarifs', e.target.value)}>
            <option value="">—</option>
            <option value="ht">HT</option>
            <option value="ttc">TTC</option>
          </select>
          <ErreurChamp erreurs={erreurs} champ="base_tarifs" />
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="gen-tarif-provenance">Source des prix</Label>
          <select id="gen-tarif-provenance" className={SELECT} value={t.provenance || ''}
                  onChange={(e) => setTarifChamp('provenance', e.target.value)}>
            <option value="">—</option>
            <option value="facture">Lus sur la facture</option>
            <option value="oral">Déclarés oralement</option>
          </select>
        </div>
        <div className="grid gap-1.5">
          <Label htmlFor="gen-tarif-date">Date de la facture</Label>
          <Input id="gen-tarif-date" type="date" value={t.dateFacture || ''}
                 onChange={(e) => setTarifChamp('dateFacture', e.target.value)} />
        </div>
      </div>
      {mt && (
        <div className="grid gap-4 sm:grid-cols-3" data-testid="ci-tarif-mt">
          {[
            ['pointe', 'tarif_pointe', 'Heures de pointe (MAD/kWh)'],
            ['pleines', 'tarif_pleines', 'Heures pleines (MAD/kWh)'],
            ['creuses', 'tarif_creuses', 'Heures creuses (MAD/kWh)'],
            ['primeFixe', 'prime_fixe_kva_an', 'Prime fixe (MAD/kVA/an)'],
            ['puissance', 'puissance_souscrite_kva', 'Puissance souscrite (kVA)'],
          ].map(([cle, champ, libelle]) => (
            <div className="grid gap-1.5" key={cle}>
              <Label htmlFor={`gen-tarif-${cle}`}>{libelle}</Label>
              <Input id={`gen-tarif-${cle}`} type="number" min="0" step="any"
                     placeholder={cle === 'puissance' && puissanceLead != null ? String(puissanceLead) : undefined}
                     value={t[cle] ?? ''} onChange={(e) => setTarifChamp(cle, e.target.value)} />
              <ErreurChamp erreurs={erreurs} champ={`mt.${champ}`} />
            </div>
          ))}
        </div>
      )}
    </>
  )
  if (partie === 'affiner') return <div className="grid gap-3" data-testid="ci-tarif-affiner">{detail}</div>
  return (
    <fieldset className="grid gap-3 rounded-lg border border-border p-3" data-testid="ci-tarif-facture">
      <legend className="text-sm font-semibold">
        {partie === 'contrat' ? "Contrat d'électricité" : 'Tarif de la facture'}
      </legend>
      {question}
      {partie !== 'contrat' && detail}
    </fieldset>
  )
}
const TYPES_POSE = [
  { value: 'toiture_inclinee', label: 'Toiture inclinée' },
  { value: 'bac_acier', label: 'Bac acier' },
  { value: 'toit_plat_leste', label: 'Toit plat lesté' },
  { value: 'toit_plat_fixe', label: 'Toit plat fixé' },
  { value: 'ombriere', label: 'Ombrière' },
  { value: 'sol', label: 'Au sol' },
]

const SELECT = 'form-control form-control-sm'

function valeurLisible(v) {
  if (v === null || v === undefined || v === '') return '—'
  if (typeof v === 'number') return formatNumber(v)
  if (typeof v === 'boolean') return v ? 'oui' : 'non'
  if (Array.isArray(v)) return v.map(valeurLisible).join(' · ')
  if (typeof v === 'object') {
    return Object.entries(v).filter(([, x]) => x !== null && x !== undefined)
      .map(([k, x]) => `${k} ${valeurLisible(x)}`).join(', ')
  }
  return String(v)
}

/** ADEV100 — « repris du lead » : la valeur du champ vient de la fiche lead, elle reste éditable. */
export function BadgeRepris({ cle, repris }) {
  if (!Array.isArray(repris) || !repris.includes(cle)) return null
  return (
    <span className="ml-1.5 rounded bg-info/10 px-1.5 py-0.5 text-[11px] font-normal text-info"
          data-testid={`ci-repris-${cle}`}>
      {LIBELLE_REPRIS_LEAD}
    </span>
  )
}

/**
 * La valeur retenue par le serveur + sa provenance, sous un champ. ADEV100 —
 * `champ` = la clé du champ d'écran que ce « Retenu » décrit : s'il a été
 * SEMÉ depuis le lead (`repris`), le badge « repris du lead » le remplace
 * (la valeur est déjà dans le champ, éditable) ; sinon l'indication reste.
 */
function Retenu({ resolues, cle, champ = null, repris = [] }) {
  if (champ && Array.isArray(repris) && repris.includes(champ)) {
    return <p className="text-xs"><BadgeRepris cle={champ} repris={repris} /></p>
  }
  const r = resolues && resolues[cle]
  if (!r) return null
  return (
    <p className="text-xs text-muted-foreground" data-testid={`ci-retenu-${cle}`}>
      Retenu : {valeurLisible(r.valeur)} — {libelleProvenance(r.provenance)}
    </p>
  )
}

function Nombre({ id, label, value, onChange, placeholder, testid }) {
  return (
    <div className="grid gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} type="number" min="0" step="any" placeholder={placeholder}
             data-testid={testid || id} value={value ?? ''}
             onChange={(e) => onChange(e.target.value)} />
    </div>
  )
}

// ADEV102 — les CINQ questions de l'appel, dans l'ordre : consommation, contrat,
// phase, activité et horaires, surface. Chaque question montre, en aide, la
// phrase posée au client (contrat `lead_pro.json`, `questions_pro`) — rien d'interne.
const QUESTION_CONSO = "« Combien payez-vous d'électricité par mois, à peu près ? Ou combien de kWh, si vous l'avez sous les yeux ? »"
const QUESTION_PHASE = '« Votre compteur est-il monophasé ou triphasé ? »'
const QUESTION_HORAIRES = '« Quelle est votre activité ? Quels jours et à quelles heures êtes-vous ouverts ? Fermez-vous certains mois de l\u2019année ? »'
const QUESTION_SURFACE = '« Où pourrait-on poser les panneaux, et quelle surface est disponible, à peu près ? »'

/** La phrase posée au client, en aide sous le titre d'une question. */
export function AideAppel({ id, children }) {
  return <p className="text-xs text-muted-foreground" data-testid={`ci-aide-${id}`}>{children}</p>
}

/**
 * `contrat` : la question 2 (contrat d'électricité), `activite` : le début de
 * la question 4 (catégorie commerciale), `affiner` : le complément du tarif —
 * trois emplacements remplis par `CarteProfilCi`. Les détails d'analyse sont
 * repliés sous « Affiner l'étude (facultatif) ».
 */
export default function BlocEtudeReseau({
  inclinaisonRetenue = null, tailleLimiteeToit = null,
  profil, setChamp, resolues = null, erreurConso, mentionReventeServeur = null, repris = [],
  contrat = null, activite = null, affiner = null, affinerOuvert = false,
}) {
  const p = profil || {}
  const estMt = p.tension === 'mt'
  const kwh = p.kwhMensuels || []
  const factures = p.factures || []
  const fermetures = p.fermetures || []
  return (
    <div className="mt-3.5 grid gap-4" data-testid="ci-profil">
      {/* ── 1. Consommation : UNE saisie (12 mois, total annuel OU factures MAD) ── */}
      <fieldset className="grid gap-2">
        <legend className="text-sm font-semibold">Consommation du site</legend>
        <AideAppel id="conso">{QUESTION_CONSO}</AideAppel>
        <div className="flex flex-wrap gap-3 text-sm" role="radiogroup" aria-label="Forme de la consommation">
          {[
            ['mensuel', '12 mois (kWh)'], ['annuel', 'Total annuel (kWh)'], ['factures', 'Factures (MAD)'],
          ].map(([v, l]) => (
            <label key={v} className="flex items-center gap-1.5 cursor-pointer">
              <input type="radio" name="ci-saisie-conso" value={v}
                     data-testid={`ci-saisie-${v}`}
                     checked={(p.saisieConso || 'mensuel') === v}
                     onChange={() => setChamp('saisieConso', v)} />
              {l}
            </label>
          ))}
        </div>
        {(p.saisieConso || 'mensuel') === 'mensuel' && (
          <div className="gen-monthly-grid">
            {MONTHS_FR.map((m, i) => (
              <div key={m} className="gen-month">
                <label className="gen-month-label" htmlFor={`gen-ci-kwh-${i}`}>{m}</label>
                <input id={`gen-ci-kwh-${i}`} type="number" min="0" step="any"
                       className="form-control form-control-sm"
                       value={kwh[i] ?? ''}
                       onChange={(e) => setChamp(`kwhMensuels.${i}`, e.target.value)} />
              </div>
            ))}
          </div>
        )}
        {p.saisieConso === 'annuel' && (
          <Nombre id="gen-ci-kwh-annuel" label="Consommation annuelle (kWh)"
                  placeholder="ex: 150000" value={p.kwhAnnuel}
                  onChange={(v) => setChamp('kwhAnnuel', v)} />
        )}
        {p.saisieConso === 'factures' && (
          <div className="grid gap-2" data-testid="ci-factures">
            {factures.map((f, i) => (
              <div className="grid gap-2 sm:grid-cols-3" key={i}>
                <Input type="month" aria-label={`Mois de la facture ${i + 1}`}
                       data-testid={`gen-ci-facture-mois-${i}`} value={f?.mois ?? ''}
                       onChange={(e) => setChamp(`factures.${i}.mois`, e.target.value)} />
                <Input type="number" min="0" step="any" aria-label={`Montant TTC (MAD) ${i + 1}`}
                       placeholder="Montant TTC (MAD)"
                       data-testid={`gen-ci-facture-montant-${i}`} value={f?.montant_ttc ?? ''}
                       onChange={(e) => setChamp(`factures.${i}.montant_ttc`, e.target.value)} />
                <Input type="number" min="0" step="any" aria-label={`kWh facturés ${i + 1}`}
                       placeholder="kWh (si imprimés)"
                       data-testid={`gen-ci-facture-kwh-${i}`} value={f?.kwh ?? ''}
                       onChange={(e) => setChamp(`factures.${i}.kwh`, e.target.value)} />
              </div>
            ))}
            <div>
              <Button type="button" variant="outline" size="sm"
                      onClick={() => setChamp('factures', [...factures, { mois: '', montant_ttc: '', kwh: '' }])}>
                Ajouter une facture
              </Button>
            </div>
          </div>
        )}
        <Retenu resolues={resolues} cle="kwh_mensuels" champ="kwhAnnuel" repris={repris} />
        {!repris.includes('kwhAnnuel') && <Retenu resolues={resolues} cle="kwh_annuel" />}
        {/* ERR-QAC-KWH-SAISI-INCOHERENT-FACTURES / CIQ125 — le refus s'affiche SOUS le champ. */}
        {erreurConso && (
          <p className="text-xs text-destructive" data-testid="erreur-conso">{erreurConso}</p>
        )}
      </fieldset>

      {/* ── 2. Contrat d'électricité (tarif de la facture) ── */}
      {contrat}

      {/* ── 3. Phase du compteur ── */}
      <fieldset className="grid gap-2 sm:grid-cols-3">
        <legend className="text-sm font-semibold">Phase du compteur</legend>
        <div className="sm:col-span-3"><AideAppel id="phase">{QUESTION_PHASE}</AideAppel></div>
        <div className="grid gap-1.5">
          <Label htmlFor="gen-ci-phases">Phases</Label>
          <select id="gen-ci-phases" className={SELECT} value={p.phases || ''}
                  onChange={(e) => setChamp('phases', e.target.value)}>
            <option value="">—</option>
            <option value="mono">Monophasé</option>
            <option value="tri">Triphasé</option>
            <option value="inconnu">Inconnu</option>
          </select>
          <Retenu resolues={resolues} cle="phases" champ="phases" repris={repris} />
        </div>
      </fieldset>

      {/* ── 4. Activité et horaires : catégorie, jours, heures, fermetures ── */}
      <fieldset className="grid gap-2">
        <legend className="text-sm font-semibold">Activité et horaires</legend>
        <AideAppel id="horaires">{QUESTION_HORAIRES}</AideAppel>
        {activite}
        <div className="flex flex-wrap gap-3 text-sm">
          {JOURS_SEMAINE.map((j, i) => (
            <label key={j} className="flex items-center gap-1.5 cursor-pointer">
              <input type="checkbox" data-testid={`gen-ci-jour-${i}`}
                     checked={Boolean((p.joursOuverts || [])[i])}
                     onChange={(e) => setChamp(`joursOuverts.${i}`, e.target.checked)} />
              {j}
            </label>
          ))}
        </div>
        <Retenu resolues={resolues} cle="jours_ouverts" champ="joursOuverts" repris={repris} />
        <div className="grid gap-3 sm:grid-cols-3">
          {TYPES_JOUR.map(({ cle, libelle }) => (
            <div className="grid gap-1.5" key={cle}>
              <Label>{libelle} — heures (début / fin)</Label>
              <div className="flex gap-2">
                <Input type="number" min="0" step="any" aria-label={`${libelle} début`}
                       data-testid={`gen-ci-plage-${cle}-debut`} placeholder="ex: 8"
                       value={p.plages?.[cle]?.debut ?? ''}
                       onChange={(e) => setChamp(`plages.${cle}.debut`, e.target.value)} />
                <Input type="number" min="0" step="any" aria-label={`${libelle} fin`}
                       data-testid={`gen-ci-plage-${cle}-fin`} placeholder="ex: 18"
                       value={p.plages?.[cle]?.fin ?? ''}
                       onChange={(e) => setChamp(`plages.${cle}.fin`, e.target.value)} />
              </div>
            </div>
          ))}
        </div>
        <Retenu resolues={resolues} cle="plages" champ="plages" repris={repris} />
        <div className="grid gap-2" data-testid="ci-fermetures">
          {fermetures.map((f, i) => (
            <div className="grid gap-2 sm:grid-cols-3" key={i}>
              <Input type="date" aria-label={`Fermeture ${i + 1} du`} value={f?.du ?? ''}
                     onChange={(e) => setChamp(`fermetures.${i}.du`, e.target.value)} />
              <Input type="date" aria-label={`Fermeture ${i + 1} au`} value={f?.au ?? ''}
                     onChange={(e) => setChamp(`fermetures.${i}.au`, e.target.value)} />
              <Input aria-label={`Fermeture ${i + 1} motif`} placeholder="Motif (congés, arrêt…)"
                     value={f?.motif ?? ''}
                     onChange={(e) => setChamp(`fermetures.${i}.motif`, e.target.value)} />
            </div>
          ))}
          <div>
            <Button type="button" variant="outline" size="sm"
                    onClick={() => setChamp('fermetures', [...fermetures, { du: '', au: '', motif: '' }])}>
              Ajouter une fermeture
            </Button>
          </div>
        </div>
      </fieldset>

      {/* ── 5. Surface disponible ── */}
      <fieldset className="grid gap-4 sm:grid-cols-3">
        <legend className="text-sm font-semibold">Surface disponible</legend>
        <div className="sm:col-span-3"><AideAppel id="surface">{QUESTION_SURFACE}</AideAppel></div>
        <div className="grid gap-1.5">
          <Label htmlFor="gen-ci-type-pose">Type de pose</Label>
          <select id="gen-ci-type-pose" className={SELECT} value={p.typePose || ''}
                  onChange={(e) => setChamp('typePose', e.target.value)}>
            <option value="">—</option>
            {TYPES_POSE.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
          <Retenu resolues={resolues} cle="type_pose" champ="typePose" repris={repris} />
        </div>
        <div className="grid gap-1.5">
          <Nombre id="gen-ci-surface" label="Surface utile (m²)" value={p.surfaceUtile}
                  onChange={(v) => setChamp('surfaceUtile', v)} />
          <Retenu resolues={resolues} cle="surface_utile_m2" champ="surfaceUtile" repris={repris} />
        </div>
        {/* CMP5 / R1 — une pente SAISIE l'emporte ; sinon le moteur dit la
            pose retenue (30° par défaut, rasante 10° pour loger la taille). */}
        <div className="grid gap-1.5">
          <Nombre id="gen-ci-pente" label="Inclinaison des panneaux (°)" value={p.penteDeg}
                  onChange={(v) => setChamp('penteDeg', v)} />
          <Retenu resolues={resolues} cle="pente_deg" champ="penteDeg" repris={repris} />
          {inclinaisonRetenue && (
            <p className="text-xs text-muted-foreground" data-testid="ci-inclinaison-retenue">
              Inclinaison retenue par le moteur : {formatNumber(inclinaisonRetenue.deg, { decimals: 0 })}°
              {inclinaisonRetenue.rasante ? ' (pose rasante)' : ''} — une pente saisie l&apos;emporte.
            </p>
          )}
          {tailleLimiteeToit && (
            <p className="text-xs text-warning" data-testid="ci-taille-toit">{tailleLimiteeToit}</p>
          )}
        </div>
      </fieldset>

      {/* ── Affiner (facultatif) : ce que l'analyste règle, replié ── */}
      <details className="rounded-lg border border-border p-3" data-testid="ci-affiner"
               open={affinerOuvert || undefined}>
        <summary className="cursor-pointer text-sm font-semibold">Affiner l&apos;étude (facultatif)</summary>
        <div className="mt-3 grid gap-4">
          {affiner}
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-1.5">
              <Label htmlFor="gen-ci-talon">Talon de consommation (kW)</Label>
              <Input id="gen-ci-talon" type="number" min="0" step="any"
                     disabled={Boolean(p.talonInconnu)} value={p.talonKw ?? ''}
                     onChange={(e) => setChamp('talonKw', e.target.value)} />
              <label className="flex items-center gap-2 text-xs cursor-pointer">
                <input type="checkbox" data-testid="gen-ci-talon-inconnu"
                       checked={Boolean(p.talonInconnu)}
                       onChange={(e) => setChamp('talonInconnu', e.target.checked)} />
                Je ne sais pas
              </label>
              <Retenu resolues={resolues} cle="talon" />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="gen-ci-couverture">Couverture</Label>
              <Input id="gen-ci-couverture" placeholder="ex: béton, bac acier…"
                     value={p.couverture ?? ''}
                     onChange={(e) => setChamp('couverture', e.target.value)} />
              <Retenu resolues={resolues} cle="couverture" />
            </div>
          </div>
          <fieldset className="grid gap-4 sm:grid-cols-3">
            <legend className="text-sm font-semibold">Raccordement</legend>
            <div className="grid gap-1.5">
              <Label htmlFor="gen-ci-tension">Tension</Label>
              <select id="gen-ci-tension" data-testid="gen-tension" className={SELECT}
                      value={p.tension || ''} onChange={(e) => setChamp('tension', e.target.value)}>
                <option value="">—</option>
                <option value="bt">Basse tension (BT)</option>
                <option value="mt">Moyenne tension (MT)</option>
                <option value="inconnue">Inconnue</option>
              </select>
              <Retenu resolues={resolues} cle="tension" champ="tension" repris={repris} />
            </div>
            <div className="grid gap-1.5">
              <Nombre id="gen-ci-puissance" label="Puissance souscrite (kVA)"
                      value={p.puissanceSouscrite}
                      onChange={(v) => setChamp('puissanceSouscrite', v)} />
              <Retenu resolues={resolues} cle="puissance_souscrite_kva" />
            </div>
            <div className="grid gap-1.5">
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" data-testid="gen-ci-revente" disabled={!estMt}
                       checked={estMt && Boolean(p.revente)}
                       onChange={(e) => setChamp('revente', e.target.checked)} />
                {estMt ? LIBELLE_REVENTE_MT : 'Revente du surplus'}
              </label>
              {!estMt && (
                <p className="text-xs text-muted-foreground" data-testid="ci-revente-bt">
                  {mentionReventeServeur || MENTION_REVENTE_BT}
                </p>
              )}
            </div>
          </fieldset>
        </div>
      </details>

      {/* Taille explicite : le seul réglage de taille (D-QJR5-13, souveraine). */}
      <div className="grid gap-1.5 sm:max-w-xs">
        <Nombre id="gen-ci-taille" label="Taille explicite (kWc)"
                value={p.tailleExplicite}
                onChange={(v) => setChamp('tailleExplicite', v)} />
        <p className="text-xs text-muted-foreground" data-testid="ci-taille-aide">
          vide = taille calculée par la règle de l'horizon marginal
        </p>
      </div>
    </div>
  )
}