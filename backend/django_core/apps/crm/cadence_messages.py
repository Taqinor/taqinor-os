"""Rendu des messages de touche : gabarits, placeholders, validité, segments, identité (SPL9, extrait de crm/services.py : déplacement pur).

Module de type (a) de la scission : il n'importe ni ``.services`` ni un
module racine ; ``services`` réexporte ce qu'il faut (façade).
"""
import logging
import re as _re

from . import activity
from .cadence_reperes import _lead_porte_tag, prefixe_activite_message_ouvert
from .leads_premier_contact import marquer_premier_contact
from .models import Lead, LeadActivity, RelanceEtape
from .visites_rdv import resoudre_lien_rdv

logger = logging.getLogger(__name__)


#: MRY13 — la touche dont le texte est un SCRIPT à dire, pas un message à
#: coller : son lien wa.me ne doit donc porter aucun `?text=`.
_TEMPLATES_VOCAUX = frozenset({'vocal_j3'})

#: Placeholders que le rendu sait remplir. Un placeholder de cette liste resté
#: SANS valeur fait OMETTRE sa phrase — jamais un blanc, jamais un défaut.
_PLACEHOLDERS_RENDUS = (
    'civilite', 'nom', 'prenom', 'ville', 'reference', 'lien',
    'lien_rdv', 'date_validite', 'conseiller',
    # CAD96 (21/09/2026) — le nom de marque affiché (résolu côté serveur,
    # jamais codé en dur ; voir ``_nom_affiche_marque``).
    'marque',
    # VISITE-CADENCE (15/09/2026) — la date du RENDEZ-VOUS de visite technique
    # posée sur la fiche (``Lead.visite_prevue_le``), rendue « mardi 16
    # septembre ». Fiche sans date ⇒ valeur vide ⇒ la phrase entière est OMISE
    # comme n'importe quel autre placeholder non résolu : on ne confirme jamais
    # un rendez-vous dont on ignore le jour.
    'date_visite',
    # 08/09/2026 — la PREUVE de la touche `j4_preuve` (mois, ville et lien de
    # la page publique d'une `parametres.Realisation` réelle).
    # CAD95 (21/09/2026) — vidéo COURTE (30-60 s) du même chantier, proposée
    # EN PLUS du lien (jamais à la place) ; sa propre phrase est omise SEULE
    # (MRY13) quand `Realisation.lien_video` est vide.
    # CAD71 (21/09/2026) — `avis_google` : lien de la fiche Google, réglage
    # société (`CompanyProfile.lien_avis_google`) — PAS le lien du devis.
    'mois_preuve', 'ville_preuve', 'lien_preuve', 'puissance_preuve',
    'lien_video_preuve', 'lien_google',
    # CAD127 (21/09/2026) — l'origine RÉELLE du lead : le nom de la personne
    # qui l'a recommandé, et le mois où il nous avait consultés. Vides quand
    # la donnée n'existe pas ⇒ leur phrase est OMISE, jamais un crochet.
    'prescripteur', 'mois_dossier',
    # CIQ500 (05/10/2026) — la raison sociale du lead (``Lead.societe``,
    # nettoyée — contrat CIQ1 `lead_pro.json`). Vide ⇒ la phrase qui la porte
    # est OMISE (MRY13), jamais un blanc « pour  ».
    'societe')

#: Les trois placeholders de la preuve. Regroupés pour n'aller chercher une
#: réalisation QUE si le texte en porte au moins un (même discipline que
#: `{lien_rdv}` : aucun travail, aucune requête, quand ce n'est pas demandé).
_PLACEHOLDERS_PREUVE = ('{mois_preuve}', '{ville_preuve}', '{lien_preuve}',
                        '{puissance_preuve}', '{lien_video_preuve}')

#: Noms de mois en français, pour « posée en juillet 2026 ». Codés ici plutôt
#: que via une locale système : le rendu d'un message client ne doit pas
#: dépendre des locales installées sur le serveur.
_MOIS_FR = (
    'janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet',
    'août', 'septembre', 'octobre', 'novembre', 'décembre')


#: Jours de la semaine en français (lundi = 0, comme ``date.weekday()``).
#: Codés ici, comme ``_MOIS_FR`` juste au-dessus : le rendu d'un message client
#: ne doit dépendre d'aucune locale installée sur le serveur.
_JOURS_FR = ('lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi',
             'dimanche')


def _date_visite_francais(valeur):
    """« mardi 16 septembre » à partir d'une date, ou '' si elle est inconnue.

    VISITE-CADENCE — la forme PARLÉE plutôt que « 16/09/2026 » : c'est un
    rendez-vous qu'on confirme à quelqu'un, pas une échéance administrative, et
    « mardi » est précisément l'information qui évite l'absence du client.
    L'ANNÉE est tue à dessein : on confirme la veille, elle n'apporte rien et
    alourdit la phrase.

    Une date absente rend une chaîne VIDE, ce qui fait OMETTRE la phrase
    (MRY13) — on n'écrit jamais un jour approximatif."""
    if valeur is None:
        return ''
    try:
        return (f'{_JOURS_FR[valeur.weekday()]} {valeur.day} '
                f'{_MOIS_FR[valeur.month - 1]}')
    except (AttributeError, IndexError, TypeError):
        return ''


def _mois_francais(valeur):
    """« juillet 2026 » à partir d'une date, ou '' si elle est inconnue.

    Une date absente rend une chaîne VIDE, ce qui fait omettre la phrase
    (MRY13) — on n'écrit jamais un mois approximatif."""
    if valeur is None:
        return ''
    try:
        return f'{_MOIS_FR[valeur.month - 1]} {valeur.year}'
    except (AttributeError, IndexError, TypeError):
        return ''


def _kwc_francais(valeur):
    """« 11,44 » / « 5 » à partir d'une puissance en kWc, ou '' si inconnue
    (la phrase « Puissance installée » est alors omise SEULE, MRY13)."""
    if valeur is None:
        return ''
    try:
        texte = f'{float(valeur):.2f}'.rstrip('0').rstrip('.')
    except (TypeError, ValueError):
        return ''
    return texte.replace('.', ',')


def _contexte_preuve(lead):
    """MRY-PREUVE — mois / ville / lien d'une réalisation RÉELLE pour ce lead.

    Le catalogue et le choix vivent dans l'app FONDATION `parametres`
    (`selectors.realisation_pour_lead` : même ville d'abord, sinon la plus
    proche dans le rayon, sinon la DERNIÈRE installation de la société —
    repli fondateur 08/09/2026) ; `crm` ne fait que consommer ce sélecteur. Aucune
    réalisation utilisable → les trois valeurs restent VIDES et
    `_omettre_phrases_incompletes` retire la phrase entière : jamais un
    chantier inventé, jamais un crochet laissé au client."""
    vide = {'mois_preuve': '', 'ville_preuve': '', 'lien_preuve': '',
            'puissance_preuve': '', 'lien_video_preuve': ''}
    try:
        from apps.parametres.selectors import realisation_pour_lead
        realisation = realisation_pour_lead(lead)
    except Exception:  # noqa: BLE001 — une preuve absente n'est jamais inventée
        logger.warning('Preuve J4 : catalogue illisible (lead #%s)',
                       getattr(lead, 'pk', '?'), exc_info=True)
        return vide
    if realisation is None:
        return vide
    return {
        'mois_preuve': _mois_francais(realisation.mise_en_service),
        'ville_preuve': (realisation.ville or '').strip(),
        'lien_preuve': (realisation.url_page or '').strip(),
        'puissance_preuve': _kwc_francais(realisation.puissance_kwc),
        # CAD95 — vidéo courte EN PLUS du lien ; vide si la réalisation n'en
        # porte aucune (jamais un défaut inventé).
        'lien_video_preuve': (realisation.lien_video or '').strip(),
    }


def _omettre_phrases_incompletes(texte, manquants):
    """MRY13 — retire les phrases qui portent un placeholder sans valeur.

    Laisser un blanc à la place d'une date de validité ou d'une référence
    produirait un message client trompeur (« valable jusqu'au  »). On préfère
    perdre la phrase que mentir : découpe par ligne puis par « . », et on
    ne garde que les fragments dont tous les placeholders sont résolus."""
    if not manquants:
        return texte
    trous = ['{' + cle + '}' for cle in manquants]
    lignes_gardees = []
    for ligne in (texte or '').split('\n'):
        if not any(trou in ligne for trou in trous):
            lignes_gardees.append(ligne)
            continue
        morceaux = ligne.split('. ')
        gardes = [m for m in morceaux
                  if not any(trou in m for trou in trous)]
        if gardes:
            recolle = '. '.join(gardes)
            if ligne.rstrip().endswith('.') and not recolle.endswith('.'):
                recolle += '.'
            lignes_gardees.append(recolle)
    return '\n'.join(lignes_gardees).strip()


