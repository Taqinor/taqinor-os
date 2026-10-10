"""Signaux client et touches de rappel (SPL17, extrait de crm/services.py : déplacement pur).

Module de type (a) de la scission : il n'importe ni ``.services`` ni un
module racine ; ``services`` réexporte ce qu'il faut (façade).
"""
import datetime
import logging

from django.utils import timezone

from . import activity, stages
from .cadence_config import CLE_DEVIS, q_etape
from .cadence_filet import _poser_etape_de_filet
from .cadence_plan import (
    _prochaine_touche_a_faire,
    _recaler_file,
    deplacer_echeance_etape,
    reporter_prochaine_touche,
)
from .cadence_reperes import q_etape_moteur, q_visite
from .leads_consentement import _ecrire_registre_contact
from .leads_notifications import _build_lead_wa_reply_url
from .leads_socle import lead_notification_recipients
from .models import Lead, LeadActivity, RelanceEtape
from .visites import avec_direction

logger = logging.getLogger(__name__)


def noter_version_remplacee_ouverte(devis_reference: str, lead, *,
                                    remplacee_par: str = '') -> bool:
    """ACRM11 (C-ACRM-006, volet signaux) — le client a ouvert le lien d'une
    version REMPLACÉE par une révision : UNE note système au chatter du lead
    (« ancienne version <V1> (remplacée par <V2>) ouverte »), et RIEN
    d'autre — ni touche « Proposition rouverte — appeler », ni report de la
    prochaine touche, ni recalcul de score, ni notification : la relance
    porte sur la version en vigueur. Idempotente (une seule note par
    version remplacée, quel que soit le nombre d'ouvertures). Renvoie
    ``True`` si la note vient d'être écrite. Best-effort côté appelant."""
    if lead is None or getattr(lead, 'company_id', None) is None:
        return False
    corps = f'Ancienne version {devis_reference}'
    if remplacee_par:
        corps += f' (remplacée par {remplacee_par})'
    corps += ' ouverte par le client — la relance porte sur la version en ' \
             'vigueur.'
    if LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.NOTE, body=corps).exists():
        return False
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE, body=corps)
    return True


def notifier_signal_lecture(devis_reference: str, lead, *, friction_section='',
                            resume='', remplacee_par=None) -> None:
    """CAD135 — « il relit le prix » / « il lit en détail » arrivent au lead.

    ``friction_section`` non vide ⇒ signal de FRICTION (relecture répétée
    d'une section, le libellé FR est fourni par l'appelant) ; sinon ⇒ lecture
    APPROFONDIE. ``resume`` est le détail déjà composé côté document, repris
    tel quel — ce module n'invente aucun chiffre de temps passé.

    Écrit une note SYSTÈME (``user=None`` : ne fait jamais avancer le funnel,
    règle du 07/09/2026) puis notifie par le chemin commun. Best-effort
    intégral : un signal de lecture ne fait jamais retomber une requête
    publique.

    ACRM11 — ``remplacee_par`` (non ``None``) : le signal vient d'une version
    REMPLACÉE ; seule la note « ancienne version » est écrite
    (``noter_version_remplacee_ouverte``), aucune notification.
    """
    if remplacee_par is not None:
        try:
            noter_version_remplacee_ouverte(
                devis_reference, lead, remplacee_par=remplacee_par)
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            logger.warning(
                'ACRM11 : note de version remplacée non écrite (lead #%s)',
                getattr(lead, 'pk', None), exc_info=True)
        return
    try:
        if lead is None or getattr(lead, 'company_id', None) is None:
            return
        if friction_section:
            corps = (f'Le client relit la section « {friction_section} » de '
                     f'la proposition {devis_reference} — un appel peut '
                     'débloquer la décision.')
            titre = f'Devis {devis_reference} — le client relit une section'
        else:
            corps = ('Le client a commencé à lire la proposition '
                     f'{devis_reference} en détail.')
            titre = f'Devis {devis_reference} — lecture en détail'
        if resume:
            corps += f' ({resume})'
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=None,
            kind=LeadActivity.Kind.NOTE, body=corps)
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'CAD135 : note de signal de lecture non écrite (lead #%s)',
            getattr(lead, 'pk', None), exc_info=True)
        return
    try:
        company = getattr(lead, 'company', None)
        recipients = avec_direction(
            lead_notification_recipients(lead), company)
        if not recipients:
            return
        from apps.notifications.services import notify_many
        corps_notif = [corps]
        wa_url = _build_lead_wa_reply_url(lead)
        if wa_url:
            corps_notif.append(f'Appeler / répondre maintenant : {wa_url}')
        notify_many(
            recipients,
            # Aucun type d'événement neuf : le signal emprunte le MÊME chemin
            # que « devis ouvert », dont il est la suite directe.
            'devis_opened',
            titre,
            body='\n'.join(corps_notif),
            link=f'/crm/visiteurs?lead={lead.pk}',
            company=company,
        )
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'CAD135 : notification de signal de lecture échouée (lead #%s)',
            getattr(lead, 'pk', None), exc_info=True)


