import { Button } from '../../../ui'
import { formatDate, formatMAD } from '../../../lib/format'
import { STAGE_LABELS } from '../../crm/stages'
import BoutonTelechargerDevis from './BoutonTelechargerDevis'
import { cheminAutorise } from './ecrans'
import { useOuvrirEcran, usePreparerTouche } from './useCarte'

/* COP-F3 — la file, le matin, la recherche, la fiche. Les boutons appellent
   Django DIRECTEMENT (zéro appel au modèle) : « Préparer » ajoute la carte de la
   touche à la conversation, « Ouvrir la fiche » suit le routeur. Une touche à
   la fois : aucun « tout envoyer ». Les libellés d'étape viennent de la
   constante d'étapes du front (miroir de STAGES.py), jamais d'une liste en dur. */

const etapeLibelle = (cle) => STAGE_LABELS[cle] ?? cle ?? ''
const dateCourte = (iso) => (iso ? formatDate(iso) : '')

// `chemin` (AIC94) : une autre fiche que celle du lead (la visite du matin).
function OuvrirFiche({ leadId, chemin }) {
  const navigate = useOuvrirEcran()
  const cible = chemin || (leadId ? `/crm/leads/${leadId}` : null)
  if (!cible) return null
  return (
    <Button variant="outline" size="sm" className="min-h-10" onClick={() => navigate(cible)}>
      Ouvrir la fiche
    </Button>
  )
}

function BoutonPreparer({ toucheId, preparer, occupe }) {
  if (!toucheId) return null
  return (
    <Button size="sm" className="min-h-10" disabled={occupe != null} loading={occupe === toucheId}
      onClick={() => preparer(toucheId)}>
      Préparer
    </Button>
  )
}

function Rangee({ titre, detail, children }) {
  return (
    <li className="min-w-0 break-words rounded-md border border-border bg-background/60 p-2">
      <p className="text-sm font-medium">{titre}</p>
      {detail && <p className="text-xs text-muted-foreground">{detail}</p>}
      <div className="mt-1.5 flex flex-wrap gap-2">{children}</div>
    </li>
  )
}

function Vide({ texte }) {
  return <p className="text-sm text-muted-foreground">{texte}</p>
}

function Erreur({ texte }) {
  return texte ? <p className="mt-2 text-xs text-destructive" role="alert">{texte}</p> : null
}

// Rangée d'une touche (file de suivi ET bloc « relances » du matin : même forme).
function RangeeTouche({ ligne, preparer, occupe }) {
  const retard = ligne.retard_jours_ouvres > 0 ? ` · ${ligne.retard_jours_ouvres} j ouvré(s) de retard` : ''
  return (
    <Rangee
      titre={`${ligne.nom} — ${ligne.touche}`}
      detail={`${etapeLibelle(ligne.etape)} · prévue le ${dateCourte(ligne.touche_prevue)} · ${ligne.canal}${retard}`}
    >
      <BoutonPreparer toucheId={ligne.touche_id} preparer={preparer} occupe={occupe} />
      <OuvrirFiche leadId={ligne.lead_id} />
    </Rangee>
  )
}

function ListeTouches({ lignes }) {
  const { preparer, occupe, erreur } = usePreparerTouche()
  if (!lignes?.length) return <Vide texte="Rien à relancer pour le moment." />
  return (
    <>
      <ul className="space-y-2">
        {lignes.map((l) => (
          <RangeeTouche key={`${l.lead_id}-${l.touche_id ?? l.touche}`} ligne={l} preparer={preparer} occupe={occupe} />
        ))}
      </ul>
      <Erreur texte={erreur} />
    </>
  )
}

export function CarteFileTouches({ carte }) {
  const d = carte.donnees
  return (
    <div>
      <p className="mb-2 text-sm font-semibold">Touches à faire ({d.total ?? d.lignes?.length ?? 0})</p>
      <ListeTouches lignes={d.lignes} />
    </div>
  )
}

