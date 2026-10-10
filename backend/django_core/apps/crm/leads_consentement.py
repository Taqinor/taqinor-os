"""Consentement et registre de contact des leads (SPL6, extrait de crm/services.py : déplacement pur).

Module de type (a) de la scission : il n'importe ni ``.services`` ni un
module racine ; ``services`` réexporte ce qu'il faut (façade).
"""
import logging

from django.utils import timezone

logger = logging.getLogger(__name__)


def enregistrer_consentement_lead(
        lead, *, purpose, granted=True, source='', version_texte='',
        ip_confirmation=None, occurred_at=None):
    """Pose (ou met à jour) le consentement d'un lead pour un canal donné.

    ``purpose`` ∈ 'marketing' / 'email' / 'sms' / 'whatsapp'…
    ``lead.email`` est utilisé comme identifiant si présent, sinon
    ``lead.telephone``. Crée une NOUVELLE entrée à chaque appel (le registre
    ``ConsentRecord`` est un historique append-only, cf. FG394) — la lecture
    de l'état courant prend toujours la ligne la plus récente.

    CRX39 — ``occurred_at`` (additif, défaut ``now()`` : tout appelant existant
    est inchangé) porte l'horodatage RÉEL du consentement quand on le connaît,
    comme le champ le demande explicitement (« sur le consent_timestamp
    existant côté métier »). Sans lui, le registre daterait le consentement du
    moment où l'ERP l'a enregistré, pas de celui où la personne l'a donné —
    une preuve CNDP fausse est pire qu'une preuve absente.
    """
    from core.models import ConsentRecord

    identifiant = (lead.email or lead.telephone or '').strip()
    if not identifiant:
        return None
    return ConsentRecord.objects.create(
        company=lead.company,
        subject_identifier=identifiant,
        purpose=purpose,
        granted=granted,
        source=source or '',
        occurred_at=occurred_at or timezone.now(),
        version_texte=version_texte or '',
        ip_confirmation=ip_confirmation,
    )


#: CRX39 — origine consignée dans ``ConsentRecord.source`` pour l'intake web.
CONSENT_SOURCE_SITE_WEB = 'formulaire site web'


def enregistrer_consentements_intake_web(lead):
    """CRX39 (DRAFT165-57) — trace au REGISTRE le consentement recueilli par le
    formulaire du site, FINALITÉ PAR FINALITÉ.

    Jusqu'ici le consentement du visiteur ne vivait que sur la fiche
    (``Lead.consent_timestamp`` / ``Lead.whatsapp_opt_in``) : le registre
    ``core.ConsentRecord`` — celui qu'une demande CNDP interroge, celui que
    lisent le DSR et les filtres marketing — restait VIDE pour la source de
    leads n°1. Cette fonction est le pont, appelée à la CRÉATION du lead par
    le webhook site.

    Deux finalités, chacune écrite SEULEMENT si la donnée existe (jamais un
    consentement supposé — règle « aucun chiffre/fait inventé ») :
      • ``marketing`` — la case du formulaire, ACCORDÉE, datée du
        ``consentTimestamp`` transmis par le site (pas de l'instant serveur) ;
      • ``whatsapp`` — l'opt-in WhatsApp, accordé OU refusé selon la case
        (``whatsapp_opt_in`` vaut ``None`` quand la question n'a pas été posée
        : on n'écrit alors RIEN, un silence n'est pas un refus).

    ``ip_confirmation`` reste vide À DESSEIN : ce champ est la preuve du clic
    de confirmation d'un DOUBLE opt-in, que le formulaire du site ne pratique
    pas — y verser l'IP de la soumission maquillerait un simple opt-in en
    double opt-in. Idem ``version_texte`` : le site ne transmet aucune version
    de texte de consentement aujourd'hui.

    Renvoie la liste des entrées créées (vide si aucune donnée exploitable).
    Ne lève pas sur un lead sans email ni téléphone (le point d'entrée unique
    ``enregistrer_consentement_lead`` renvoie alors ``None``).
    """
    horodatage = getattr(lead, 'consent_timestamp', None)
    creees = []
    if horodatage:
        entree = enregistrer_consentement_lead(
            lead, purpose='marketing', granted=True,
            source=CONSENT_SOURCE_SITE_WEB, occurred_at=horodatage)
        if entree is not None:
            creees.append(entree)
    opt_in = getattr(lead, 'whatsapp_opt_in', None)
    if opt_in is not None:
        entree = enregistrer_consentement_lead(
            lead, purpose='whatsapp', granted=bool(opt_in),
            source=CONSENT_SOURCE_SITE_WEB, occurred_at=horodatage or None)
        if entree is not None:
            creees.append(entree)
    return creees


