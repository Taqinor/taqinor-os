// MRY14/MRY13 — Aperçu du message d'une touche de relance AVANT ouverture de
// WhatsApp (décision D5 : aucun envoi automatique, le clic humain reste seul
// maître). Patron `DevisList.jsx openWhatsApp` (:2049) : `window.open(wa_url)`
// PUIS l'appel serveur qui marque la touche faite — jamais l'inverse (le clic
// humain a déjà eu lieu quoi qu'il arrive côté serveur).
//
// MRY32 — DÉPLACÉ de `pages/crm/ToucheMessageDialog.jsx` vers ici : la frise
// de la fiche lead (`features/crm/workspace/sections/CadenceFrise.jsx`) doit
// pouvoir l'ouvrir pour ses propres lignes actionnables (touche à faire/en
// retard), et `features/` n'importe jamais depuis `pages/` (sens d'import
// inverse). L'ancien chemin (`pages/crm/ToucheMessageDialog.jsx`) devient un
// simple ré-export pour ne rien casser des appelants existants (le widget
// Cockpit, l'écran de suivi, et leur test `ToucheMessageDialog.mry14.test.jsx`
// qui importe encore `./ToucheMessageDialog`).
import { useEffect, useState } from 'react'
import { Copy, Mic, Send, TriangleAlert } from 'lucide-react'
import crmApi from '../../../api/crmApi'
import { toast } from '../../../ui/confirm'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
  Button, Spinner,
} from '../../../ui'

// CAD63 — les deux langues qu'on peut CHOISIR au moment utile : celles du
// champ `Lead.langue_preferee` (même paire que `DevisTab.jsx`). Jamais
// l'anglais ni l'arabe classique : aucun texte de relance validé (CAD64).
const LANGUES_MESSAGE = [['fr', 'FR'], ['darija', 'Darija']]
const LIBELLE_LANGUE = { fr: 'le français', darija: 'la darija' }
// CAD64 — le nom de la langue DEMANDÉE dans l'avertissement de repli
// (« ce texte n'existe pas encore en darija »). `en`/`ar` viennent du
// résolveur commun des documents client (langue documentaire du client).
const NOM_LANGUE = { darija: 'darija', en: 'anglais', ar: 'arabe' }
// Écritures de droite à gauche — seulement quand le texte EST dans cette
// langue (jamais pour une version française partie en repli).
const LANGUES_RTL = ['darija', 'ar']
// CAD70 — le catalogue des réalisations vit dans Paramètres (onglet
// « Réalisations », `RealisationsSection.jsx`).
const LIEN_CATALOGUE_REALISATIONS = '/parametres'