# ── CAD-K ── CAD136 — le client vient d'agir, et personne n'était prévenu ───
#
# Audit L3 du 21/09/2026. Répondre à une section du questionnaire enrichissait
# le lead, recalculait le score et écrivait une note — sans AUCUNE
# notification ; la photo de facture envoyée depuis le site était attachée
# (avec OCR si la clé est active) sans prévenir personne. Le client vient
# pourtant de passer cinq minutes sur NOTRE formulaire : c'est la meilleure
# fenêtre de la semaine.
#
# CE QUE CE POINT D'ENTRÉE FAIT, ET NE FAIT PAS. Il NOTIFIE, et rien d'autre.
# Les deux GESTES que ces signaux appellent sont posés par leurs appelants,
# chacun par sa mécanique : la touche « Questionnaire complété — appeler »
# par celle de CAD130 (``poser_touche_signal``, plus bas), et la photo de
# facture, qui appelle une tâche de PRODUCTION (« préparer le devis ») et non
# une relance (nuance du round 2), par ``poser_etape_preparer_devis``.

#: Les deux natures de signal, et le geste qu'elles appellent. Le libellé dit
#: au responsable ce qu'il a à faire — jamais un « il s'est passé quelque
#: chose » qu'il faut aller décoder.
SIGNAL_QUESTIONNAIRE = 'questionnaire'
SIGNAL_PHOTO_FACTURE = 'photo_facture'

_SIGNAUX_CLIENT = {
    SIGNAL_QUESTIONNAIRE: (
        'a répondu au questionnaire',
        'Le client vient de remplir NOTRE formulaire : c\'est la meilleure '
        'fenêtre de la semaine pour l\'appeler.'),
    SIGNAL_PHOTO_FACTURE: (
        'a envoyé une photo de sa facture',
        'Tout est là pour PRÉPARER LE DEVIS — ce n\'est pas une relance, '
        'c\'est de la production.'),
}


def notifier_signal_client(lead, signal, *, detail='') -> None:
    """CAD136 — prévient le responsable qu'un client vient d'AGIR.

    ``signal`` ∈ ``SIGNAL_QUESTIONNAIRE`` / ``SIGNAL_PHOTO_FACTURE``. Un
    signal inconnu ne notifie RIEN plutôt qu'un message vide. ``detail``
    précise (la section répondue, par exemple) sans jamais rien inventer.

    Best-effort intégral : ni une réponse de questionnaire ni une photo ne
    peuvent retomber parce que la cloche est en panne.
    """
    libelle = _SIGNAUX_CLIENT.get(signal)
    if libelle is None or lead is None or getattr(
            lead, 'company_id', None) is None:
        return
    quoi, conseil = libelle
    try:
        company = getattr(lead, 'company', None)
        recipients = avec_direction(
            lead_notification_recipients(lead), company)
        if not recipients:
            return
        from apps.notifications.services import notify_many
        nom = (getattr(lead, 'nom', '') or '').strip() or 'Le client'
        corps = [f'{nom} {quoi}.']
        if detail:
            corps.append(detail)
        corps.append(conseil)
        wa_url = _build_lead_wa_reply_url(lead)
        if wa_url:
            corps.append(f'Appeler / répondre maintenant : {wa_url}')
        notify_many(
            recipients,
            # Aucun type d'événement neuf : c'est le même canal que les
            # autres signaux venus du client.
            'devis_opened',
            f'{nom} {quoi}',
            body='\n'.join(corps),
            link=f'/crm/leads/{lead.pk}',
            company=company,
        )
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'CAD136 : notification de signal client échouée (lead #%s, %s)',
            getattr(lead, 'pk', None), signal, exc_info=True)


# ── CAD-K ── CAD130 — un signal du client fait BOUGER la cadence ────────────
#
# Audit L3 du 21/09/2026. Le client rouvre sa proposition trois fois dans la
# soirée : une note, une notification — et la file de Meryem ne bouge pas d'un
# millimètre. L'avance d'étape sur ouverture a été débranchée à juste titre
# (règle fondateur du 07/09 : le FUNNEL ne bouge que sur une réponse
# confirmée), mais rien n'avait pris sa place côté RAPPEL.
#
# DÉCISION DE CONCEPTION (round 2) — ``reporter_prochaine_touche`` DÉCALE une
# touche existante, il n'en fabrique pas une. Un signal, lui, doit PRODUIRE
# une touche visible, nommée par ce qui s'est passé (« Proposition rouverte —
# appeler »). Elle est donc CRÉÉE — une, jamais deux — et elle REMPLACE la
# prochaine touche du plan : si celle-ci tomberait avant elle ou le même
# jour, elle glisse derrière (avec toute sa suite et son ancre, par la
# mécanique existante — décaler, jamais redémarrer, jamais un second plan).
#
# LES CINQ GARDES, toutes vérifiables :
#   1. la touche signal remplace la prochaine touche du plan en la décalant ;
#   2. jamais plus d'un appel et d'un message par jour et par lead (CAD20) ;
#   3. jamais hors fenêtre (``horaires.prochain_creneau_appel``) ;
#   4. jamais sur un lead « ne plus contacter », perdu, archivé ou signé ;
#   5. un délai minimal depuis la dernière touche faite
#      (``cadence_temps.SIGNAL_ECART_MIN``).