def _nom_affiche_conseiller(lead, user):
    """Règle fondateur du 08/09/2026 : aucun prénom de personne (Meryem,
    Reda) n'est codé en dur dans un message client — l'expéditeur affiché
    est TOUJOURS le RESPONSABLE du lead (``lead.owner``), jamais forcément
    l'utilisateur qui clique sur « Envoyer ». Repli sur le responsable par
    défaut des leads de la société (``CompanyProfile.responsable_defaut_leads``
    — même lecture que ``default_responsable_for``, sans son round-robin : on
    rend un message, on n'assigne pas un lead) ; en dernier repli seulement,
    l'utilisateur courant."""
    conseiller = getattr(lead, 'owner', None)
    if conseiller is None:
        from apps.parametres.models import CompanyProfile
        profile = CompanyProfile.objects.filter(company=lead.company).first()
        conseiller = profile.responsable_defaut_leads if profile else None
    if conseiller is None:
        conseiller = user
    if conseiller is None:
        return ''
    return (getattr(conseiller, 'first_name', '')
            or getattr(conseiller, 'username', '') or '')


def _nom_affiche_marque(lead):
    """CAD96 (21/09/2026) — le nom de marque AFFICHÉ dans un texte client.

    Trois graphies codées en dur coexistaient (« la marque », « la marque
    Solutions », « Taqinor Solutions ») dans le même guide de messages,
    incohérence déjà présente dans le document source validé. Plutôt que de
    figer UNE de ces graphies dans le code (une future société white-label
    hériterait du nom de la marque), la marque vient désormais de
    ``parametres.CompanyProfile.nom`` — même source que les PDFs (SCA27) —
    avec repli sur ``Company.nom`` si la société n'a pas encore de profil."""
    company = getattr(lead, 'company', None)
    if company is None:
        return ''
    try:
        from apps.parametres.models import CompanyProfile
        profile = CompanyProfile.objects.filter(company=company).first()
    except Exception:  # noqa: BLE001 — un profil illisible ne bloque jamais l'envoi
        profile = None
    nom = (getattr(profile, 'nom', '') or '').strip()
    if nom:
        return nom
    return (getattr(company, 'nom', '') or '').strip()


def _civilite_et_prenom(lead, langue):
    """``(civilite, prenom)`` de la salutation d'un message client.

    CAD65 (audit L3 du 21/09/2026) — la civilité vient de la DONNÉE
    ``Lead.civilite`` (M./Mme, saisie au premier contact), jamais d'un défaut
    codé en dur : le « M. » posé d'office le 07/09/2026 faisait écrire
    « Bonjour M. » à une cliente sur tous les messages. Rendu : « M. » /
    « Mme » en français, « السي » / « لالة » en darija. Civilité INCONNUE ⇒
    chaîne VIDE ⇒ salutation NEUTRE (le prénom seul), jamais un genre supposé
    — ``_placer_civilite`` retire alors le placeholder et son espace, sans
    faire sauter la phrase d'accueil.

    Sans prénom (formulaire Meta au nom seul, société), le NOM prend sa place
    dans la salutation plutôt que de faire SAUTER toute la phrase d'accueil.

    Extrait de ``message_pour_etape`` (VISITE-CADENCE) pour que le rendu d'un
    message de VISITE — qui n'a pas de touche derrière lui — s'adresse au
    client exactement de la même façon : deux copies de cette règle auraient
    fini par se vouvoyer différemment.
    """
    civilite = (getattr(lead, 'civilite', '') or '').strip()
    if langue == 'darija':
        civilite = _CIVILITE_DARIJA.get(civilite, '')
    elif civilite not in _CIVILITES_CONNUES:
        civilite = ''
    prenom = (lead.prenom or '').strip() or (lead.nom or '').strip()
    return civilite, prenom


def _societe_du_lead(lead):
    """CIQ500 — la raison sociale du lead telle que servie par le contrat
    CIQ1 (``Lead.societe``), NETTOYÉE : espaces de bord retirés et blancs
    internes réduits à un seul. Vide ⇒ ``''`` (la phrase qui porte
    ``{societe}`` est alors omise — MRY13 —, jamais un blanc)."""
    return ' '.join(str(getattr(lead, 'societe', '') or '').split())


#: CAD65 — les civilités du lead (``Lead.Civilite``) et leur rendu darija.
_CIVILITES_CONNUES = ('M.', 'Mme')
_CIVILITE_DARIJA = {'M.': 'السي', 'Mme': 'لالة'}


def _placer_civilite(corps, civilite):
    """CAD65 — ``{civilite}`` est FACULTATIF : sans valeur, on retire le
    placeholder ET son espace (« Bonjour {civilite} {prenom} » → « Bonjour
    {prenom} »), au lieu de le compter manquant — ce qui ferait OMETTRE
    toute la phrase d'accueil (MRY13) — ou de laisser un double espace."""
    if civilite or '{civilite}' not in (corps or ''):
        return corps
    return (corps.replace('{civilite} ', '').replace(' {civilite}', '')
            .replace('{civilite}', ''))


#: VISITE-CADENCE — les clés de gabarit que le rendu « message de visite »
#: accepte. Liste FERMÉE : un `?cle=` inconnu est un 400 qui NOMME le champ,
#: jamais un message vide servi en 200 (l'écran croirait avoir un texte).
#: AGR414 — ``visite_releve_point_eau`` : la visite de relevé du point d'eau
#: proposée AVANT le devis agricole, avec sa liste de préparation (FR + darija).
CLES_MESSAGE_VISITE = (
    'visite_proposition', 'visite_confirmation', 'visite_releve_point_eau',
)

#: AGR526 — les textes des DOSSIERS institutionnels (playbooks de segment
#: CAD125) que le même rendu sert — mais SEULEMENT au lead pour qui
#: ``cle_message_segment`` renvoie cette clé (jamais un FDA à un exploitant
#: au gasoil, jamais un 82-21 à un résidentiel).
CLES_MESSAGE_DOSSIER = ('dossier_fda', 'dossier_8221')


def cle_message_visite_autorisee(lead, cle):
    """AGR526 — ``cle`` est-elle un texte que ``message-visite`` rend pour CE
    lead ? Une clé de visite toujours ; une clé de dossier seulement quand le
    playbook de segment du lead la confirme (``cle_message_segment``)."""
    if cle in CLES_MESSAGE_VISITE:
        return True
    return cle in CLES_MESSAGE_DOSSIER and cle_message_segment(lead) == cle


def cles_message_visite_du_lead(lead):
    """AGR526 — les clés que ``message-visite`` accepte pour CE lead (le
    refus 400 les NOMME)."""
    cles = list(CLES_MESSAGE_VISITE)
    dossier = cle_message_segment(lead)
    if dossier in CLES_MESSAGE_DOSSIER:
        cles.append(dossier)
    return cles