function BlocDevisSansReponse({ bloc }) {
  if (!bloc?.lignes?.length) return null
  return (
    <div className="mt-3">
      <p className="mb-1.5 text-sm font-semibold">Devis sans réponse ({bloc.total ?? bloc.lignes.length})</p>
      <ul className="space-y-2">
        {bloc.lignes.map((l) => (
          <Rangee key={l.devis_id} titre={`${l.reference} — ${l.nom}`}
            detail={`envoyé le ${dateCourte(l.envoye_le)} · ${l.jours_sans_reponse} jours sans réponse`}>
            <BoutonTelechargerDevis devisId={l.devis_id} reference={l.reference} />
            <OuvrirFiche leadId={l.lead_id} />
          </Rangee>
        ))}
      </ul>
    </div>
  )
}

// AIC95/AIC94 — une rangée par visite (ligne `visites.selectors.ligne_ma_journee`,
// figée au contrat) : le lead, la date prévue, « Ouvrir la fiche » de la visite.
// `date_prevue` est un JOUR (aucune heure n'existe côté serveur : rien d'inventé).
function BlocVisites({ bloc }) {
  if (!bloc?.total) return null
  return (
    <div className="mt-3">
      <p className="mb-1.5 text-sm font-semibold">
        Visites ({bloc.total}){bloc.en_retard ? ` — dont ${bloc.en_retard} en retard` : ''}
      </p>
      <ul className="space-y-2">
        {(bloc.lignes ?? []).map((v) => (
          <Rangee key={v.id} titre={v.lead_nom || 'Visite'}
            detail={[`prévue le ${dateCourte(v.date_prevue)}`, v.ville].filter(Boolean).join(' · ')}>
            <OuvrirFiche chemin={`/visites/${v.id}`} />
          </Rangee>
        ))}
      </ul>
    </div>
  )
}

// Copilote vague 2 (BRF8) — les blocs du point du matin servis seulement quand le
// copilote est allumé ET que le compte lit le module (sinon la clé est absente :
// rien ne s'affiche). Les liens viennent du serveur et ne sont suivis que s'ils sont
// un écran de la table `ecrans.js` ; les « à faire » sont des ensembles fermés du
// serveur, jamais du texte de modèle ; les noms de clients sont rendus en texte brut.
const GESTES = {
  assigner: 'à assigner', completer: 'à compléter', valider: 'à valider', refaire: 'à refaire',
  creer: 'à créer', reprendre_visite: 'reprendre la visite', dessiner: 'à dessiner', simuler: 'à simuler',
  corriger_electrique: 'corriger l’électrique', retenir: 'retenir une variante',
  faire_approuver: 'à faire approuver', publier: 'à publier', preparer_calepinage: 'calepinage à préparer',
  commander_materiel: 'commander le matériel', encaisser_acompte: 'encaisser l’acompte',
  planifier_pose: 'planifier la pose', assigner_technicien: 'assigner un technicien', poser: 'à poser',
  relancer: 'à relancer', encaisser: 'à encaisser', emettre: 'à émettre', facturer: 'à facturer',
  emettre_brouillon: 'brouillon à émettre', reviser: 'à réviser',
  planifier: 'à planifier', demarrer: 'à démarrer', resoudre: 'à résoudre', cloturer: 'à clôturer',
}
const BLOCAGES = {
  sans_date: 'sans date', sans_technicien: 'sans technicien', pose_sans_intervention: 'pose sans intervention',
  pose_depassee: 'pose dépassée', acompte_non_encaisse: 'acompte non encaissé',
}
const STATUTS = {
  brouillon: 'brouillon', en_cours: 'en cours', terminee: 'terminée', validee: 'validée', a_refaire: 'à refaire',
  annulee: 'annulée', envoye: 'envoyé', accepte: 'accepté', refuse: 'refusé', expire: 'expiré',
}
const mot = (table, cle) => table[cle] ?? String(cle ?? '').replace(/_/g, ' ')
const suite = (cle) => (cle && cle !== 'rien' ? mot(GESTES, cle) : null)
const joindre = (...morceaux) => morceaux.filter(Boolean).join(' · ')
const montant = (texte) => (texte == null || texte === '' ? null : formatMAD(Number(texte)))