#: La nature du signal qui a posé la touche. `SIGNAL_QUESTIONNAIRE` (CAD136)
#: est déclaré plus haut : même vocabulaire que la notification.
SIGNAL_PROPOSITION_ROUVERTE = 'proposition_rouverte'

#: Le libellé de la touche que chaque signal pose. Il dit le GESTE (« appeler »)
#: et sa raison — c'est ce que la file affiche. Sert aussi de clé
#: d'idempotence : une touche signal encore ouverte n'est jamais doublée.
TOUCHES_SIGNAL = {
    SIGNAL_PROPOSITION_ROUVERTE: 'Proposition rouverte — appeler',
    SIGNAL_QUESTIONNAIRE: 'Questionnaire complété — appeler',
}

#: Les touches signal vivent dans la cadence hors protocole déjà utilisée par
#: le dépôt (même choix que le rappel demandé de CAD129) : elles ne sont pas
#: un barreau, et aucune matérialisation réactive ne leur fait naître de suite.
SIGNAL_CADENCE = 'generique'

#: Ce que le moteur a fait, en une phrase, pour le chatter — et pourquoi une
#: touche n'a PAS été posée (lead hors cadence), pour les journaux.
_SIGNAL_RAISONS = {
    SIGNAL_PROPOSITION_ROUVERTE: 'le client a rouvert sa proposition à '
                                 'plusieurs reprises',
    SIGNAL_QUESTIONNAIRE: 'le client vient de répondre au questionnaire',
}


def _libelles_touche_signal():
    """Les touches qui COUVRENT déjà un signal : les touches signal elles-mêmes
    et le rappel que le client a demandé (CAD129) — un client qui attend
    notre appel n'a pas besoin d'une seconde touche pour le même appel."""
    return tuple(TOUCHES_SIGNAL.values()) + (RAPPEL_DEMANDE_LIBELLE,)


def refus_touche_signal(lead):
    """CAD130 — la raison (FR) pour laquelle AUCUNE touche signal ne se pose
    sur ce lead, ou ``''``. Garde 4 : ne plus contacter, perdu, archivé,
    signé — dans cet ordre, la première qui s'applique."""
    if lead is None or getattr(lead, 'company_id', None) is None:
        return 'lead sans société'
    if getattr(lead, 'ne_plus_contacter', False):
        return 'le client a demandé à ne plus être contacté'
    if getattr(lead, 'perdu', False):
        return 'lead perdu'
    if getattr(lead, 'is_archived', False):
        return 'lead archivé'
    if getattr(lead, 'stage', None) == stages.SIGNED:
        return 'lead signé'
    return ''


def _prochaine_touche_du_plan(lead, exclure_libelles):
    """La prochaine touche À FAIRE du PLAN — un barreau de protocole, pas une
    étape posée à la main par le moteur (filet, visite, rappel, signal) :
    celles-là ont leur propre date, décidée pour une autre raison."""
    from django.db.models import F

    return (lead.relance_etapes
            .filter(statut=RelanceEtape.Statut.A_FAIRE)
            .exclude(q_etape_moteur())
            .exclude(libelle__in=tuple(exclure_libelles))
            .order_by(F('due_at').asc(nulls_last=True), 'due_date', 'ordre')
            .first())


def _genre_du_canal(canal):
    """CAD20 — les deux seuls genres que la règle distingue : un MESSAGE
    (WhatsApp / e-mail, ``horaires.est_un_message`` fait autorité) ou un
    APPEL (tout le reste, visite comprise — le plus prudent)."""
    from . import horaires

    return 'message' if horaires.est_un_message(canal) else 'appel'