def message_visite_pour_lead(lead, cle, *, user=None, masquer_numero=False):
    """VISITE-CADENCE — le message de visite d'un LEAD, rendu côté serveur.

    ``{'corps_fr': str, 'corps_darija': str}`` — les DEUX langues d'un coup :
    l'écran propose le copier-coller dans celle que le client parle, sans
    second aller-retour.

    CAD111 — plus ``wa_url_fr`` / ``wa_url_darija`` / ``phone`` : le lien
    wa.me est construit CÔTÉ SERVEUR (numéro normalisé E.164 par
    ``build_wa_url`` — « 06… » devient « 2126… »), comme pour les touches
    normales ; l'écran ne fabrique plus un lien en chiffres bruts.
    ``masquer_numero`` (rôle sans ``client_pii_voir``) : aucun numéro ne sort
    — liens ``None``, ``phone`` vide, même règle que la file des relances.

    MÊME machinerie que les messages de cadence (``message_pour_etape``) :
    mêmes placeholders autorisés, même ``{conseiller}`` = le RESPONSABLE du
    lead (jamais un prénom codé en dur), et surtout même règle MRY13 — une
    phrase dont le placeholder n'a pas de valeur RÉELLE est OMISE. Un lead
    sans ``visite_prevue_le`` ne reçoit donc pas « la visite prévue  chez
    vous » : la phrase disparaît, et le reste du message tient debout.

    Le serveur REND, il n'ENVOIE pas (décision D5) — aucun appel sortant.

    Renvoie ``None`` si ``cle`` n'est pas une clé de visite connue : c'est
    l'appelant (la vue) qui en fait un 400 nommant le champ.
    """
    from apps.parametres.models_messages import MessageTemplate
    from apps.ventes.utils.whatsapp import build_wa_url, render_message_template

    # AGR526 — une clé de DOSSIER n'est rendue qu'au lead dont le playbook de
    # segment la confirme ; sinon ``None`` (la vue en fait un 400 sur ``cle``).
    if not cle_message_visite_autorisee(lead, cle):
        return None

    date_visite = _date_visite_francais(
        getattr(lead, 'visite_prevue_le', None))
    rendu = {}
    for champ, langue in (('corps_fr', 'fr'), ('corps_darija', 'darija')):
        civilite, prenom = _civilite_et_prenom(lead, langue)
        contexte = {
            'civilite': civilite,
            'nom': (lead.nom or '').strip(),
            'prenom': prenom,
            'ville': (lead.ville or '').strip(),
            'conseiller': _nom_affiche_conseiller(lead, user),
            'marque': _nom_affiche_marque(lead),
            'date_visite': date_visite,
            # CIQ500 — la raison sociale, vide ⇒ phrase omise (MRY13).
            'societe': _societe_du_lead(lead),
        }
        corps = MessageTemplate.get_corps(lead.company, cle, langue) or ''
        # CAD126 — variante de SEGMENT par exception (pompage / B2B).
        corps = _corps_pour_segment(corps, cle, lead, langue)
        # CAD65 — civilité inconnue : salutation neutre, jamais omise.
        corps = _placer_civilite(corps, civilite)
        manquants = [c for c in _PLACEHOLDERS_RENDUS
                     if '{' + c + '}' in corps
                     and not str(contexte.get(c, '')).strip()]
        rendu[champ] = render_message_template(
            _omettre_phrases_incompletes(corps, manquants), contexte)
    # CAD111 — les liens wa.me construits par le SERVEUR (E.164), un par
    # langue, jamais par l'écran ; aucun numéro pour un rôle sans droit PII.
    phone = '' if masquer_numero else (lead.whatsapp or lead.telephone or '')
    rendu['wa_url_fr'] = build_wa_url(phone, rendu['corps_fr']) if phone else None
    rendu['wa_url_darija'] = (build_wa_url(phone, rendu['corps_darija'])
                              if phone else None)
    rendu['phone'] = phone
    return rendu


#: CAD111 — les langues dans lesquelles le message de visite peut être ouvert
#: (les deux corps que `message_visite_pour_lead` rend).
LANGUES_MESSAGE_VISITE = ('fr', 'darija')


def journaliser_message_visite_ouvert(lead, user, *, cle, langue, etape=None):
    """CAD111 — le message de VISITE a été OUVERT dans WhatsApp (clic humain).

    Jumeau de ``journaliser_whatsapp_ouvert`` : une activité typée WhatsApp au
    chatter — comptée comme tentative et premier contact par les récepteurs —,
    journalisée comme « ouvert » et JAMAIS comme « fait » : aucune issue,
    aucune touche avancée, aucune cadence arrêtée. Quand le message est ouvert
    depuis une TOUCHE (``etape``, encore à faire), la ligne porte le préfixe
    RLC3 de cette touche : son panneau « Fait » sait alors que le message a
    été ouvert, au lieu de faire cocher l'aveu faux « marquée faite sans avoir
    ouvert le message ». Renvoie l'activité créée."""
    quoi = {
        'visite_proposition': 'proposer la visite',
        # AGR414 — la visite de relevé du point d'eau (agricole).
        'visite_releve_point_eau': 'proposer le relevé du point d’eau',
        # AGR526 — les textes de dossier des playbooks de segment.
        'dossier_fda': 'demander où en est le dossier de subvention FDA',
        'dossier_8221': 'demander où en est le dossier du site',
    }.get(cle, 'confirmer la visite')
    langue_txt = 'darija' if langue == 'darija' else 'français'
    if etape is not None:
        corps = (f'{prefixe_activite_message_ouvert(etape)} (cadence '
                 f'{etape.cadence}) : message de visite « {quoi} » ouvert en '
                 f'{langue_txt} ; la touche reste à faire jusqu’à la réponse '
                 'du client.')
    else:
        corps = (f'WhatsApp ouvert — message de visite « {quoi} » en '
                 f'{langue_txt} : message préparé, rien n’est marqué fait.')
    activite = LeadActivity.objects.create(
        company=lead.company, lead=lead, user=user,
        kind=LeadActivity.Kind.WHATSAPP, body=corps)
    marquer_premier_contact(lead)
    return activite


# ── CAD-F ── CAD63 — changer la langue AU MOMENT UTILE ───────────────────────
#
# Le texte d'une touche était rendu dans la langue de la fiche, point : si la
# commerciale découvrait au téléphone que le client ne lit pas le français,
# elle devait quitter la touche, ouvrir la fiche, changer le champ, revenir.
# La langue peut désormais être CHOISIE pour le message affiché (``langue=``
# sur le rendu) et ENREGISTRÉE sur le lead en un geste — la réponse « ne parle
# que darija » de la touche, ou la confirmation de l'aperçu. Le vocabulaire
# est celui du champ ``Lead.langue_preferee`` lui-même : aucune langue n'est
# ouverte ici sans texte validé derrière elle (CAD64 — ni l'anglais ni l'arabe
# classique tant que la relance n'en a pas).

def langues_relance():
    """CAD63 — les langues qu'on peut CHOISIR pour le message d'une touche :
    les valeurs du champ ``Lead.langue_preferee`` (lues sur le modèle, jamais
    recopiées)."""
    return tuple(Lead.LanguePreferee.values)


def refus_langue_relance(langue):
    """CAD63 — pourquoi ``langue`` n'est pas une langue de relance, ou
    ``None``. Le message NOMME la valeur reçue et les langues proposées
    (règle fondateur du 08/09/2026 : jamais un refus muet)."""
    langue = (langue or '').strip()
    if langue in langues_relance():
        return None
    proposees = ', '.join(
        f'« {valeur} » ({libelle})'
        for valeur, libelle in Lead.LanguePreferee.choices)
    return (f'« Langue du message » : « {langue} » n’est pas une langue de '
            f'relance. Langues proposées : {proposees}.')


def definir_langue_preferee(lead, user, langue):
    """CAD63 — pose ``Lead.langue_preferee`` et le JOURNALISE comme la fiche
    le ferait (ligne « modification » du chatter, ancien → nouveau).

    L'appelant a validé ``langue`` (``refus_langue_relance``). Idempotente :
    une langue déjà posée ne produit ni écriture ni ligne. Renvoie ``True``
    si la langue vient de changer."""
    import copy

    if (lead.langue_preferee or '') == langue:
        return False
    avant = copy.copy(lead)
    lead.langue_preferee = langue
    lead.save(update_fields=['langue_preferee'])
    activity.log_changes(avant, lead, user)
    return True


# ── CAD-F ── CAD64 — le repli de langue devient VISIBLE ─────────────────────
#
# Deux causes, un seul effet silencieux. (1) La langue de la relance se lisait
# ``lead.langue_preferee or 'fr'`` au lieu de passer par le résolveur COMMUN
# des documents client (``parametres.i18n_resolver.resolve_langue_sortie`` —
# ``Client.langue_document`` puis la langue de repli de la société) : un devis
# pouvait partir en arabe pendant que la relance restait en français, sans que
# rien ne le dise. (2) ``MessageTemplate.get_corps`` retombe sur le FRANÇAIS
# quand la clé n'a pas de texte dans la langue demandée — darija, anglais ou
# arabe classique — sans un mot. On ne traduit JAMAIS automatiquement : on
# PRÉVIENT (``repli_langue`` dans la réponse, avertissement à l'aperçu).