#: Finalité inscrite au registre pour la prospection commerciale.
CONSENT_PURPOSE_PROSPECTION = 'marketing'

#: Données NON collectées auprès de la personne (Meta, import, document).
#: Le libellé est court À DESSEIN : ``ConsentRecord.source`` fait 120
#: caractères et porte aussi l'origine — une base légale tronquée ne prouve
#: rien. Le texte complet des deux articles est en tête de cette section.
BASE_LEGALE_NON_COLLECTEE = 'base légale : loi 09-08 art. 5 §3 + décret ' \
                            '2-09-165 art. 34'
#: La personne a elle-même sollicité le contact (appel, message, salon).
BASE_LEGALE_SOLLICITATION = 'base légale : relation précontractuelle à la ' \
                            'demande de la personne (loi 09-08 art. 5)'

CONSENT_SOURCE_SAISIE_MANUELLE = 'saisie manuelle CRM'
CONSENT_SOURCE_META_LEAD_ADS = 'formulaire Meta Lead Ads'
CONSENT_SOURCE_WHATSAPP_ENTRANT = 'message WhatsApp entrant'
CONSENT_SOURCE_DOCUMENT = 'document importé'


def enregistrer_base_legale_lead(lead, *, source, base_legale,
                                 occurred_at=None):
    """Trace au registre la BASE LÉGALE d'un lead créé hors formulaire du site.

    ``granted=False`` : aucune case n'a été cochée par la personne sur ces
    chemins. L'entrée existe pour que le registre ne soit pas MUET sur une
    cohorte entière — une demande CNDP y lit la source ET le fondement
    invoqué. Best-effort intégral : une création de lead ne tombe jamais
    parce que le registre n'a pas pu être écrit.
    """
    try:
        return enregistrer_consentement_lead(
            lead, purpose=CONSENT_PURPOSE_PROSPECTION, granted=False,
            source=f'{source} — {base_legale}'[:120],
            occurred_at=occurred_at)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'CAD90 : base légale non écrite au registre pour le lead #%s',
            getattr(lead, 'pk', None), exc_info=True)
        return None


#: ACRM59 (C-ACRM-044) — les FINALITÉS DE CONTACT du registre : une
#: opposition les refuse TOUTES (la prospection, et chaque canal recueilli à
#: l'intake — WhatsApp —, plus l'e-mail et le SMS que le registre connaît).
#: Aucune finalité nouvelle n'est inventée : ce sont celles que
#: ``enregistrer_consentement_lead`` documente.
FINALITES_CONTACT = (CONSENT_PURPOSE_PROSPECTION, 'whatsapp', 'email', 'sms')

#: ACRM59 — la source d'une opposition LEVÉE depuis la fiche.
CONSENT_SOURCE_OPPOSITION_LEVEE = 'opposition levée par {utilisateur}'


def _identifiants_registre(lead):
    """ACRM59 — CHAQUE identifiant de la personne (e-mail ET téléphone,
    sans doublon) : une opposition lue sous le téléphone doit tenir autant
    que sous l'e-mail."""
    vus = []
    for valeur in (getattr(lead, 'email', None),
                   getattr(lead, 'telephone', None)):
        valeur = (valeur or '').strip()
        if valeur and valeur not in vus:
            vus.append(valeur)
    return vus


def _ecrire_registre_contact(lead, *, granted, source, occurred_at=None):
    """ACRM59 — une ligne par (identifiant, finalité de contact)."""
    from core.models import ConsentRecord

    quand = occurred_at or timezone.now()
    lignes = [
        ConsentRecord(
            company=lead.company, subject_identifier=identifiant,
            purpose=finalite, granted=granted, source=source[:120],
            occurred_at=quand)
        for identifiant in _identifiants_registre(lead)
        for finalite in FINALITES_CONTACT]
    if not lignes:
        return None
    ConsentRecord.objects.bulk_create(lignes)
    return lignes[0]


def tracer_levee_opposition_registre(lead, user, *, occurred_at=None):
    """ACRM59 — décocher « ne plus contacter » sur la fiche inscrit au
    registre une ligne ``granted=True`` par finalité de contact et par
    identifiant, dont la source NOMME l'utilisateur (« opposition levée par
    <utilisateur> »). Best-effort, comme l'opposition."""
    try:
        qui = getattr(user, 'username', '') or 'utilisateur inconnu'
        return _ecrire_registre_contact(
            lead, granted=True,
            source=CONSENT_SOURCE_OPPOSITION_LEVEE.format(utilisateur=qui),
            occurred_at=occurred_at)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'ACRM59 : levée d\'opposition non écrite au registre (lead #%s)',
            getattr(lead, 'pk', None), exc_info=True)
        return None