def _jour_occupe_pour(lead, genre, exclure_pk=None):
    """CAD20 — ``jour_occupe(date_locale)`` pour ce lead et ce GENRE (appel /
    message) : une touche du même genre déjà FAITE ce jour-là, ou encore À
    FAIRE à ce jour-là (la touche du plan qui va glisser exceptée)."""
    from . import horaires

    def _meme_genre(canal):
        return _genre_du_canal(canal) == genre

    def jour_occupe(jour):
        debut = datetime.datetime.combine(
            jour, datetime.time(0, 0), tzinfo=horaires.CASABLANCA)
        fin = debut + datetime.timedelta(days=1)
        a_faire = (lead.relance_etapes
                   .filter(statut=RelanceEtape.Statut.A_FAIRE, due_date=jour))
        faites = (lead.relance_etapes
                  .filter(statut=RelanceEtape.Statut.FAIT,
                          traite_le__gte=debut, traite_le__lt=fin))
        if exclure_pk is not None:
            a_faire = a_faire.exclude(pk=exclure_pk)
        canaux = (list(a_faire.values_list('canal', flat=True))
                  + list(faites.values_list('canal', flat=True)))
        return any(_meme_genre(c) for c in canaux)

    return jour_occupe


def poser_touche_signal(lead, signal, *, user=None, maintenant=None):
    """CAD130 — un SIGNAL du client pose UNE touche « …, appeler » dans la file.

    ``signal`` ∈ ``TOUCHES_SIGNAL`` (proposition rouverte, questionnaire
    complété). Renvoie la touche signal (créée, ou déjà ouverte), ou ``None``
    quand le signal ne pose rien (signal inconnu, garde 4).

    IDEMPOTENTE : une touche signal — ou un rappel demandé par le client —
    encore ouverte couvre déjà le signal ; trois ouvertures de la proposition
    ne font jamais trois touches, ni trois décalages du plan.

    Best-effort intégral : un signal ne fait jamais retomber la requête ou la
    tâche planifiée qui l'observe."""
    from . import cadence_temps, horaires

    libelle = TOUCHES_SIGNAL.get(signal)
    if libelle is None:
        return None
    if getattr(lead, 'pk', None):
        # L'instance de l'appelant peut être périmée (même précaution que
        # `assurer_prochaine_etape_apres_succes`) : la garde 4 lit l'état réel.
        try:
            lead.refresh_from_db(fields=['stage', 'perdu', 'is_archived',
                                         'ne_plus_contacter',
                                         'contact_preference'])
        except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
            logger.warning('CAD130 : lead #%s illisible', lead.pk,
                           exc_info=True)
            return None
    if refus_touche_signal(lead):
        return None
    try:
        # 1. Idempotence : le signal est déjà couvert par une touche ouverte.
        deja = (lead.relance_etapes
                .filter(libelle__in=_libelles_touche_signal(),
                        statut=RelanceEtape.Statut.A_FAIRE)
                .order_by('due_date', 'pk').first())
        if deja is not None:
            return deja

        # 2. Le canal : un appel — sauf pour un client « WhatsApp uniquement »
        #    (CAD32 : sa préférence gagne toujours, on lui écrit).
        canal = RelanceEtape.Canal.APPEL
        if (getattr(lead, 'contact_preference', '')
                == cadence_temps.PREFERENCE_WHATSAPP_ONLY):
            canal = RelanceEtape.Canal.WHATSAPP
        genre = _genre_du_canal(canal)

        # 3. Les dates, par la règle PURE (cadence_temps.echeances_signal).
        instant = maintenant or timezone.now()
        derniere = (lead.relance_etapes
                    .filter(statut=RelanceEtape.Statut.FAIT,
                            traite_le__isnull=False)
                    .order_by('-traite_le').values_list('traite_le',
                                                        flat=True).first())
        plan = _prochaine_touche_du_plan(lead, _libelles_touche_signal())
        echeance, glisse_a = cadence_temps.echeances_signal(
            maintenant=instant, derniere_faite=derniere,
            prochaine=getattr(plan, 'due_at', None),
            jour_occupe=_jour_occupe_pour(
                lead, genre, exclure_pk=getattr(plan, 'pk', None)),
            creneau=lambda dt: horaires.prochain_creneau_appel(
                dt, lead.company, canal=canal),
            lendemain=lambda dt: cadence_temps.lendemain_joignable(
                dt, lead.company, canal))

        # 4. La touche du plan glisse DERRIÈRE la touche signal, avec toute sa
        #    suite et son ancre (mécanique existante, jamais une seconde).
        deplacee = None
        if plan is not None and glisse_a is not None:
            # Les gestes du RENDEZ-VOUS de visite (confirmer la veille,
            # débriefer le lendemain) partagent la cadence du plan mais sont
            # ancrés sur la DATE DE VISITE : le glissement de la suite du plan
            # ne doit jamais les emporter. Ils sont remis à leur date.
            # COCKPIT-CONTRÔLE — un glissement décidé par le MOTEUR : aucun
            # report compté (``compter_report=False``), et les gestes de
            # visite retrouvent AUSSI leur échéance d'origine.
            visites = list(lead.relance_etapes
                           .filter(q_visite(),
                                   statut=RelanceEtape.Statut.A_FAIRE)
                           .values_list('pk', 'due_at', 'due_date',
                                        'due_initial_at'))
            deplacee = reporter_prochaine_touche(
                lead, user, glisse_a, etape=plan, journaliser=False,
                compter_report=False)
            for pk, due_at, due_date, due_initial_at in visites:
                RelanceEtape.objects.filter(pk=pk).update(
                    due_at=due_at, due_date=due_date,
                    due_initial_at=due_initial_at)

        # 5. LA touche signal.
        etape = RelanceEtape.objects.create(
            company=lead.company, lead=lead, cadence=SIGNAL_CADENCE, ordre=0,
            canal=canal, libelle=libelle,
            due_at=echeance,
            due_date=echeance.astimezone(horaires.CASABLANCA).date(),
            note=f'Posée automatiquement : {_SIGNAL_RAISONS[signal]}.')
        _recaler_file(lead, user)

        # 6. UNE note système (``user=None`` : poser une touche n'est pas un
        #    contact, garde QJ7) qui dit ce que le moteur a fait.
        quand = echeance.astimezone(horaires.CASABLANCA)
        corps = (f'Signal client — {_SIGNAL_RAISONS[signal]} : touche « '
                 f'{libelle} » posée pour le {quand:%d/%m/%Y à %H:%M}.')
        if deplacee is not None:
            apres = deplacee.due_at.astimezone(horaires.CASABLANCA)
            nom = (deplacee.libelle or '').strip() \
                or deplacee.get_canal_display()
            corps += (f' La touche du plan « {nom} » glisse au '
                      f'{apres:%d/%m/%Y à %H:%M}, avec sa suite (décaler, '
                      'jamais redémarrer).')
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=None,
            kind=LeadActivity.Kind.NOTE, body=corps)
        return etape
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'CAD130 : touche signal non posée (lead #%s, %s)',
            getattr(lead, 'pk', None), signal, exc_info=True)
        return None