def langue_relance_du_lead(lead):
    """CAD64 — la langue DEMANDÉE pour les messages de relance de ce lead.

    La préférence posée sur le lead (``langue_preferee`` — FR ou darija, le
    seul registre de la relance WhatsApp) prime ; à défaut, le résolveur
    COMMUN des documents client (langue documentaire du client, puis repli de
    la société, puis FR). Aucun texte n'est ouvert ici : si la langue résolue
    n'a pas de texte validé pour une clé, le rendu retombe sur le français et
    le DIT (``repli_langue``)."""
    preference = (getattr(lead, 'langue_preferee', '') or '').strip()
    if preference:
        return preference
    from apps.parametres.i18n_resolver import resolve_langue_sortie
    return resolve_langue_sortie(
        client=getattr(lead, 'client', None),
        company=getattr(lead, 'company', None))


def texte_en_repli_de_langue(company, cle, langue):
    """CAD64 — le texte de ``cle`` retombe-t-il sur le FRANÇAIS faute
    d'exister dans ``langue`` ?

    Lu par l'API publique du catalogue (``MessageTemplate.get_corps``), jamais
    en recopiant sa règle : la langue demandée est en repli quand elle n'est
    pas le français et que son corps est EXACTEMENT le corps français."""
    if not cle or (langue or 'fr') == 'fr':
        return False
    from apps.parametres.models_messages import MessageTemplate
    corps_langue = MessageTemplate.get_corps(company, cle, langue) or ''
    if not corps_langue.strip():
        return False
    return corps_langue == (MessageTemplate.get_corps(company, cle, 'fr') or '')


# ── CAD-F ── CAD69 — les crochets [ ] ne partent plus en silence ────────────
#
# `render_message_template` ne substitue que les {accolades} et MRY13 n'omet
# que les phrases à accolades vides : un blanc écrit « [jour] », « [montant en
# dirhams] » dans un texte validé (`rappel_plus_tard`, `offre_reda`) partait
# TEL QUEL dans WhatsApp, alors que le catalogue promet « jamais un crochet
# vide envoyé au client ». Ces blancs sont à compléter À LA MAIN (on n'invente
# ni un jour ni un montant) : le rendu les LISTE, l'aperçu bloque l'ouverture
# tant qu'ils sont là.

#: Un blanc à compléter : un texte court entre crochets, sur une seule ligne.
_RE_CROCHET = _re.compile(r'\[[^\[\]\n]{1,80}\]')


def crochets_a_completer(texte):
    """CAD69 — les blancs ``[…]`` encore présents dans ``texte``, dans l'ordre
    d'apparition, sans doublon (``[]`` si aucun)."""
    vus = []
    for trou in _RE_CROCHET.findall(texte or ''):
        if trou not in vus:
            vus.append(trou)
    return vus