function OuvrirLien({ lien, label = 'Ouvrir' }) {
  const ouvrir = useOuvrirEcran()
  if (!cheminAutorise(lien)) return null
  return (
    <Button variant="outline" size="sm" className="min-h-10" onClick={() => ouvrir(lien)}>
      {label}
    </Button>
  )
}

// Un bloc du matin : titre + compte, quelques rangées (celles du serveur, jamais
// retriées ni refiltrées), puis « Tout voir » vers l'écran quand le serveur en donne un.
function BlocMatin({ titre, nombre, resume, lignes, lien, decrire }) {
  if (!nombre && !lignes?.length) return null
  return (
    <div className="mt-3 min-w-0">
      <p className="mb-1.5 text-sm font-semibold">{titre} ({nombre ?? lignes.length})</p>
      {resume && <p className="mb-1.5 text-xs text-muted-foreground">{resume}</p>}
      {lignes?.length > 0 && (
        <ul className="space-y-2">
          {lignes.map((l, i) => {
            const r = decrire(l)
            return (
              <Rangee key={r.cle ?? i} titre={r.titre} detail={r.detail}>
                <OuvrirLien lien={r.lien} />
              </Rangee>
            )
          })}
        </ul>
      )}
      {lien && <div className="mt-1.5"><OuvrirLien lien={lien} label="Tout voir" /></div>}
    </div>
  )
}

function BlocVisitesEquipe({ bloc }) {
  if (!bloc) return null
  const nombre = (bloc.sans_technicien ?? 0) + (bloc.a_valider ?? 0) + (bloc.en_retard ?? 0)
  return (
    <BlocMatin titre="Visites de l’équipe" nombre={nombre} lignes={bloc.lignes} lien={bloc.lien}
      resume={`${bloc.sans_technicien ?? 0} sans technicien · ${bloc.a_valider ?? 0} à valider · ${bloc.en_retard ?? 0} en retard`}
      decrire={(l) => ({
        cle: l.id,
        titre: l.lead_nom || 'Visite',
        detail: joindre(l.ville, l.date_prevue && `prévue le ${dateCourte(l.date_prevue)}`, l.en_retard && 'en retard', suite(l.a_faire)),
        lien: l.lien,
      })} />
  )
}

function BlocCalepinages({ bloc }) {
  if (!bloc) return null
  const sans = bloc.sans_calepinage
  return (
    <>
      <BlocMatin titre="Calepinages à traiter" nombre={bloc.total} lignes={bloc.lignes}
        decrire={(l) => ({
          cle: l.calepinage,
          titre: l.reference,
          detail: joindre(l.modifie_le && `modifié le ${dateCourte(l.modifie_le)}`, suite(l.a_faire)),
          lien: l.lien,
        })} />
      {sans && (
        <BlocMatin titre="Visites validées sans calepinage" nombre={sans.total} lignes={sans.lignes}
          decrire={(l) => ({
            cle: l.visite_id,
            titre: l.lead_nom || 'Visite',
            detail: joindre(l.validee_le && `validée le ${dateCourte(l.validee_le)}`, suite(l.a_faire)),
            lien: l.lien,
          })} />
      )}
    </>
  )
}

function BlocChantiers({ bloc }) {
  if (!bloc) return null
  const rangee = (l) => ({
    cle: l.id,
    titre: `${l.reference} — ${l.client_nom}`,
    detail: joindre(
      (l.blocages ?? []).map((b) => mot(BLOCAGES, b)).join(', '),
      l.date_pose_prevue && `pose le ${dateCourte(l.date_pose_prevue)}`,
      l.technicien_nom, suite(l.a_faire),
    ),
    lien: l.lien,
  })
  return (
    <>
      <BlocMatin titre="Chantiers bloqués" nombre={bloc.bloques?.total} lignes={bloc.bloques?.lignes} decrire={rangee} />
      <BlocMatin titre="Poses de la semaine" nombre={bloc.poses_semaine?.total} lignes={bloc.poses_semaine?.lignes}
        lien={bloc.lien} decrire={rangee} />
    </>
  )
}