def poser_etape_preparer_devis(lead, *, origine, user=None, jours=None,
                               journaliser=True):
    """CAD136 — une pièce qui permet de CHIFFRER (la photo de la facture) pose
    la tâche de PRODUCTION « Préparer et envoyer le devis (ou fixer un
    rappel) » — jamais une relance (nuance du round 2) : tout est là pour
    faire le devis, c'est ce geste-là qu'il faut dans la file.

    Même étape, même délai que le filet « client joint » et que la pièce reçue
    sur WhatsApp (CAD101) : DEMAIN, au prochain créneau d'appel. Une étape
    « préparer le devis » déjà ouverte n'est ni doublée ni DÉPLACÉE (elle a
    peut-être été datée à la main). Garde 4 de CAD130 : rien sur un lead ne
    plus contacter, perdu, archivé ou signé. Best-effort : ne lève jamais.
    Renvoie l'étape (posée ou déjà ouverte), ou ``None``.

    Retour de visite SANS devis (décision fondateur du 24/09/2026) — deux
    réglages, et rien d'autre :

    * ``jours`` : le délai quand le terrain a convenu d'un moment DEVANT le
      client (« cette semaine » = trois jours, ``_plan_du_debrief``) ; par
      défaut (``None``), celui du barreau ``devis`` de la société
      (Paramètres, PARAM-CADENCE — demain par défaut) ;
    * ``journaliser=False`` : l'appelant écrit lui-même la suite dans SA note
      (la note du retour terrain), jamais une seconde ligne de chatter."""
    from . import horaires

    if getattr(lead, 'pk', None) is None or refus_touche_signal(lead):
        return None
    try:
        ouverte = (lead.relance_etapes
                   .filter(q_etape(CLE_DEVIS),
                           statut=RelanceEtape.Statut.A_FAIRE)
                   .order_by('due_date', 'pk').first())
        if ouverte is not None:
            return ouverte
        etape = _poser_etape_de_filet(
            lead, cle=CLE_DEVIS, jours=jours, note=f'Posée : {origine}.')
        _recaler_file(lead, user)
        if not journaliser:
            return etape
        quand = etape.due_at.astimezone(horaires.CASABLANCA)
        # Note SYSTÈME (``user=None``) : poser une tâche n'est pas un contact.
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=None,
            kind=LeadActivity.Kind.NOTE,
            body=(f'{origine[:1].upper()}{origine[1:]} : étape « '
                  f'{etape.libelle} » posée pour le '
                  f'{quand:%d/%m/%Y à %H:%M} — tâche de production, pas une '
                  'relance.'))
        return etape
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'CAD136 : étape « préparer le devis » non posée (lead #%s)',
            getattr(lead, 'pk', None), exc_info=True)
        return None