def message_pour_etape(etape, *, request=None, user=None, cle=None,
                       langue=None):
    """MRY13 — Le message d'UNE touche, rendu côté serveur.

    Forme `relance_etape_message` (contrat MRY25) :
    ``{message, wa_url, langue, phone, placeholders_manquants}``.

    CAD63 — ``langue`` (une de ``langues_relance()``, validée par
    l'appelant) force la langue du rendu pour CE message, sans toucher la
    fiche : c'est l'aperçu qu'on bascule FR ↔ darija au téléphone.

    CAD-A — ``cle`` (une des ``CLES_MESSAGE_REPONSE``) rend, pour le lead de
    cette touche, le texte de RÉPONSE convenu (« stop_contact » après « Ne
    plus me contacter », « rappel_plus_tard » après « Plus tard ») au lieu du
    gabarit de la touche. Même machinerie, même forme : l'écran propose
    l'envoi, le clic humain ouvre WhatsApp (décision D5).

    Le serveur RÉEND, il n'ENVOIE pas (décision D5) : l'écran montre une
    modale d'aperçu, et c'est le clic humain qui ouvre WhatsApp. Aucun BSP,
    aucun appel réseau sortant.

    Règle absolue du lot : AUCUN chiffre inventé. Une phrase dont le
    placeholder n'a pas de valeur réelle est OMISE (jamais un blanc, jamais un
    défaut), et `placeholders_manquants` le dit à l'appelant. Les prix, kWc et
    économies ne sont pas des placeholders du tout : ils restent dans le devis
    et la proposition."""
    from apps.parametres.models_messages import MessageTemplate
    from apps.ventes.utils.whatsapp import build_wa_url, render_message_template

    lead = etape.lead
    # CAD64 — la langue passe par le résolveur COMMUN (préférence du lead,
    # puis langue documentaire du client, puis repli société), jamais un
    # `or 'fr'` local qui laissait la relance en français pendant que le
    # devis partait en arabe.
    langue = langue or langue_relance_du_lead(lead)
    # CAD-A — le texte de réponse demandé remplace le gabarit de la touche.
    template_cle = cle or etape.template_cle
    # CAD127 — le premier message dit la VÉRITÉ sur l'origine : « vous venez
    # de remplir notre formulaire » est faux pour un lead venu par téléphone,
    # en boutique, par recommandation ou d'un message entrant. La clé est
    # choisie d'après le canal déjà enregistré, AVANT de lire le gabarit.
    cle_rendue = cle_identite_pour_lead(lead, template_cle,
                                        reference=etape.due_date)
    corps = MessageTemplate.get_corps(
        lead.company, cle_rendue, langue) if cle_rendue else ''
    # CAD64 — le texte n'existe pas dans la langue demandée : c'est la version
    # FRANÇAISE qui part, et on le DIT. Le texte est alors rendu comme un
    # texte français (civilité « M. »/« Mme » — CAD65 —, variante de
    # segment), jamais un « السي » collé dans une phrase française.
    repli_langue = texte_en_repli_de_langue(lead.company, cle_rendue, langue)
    langue_texte = 'fr' if repli_langue else langue
    # CAD126 — variante de SEGMENT par exception : « sur votre toit » ne part
    # pas à un pompage au bord d'un forage, « en famille » pas à une
    # entreprise. Par exception SEULEMENT, et jamais sur un texte que la
    # société a personnalisé.
    # CIQ506 — une touche de canal E-MAIL (sans texte de réponse demandé) se
    # rend dans sa FORME e-mail (`forme_email`, CIQ502 : objet + corps,
    # français, neutre de segment) ; sans forme pour sa clé — ou dans une
    # autre langue que le français —, le texte de la clé tient lieu de corps
    # (comme `relance_email_j10`), sans objet.
    est_email = (etape.canal == RelanceEtape.Canal.EMAIL and not cle)
    forme = None
    if est_email and langue_texte == 'fr':
        from apps.parametres.models_messages import forme_email
        forme = forme_email(template_cle)
    if forme:
        corps = forme['corps']
    else:
        corps = _corps_pour_segment(corps, cle_rendue, lead, langue_texte)
    objet_gabarit = forme['objet'] if forme else ''

    civilite, prenom = _civilite_et_prenom(lead, langue_texte)
    # CAD65 — civilité inconnue : salutation neutre, jamais omise.
    corps = _placer_civilite(corps, civilite)
    objet_gabarit = _placer_civilite(objet_gabarit, civilite)
    contexte = {
        'civilite': civilite,
        'nom': (lead.nom or '').strip(),
        'prenom': prenom,
        'ville': (lead.ville or '').strip(),
        'conseiller': _nom_affiche_conseiller(lead, user),
        'marque': _nom_affiche_marque(lead),
        # CIQ500 — la raison sociale du lead ; vide ⇒ phrase OMISE (MRY13)
        # et `societe` listé dans `placeholders_manquants`.
        'societe': _societe_du_lead(lead),
        'reference': '',
        'lien': '',
        'date_validite': '',
        # VISITE-CADENCE (revue Fable 15/09) — la touche « Confirmer la visite
        # (veille) » porte template_cle='visite_confirmation' et se rend par
        # ICI (ToucheMessageDialog → message/) : sans cette clé, la phrase
        # avec la date était TOUJOURS omise et le message ne confirmait rien.
        'date_visite': _date_visite_francais(
            getattr(lead, 'visite_prevue_le', None)),
        'lien_google': '',
        # CAD127 — l'origine réelle. Résolus seulement si le texte les
        # demande (aucune requête sinon) ; vides ⇒ phrase OMISE (MRY13).
        'prescripteur': (_nom_prescripteur(lead)
                         if '{prescripteur}' in (corps or '') else ''),
        'mois_dossier': (_mois_dossier_francais(lead)
                         if '{mois_dossier}' in (corps or '') else ''),
    }
    # CAD71 (21/09/2026) — {lien_google} : lien de la fiche Google de la
    # société, réglage dédié (`CompanyProfile.lien_avis_google`) — AVANT
    # ce champ, `avis_google` recevait le lien du DEVIS via `{lien}`, jamais
    # celui de la fiche Google. Résolu seulement si le texte le demande
    # (même discipline que `{lien_rdv}`/la preuve J4).
    if '{lien_google}' in (corps or ''):
        from apps.parametres.models import CompanyProfile
        profile = CompanyProfile.objects.filter(company=lead.company).first()
        contexte['lien_google'] = (
            (profile.lien_avis_google if profile else '') or '').strip()
    if etape.devis_id:
        try:
            from apps.ventes.selectors import get_devis_by_pk
            from apps.ventes.utils.client_links import url_proposition
            devis = get_devis_by_pk(etape.devis_id)
            if devis is not None:
                contexte['reference'] = getattr(devis, 'reference', '') or ''
                # CAD59 — le message applique le MÊME repli que le PDF :
                # `date_validite` si posée, sinon date de création + le
                # réglage société `quote_validity_days`. Lire le seul champ
                # laissait MRY13 supprimer la phrase entière quand il était
                # vide, et le WhatsApp contredisait alors un PDF qui, lui,
                # affichait « valable jusqu'au X ». Règle #4 respectée : on ne
                # touche pas au moteur de rendu, on lit la MÊME règle.
                validite = _date_validite_comme_le_pdf(devis)
                if validite:
                    contexte['date_validite'] = validite.strftime('%d/%m/%Y')
                contexte['lien'] = url_proposition(devis) or ''
        except Exception:  # noqa: BLE001 — un lien absent n'est jamais inventé
            logger.warning(
                'MRY13: contexte devis illisible (étape #%s)',
                getattr(etape, 'pk', '?'), exc_info=True)

    # `{lien_rdv}` n'est résolu QUE s'il est présent (aucun jeton créé sinon),
    # et sa valeur rejoint le CONTEXTE au lieu d'être substituée tout de suite
    # dans le corps. C'était le trou : `resoudre_lien_rdv` remplaçait le
    # placeholder par '' quand la génération du jeton échouait, AVANT le calcul
    # des placeholders manquants — la phrase « réservez ici : {lien_rdv} »
    # n'était donc jamais omise et partait au client avec un blanc, exactement
    # ce que la règle « aucun chiffre/lien inventé » interdit.
    if '{lien_rdv}' in (corps or ''):
        contexte['lien_rdv'] = (
            resoudre_lien_rdv('{lien_rdv}', lead, request=request) or '')

    # La PREUVE de la touche J4 : mois, ville et lien d'une réalisation RÉELLE
    # de la société, choisie sur la ville du lead. Résolue seulement si le
    # texte la demande, et rejoignant le CONTEXTE (donc soumise au calcul des
    # placeholders manquants) — sans catalogue, la phrase est OMISE.
    # CAD70 — sans AUCUNE réalisation utilisable (le cas PAR DÉFAUT d'une
    # société qui n'a rien publié), les phrases de preuve sautent toutes et il
    # ne reste qu'une phrase orpheline (« Le suivi de production est en temps
    # réel… ») : la touche ne doit alors PAS proposer ce message. Le drapeau
    # `preuve_manquante` le dit à l'aperçu (et le POST `whatsapp/` le refuse).
    preuve_manquante = False
    if any(t in (corps or '') for t in _PLACEHOLDERS_PREUVE):
        preuve = _contexte_preuve(lead)
        contexte.update(preuve)
        preuve_manquante = not any(
            str(valeur).strip() for valeur in preuve.values())

    manquants = [cle for cle in _PLACEHOLDERS_RENDUS
                 if ('{' + cle + '}' in (corps or '')
                     or '{' + cle + '}' in objet_gabarit)
                 and not str(contexte.get(cle, '')).strip()]
    corps = _omettre_phrases_incompletes(corps, manquants)
    message = render_message_template(corps, contexte)
    # CIQ506 — l'objet : même contexte, même omission MRY13 (un objet dont le
    # placeholder n'a pas de valeur est OMIS, jamais un blanc ni un défaut).
    objet = render_message_template(
        _omettre_phrases_incompletes(objet_gabarit, manquants),
        contexte).strip() if objet_gabarit else ''

    phone = lead.whatsapp or lead.telephone or ''
    if est_email:
        # Une touche e-mail n'ouvre pas WhatsApp : `wa_url` vaut `null`, et le
        # lien `mailto:` est construit par le serveur. Rien n'est envoyé (D5).
        wa_url = None
    elif template_cle in _TEMPLATES_VOCAUX:
        # Le texte est le SCRIPT du vocal : on ouvre la conversation, on ne
        # pré-remplit rien — coller un script à dire serait absurde.
        wa_url = build_wa_url(phone, '')
        if wa_url:
            wa_url = wa_url.split('?text=')[0]
    else:
        wa_url = build_wa_url(phone, message)
    return {
        'message': message,
        'wa_url': wa_url,
        'langue': langue,
        'phone': phone,
        'placeholders_manquants': manquants,
        # CAD64 — `True` : le texte n'existe pas dans `langue`, la version
        # française part à sa place (l'aperçu le dit ; le cas se mesure).
        'repli_langue': repli_langue,
        # CAD69 — les blancs `[…]` à compléter à la main avant tout envoi
        # (l'aperçu bloque « Ouvrir WhatsApp » tant qu'il y en a).
        'crochets': crochets_a_completer(message),
        # CAD70 — `True` : le texte demande une preuve (J4) et la société n'a
        # AUCUNE réalisation publiée — jamais une preuve inventée ni un
        # chantier mélangé : l'aperçu remplace l'envoi par l'aide.
        'preuve_manquante': preuve_manquante,
        # CAD79 — `True` : le texte est le SCRIPT d'une note vocale à DIRE
        # (`wa_url` sans `?text=`), jamais un message écrit à envoyer.
        'vocal': template_cle in _TEMPLATES_VOCAUX,
        # CIQ506 — l'objet de l'e-mail (chaîne VIDE hors canal e-mail) et le
        # lien `mailto:` (RFC 6068) ; `null` hors e-mail, sans adresse, ou
        # pour un rôle sans `client_pii_voir` (même masquage que `lead_email`).
        'objet': objet if est_email else '',
        'mailto_url': (_mailto_url(lead, objet, message, user)
                       if est_email else None),
    }


def _mailto_url(lead, objet, corps, user):
    """CIQ506 — ``mailto:<adresse>?subject=…&body=…`` (RFC 6068, espaces en
    ``%20``, sauts de ligne en CRLF), ou ``None`` : fiche sans adresse, ou
    rôle sans ``client_pii_voir`` (la file des relances ne doit pas rendre
    l'adresse que la fiche lui masque)."""
    from urllib.parse import quote

    from .serializers import pii_masquee_pour

    adresse = (getattr(lead, 'email', '') or '').strip()
    if not adresse or pii_masquee_pour(user):
        return None
    parametres = []
    if objet:
        parametres.append('subject=' + quote(objet, safe=''))
    if corps:
        crlf = corps.replace('\r\n', '\n').replace('\n', '\r\n')
        parametres.append('body=' + quote(crlf, safe=''))
    url = 'mailto:' + quote(adresse, safe='@+')
    return url + ('?' + '&'.join(parametres) if parametres else '')


#: CAD70 — le refus du POST `whatsapp/` quand la preuve manque (le champ est
#: nommé tel que l'écran le montre).
REFUS_PREUVE_MANQUANTE = (
    '« Preuve — installation comparable » : aucune réalisation publiée. '
    'Ajoutez-en une au catalogue (Paramètres → Réalisations) ou passez cette '
    'touche — ce message ne part pas sans preuve réelle.')


# ── CAD-F ── CAD71 (21/09/2026) ──────────────────────────────────────────
class GabaritNonAssignable(Exception):
    """Un gabarit de message exige un réglage société qui manque encore."""


#: Gabarits dont l'assignation exige un réglage société non vide, avec le
#: libellé humain du réglage manquant (repris dans le refus). `avis_google`
#: envoyait le lien du DEVIS du client à la place d'un lien vers la fiche
#: Google tant que ce garde-fou n'existait pas (`{lien}` n'était alimenté que
#: par `url_proposition`, jamais un lien Google) : on refuse maintenant
#: l'ASSIGNATION plutôt que de laisser la phrase partir vide ou fausse.
_GABARITS_REGLAGE_REQUIS = {
    'avis_google': ('lien_avis_google', 'lien de la fiche Google'),
}