function BlocImpayes({ bloc }) {
  if (!bloc) return null
  return (
    <BlocMatin titre="Factures impayées" nombre={bloc.nb_factures} lignes={bloc.lignes} lien={bloc.lien}
      resume={montant(bloc.total_du) && `Total dû : ${montant(bloc.total_du)}`}
      decrire={(l) => ({
        cle: l.facture_id,
        titre: `${l.reference} — ${l.client_nom}`,
        detail: joindre(montant(l.montant_du), l.jours_retard > 0 && `${l.jours_retard} j de retard`, l.niveau,
          l.contestee && 'contestée', suite(l.a_faire)),
        lien: l.lien,
      })} />
  )
}

function BlocTickets({ bloc }) {
  if (!bloc) return null
  return (
    <BlocMatin titre="Tickets ouverts" nombre={bloc.ouverts} lignes={bloc.lignes} lien={bloc.lien}
      resume={bloc.en_retard_sla ? `${bloc.en_retard_sla} en retard de délai de service` : null}
      decrire={(l) => ({
        cle: l.ticket_id,
        titre: `${l.reference} — ${l.client_nom}`,
        detail: joindre(l.equipement, l.priorite, l.en_retard_sla && 'en retard', l.sous_garantie && 'sous garantie', suite(l.a_faire)),
        lien: l.lien,
      })} />
  )
}

export function CarteMatin({ carte }) {
  const d = carte.donnees
  return (
    <div>
      <p className="mb-2 text-sm font-semibold">Votre matin</p>
      {d.relances && (
        <>
          <p className="mb-1.5 text-xs text-muted-foreground">Relances du jour : {d.relances.total ?? 0}</p>
          <ListeTouches lignes={d.relances.lignes} />
        </>
      )}
      <BlocVisites bloc={d.visites} />
      <BlocDevisSansReponse bloc={d.devis_sans_reponse} />
      <BlocVisitesEquipe bloc={d.visites_equipe} />
      <BlocCalepinages bloc={d.calepinages} />
      <BlocChantiers bloc={d.chantiers} />
      <BlocImpayes bloc={d.impayes} />
      <BlocTickets bloc={d.tickets} />
    </div>
  )
}

export function CarteListeLeads({ carte }) {
  const { preparer, occupe, erreur } = usePreparerTouche()
  const d = carte.donnees
  if (!d.lignes?.length) return <Vide texte="Aucun lead trouvé." />
  return (
    <div>
      <p className="mb-2 text-sm font-semibold">Leads trouvés ({d.total ?? d.lignes.length})</p>
      <ul className="space-y-2">
        {d.lignes.map((l) => (
          <Rangee key={l.lead_id} titre={l.nom}
            detail={[l.ville, l.etape_libelle || etapeLibelle(l.etape), l.telephone].filter(Boolean).join(' · ')}>
            <BoutonPreparer toucheId={l.prochaine_touche?.touche_id} preparer={preparer} occupe={occupe} />
            <OuvrirFiche leadId={l.lead_id} />
          </Rangee>
        ))}
      </ul>
      <Erreur texte={erreur} />
    </div>
  )
}