def poser_touche_signal_du_lead_id(lead_id, signal, *, company):
    """CAD130 — variante par ID pour les autres apps (``ventes`` ne tient que
    ``devis.lead_id`` et n'importe jamais les modèles du CRM). La société est
    TOUJOURS celle de l'appelant (le devis), jamais déduite du lead seul.
    Ne lève jamais."""
    if not lead_id or company is None:
        return None
    try:
        lead = Lead.objects.filter(pk=lead_id, company=company).first()
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning('CAD130 : lead #%s illisible', lead_id, exc_info=True)
        return None
    if lead is None:
        return None
    return poser_touche_signal(lead, signal)


#: QW5 — libellés FR par canal de contact proposition (WJ85/WJ54 — le site
#: envoie 'rappel'/'whatsapp'/'question'/'voice'/'revision', un vocabulaire
#: plus large que ce que ce module connaissait (whatsapp/rappel seuls).
_CONTACT_CANAL_LABELS = {
    'whatsapp': 'par WhatsApp',
    'rappel': 'par téléphone (rappel)',
    'question': 'question avant signature',
    'voice': 'orienté vers une note vocale WhatsApp',
    'revision': 'demande de modification',
}

#: QW5 — libellés FR par type de modification demandée (WJ54, uniquement
#: pertinent quand canal == 'revision').
_REVISION_KIND_LABELS = {
    'kwc': 'ajuster la puissance (kWc)',
    'batterie': 'changer l’option batterie',
    'autre': 'autre modification',
}


def notify_client_contact_request(devis_reference: str, lead,
                                  canal='', message='', revision_kind='') -> None:
    """QJ27/QW5 — Le CLIENT demande à être contacté (proposition publique).

    Consigne la demande dans le chatter du lead (note SYSTÈME, user=None — ne
    fait donc jamais avancer le funnel QJ7) ET notifie le responsable du lead
    ET son supérieur (repli managers société quand l'un des deux manque), avec
    un lien wa.me « répondre maintenant ». Best-effort — jamais d'exception
    propagée. La société vient TOUJOURS du lead (jamais d'un corps de requête).

    QW5 — ``revision_kind`` (WJ54, uniquement quand ``canal == 'revision'``)
    est journalisé dans le chatter et le corps de notification. Le canal
    ``rappel`` sur une demande CLIENT (proposition) est une obligation de
    RAPPEL — même sémantique que QW4 (``contact_preference=phone_ok``) : si le
    lead lié n'a pas encore cette préférence posée, on la pose ici aussi et on
    déclenche la même notification distincte + SLA rappel (jamais dupliquée —
    ``notify_lead_callback_requested`` est déjà idempotent par lead)."""
    try:
        canal_key = (canal or '').strip()
        canal_label = _CONTACT_CANAL_LABELS.get(canal_key, '')
        nom = (getattr(lead, 'nom', '') or '').strip() or 'Le client'
        # Note chatter (toujours, même sans destinataire notifiable).
        note = f'Le client demande à être contacté ({devis_reference})'
        if canal_label:
            note += f' — {canal_label}'
        if canal_key == 'revision' and revision_kind:
            note += f' [{_REVISION_KIND_LABELS.get(revision_kind, revision_kind)}]'
        if message:
            note += f' : « {message[:2000]} »'
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=None,
            kind=LeadActivity.Kind.NOTE, body=note)

        # ACRM63 (D-ACRM-5 (3)=(a)) — la personne « ne plus contacter » qui
        # demande ELLE-MÊME un rappel lève son opposition (note datée +
        # registre), AVANT de poser la touche.
        if canal_key == 'rappel':
            _lever_opposition_a_la_demande_du_client(lead)

        # QW5/QW4 — un rappel demandé DEPUIS LA PROPOSITION est la même
        # obligation qu'un rappel demandé à la capture : pose la préférence si
        # absente et route vers la notification distincte + SLA rappel.
        if canal_key == 'rappel' and getattr(lead, 'contact_preference', None) != Lead.ContactPreference.PHONE_OK:
            lead.contact_preference = Lead.ContactPreference.PHONE_OK
            # QX15 — même horodatage dédié que le webhook : le SLA rappel
            # mesure depuis la POSE de la préférence, pas depuis la création
            # du lead (un vieux lead qui demande un rappel MAINTENANT ne doit
            # pas être instantanément « SLA rompu »).
            lead.contact_preference_set_at = timezone.now()
            lead.save(update_fields=[
                'contact_preference', 'contact_preference_set_at'])
        if canal_key == 'rappel':
            notify_lead_callback_requested(lead)
            # CAD129 — la demande entre dans la FILE, pas seulement dans la
            # cloche : une notification noyée faisait disparaître la demande
            # la plus forte qu'un prospect puisse faire.
            poser_touche_rappel_demande(lead, user=None)

        recipients = lead_notification_recipients(lead)
        if not recipients:
            return
        from apps.notifications.services import notify_many
        wa_url = _build_lead_wa_reply_url(lead)
        body_parts = [
            f'{nom} demande à être contacté au sujet du devis '
            f'{devis_reference}'
            + (f' ({canal_label})' if canal_label else '') + '.']
        if canal_key == 'revision' and revision_kind:
            body_parts.append(
                f'Type de modification : {_REVISION_KIND_LABELS.get(revision_kind, revision_kind)}')
        if message:
            body_parts.append(f'Message : « {message[:2000]} »')
        if wa_url:
            body_parts.append(f'Répondre maintenant : {wa_url}')
        notify_many(
            recipients,
            'client_contact_request',
            f'Le client demande à être contacté — {devis_reference}',
            body='\n'.join(body_parts),
            link=f'/crm/leads?lead={lead.pk}',
            company=lead.company,
        )
    except Exception as exc:  # noqa: BLE001 — best-effort
        import logging
        logging.getLogger(__name__).warning(
            'QJ27: notify_client_contact_request échoué pour lead #%s '
            'devis %s : %s', getattr(lead, 'pk', '?'), devis_reference, exc)