def verifier_gabarit_assignable(company, template_cle):
    """CAD71 — lève ``GabaritNonAssignable`` si ``template_cle`` exige un
    réglage société (``CompanyProfile``) qui est vide ; ne fait rien pour un
    gabarit sans exigence (comportement historique inchangé). À appeler
    AVANT d'enregistrer l'assignation d'un gabarit à une touche (gabarit
    `parametres.CadenceRelanceEtape` ou touche `crm.RelanceEtape`) — crochet
    attendu côté écran : `apps/parametres/views_referentiels.py`
    (`CadenceRelanceEtapeViewSet`/son serializer) doit l'appeler avant
    `save()` pour que le refus atteigne réellement l'éditeur."""
    exige = _GABARITS_REGLAGE_REQUIS.get(template_cle)
    if exige is None:
        return
    champ, libelle = exige
    from apps.parametres.models import CompanyProfile
    profile = CompanyProfile.objects.filter(company=company).first()
    valeur = ((getattr(profile, champ, '') if profile else '') or '').strip()
    if not valeur:
        raise GabaritNonAssignable(
            f'« {libelle} » n\'est pas renseigné dans les réglages de la '
            f'société : assignez d\'abord ce réglage avant de choisir ce '
            f'gabarit (Paramètres → Société).')


#: L'intention de financement qui déclenche la validité longue. Valeur de
#: ``crm.Lead.FinancingIntent.CREDIT`` — lue en littéral ici pour ne pas
#: importer les modèles depuis une fonction appelée à chaud.
FINANCEMENT_CREDIT = 'credit'


def lead_finance_a_credit(lead):
    """Le lead a-t-il DÉCLARÉ financer à crédit ?

    « Pas encore décidé » et « comptant » ne déclenchent rien : on n'allonge
    pas une validité sur une supposition.
    """
    return (getattr(lead, 'financing_intent', None) or '') == \
        FINANCEMENT_CREDIT


def lead_dossier_subvention_en_instruction(lead):
    """AGR523 — le dossier de subvention du lead est-il DÉPOSÉ (en
    instruction) ? « À déposer », vide, accordé ou refusé : non."""
    return (getattr(lead, 'dossier_subvention', None) or '') == 'depose'


#: AGR523 — la fin de la note d'historique quand la validité vient du
#: dossier de subvention en instruction.
MOTIF_VALIDITE_SUBVENTION = ('dossier de subvention en instruction (réglage '
                             'société)')


#: CIQ510 (contrat CIQ1 ``lead_pro.json``, ``financing_intent``) — les
#: financements PRO déclarés qui reçoivent la règle « financé » : crédit
#: bancaire / offre de financement / ligne verte (``credit``) et crédit-bail
#: (``credit_bail``, valeur interne). Comptant et indécis : jamais.
FINANCEMENTS_PRO = ('credit', 'credit_bail')
#: Les segments PRO (``Lead.type_installation``).
SEGMENTS_PRO = ('commercial', 'industriel')


def lead_financement_pro_declare(lead):
    """CIQ510 — un lead commercial/industriel a-t-il DÉCLARÉ un financement
    pro (contrat CIQ1) ? Jamais sur une supposition."""
    return ((getattr(lead, 'type_installation', None) or '') in SEGMENTS_PRO
            and (getattr(lead, 'financing_intent', None) or '')
            in FINANCEMENTS_PRO)


def lead_en_attente_d_accord(lead):
    """CIQ510 — le lead porte-t-il une étiquette d'attente posée par la
    réponse « En attente d'un accord » (CIQ508, une par raison) ?"""
    return any(_lead_porte_tag(lead, tag)
               for tag in ETIQUETTES_RAISON_ATTENTE)


def _validite_selon_financement(lead, devis, date_fin_de_suivi):
    """La date de validité à POSER sur ce devis.

    Comptant / indécis : la fin du plan de suivi (comportement VALID1
    inchangé — une date dérivée des cadences du fondateur, jamais inventée).
    Crédit : la date du réglage société, si elle est PLUS LOINTAINE — on ne
    raccourcit jamais une validité déjà plus longue, et une société qui règle
    sa validité à 10 jours ne se retrouve pas avec un devis financé qui expire
    AVANT la fin de son propre suivi.
    """
    # AGR523 — un dossier de subvention DÉPOSÉ (en instruction) reçoit la
    # MÊME règle que le crédit : le réglage société, s'il est plus lointain.
    # Aucun nouveau nombre, aucune durée propre à la FDA.
    # CIQ510 — même règle pour un financement PRO déclaré (contrat CIQ1) et
    # pour un lead qui porte une étiquette d'attente d'accord (CIQ508).
    if not (lead_finance_a_credit(lead)
            or lead_financement_pro_declare(lead)
            or lead_en_attente_d_accord(lead)
            or lead_dossier_subvention_en_instruction(lead)):
        return date_fin_de_suivi
    try:
        from apps.ventes.services import date_validite_credit
        candidate = date_validite_credit(devis)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'CAD57 : validité crédit illisible (devis #%s)',
            getattr(devis, 'pk', '?'), exc_info=True)
        return date_fin_de_suivi
    if candidate is None:
        return date_fin_de_suivi
    if date_fin_de_suivi is None:
        return candidate
    return max(candidate, date_fin_de_suivi)


# ── CAD-E ── CAD59 — le message J9 et le PDF disent la MÊME date ───────────
#
# Le moteur de devis a un repli documenté (``date_validite``, sinon date de
# création + le réglage société ``quote_validity_days``) alors que
# ``message_pour_etape`` ne lisait QUE ``devis.date_validite`` : vide, MRY13
# supprimait la phrase entière et le WhatsApp enchaînait sur « Après, je dois
# revalider les prix… » pendant que le PDF affichait « valable jusqu'au X ».
# Deux voix contradictoires sur le même dossier.
#
# Règle #4 respectée : on ne touche PAS au moteur de rendu — on lit la MÊME
# règle, par la surface de lecture de ventes.

def _date_validite_comme_le_pdf(devis):
    """La date de validité que le PDF affiche, ou ``None``.

    ``None`` fait OMETTRE la phrase (MRY13) — c'est le comportement voulu
    quand la date est indéterminable : jamais un blanc, jamais une date
    inventée. Le chemin ``devis=None`` (TREADMILL-1538) reste couvert par
    CAD55.
    """
    if devis is None:
        return None
    try:
        from apps.ventes.selectors import date_validite_effective
        return date_validite_effective(devis)
    except Exception:  # noqa: BLE001 — jamais bloquant, jamais inventé
        logger.warning(
            'CAD59 : validité illisible (devis #%s)',
            getattr(devis, 'pk', '?'), exc_info=True)
        return getattr(devis, 'date_validite', None)


# ── CAD-E ── CAD58 — plus aucune touche de cadence n'est une VISITE ────────
#
# [TRANCHÉ 21/09/2026] Le barreau 5 de la cadence générique portait le canal
# `visite` à J+35 sans poser AUCUNE condition de devis, alors que la décision
# fondateur du 15/09 est « visite technique JAMAIS avant le devis, proposée
# après ». Le gabarit par défaut a changé (J+35 = appel), mais une société
# seedée AVANT cette date garde sa ligne en base : `seed_cadence` ne retouche
# jamais un barreau existant (et c'est une bonne règle — le fondateur peut
# personnaliser). On normalise donc à la MATÉRIALISATION, là où la touche
# devient réelle : un gabarit legacy `visite` pose un APPEL.
#
# Ni le nombre, ni l'ordre, ni le J+N des barreaux ne changent : seul le canal
# du dernier. La visite technique garde son chemin propre (proposition après
# devis, VISITE-CADENCE du 15/09) — ce n'est pas un barreau de protocole.


# ── CAD-J ── CAD124 — pas d'axe segment dans le gabarit de cadence ────────
#
# [TRANCHÉ 21/09/2026] `calculer_echeances_cadence` ne lit AUCUN segment, et
# ce n'est pas un oubli : le gabarit de cadence reste aveugle au
# `type_installation`. Le CRM s'en sert ailleurs — pour scorer
# (`apps/crm/scoring.py`) et pour exiger les bons champs au devis
# (`apps/ventes/devis_auto.py`) — mais l'ordonnancement des touches, lui, est
# le MÊME protocole pour tout le monde.
#
# Ce que les segments changent vraiment, c'est le TEXTE : variantes par
# exception sur les clés qui mentent (CAD126) et playbook conditionné sur
# `{type_installation}` (CAD125). Les deux passent par des mécanismes qui
# existent déjà — zéro migration, zéro sélecteur de plus, zéro barreau ajouté.
#
# La décision se rouvrira sur le VOLUME par segment (comptage CADM7), pas
# avant. Voir aussi le commentaire jumeau dans
# `apps/parametres/models_relance.py` (clé `unique_together` du gabarit).