function DevisDeLaFiche({ devis }) {
  if (!devis?.length) return null
  return (
    <ul className="mt-2 space-y-1.5">
      {devis.map((dv) => (
        <li key={dv.id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
          <span>
            {dv.reference} · {dv.statut}
            {dv.total_ttc ? ` · ${formatMAD(Number(dv.total_ttc))}` : ''}
          </span>
          <BoutonTelechargerDevis devisId={dv.id} reference={dv.reference} label="Télécharger" />
        </li>
      ))}
    </ul>
  )
}

// Copilote vague 2 (BRF8) — où en est le lead dans chaque module (`dossier`, servi
// seulement copilote allumé) : une ligne par module que le compte lit, ids et états.
// Une clé absente = module non lisible (rien affiché) ; `null` = rien pour ce lead.
function lignesDossier(dossier) {
  const { visite, calepinage, devis, chantier, factures, tickets } = dossier
  const lignes = []
  if ('visite' in dossier) {
    lignes.push({ cle: 'visite', lien: visite?.lien, texte: visite
      ? joindre('Visite', mot(STATUTS, visite.statut), visite.date && dateCourte(visite.date)) : 'Visite : aucune' })
  }
  if ('calepinage' in dossier) {
    lignes.push({ cle: 'calepinage', lien: calepinage?.lien, texte: calepinage
      ? joindre(`Calepinage ${calepinage.reference}`, suite(calepinage.a_faire)) : 'Calepinage : aucun' })
  }
  if ('devis' in dossier) {
    lignes.push({ cle: 'devis', lien: devis?.lien, texte: devis
      ? joindre(`Devis ${devis.reference}`, mot(STATUTS, devis.statut)) : 'Devis : aucun' })
  }
  if ('chantier' in dossier) {
    lignes.push({ cle: 'chantier', lien: chantier?.lien, texte: chantier
      ? joindre(`Chantier ${chantier.reference}`, mot(STATUTS, chantier.statut)) : 'Chantier : aucun' })
  }
  if (factures) {
    lignes.push({ cle: 'factures', lien: factures.lien, texte: joindre(
      montant(factures.reste_a_facturer_ttc) && `Reste à facturer ${montant(factures.reste_a_facturer_ttc)}`,
      montant(factures.reste_a_payer_ttc) && `reste à payer ${montant(factures.reste_a_payer_ttc)}`,
      suite(factures.a_faire)) })
  }
  if (tickets) {
    lignes.push({ cle: 'tickets', lien: tickets.lien, texte: `Tickets ouverts : ${tickets.ouverts ?? 0}` })
  }
  return lignes
}

function DossierDuLead({ dossier }) {
  if (!dossier) return null
  const lignes = lignesDossier(dossier)
  if (!lignes.length) return null
  return (
    <div className="mt-2 min-w-0">
      <p className="text-xs font-semibold">Dossier</p>
      <ul className="mt-1 space-y-1.5">
        {lignes.map((l) => (
          <li key={l.cle} className="flex flex-wrap items-center justify-between gap-2 break-words text-xs">
            <span className="min-w-0">{l.texte}</span>
            <OuvrirLien lien={l.lien} />
          </li>
        ))}
      </ul>
    </div>
  )
}

export function CarteFicheLead({ carte }) {
  const { preparer, occupe, erreur } = usePreparerTouche()
  const d = carte.donnees
  const id = d.identite ?? {}
  const prochaine = d.prochaine_touche
  const dernieres = (d.chatter ?? []).slice(0, 3)
  return (
    <div>
      <p className="text-sm font-semibold">
        {[id.prenom, id.nom].filter(Boolean).join(' ')}{id.societe ? ` — ${id.societe}` : ''}
      </p>
      <p className="text-xs text-muted-foreground">
        {[id.ville, etapeLibelle(d.etape), id.telephone].filter(Boolean).join(' · ')}
      </p>
      {d.alertes?.length > 0 && <p className="mt-1 text-xs text-warning">{d.alertes.join(' · ')}</p>}
      {dernieres.length > 0 && (
        <ul className="mt-2 list-disc pl-5 text-xs text-muted-foreground">
          {dernieres.map((c, i) => <li key={i}>{c.texte || c.champ}</li>)}
        </ul>
      )}
      <DevisDeLaFiche devis={d.devis} />
      <DossierDuLead dossier={d.dossier} />
      {prochaine && (
        <p className="mt-2 text-xs">
          Prochaine touche : {prochaine.libelle} — {dateCourte(prochaine.due_date)}
        </p>
      )}
      <div className="mt-2 flex flex-wrap gap-2">
        <BoutonPreparer toucheId={prochaine?.touche_id} preparer={preparer} occupe={occupe} />
        <OuvrirFiche leadId={id.id} />
      </div>
      <Erreur texte={erreur} />
    </div>
  )
}

// `suite_touche` : une touche traitée + la prochaine du lead.
export function CarteSuiteTouche({ carte }) {
  const d = carte.donnees
  const p = d.prochaine_touche
  return (
    <div>
      <p className="text-sm font-semibold">Touche traitée — {d.libelle || d.lead_nom}</p>
      <p className="text-xs text-muted-foreground">
        {p ? `Prochaine touche : ${p.libelle} — ${dateCourte(p.due_date)}` : 'Plus aucune touche ouverte pour ce lead.'}
      </p>
    </div>
  )
}