export default function ToucheMessageDialog({
  etape, open, onOpenChange, onSent,
  // CAD63 — appelé après l'enregistrement de la langue du client (le parent
  // relit sa file : `lead_langue` a changé).
  onLangueEnregistree,
}) {
  const [loading, setLoading] = useState(false)
  const [erreur, setErreur] = useState(false)
  const [rendu, setRendu] = useState(null)
  const [sending, setSending] = useState(false)
  // CAD63 — la langue BASCULÉE à l'aperçu (null = celle de la fiche) : le
  // texte est rechargé dans cette langue, la fiche ne change que sur la
  // confirmation explicite « c'est sa langue ».
  const [langueChoisie, setLangueChoisie] = useState(null)
  const [enregistrementLangue, setEnregistrementLangue] = useState(false)
  const [langueEnregistree, setLangueEnregistree] = useState(null)

  useEffect(() => {
    let active = true
    if (!open || !etape) {
      queueMicrotask(() => {
        if (!active) return
        setRendu(null); setLangueChoisie(null); setLangueEnregistree(null)
      })
      return () => { active = false }
    }
    queueMicrotask(() => { if (active) { setLoading(true); setErreur(false) } })
    // CAD-A — `message_cle` : le texte de RÉPONSE convenu (accusé « ne plus
    // contacter », « je vous rappelle plus tard ») rendu pour CE client —
    // même forme de contrat que le message de la touche.
    // CAD63 — une langue basculée recharge le MÊME texte dans cette langue.
    let requete
    if (langueChoisie) {
      requete = crmApi.getRelanceEtapeMessageLangue(
        etape.id, { cle: etape.message_cle, langue: langueChoisie })
    } else {
      requete = etape.message_cle
        ? crmApi.getRelanceEtapeMessage(etape.id, etape.message_cle)
        : crmApi.getRelanceEtapeMessage(etape.id)
    }
    requete
      .then((r) => { if (active) setRendu(r.data) })
      .catch(() => { if (active) setErreur(true) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [open, etape, langueChoisie])

  // CAD63 — la langue AFFICHÉE (bouton actif du basculeur) et celle de la
  // fiche : l'écart entre les deux propose l'enregistrement.
  const langueAffichee = langueChoisie ?? rendu?.langue ?? null
  const langueFiche = langueEnregistree ?? etape?.lead_langue ?? 'fr'
  const proposerEnregistrement = Boolean(langueChoisie) && langueChoisie !== langueFiche
  // CAD64 — la langue du TEXTE réellement rendu : le français quand le
  // serveur signale un repli, sinon la langue demandée.
  const langueTexte = rendu?.repli_langue ? 'fr' : (rendu?.langue ?? 'fr')
  const texteRtl = LANGUES_RTL.includes(langueTexte)

  const enregistrerLangue = async () => {
    if (!langueChoisie) return
    setEnregistrementLangue(true)
    try {
      await crmApi.definirLangueRelanceEtape(etape.id, langueChoisie)
      setLangueEnregistree(langueChoisie)
      toast.success(`Langue du client enregistrée : ${LIBELLE_LANGUE[langueChoisie] ?? langueChoisie}.`)
      onLangueEnregistree?.(etape.id, langueChoisie)
    } catch (err) {
      // Règle « le champ fautif, le message exact » : le refus du serveur
      // nomme le champ `langue`.
      toast.error(err?.response?.data?.erreurs?.langue
        ?? 'La langue du client n’a pas pu être enregistrée.')
    } finally {
      setEnregistrementLangue(false)
    }
  }

  // CAD69 — les blancs `[…]` à compléter à la main (liste servie par le
  // serveur) : tant qu'il y en a, le texte ne part pas pré-rempli.
  const crochets = rendu?.crochets ?? []
  const aCompleter = crochets.length > 0
  // La conversation SANS texte pré-rempli (même numéro, même lien serveur).
  const urlConversation = rendu?.wa_url ? rendu.wa_url.split('?text=')[0] : null
  // CAD70 — la preuve J4 manque (aucune réalisation publiée) : le message
  // n'est pas proposé du tout.
  const preuveManquante = Boolean(rendu?.preuve_manquante)
  // CAD78 — une touche e-mail : jamais de CTA WhatsApp (texte à copier).
  const toucheEmail = etape?.canal === 'email'
  const envoiWhatsApp = !preuveManquante && !toucheEmail
  // CAD79 — le « vocal » : un SCRIPT à lire en note vocale (le serveur le dit,
  // `vocal`, et son lien n'a pas de texte pré-rempli) — jamais un message
  // écrit envoyé à la place de la voix.
  const vocal = Boolean(rendu?.vocal)

  const copier = async () => {
    if (!rendu?.message) return
    try {
      await navigator.clipboard.writeText(rendu.message)
      toast.success('Texte copié.')
    } catch {
      // best-effort — presse-papier indisponible (contexte non sécurisé,
      // permission refusée) : le texte reste lisible et sélectionnable.
    }
  }

  const ouvrirWhatsApp = async (url = rendu?.wa_url) => {
    if (!url) return
    // Le clic humain d'abord (le message est déjà écrit) — le marquage
    // serveur qui suit ne doit jamais bloquer l'ouverture déjà faite.
    window.open(url, '_blank', 'noopener')
    if (etape.message_cle) {
      // CAD-A — un accusé de RÉPONSE suit une touche DÉJÀ close : il n'y a
      // pas de touche à journaliser comme « message ouvert » (RLC3 ne vaut
      // que pour une touche encore à faire).
      toast.success('WhatsApp ouvert avec le message de réponse.')
      onOpenChange(false)
      return
    }
    setSending(true)
    try {
      // CAD63 — langue basculée : le serveur vérifie le rendu RÉELLEMENT
      // ouvert (sinon il re-rendrait dans la langue de la fiche).
      const r = langueChoisie
        ? await crmApi.whatsappRelanceEtapeLangue(etape.id, langueChoisie)
        : await crmApi.whatsappRelanceEtape(etape.id)
      // RELANCE-WA (fondateur 08/09/2026) — ouvrir WhatsApp n'avance plus la
      // touche : le clic est journalisé, la touche reste à faire jusqu'à la
      // réponse du client (questions « Fait »).
      toast.success(vocal
        ? 'Conversation ouverte : enregistrez la note vocale — la touche reste à faire : marquez « Fait » après la réponse du client.'
        : 'WhatsApp ouvert — la touche reste à faire : marquez « Fait » après la réponse du client.')
      onSent?.(etape.id, r?.data)
      onOpenChange(false)
    } catch {
      // best-effort — WhatsApp est déjà ouvert ; un échec du marquage reste
      // silencieux ici, la file se resynchronisera au prochain chargement.
    } finally {
      setSending(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          {/* CAD78 — une touche e-mail n'est jamais présentée comme un
              WhatsApp (la ligne ouvre son texte en place ; ceinture ici). */}
          <DialogTitle>
            {toucheEmail ? 'E-mail' : (vocal ? 'Note vocale' : 'WhatsApp')} — {etape?.lead_nom || 'Lead'}
          </DialogTitle>
        </DialogHeader>
        {loading ? (
          <Spinner />
        ) : erreur ? (
          <p className="text-sm text-muted-foreground">Message indisponible pour le moment.</p>
        ) : (
          <div className="flex flex-col gap-3">
            {/* CAD63 — changer la langue AU MOMENT UTILE : deux boutons qui
                rechargent le texte, sans quitter la touche. Le texte reste
                NON éditable (traçabilité de ce qui part réellement). */}
            <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Langue du message">
              {LANGUES_MESSAGE.map(([code, libelle]) => (
                <Button
                  key={code} type="button" size="sm"
                  variant={langueAffichee === code ? 'default' : 'outline'}
                  aria-pressed={langueAffichee === code}
                  onClick={() => setLangueChoisie(code)}
                >
                  {libelle}
                </Button>
              ))}
              {proposerEnregistrement && (
                <Button
                  type="button" size="sm" variant="outline"
                  disabled={enregistrementLangue} loading={enregistrementLangue}
                  onClick={enregistrerLangue}
                  data-testid="enregistrer-langue-client"
                >
                  C’est sa langue : enregistrer {LIBELLE_LANGUE[langueChoisie] ?? langueChoisie} sur la fiche
                </Button>
              )}
            </div>
            {/* Darija = écriture arabe, de droite à gauche : sans `dir`, le
                navigateur range les segments (prénom en lettres latines, nom
                de la société) dans un ordre illisible — incident du 07/09.
                `rendu` est encore null au premier rendu (avant le chargement). */}
            {/* CAD70 — sans réalisation publiée, le message J4 se réduirait à
                une phrase orpheline : il n'est PAS proposé. L'aide dit quoi
                faire (publier une réalisation — la porte d'entrée du catalogue
                — ou passer la touche). Jamais une preuve inventée. */}
            {preuveManquante ? (
              <div
                className="rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm"
                role="status" data-testid="preuve-manquante"
              >
                <p className="font-medium">
                  Aucune réalisation publiée : choisissez-en une ou passez cette touche.
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Ce message montre une installation comparable RÉELLE ; sans catalogue il se
                  réduirait à une phrase sans sujet.{' '}
                  <a href={LIEN_CATALOGUE_REALISATIONS} className="font-medium text-primary underline">
                    Ouvrir le catalogue (Paramètres → Réalisations)
                  </a>
                </p>
              </div>
            ) : (
              <>
                {/* CAD79 — le texte du vocal est un script à LIRE à voix
                    haute : il n'est jamais pré-rempli dans la conversation. */}
                {vocal && (
                  <p className="text-xs font-medium text-muted-foreground" data-testid="script-vocal">
                    Script à lire en note vocale — il ne part pas en texte écrit.
                  </p>
                )}
                <div
                  className={`whitespace-pre-wrap rounded-lg border border-border bg-muted/40 p-3 text-sm${texteRtl ? ' text-right' : ''}`}
                  dir={texteRtl ? 'rtl' : 'auto'}
                  lang={texteRtl ? 'ar' : langueTexte}
                >
                  {rendu?.message || '…'}
                </div>
              </>
            )}
            {/* CAD64 — le repli de langue n'est plus silencieux : le texte
                n'existe pas encore dans la langue du client, c'est la version
                française qui partira. On prévient — on ne traduit jamais. */}
            {rendu?.repli_langue && (
              <p className="flex items-start gap-1.5 text-xs text-warning" data-testid="repli-langue">
                <TriangleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
                Ce texte n’existe pas encore en {NOM_LANGUE[rendu.langue] ?? rendu.langue} : c’est la
                version française qui partira.
              </p>
            )}
            {/* Règle « aucun chiffre inventé » — un placeholder sans valeur
                réelle a fait OMETTRE la phrase côté serveur, jamais un blanc
                à sa place : l'écran nomme juste ce qui manquait. */}
            {!preuveManquante && rendu?.placeholders_manquants?.length > 0 && (
              <p className="flex items-start gap-1.5 text-xs text-warning">
                <TriangleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
                Informations manquantes ({rendu.placeholders_manquants.join(', ')}) — la
                phrase correspondante a été omise du message.
              </p>
            )}
            {/* CAD69 — un crochet ne part JAMAIS tel quel chez le client
                (« [montant en dirhams] » serait exactement la fuite que la
                règle « zéro chiffre inventé » vise) : ils sont listés, et
                « Ouvrir WhatsApp » reste bloqué tant qu'ils sont là. */}
            {aCompleter && (
              <p className="flex items-start gap-1.5 text-xs text-warning" role="alert" data-testid="crochets-a-completer">
                <TriangleAlert className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
                À compléter avant envoi : {crochets.join(', ')} — copiez le texte, complétez
                les crochets dans la conversation : il ne part jamais pré-rempli avec eux.
              </p>
            )}
            {!toucheEmail && !rendu?.wa_url && (
              <p className="text-sm text-destructive">
                Aucun numéro exploitable : le message ne peut pas être ouvert dans WhatsApp.
              </p>
            )}
          </div>
        )}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={sending}>
            Fermer
          </Button>
          {/* CAD70 — sans preuve, aucun geste d'envoi : ni copier la phrase
              orpheline, ni ouvrir WhatsApp avec elle. */}
          {!preuveManquante && (
            <Button variant="outline" onClick={copier} disabled={!rendu?.message}>
              <Copy className="mr-1 size-4" aria-hidden="true" />
              Copier
            </Button>
          )}
          {envoiWhatsApp && aCompleter && (
            <Button
              variant="outline" onClick={() => ouvrirWhatsApp(urlConversation)}
              disabled={!urlConversation || sending}
            >
              Ouvrir la conversation (sans texte)
            </Button>
          )}
          {envoiWhatsApp && (
            <Button
              onClick={() => ouvrirWhatsApp()}
              disabled={!rendu?.wa_url || aCompleter || sending} loading={sending}
            >
              {vocal ? (
                <>
                  <Mic className="mr-1 size-4" aria-hidden="true" />
                  Enregistrer une note vocale
                </>
              ) : (
                <>
                  <Send className="mr-1 size-4" aria-hidden="true" />
                  Ouvrir WhatsApp
                </>
              )}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