#: ACRM63 — source de registre et libellé de chatter d'une opposition levée
#: PAR la personne elle-même (demande de rappel depuis sa proposition).
CONSENT_SOURCE_OPPOSITION_LEVEE_CLIENT = (
    'opposition levée à la demande du client (rappel demandé)')
NOTE_OPPOSITION_LEVEE_CLIENT = 'opposition levée à la demande du client'


def _lever_opposition_a_la_demande_du_client(lead) -> bool:
    """ACRM63 — D-ACRM-5 (3)=(a) : un lead ``ne_plus_contacter`` dont la
    personne demande elle-même un rappel passe à ``False``, avec une note de
    chatter datée « opposition levée à la demande du client » et les lignes
    ``ConsentRecord`` accordées (réutilise ``tracer_levee_opposition_registre``
    via ``_ecrire_registre_contact`` — aucune seconde écriture du registre).
    Un lead non opposé : rien. Renvoie ``True`` si l'opposition a été levée."""
    if lead is None or not getattr(lead, 'ne_plus_contacter', False):
        return False
    maintenant = timezone.now()
    lead.ne_plus_contacter = False
    lead.save(update_fields=['ne_plus_contacter'])
    LeadActivity.objects.create(
        company=lead.company, lead=lead, user=None,
        kind=LeadActivity.Kind.NOTE,
        body=(f'{NOTE_OPPOSITION_LEVEE_CLIENT} '
              f'({timezone.localtime(maintenant):%d/%m/%Y %H:%M})'))
    _ecrire_registre_contact(
        lead, granted=True, source=CONSENT_SOURCE_OPPOSITION_LEVEE_CLIENT,
        occurred_at=maintenant)
    return True


#: QW4 — marqueur de note système : posé UNE FOIS par lead pour éviter de
#: notifier plusieurs fois la même demande de rappel (idempotence, même
#: patron que ``ESCALATION_MARKER`` de ``recycler_leads_non_travailles``).
CALLBACK_REQUESTED_MARKER = 'auto — rappel demandé (contact_preference=phone_ok)'


def notify_lead_callback_requested(lead) -> None:
    """QW4 — Notification DISTINCTE, urgence plus élevée, quand un lead arrive
    avec ``contact_preference=phone_ok`` (« rappel demandé »), différente du
    générique ``notify_new_lead`` (réponse WhatsApp). Notifie owner + supérieur
    (repli managers société). Idempotent par lead — jamais renotifié deux fois
    pour la même demande (marqueur chatter). Best-effort — jamais d'exception
    propagée."""
    try:
        if getattr(lead, 'contact_preference', None) != Lead.ContactPreference.PHONE_OK:
            return
        already = LeadActivity.objects.filter(
            lead=lead, kind=LeadActivity.Kind.NOTE,
            body__startswith=CALLBACK_REQUESTED_MARKER,
        ).exists()
        if already:
            return
        LeadActivity.objects.create(
            company=lead.company, lead=lead, user=None,
            kind=LeadActivity.Kind.NOTE,
            body=f'{CALLBACK_REQUESTED_MARKER}.',
        )
        recipients = lead_notification_recipients(lead)
        if not recipients:
            return
        from apps.notifications.services import notify_many
        nom = (getattr(lead, 'nom', '') or '').strip() or 'Un prospect'
        body_parts = [f'{nom} a demandé un RAPPEL téléphonique (pas une réponse WhatsApp).']
        tel = (getattr(lead, 'telephone', '') or '').strip()
        if tel:
            body_parts.append(f'Numéro à rappeler : {tel}')
        notify_many(
            recipients,
            'lead_callback_requested',
            f'☎ Rappeler {nom} — rappel demandé',
            body='\n'.join(body_parts),
            link=f'/crm/leads?lead={lead.pk}',
            company=lead.company,
        )
    except Exception as exc:  # noqa: BLE001 — best-effort
        import logging
        logging.getLogger(__name__).warning(
            'QW4: notify_lead_callback_requested échoué pour lead #%s : %s',
            getattr(lead, 'pk', '?'), exc)