#: CAD124 — la trace lisible de la décision, pour un futur audit qui se
#: demanderait pourquoi le gabarit ignore le segment.
CAD124_PAS_D_AXE_SEGMENT = (
    'pas d’axe segment dans le gabarit de cadence — décision du 21/09/2026'
)


# ── CAD-J ── CAD125 — le dossier 82-21 et le dossier FDA ont une parole ────
#
# `Lead.regularisation_8221` est capté, LU par le scoring (+5 points) — et par
# aucune logique de message ni de touche ; aucune des clés de relance ne
# parlait d'une subvention ou d'un dossier institutionnel, alors que le
# résidentiel a son équivalent avec `j6_garanties`.
#
# Le remède n'ajoute NI barreau NI migration de cadence : c'est une TÂCHE de
# `Playbook`, conditionnée sur `{type_installation}` — le mécanisme existe et
# est déjà évalué contre ce contexte (`_playbook_correspond_au_lead`).
#
# Contexte daté (pour la docstring, jamais pour le client) : le décret
# d'application de la loi 82-21 est en vigueur depuis le 09/06/2026 (BO 7489).
# GARDE-FOU « zéro chiffre inventé » : les TEXTES ne citent AUCUN montant,
# AUCUN plafond, AUCUNE fenêtre de dépôt (le plafond FDA et la fenêtre du
# round 2 sont introuvables sur leur source), AUCUN nombre de régimes.

#: Les deux playbooks de segment, avec leur condition et leur tâche unique.
#: `stage` vient de STAGES.py (règle #2), jamais d'un littéral.
PLAYBOOKS_SEGMENT_CAD125 = (
    {
        # Le NOM reste la clé d'idempotence du seed (jamais renommé : un
        # nouveau nom doublerait le playbook des sociétés existantes).
        'nom': 'Segment — dossier d’autoproduction 82-21',
        'segments': ('industriel', 'commercial'),
        # CIQ517 (D-CIQ-6) — seulement un site MT (contrat CIQ1), une
        # régularisation 82-21 ou un client qui veut revendre : AU MOINS UN
        # de ces critères. Un commerce en BT ne reçoit plus la question
        # (Q9/CAD163 : on n'aborde jamais la loi 82-21 spontanément).
        'criteres_un_parmi': (
            ('tension_raccordement', 'mt'),
            ('regularisation_8221', True),
            ('objectif_projet', 'injection_8221'),
        ),
        'cle_message': 'dossier_8221',
        'tache': ('Demander où en sont le raccordement et les autorisations '
                  'du site (texte « dossier_8221 » au catalogue des '
                  'messages)'),
    },
    {
        'nom': 'Segment — dossier de subvention agricole (FDA)',
        'segments': ('agricole',),
        # AGR525 — réservé à la pompe AU BUTANE : le pilote FDA vise le
        # remplacement du butane (Guide FDA 2024, D-AGR-6). Un exploitant au
        # gasoil ou sur le réseau ne reçoit pas la question.
        'criteres': (('pompe_alim_actuelle', 'butane'),),
        'cle_message': 'dossier_fda',
        'tache': ('Demander où en est le dossier de subvention agricole FDA '
                  '(texte « dossier_fda » au catalogue des messages)'),
    },
)


def _condition_playbook_segment(entree):
    """La condition `core.rules` d'un playbook de segment : ses segments, ET
    ses critères supplémentaires (AGR525, tous requis) ou alternatifs
    (CIQ517, ``criteres_un_parmi`` : au moins un) quand il en porte."""
    criteres = entree.get('criteres') or ()
    un_parmi = entree.get('criteres_un_parmi') or ()
    if not (criteres or un_parmi):
        return _condition_segment(entree['segments'])
    if un_parmi:
        return {
            'op': 'and',
            'conditions': [
                _condition_segment(entree['segments']),
                {'op': 'or', 'conditions': [
                    {'field': champ, 'operator': 'eq', 'value': valeur}
                    for champ, valeur in un_parmi]},
            ],
        }
    feuilles = [
        {'field': 'type_installation', 'operator': 'eq', 'value': segment}
        for segment in entree['segments']]
    segment = (feuilles[0] if len(feuilles) == 1
               else {'op': 'or', 'conditions': feuilles})
    return {
        'op': 'and',
        'conditions': [segment] + [
            {'field': champ, 'operator': 'eq', 'value': valeur}
            for champ, valeur in criteres],
    }


def _lead_satisfait_criteres(lead, entree):
    un_parmi = entree.get('criteres_un_parmi') or ()
    if un_parmi and not any(getattr(lead, champ, None) == valeur
                            for champ, valeur in un_parmi):
        return False
    return all(getattr(lead, champ, None) == valeur
               for champ, valeur in (entree.get('criteres') or ()))


def _condition_segment(segments):
    """L'arbre `core.rules` qui matche ces `type_installation` — et eux seuls.

    Un lead sans segment renseigné ne matche AUCUN des deux : on ne pose pas
    la question du dossier 82-21 à quelqu'un dont on ignore le marché.
    """
    return {
        'op': 'or',
        'conditions': [
            {'field': 'type_installation', 'operator': 'eq', 'value': segment}
            for segment in segments
        ],
    }


def seed_playbooks_segment(company, *, stage=None):
    """CAD125 — pose (idempotemment) les deux playbooks de segment.

    ``stage`` est l'étape du funnel qui porte la tâche ; par défaut celle de
    la prise de contact (``stages.CONTACTED``), importée de STAGES.py. Renvoie
    la liste des ``Playbook`` concernés (créés ou déjà présents).

    Additif et rejouable : ``get_or_create`` sur (société, nom), puis sur
    l'étape et la tâche. Un playbook que le fondateur aurait désactivé ou
    personnalisé n'est JAMAIS réécrit.
    """
    from . import stages as _stages
    from .models import Playbook, PlaybookEtape, PlaybookTache

    cible = stage or _stages.CONTACTED
    resultats = []
    for entree in PLAYBOOKS_SEGMENT_CAD125:
        playbook, cree = Playbook.objects.get_or_create(
            company=company, nom=entree['nom'],
            defaults={'actif': True,
                      'condition': _condition_playbook_segment(entree)})
        resultats.append(playbook)
        if not cree:
            continue
        etape, _ = PlaybookEtape.objects.get_or_create(
            playbook=playbook, stage=cible, defaults={'ordre': 0})
        PlaybookTache.objects.get_or_create(
            etape=etape, libelle=entree['tache'],
            defaults={'obligatoire': False, 'ordre': 0})
    return resultats


def cle_message_segment(lead):
    """La clé de message institutionnelle de CE lead, ou ``None``.

    Lecture pure : sert à l'écran qui propose le texte à copier, et au test.
    Un lead résidentiel — ou sans segment — n'en a AUCUNE : il a déjà
    `j6_garanties`, et on n'invente pas un dossier institutionnel pour lui.
    """
    segment = (getattr(lead, 'type_installation', None) or '').strip()
    if not segment:
        return None
    for entree in PLAYBOOKS_SEGMENT_CAD125:
        if segment in entree['segments']:
            # AGR525 — `dossier_fda` pour un agricole AU BUTANE seulement.
            if not _lead_satisfait_criteres(lead, entree):
                return None
            return entree['cle_message']
    return None


