import { useEffect, useState } from 'react'
import { MessageCircle, TriangleAlert } from 'lucide-react'
import { Button, buttonVariants } from '../../../ui'
import { cn } from '../../../lib/cn'
import crmApi from '../../../api/crmApi'
import { formatDate } from '../../../lib/format'
import { lienWhatsAppSur, AGE_MAX_CARTE_MS } from './cartes'
import BoutonTelechargerDevis from './BoutonTelechargerDevis'
import { useOuvrirEcran, usePatchCarte } from './useCarte'

/* COP-F4 — cartes WhatsApp et documents. L'assistant n'ENVOIE rien : il prépare,
   la commerciale appuie (D-WHATSAPP, wa.me). Un lien WhatsApp n'est ouvert que
   s'il commence par https://wa.me/ ou https://api.whatsapp.com/. */

const LANGUES_RTL = ['darija', 'ar']

function LienWhatsApp({ url, libelle }) {
  const sur = lienWhatsAppSur(url)
  if (!sur) {
    return <p className="text-sm text-destructive">Aucun numéro exploitable : WhatsApp ne peut pas être ouvert.</p>
  }
  return (
    <a
      href={sur} target="_blank" rel="noopener noreferrer"
      className={cn(buttonVariants({ size: 'sm' }), 'min-h-11')}
    >
      <MessageCircle className="size-4" aria-hidden="true" />
      {libelle}
    </a>
  )
}

function Texte({ texte, langue }) {
  const rtl = LANGUES_RTL.includes(langue)
  return (
    <div
      data-testid="wa-texte"
      className={`whitespace-pre-wrap break-words rounded-lg border border-border bg-muted/40 p-2.5 text-sm${rtl ? ' text-right' : ''}`}
      dir={rtl ? 'rtl' : 'auto'}
    >
      {texte}
    </div>
  )
}

// `wa_message` : texte prêt (le VALIDÉ du suivi) + lien wa.me. Sans texte, la
// conversation s'ouvre nue (la commerciale écrit elle-même).
export function CarteWaMessage({ carte }) {
  const d = carte.donnees
  const url = d.wa_url ?? d.lien_wa_me
  return (
    <div>
      {d.texte
        ? <Texte texte={d.texte} langue={d.langue_servie} />
        : <p className="text-sm text-muted-foreground">Aucun texte validé pour cet objectif : la conversation s’ouvre sans texte.</p>}
      <div className="mt-2.5">
        <LienWhatsApp url={url} libelle={d.texte ? 'Ouvrir WhatsApp' : 'Ouvrir la conversation'} />
      </div>
    </div>
  )
}

function detailErreur(err, repli) {
  const detail = err?.response?.data?.detail
  return typeof detail === 'string' && detail ? detail : repli
}

const entierPositif = (v) => (Number.isInteger(v) && v > 0 ? v : null)

// Corps de l'aperçu ET du commit : les devis de la carte, et la langue SERVIE
// quand le serveur la donne. Sans elle, aucune langue n'est imposée : le serveur
// reprend celle du lead, comme pour l'aperçu (jamais un `fr` qui écraserait un
// aperçu en darija). `null` quand la carte ne permet pas d'enregistrer l'envoi.
function corpsEnvoi(d) {
  const ids = Array.isArray(d.devis_ids) ? d.devis_ids : []
  if (!entierPositif(d.lead_id) || ids.length === 0 || !ids.every(entierPositif)) return null
  const langue = typeof d.langue === 'string' && d.langue ? d.langue : null
  return langue ? { devis_ids: ids, langue } : { devis_ids: ids }
}