#: Libellé de la touche « rappel demandé ». Sert aussi de clé d'idempotence :
#: deux clics du même client ne laissent jamais deux lignes dans la file.
RAPPEL_DEMANDE_LIBELLE = 'Rappeler le client (il l’a demandé)'

#: Cadence des touches hors protocole déjà utilisée par le dépôt.
RAPPEL_DEMANDE_CADENCE = 'generique'


def _touche_rappel_demande_ouverte(lead):
    """La touche « rappel demandé » encore À FAIRE sur ce lead, ou ``None``."""
    return (lead.relance_etapes
            .filter(libelle=RAPPEL_DEMANDE_LIBELLE,
                    statut=RelanceEtape.Statut.A_FAIRE)
            .order_by('due_date', 'pk')
            .first())


def poser_touche_rappel_demande(lead, *, user=None, quand=None):
    """CAD129 — un rappel demandé devient une TOUCHE datée, pas une notification.

    ``quand`` (instant ou date) par défaut = maintenant ; l'échéance réelle est
    toujours recalée sur le prochain créneau d'APPEL de la société — un rappel
    promis à 23 h ne rend service à personne.

    Renvoie la touche (déplacée ou créée), ou ``None`` si le lead n'a pas de
    société. Best-effort intégral : une demande client n'est JAMAIS perdue
    parce que la file n'a pas pu être écrite — l'appelant a déjà consigné la
    note et notifié le responsable.
    """
    from . import horaires

    if lead is None or getattr(lead, 'company_id', None) is None:
        return None
    try:
        instant = quand or timezone.now()
        if not isinstance(instant, datetime.datetime):
            instant = datetime.datetime.combine(
                instant, datetime.time(0, 0), tzinfo=horaires.CASABLANCA)
        elif timezone.is_naive(instant):
            instant = timezone.make_aware(instant, datetime.timezone.utc)
        echeance = horaires.prochain_creneau_appel(
            instant, lead.company, canal=RelanceEtape.Canal.APPEL)

        # 1. Une touche « rappel demandé » déjà ouverte est DÉPLACÉE, jamais
        #    dupliquée : deux clics ne font pas deux lignes dans la file.
        #    COCKPIT-CONTRÔLE : une demande du CLIENT, jamais un report
        #    compté à la commerciale — l'origine suit l'échéance.
        deja = _touche_rappel_demande_ouverte(lead)
        if deja is not None:
            deplacer_echeance_etape(deja, echeance)
            _recaler_file(lead, user)
            return deja

        # 2. Un plan en cours : on le RAMÈNE, avec tout son reste (l'ancre
        #    comprise). C'est « décaler, jamais redémarrer ».
        ouverte = _prochaine_touche_a_faire(lead)
        if ouverte is not None:
            deplacee = reporter_prochaine_touche(
                lead, user, echeance, etape=ouverte, journaliser=False,
                compter_report=False)
            if deplacee is not None:
                # Python 3.11 (prod/CI) refuse une expression MULTI-LIGNE dans
                # une f-string : le libellé est composé AVANT.
                quand_local = echeance.astimezone(horaires.CASABLANCA)
                quand_lisible = quand_local.strftime('%d/%m/%Y à %H:%M')
                activity.log_note(
                    lead, user,
                    'Rappel demandé par le client : la prochaine touche est '
                    f'ramenée au {quand_lisible}, et la suite du plan glisse '
                    'du même écart.')
                return deplacee

        # 3. Plus aucune touche ouverte : UNE touche, jamais un second plan.
        etape = RelanceEtape.objects.create(
            company=lead.company, lead=lead,
            cadence=RAPPEL_DEMANDE_CADENCE, ordre=0,
            canal=RelanceEtape.Canal.APPEL,
            libelle=RAPPEL_DEMANDE_LIBELLE,
            due_at=echeance,
            due_date=echeance.astimezone(horaires.CASABLANCA).date(),
            note='Posée automatiquement : le client a demandé un rappel.')
        _recaler_file(lead, user)
        return etape
    except Exception:  # noqa: BLE001 — best-effort, jamais bloquant
        logger.warning(
            'CAD129 : touche de rappel non posée pour le lead #%s',
            getattr(lead, 'pk', None), exc_info=True)
        return None
