import { Button } from '../../../ui'
import { formatDate, formatMAD } from '../../../lib/format'
import { STAGE_LABELS } from '../../crm/stages'
import BoutonTelechargerDevis from './BoutonTelechargerDevis'
import { useOuvrirEcran, usePreparerTouche } from './useCarte'

/* COP-F3 — la file, le matin, la recherche, la fiche. Les boutons appellent
   Django DIRECTEMENT (zéro appel au modèle) : « Préparer » ajoute la carte de la
   touche à la conversation, « Ouvrir la fiche » suit le routeur. Une touche à
   la fois : aucun « tout envoyer ». Les libellés d'étape viennent de la
   constante d'étapes du front (miroir de STAGES.py), jamais d'une liste en dur. */

const etapeLibelle = (cle) => STAGE_LABELS[cle] ?? cle ?? ''
const dateCourte = (iso) => (iso ? formatDate(iso) : '')

function OuvrirFiche({ leadId }) {
  const navigate = useOuvrirEcran()
  if (!leadId) return null
  return (
    <Button variant="outline" size="sm" className="min-h-10" onClick={() => navigate(`/crm/leads/${leadId}`)}>
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
    <li className="rounded-md border border-border bg-background/60 p-2">
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

function BlocVisites({ bloc }) {
  if (!bloc?.total) return null
  return (
    <p className="mt-3 text-sm">
      Visites : <span className="font-medium">{bloc.total}</span>
      {bloc.en_retard ? ` (dont ${bloc.en_retard} en retard)` : ''}
    </p>
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