// `wa_devis` : ouvrir PUIS valider (commit) l'envoi — sans le commit le devis
// reste brouillon et le suivi ne démarre pas. Aperçu revalidé s'il est ancien.
// Sans lead ni devis identifiés, AUCUNE ouverture : une conversation ouverte sans
// envoi enregistré ne doit jamais avoir lieu.
export function CarteWaDevis({ carte, index, carteIdx }) {
  const patch = usePatchCarte(index, carteIdx)
  const d = carte.donnees
  const [erreur, setErreur] = useState('')
  const [occupe, setOccupe] = useState(false)
  const corps = corpsEnvoi(d)
  const age = () => Date.now() - (carte.verifie_le ?? carte.recu_le ?? 0)
  const commitPossible = corps != null

  const revalider = async () => {
    setOccupe(true)
    try {
      const res = await crmApi.whatsappDevisApercu(d.lead_id, corps)
      patch({ donneesPatch: res.data, verifie_le: Date.now() })
      setErreur('')
      return true
    } catch (err) {
      setErreur(detailErreur(err, 'Aperçu indisponible pour le moment.'))
      return false
    } finally {
      setOccupe(false)
    }
  }

  useEffect(() => {
    if (!carte.envoye && commitPossible && age() > AGE_MAX_CARTE_MS) queueMicrotask(revalider)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- revalidation au montage seulement
  }, [])

  const enregistrerEnvoi = async () => {
    setOccupe(true)
    try {
      await crmApi.whatsappDevis(d.lead_id, corps)
      patch({ envoye: true })
      setErreur('')
    } catch (err) {
      setErreur(detailErreur(err, 'Envoi non enregistré : le devis reste en brouillon.'))
    } finally {
      setOccupe(false)
    }
  }

  const ouvrir = async () => {
    if (!commitPossible) return
    if (age() > AGE_MAX_CARTE_MS) {
      if (await revalider()) setErreur('Aperçu mis à jour — appuyez de nouveau sur WhatsApp.')
      return
    }
    // Ouverture dans le geste, puis le commit (`whatsapp-devis`).
    window.open(lienWhatsAppSur(d.wa_url), '_blank', 'noopener')
    enregistrerEnvoi()
  }

  return (
    <div>
      <Texte texte={d.message || ''} langue={d.langue} />
      {d.links?.length > 0 && (
        <ul className="mt-1.5 text-xs text-muted-foreground">
          {d.links.map((l) => <li key={l.devis_id}>{l.reference}</li>)}
        </ul>
      )}
      <div className="mt-2.5 flex flex-wrap items-center gap-2">
        {carte.envoye
          ? <p className="text-sm font-medium" data-testid="wa-devis-envoye">Envoi enregistré : devis marqué envoyé.</p>
          : (
            <Button
              className="min-h-11" disabled={occupe || !commitPossible || !lienWhatsAppSur(d.wa_url)}
              loading={occupe} onClick={ouvrir}
            >
              <MessageCircle className="size-4" aria-hidden="true" />
              Ouvrir WhatsApp
            </Button>
          )}
        {!carte.envoye && !commitPossible && (
          <p className="text-xs text-muted-foreground" data-testid="wa-devis-sans-commit">
            Envoi à faire depuis la fiche du lead.
          </p>
        )}
      </div>
      {erreur && (
        <p className="mt-2 flex items-start gap-1.5 text-xs text-destructive" role="alert">
          <TriangleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          {erreur}
        </p>
      )}
    </div>
  )
}

// `document` : « Télécharger le devis » (jamais un lien construit hors /proposal).
export function CarteDocument({ carte }) {
  const d = carte.donnees
  return (
    <div>
      <p className="mb-2 text-sm">Devis prêt à télécharger.</p>
      <BoutonTelechargerDevis devisId={d.devis_id} options={d.options} label="Télécharger le devis" />
    </div>
  )
}

// `visite` : visite planifiée (+ la prochaine touche du lead).
export function CarteVisite({ carte }) {
  const navigate = useOuvrirEcran()
  const d = carte.donnees
  const v = d.visite ?? {}
  const p = d.prochaine_touche
  return (
    <div>
      <p className="text-sm font-semibold">
        Visite {v.statut_libelle ? `(${v.statut_libelle.toLowerCase()})` : 'planifiée'}
        {v.date_prevue ? ` le ${formatDate(v.date_prevue)}` : ''}
      </p>
      {v.commercial_nom && <p className="text-xs text-muted-foreground">Avec {v.commercial_nom}</p>}
      {v.notes && <p className="mt-1 text-xs">{v.notes}</p>}
      {p && <p className="mt-1.5 text-xs text-muted-foreground">Prochaine touche : {p.libelle}</p>}
      {v.id && (
        <Button variant="outline" size="sm" className="mt-2 min-h-10" onClick={() => navigate(`/visites/${v.id}`)}>
          Ouvrir la visite
        </Button>
      )}
    </div>
  )
}
