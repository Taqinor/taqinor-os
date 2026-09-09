// QJ-ARBRE (fondateur 09/09/2026 — « un arbre à droite du Suivi commercial
// pour voir d'un coup d'œil ce qui s'est passé avec ce client ») — l'arbre
// d'historique EN UN COUP D'ŒIL de la fiche lead.
//
// Recherche préalable (demande fondateur « search well what people do ») — le
// standard du marché est convergent : Pipedrive (« Contacts timeline » : les
// événements passés en épingles chronologiques, lisibles d'un regard),
// HubSpot (timeline d'activité par fiche, entrées condensées + aperçus),
// Odoo (chatter groupé par jour), Attio/Close (rail vertical, icône par type
// d'événement, résultat en badge). Les traits communs retenus ICI :
//   1. rail vertical + UNE icône par type (appel / WhatsApp / e-mail / note /
//      devis / étape) — l'œil trie par forme avant de lire ;
//   2. groupement par jour (« Aujourd'hui » / « Hier » / date), du plus
//      récent au plus ancien — même calendrier que le chatter (dayLabel
//      IMPORTÉ de ChatterTimeline, jamais un second) ;
//   3. une seule ligne par événement, résultat (« Joint », « Refus »…) en
//      badge — le détail complet reste dans l'onglet Historique ;
//   4. les JALONS devis (envoyé / ouvert / signé / refusé) ressortent en
//      couleur : c'est ce que le commercial cherche en premier ;
//   5. le BRUIT est filtré : les logs automatiques de champ (kind
//      'modification') sont exclus SAUF le changement d'étape funnel — un
//      « glance view » qui liste 40 modifications de champs ne montre rien.
//
// Présentation PURE (même doctrine que ChatterTimeline) : aucune mutation,
// aucun appel réseau — les entrées viennent de la fiche déjà chargée
// (`historique` du shell LeadWorkspace, repli `chatter_recent` du GET lead,
// EXACTEMENT la précédence de TimelineTab — zéro requête ajoutée).
import {
  Phone, Mail, MessageCircle, StickyNote, Sparkles, TrendingUp,
  Send, Eye, CheckCircle2, XCircle, Activity as ActivityIcon,
} from 'lucide-react'
import { OUTCOME_LABELS, dayLabel } from '../../../../components/ChatterTimeline'

// Icône + libellé + accent par type d'événement. Les kinds sont CEUX du
// serveur (crm.LeadActivity.Kind + les jalons devis virtuels de l'endpoint
// /historique/, QX32) — jamais un vocabulaire inventé ici.
const KIND_RENDER = {
  appel: { Icon: Phone, label: 'Appel' },
  whatsapp: { Icon: MessageCircle, label: 'WhatsApp' },
  email: { Icon: Mail, label: 'E-mail' },
  note: { Icon: StickyNote, label: 'Note' },
  creation: { Icon: Sparkles, label: 'Création' },
  stage: { Icon: TrendingUp, label: 'Étape', accent: 'jalon' },
  devis_sent: { Icon: Send, label: 'Devis envoyé', accent: 'jalon' },
  devis_opened: { Icon: Eye, label: 'Devis ouvert', accent: 'jalon' },
  devis_signed: { Icon: CheckCircle2, label: 'Devis signé', accent: 'gagne' },
  devis_refused: { Icon: XCircle, label: 'Devis refusé', accent: 'perdu' },
  devis_engagement: { Icon: ActivityIcon, label: 'Lecture détaillée', accent: 'jalon' },
}

// Un événement mérite-t-il l'arbre ? Les logs automatiques de champ sont du
// bruit — SAUF l'étape funnel (le seul champ qui raconte le parcours).
// eslint-disable-next-line react-refresh/only-export-components -- logique pure co-localisée (testable)
export function entreeArbre(a) {
  if (!a || !a.kind) return null
  if (a.kind === 'modification') {
    if (a.field !== 'stage') return null
    return {
      ...KIND_RENDER.stage,
      texte: `${a.old_value || '—'} → ${a.new_value || '—'}`,
    }
  }
  const rendu = KIND_RENDER[a.kind]
  if (!rendu) return null
  const badge = OUTCOME_LABELS[a.outcome] || null
  return { ...rendu, badge, texte: a.body || '' }
}

const heureCourte = (iso) => {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
}

export default function ArbreHistorique({ historique, chatterRecent }) {
  // Même précédence que TimelineTab (LW30/LW41) : `historique` (rafraîchi par
  // le shell) dès qu'il existe, sinon `chatter_recent` embarqué au GET lead.
  const source = (historique?.length ? historique : chatterRecent) ?? []
  const lignes = []
  for (const a of source) {
    const rendu = entreeArbre(a)
    if (rendu) lignes.push({ a, rendu })
  }
  // L'endpoint renvoie déjà du plus récent au plus ancien ; on re-trie par
  // sécurité (le repli chatter_recent doit suivre le même ordre).
  lignes.sort((x, y) => new Date(y.a.created_at) - new Date(x.a.created_at))

  // Groupes par jour, dans l'ordre déjà trié (même mécanique que le chatter).
  const groupes = []
  let courant = null
  for (const l of lignes) {
    const label = dayLabel(l.a.created_at)
    if (!courant || courant.label !== label) {
      courant = { label, items: [] }
      groupes.push(courant)
    }
    courant.items.push(l)
  }

  return (
    <div className="lw-arbre" data-testid="arbre-historique">
      <div className="lw-arbre-head">
        <span className="lw-arbre-titre">Historique en un coup d'œil</span>
        {lignes.length > 0 && (
          <span className="lw-arbre-compte">{lignes.length}</span>
        )}
      </div>
      {lignes.length === 0 ? (
        <p className="gen-hint">Aucun échange enregistré pour l'instant.</p>
      ) : (
        <div className="lw-arbre-defile">
          {groupes.map((g) => (
            <div key={g.label} className="lw-arbre-jour">
              <div className="lw-arbre-jour-label">{g.label}</div>
              <ul className="lw-arbre-liste">
                {g.items.map(({ a, rendu }) => {
                  const { Icon } = rendu
                  return (
                    <li
                      key={a.id ?? `${a.kind}-${a.created_at}`}
                      className={`lw-arbre-ligne${rendu.accent ? ` is-${rendu.accent}` : ''}`}
                      // Le détail complet (auteur inclus) au survol — la ligne
                      // reste une seule ligne, l'onglet Historique garde tout.
                      title={[rendu.label, a.body, a.user_nom ? `par ${a.user_nom}` : '']
                        .filter(Boolean).join(' — ')}
                    >
                      <span className="lw-arbre-puce" aria-hidden="true">
                        <Icon size={12} />
                      </span>
                      <span className="lw-arbre-texte">
                        <strong>{rendu.label}</strong>
                        {rendu.badge && (
                          <span className="lw-arbre-badge">{rendu.badge}</span>
                        )}
                        {rendu.texte && <span className="lw-arbre-corps"> {rendu.texte}</span>}
                      </span>
                      <span className="lw-arbre-heure">{heureCourte(a.created_at)}</span>
                    </li>
                  )
                })}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