def _corps_pour_segment(corps, cle, lead, langue):
    """Le corps adapté au segment du lead — ou le corps reçu, inchangé.

    Trois garde-fous, dans cet ordre :

      * seuls le FRANÇAIS et la DARIJA ont des variantes (AGR511, D-AGR-11 :
        darija du pompage écrite phrase par phrase du FR validé, jamais une
        traduction automatique) ; ``en``/``ar`` restent inchangés ;
      * un texte que la société a PERSONNALISÉ n'est jamais remplacé — la
        variante ne s'applique qu'au texte encore au catalogue d'origine DE
        CETTE LANGUE (``MESSAGE_TEMPLATE_DEFAULTS`` en FR,
        ``MESSAGE_TEMPLATE_DEFAULTS_DARIJA`` en darija), même règle que
        `_REVEIL_CLES_SEEDEES` ;
      * un segment absent, inconnu ou résidentiel ne change RIEN.

    Best-effort : en cas de lecture impossible, le corps d'origine part.
    """
    langue = (langue or 'fr')
    if not corps or not cle or langue not in ('fr', 'darija'):
        return corps
    try:
        from apps.parametres.models_messages import (
            MESSAGE_TEMPLATE_DEFAULTS, MESSAGE_TEMPLATE_DEFAULTS_DARIJA,
            variante_segment,
        )
        variante = variante_segment(
            cle, getattr(lead, 'type_installation', None), langue)
        if not variante:
            return corps
        defauts = (MESSAGE_TEMPLATE_DEFAULTS if langue == 'fr'
                   else MESSAGE_TEMPLATE_DEFAULTS_DARIJA)
        if corps.strip() != (defauts.get(cle, '') or '').strip():
            return corps
        return variante
    except Exception:  # noqa: BLE001 — jamais bloquant
        logger.warning(
            'CAD126 : variante de segment illisible (clé %s)', cle,
            exc_info=True)
        return corps


# ── CAD-J ── CAD127 — le premier message dit la VÉRITÉ sur l'origine ──────
#
# « Vous venez de remplir notre formulaire » est FAUX pour la moitié des
# origines : la même cadence part pour un lead arrivé par téléphone, en
# boutique, par recommandation, depuis un salon, repositionné par l'écran de
# placement, ou né d'une conversation entrante (CTWA, livechat). Une première
# phrase fausse est exactement ce qui fait perdre la confiance au premier
# contact.
#
# `unique_together (company, cle)` interdit toute VARIANTE sur `identite` :
# les quatre textes sont donc des clés ADDITIVES, choisies ici d'après le
# canal DÉJÀ enregistré. Aucun barreau ajouté, aucune migration.
#
# Correction du round 2 : le ticket SAV n'est PAS une origine —
# `create_lead_depuis_ticket` ne démarre aucune cadence (vérifié sur les 8
# appelants de `demarrer_cadence_contact`).


def _nom_prescripteur(lead):
    """Le nom de la personne qui a recommandé ce lead, ou ``''``.

    Lu sur le parrainage enregistré (``crm.Parrainage.parrain``) — jamais un
    prénom codé en dur (règle fondateur du 08/09). Absent ⇒ chaîne vide ⇒ la
    phrase qui le porte est OMISE (MRY13), jamais un crochet envoyé.

    CAD164 — à défaut de parrainage, le LOCATAIRE qui a donné les coordonnées
    de son propriétaire : la note de lien (``PREFIXE_LIEN_LOCATAIRE``) porte
    l'id de sa fiche, et c'est son PRÉNOM (à défaut son nom) qui est rendu.
    """
    try:
        from .models import Parrainage
        lien = (Parrainage.objects
                .filter(company=lead.company, filleul_lead=lead)
                .select_related('parrain')
                .order_by('-date_creation', '-id').first())
    except Exception:  # noqa: BLE001 — jamais bloquant, jamais inventé
        logger.warning('CAD127 : prescripteur illisible (lead #%s)',
                       getattr(lead, 'pk', '?'), exc_info=True)
        return ''
    if lien is not None and lien.parrain is not None:
        return (getattr(lien.parrain, 'nom', '') or '').strip()
    return _prenom_du_locataire_prescripteur(lead)


def _prenom_du_locataire_prescripteur(lead):
    """CAD164 — le prénom (à défaut le nom) du locataire qui a recommandé ce
    propriétaire, lu sur la note de lien ; ``''`` sinon. Bornée à la SOCIÉTÉ
    du lead. Ne lève jamais."""
    try:
        note = (LeadActivity.objects
                .filter(company=lead.company, lead=lead,
                        kind=LeadActivity.Kind.NOTE,
                        body__startswith=PREFIXE_LIEN_LOCATAIRE)
                .order_by('-created_at', '-pk')
                .values_list('body', flat=True).first())
        if not note:
            return ''
        brut = note[len(PREFIXE_LIEN_LOCATAIRE):].split(' ', 1)[0]
        if not brut.isdigit():
            return ''
        locataire = Lead.objects.filter(
            company=lead.company, pk=int(brut)).first()
    except Exception:  # noqa: BLE001 — jamais bloquant, jamais inventé
        logger.warning('CAD164 : locataire prescripteur illisible (lead #%s)',
                       getattr(lead, 'pk', '?'), exc_info=True)
        return ''
    if locataire is None:
        return ''
    return ((locataire.prenom or '').strip()
            or (locataire.nom or '').strip())


def _mois_dossier_francais(lead):
    """« mars 2026 » — le mois où ce prospect nous avait consultés.

    Dérivé de la date de création de SA fiche : une date réelle et traçable,
    jamais une estimation. Fiche sans date ⇒ chaîne vide ⇒ phrase omise.
    """
    from . import horaires

    quand = getattr(lead, 'date_creation', None)
    if not quand:
        return ''
    locale = quand.astimezone(horaires.CASABLANCA)
    return f'{_MOIS_FR[locale.month - 1]} {locale.year}'


def cle_identite_pour_lead(lead, cle_gabarit, *, reference=None):
    """La clé de message à RENDRE pour cette touche — souvent ``cle_gabarit``.

    Ne change QUE la touche d'identité (`identite`) : toutes les autres clés
    passent inchangées, y compris une clé personnalisée par la société.

    Ordre de décision :

      1. une fiche OUVERTE UN MOIS ANTÉRIEUR à la touche n'est pas une
         demande fraîche — c'est un dossier repris (repositionnement,
         réactivation) : `identite_ancien_dossier`. Aucun seuil inventé, on
         compare des MOIS calendaires, ce que le texte dit littéralement ;
      2. sinon, le canal d'origine enregistré décide
         (`CLE_IDENTITE_PAR_CANAL`) ;
      3. sinon `identite` reste : `site_web` et `meta_ads` sont de VRAIS
         formulaires, la phrase d'origine y est exacte.
    """
    if cle_gabarit != 'identite':
        return cle_gabarit
    try:
        from apps.parametres.models_messages import CLE_IDENTITE_PAR_CANAL
    except Exception:  # noqa: BLE001 — jamais bloquant
        return cle_gabarit

    ouverture = getattr(lead, 'date_creation', None)
    if ouverture is not None and reference is not None:
        from . import horaires
        locale = ouverture.astimezone(horaires.CASABLANCA).date()
        if (locale.year, locale.month) < (reference.year, reference.month):
            return 'identite_ancien_dossier'

    canal = (getattr(lead, 'canal', None) or '').strip()
    return CLE_IDENTITE_PAR_CANAL.get(canal, cle_gabarit)


#: L'étiquette posée par cette réponse (seedée par ``views.seed_tags``).
TAG_ATTENTE_ACCORD = 'Attend un accord (DPA / banque)'

#: CIQ508 (D-CIQ, 06/10/2026) — la RAISON de l'attente, liste FERMÉE du contrat
#: CIQ10 (``relance_etape_v2.json``, ``ajout_ciq10_raison_attente``) :
#: ``(valeur, libellé affiché, étiquette posée)``. ``administration`` pose
#: l'étiquette d'AGR520, inchangée ; les autres, une étiquette par RAISON
#: (seedée par ``views.seed_tags``). Aucune étape de ``STAGES.py`` : l'attente
#: ne change jamais l'étape du dossier.
RAISONS_ATTENTE = (
    ('direction', 'La direction / le comité',
     'Attend la direction / le comité'),
    ('financement', "La banque / l'organisme de financement",
     "Attend la banque / l'organisme de financement"),
    ('bailleur_murs', 'Le bailleur des murs', 'Attend le bailleur des murs'),
    ('budget_exercice', "Le budget de l'exercice suivant",
     "Budget de l'exercice suivant"),
    ('consultation', 'Une consultation en cours', 'Consultation en cours'),
    ('administration', "L'administration (DPA, dossier FDA)",
     TAG_ATTENTE_ACCORD),
)
ETIQUETTES_RAISON_ATTENTE = tuple(r[2] for r in RAISONS_ATTENTE)


#: Le préfixe de la note posée sur la fiche du PROPRIÉTAIRE : il porte l'id de
#: la fiche du locataire, et c'est lui que `_nom_prescripteur` relit. Source
#: unique (même discipline que les préfixes RLC2).
PREFIXE_LIEN_LOCATAIRE = 'Recommandé par le locataire — fiche #'
