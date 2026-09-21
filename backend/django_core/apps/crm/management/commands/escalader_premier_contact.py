"""MRY17 — L'objectif de PREMIER CONTACT est dépassé : escalade immédiate.

La promesse tenue par Meryem est « rappelé en moins de cinq minutes ouvrées ».
Rien ne la surveillait : un lead arrivé pendant qu'elle est en rendez-vous
pouvait refroidir une demi-journée sans qu'aucune surface ne s'en aperçoive.
Cette commande tourne toutes les 5 minutes (Celery Beat
``crm.escalader_premier_contact``) et, pour chaque lead NEUF jamais touché
dont l'objectif est dépassé, notifie le responsable ET son supérieur.

Quatre garde-fous qui font la différence entre une alerte utile et du bruit :

  * les minutes sont OUVRÉES (``crm.horaires.minutes_ouvrees_entre``) — un
    lead arrivé à 23 h n'est PAS en retard à 23 h 05, il l'est cinq minutes
    ouvrées après l'ouverture ;
  * l'escalade est idempotente PAR LEAD (marqueur en note chatter), sinon la
    même alerte partirait toutes les 5 minutes jusqu'au rappel ;
  * le miroir Odoo reste dehors — les 930 leads importés ne sont pas des
    demandes à rappeler (et la décision fondateur du 21/09/2026 sur la
    cadence automatique dit la même chose du miroir) ;
  * CAD31 — une seule alerte au SUPÉRIEUR par société et par passage.

CAD31 (21/09/2026), trois corrections :

  1. **toutes les SOURCES** (hors miroir Odoo). Le filtre `source=OS_NATIVE`
     laissait dehors SITE_WEB et META_LEAD_ADS, c'est-à-dire précisément le
     flot qui arrive la nuit et le week-end : la promesse « cinq minutes » ne
     surveillait aucun lead publicitaire ;
  2. **l'étape ne filtre plus** : un lead avancé à la main sans avoir été
     rappelé restait invisible. Ce qui compte est « jamais contacté », pas
     « encore au premier barreau ». Seuls les dossiers CLOS (signé, froid)
     sortent — les noms viennent de ``STAGES.py``, jamais d'un littéral ;
  3. **l'objectif n'est plus le seuil d'alerte** : l'objectif (5 min) est une
     promesse commerciale, le palier d'alerte est un réglage de bruit
     (``CompanyProfile.premier_contact_alerte_min``), et le supérieur n'est
     prévenu qu'au SECOND palier (``premier_contact_escalade_min``), une
     seule fois par passage. Trois leads de nuit franchissent le seuil à la
     même minute : trois notifications identiques ne disent rien de plus
     qu'une. Les deux paliers sont vides par défaut — le comportement est
     alors exactement celui d'avant.

    python manage.py escalader_premier_contact [--dry-run]
"""
import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

#: Marqueur d'idempotence (même patron que ``ESCALATION_MARKER`` de
#: ``recycler_leads_non_travailles``) : recherché avant toute nouvelle alerte.
MARQUEUR = 'auto — objectif premier contact dépassé'


class Command(BaseCommand):
    help = ("MRY17 — Escalade les leads neufs jamais touchés au-delà de "
            "l'objectif de premier contact (minutes OUVRÉES).")

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Compte sans notifier ni écrire en base.')

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        nb = escalader_premier_contact(dry_run=dry_run)
        prefixe = '[dry-run] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefixe}{nb} lead(s) escaladé(s).'))


def _profil(company):
    try:
        from apps.parametres.models import CompanyProfile
        return CompanyProfile.objects.filter(company=company).first()
    except Exception:  # noqa: BLE001 — défauts assumés
        return None


def _objectif_minutes(company, profil=None):
    """Objectif de la société (défaut 5). 0 = surveillance désactivée."""
    profil = profil if profil is not None else _profil(company)
    valeur = getattr(profil, 'premier_contact_objectif_min', None)
    return int(valeur) if valeur is not None else 5


def _palier_alerte(company, objectif, profil=None):
    """CAD31 — au-delà de combien de minutes ouvrées on RÉVEILLE quelqu'un.

    Vide (le défaut) ⇒ l'objectif lui-même : comportement d'avant, au chiffre
    près."""
    profil = profil if profil is not None else _profil(company)
    valeur = getattr(profil, 'premier_contact_alerte_min', None)
    return int(valeur) if valeur is not None else objectif


def _palier_superieur(company, profil=None):
    """CAD31 — le SECOND palier, celui qui remonte au supérieur.

    ``None`` (le défaut) ⇒ le supérieur est prévenu en même temps que le
    responsable, comme avant ce lot."""
    profil = profil if profil is not None else _profil(company)
    valeur = getattr(profil, 'premier_contact_escalade_min', None)
    return int(valeur) if valeur is not None else None


def _destinataires(lead):
    """``(responsable, supérieurs)`` — le premier palier réveille celui qui
    tient le dossier, le second seulement ceux qui sont au-dessus de lui.

    On part de la liste EXISTANTE (``lead_notification_recipients``, qui
    connaît déjà le repli « managers de la société » quand l'owner ou son
    supérieur manque) et on la coupe en deux : jamais un second calcul de
    destinataires qui dériverait du premier."""
    from apps.crm.services import lead_notification_recipients

    tous = lead_notification_recipients(lead)
    owner_pk = getattr(getattr(lead, 'owner', None), 'pk', None)
    if owner_pk is None:
        # Sans responsable, la liste N'EST QUE le repli managers : c'est à eux
        # que le lead revient, pas à un supérieur imaginaire.
        return tous, []
    responsable = [u for u in tous if getattr(u, 'pk', None) == owner_pk]
    superieurs = [u for u in tous if getattr(u, 'pk', None) != owner_pk]
    return responsable, superieurs


def _alerter_le_superieur(company, escalades, palier_superieur):
    """CAD31 — UNE alerte au supérieur par société et par passage.

    Trois leads arrivés la nuit franchissent le seuil à la même minute, à
    l'ouverture : trois notifications identiques ne disent rien de plus
    qu'une, et c'est ainsi qu'une alerte utile devient du bruit qu'on coupe.
    """
    from apps.notifications.models import EventType
    from apps.notifications.services import notify_many

    retenus = [(lead, minutes) for lead, minutes, _sups in escalades
               if palier_superieur is None or minutes > palier_superieur]
    if not retenus:
        return
    vus, superieurs = set(), []
    for _lead, _minutes, sups in escalades:
        for utilisateur in sups:
            pk = getattr(utilisateur, 'pk', None)
            if pk is not None and pk not in vus:
                vus.add(pk)
                superieurs.append(utilisateur)
    if not superieurs:
        return
    attente = max(minutes for _lead, minutes in retenus)
    if len(retenus) == 1:
        lead = retenus[0][0]
        nom = (lead.nom or '').strip() or 'Nouveau prospect'
        titre = f'{nom} attend depuis {attente} min ouvrées'
        lien = f'/crm/leads?lead={lead.pk}'
    else:
        titre = (f'{len(retenus)} prospects attendent un premier contact')
        lien = '/crm/leads'
    try:
        notify_many(
            superieurs, EventType.PREMIER_CONTACT_DEPASSE,
            title=titre,
            body=("Aucune prise de contact n'a encore eu lieu. Le plus "
                  f'ancien attend depuis {attente} minute(s) ouvrée(s).'),
            link=lien, company=company)
    except Exception:  # noqa: BLE001 — best-effort
        logger.warning(
            'escalader_premier_contact: alerte supérieur échouée (société %s)',
            getattr(company, 'pk', '?'), exc_info=True)


def escalader_premier_contact(dry_run=False, now=None):
    """Cœur de la commande — appelable directement (tests, tâche Celery).

    Renvoie le nombre de leads escaladés sur CE passage."""
    from django.utils import timezone

    # SCA19 — jamais `Company.objects.all()` : un tenant suspendu ne
    # doit plus déclencher d'escalade chez personne.
    from authentication.selectors import active_companies

    # CLAUDE.md #2 — la clé d'étape vient de la SOURCE UNIQUE (STAGES.py à la
    # racine, chargée par `apps.crm.stages`), jamais d'une chaîne littérale.
    from apps.crm import horaires
    from apps.crm.stages import COLD, SIGNED
    from apps.crm.models import Lead, LeadActivity
    from apps.notifications.models import EventType
    from apps.notifications.services import notify_many

    maintenant = now or timezone.now()
    nb = 0

    for company in active_companies():
        profil = _profil(company)
        objectif = _objectif_minutes(company, profil)
        if not objectif:
            continue  # surveillance désactivée pour cette société
        palier = _palier_alerte(company, objectif, profil)
        palier_superieur = _palier_superieur(company, profil)
        # CAD31 — TOUTES les sources sauf le miroir Odoo (voir l'en-tête), et
        # l'étape ne filtre plus : ce qui compte est « jamais contacté ».
        # Seuls les dossiers CLOS sortent, sur les clés de STAGES.py.
        candidats = Lead.objects.filter(
            company=company,
            first_contacted_at__isnull=True, perdu=False, is_archived=False,
        ).exclude(
            source=Lead.Source.ODOO_IMPORT_TEST,
        ).exclude(stage__in=[SIGNED, COLD]).select_related('owner')
        escalades = []
        for lead in candidats:
            try:
                ecoulees = horaires.minutes_ouvrees_entre(
                    lead.date_creation, maintenant, company)
            except Exception:  # noqa: BLE001 — un lead en échec n'arrête rien
                logger.warning(
                    'escalader_premier_contact: calcul échoué (lead %s)',
                    lead.pk, exc_info=True)
                continue
            if ecoulees <= palier:
                # Comprend le cas « lead de nuit » : hors fenêtre, zéro
                # minute ouvrée s'écoule — aucune escalade avant l'ouverture.
                continue
            if LeadActivity.objects.filter(
                    lead=lead, kind=LeadActivity.Kind.NOTE,
                    body__startswith=MARQUEUR).exists():
                continue
            nb += 1
            if dry_run:
                continue
            try:
                LeadActivity.objects.create(
                    company=company, lead=lead, user=None,
                    kind=LeadActivity.Kind.NOTE,
                    body=(f'{MARQUEUR} — {ecoulees} minute(s) ouvrée(s) '
                          f"écoulées depuis l'arrivée (objectif "
                          f'{objectif}).'))
                nom = (lead.nom or '').strip() or 'Nouveau prospect'
                # CAD31 — le PREMIER palier réveille le responsable du
                # dossier, et lui seul ; le supérieur est traité après la
                # boucle, une fois pour toute la société.
                responsable, superieurs = _destinataires(lead)
                escalades.append((lead, ecoulees, superieurs))
                notify_many(
                    responsable,
                    EventType.PREMIER_CONTACT_DEPASSE,
                    title=f'{nom} attend depuis {ecoulees} min ouvrées',
                    body=("Ce lead n'a encore reçu aucune prise de contact. "
                          f"L'objectif de la société est de {objectif} "
                          'minute(s) ouvrée(s).'),
                    link=f'/crm/leads?lead={lead.pk}', company=company)
            except Exception:  # noqa: BLE001 — best-effort
                logger.warning(
                    'escalader_premier_contact: escalade échouée (lead %s)',
                    lead.pk, exc_info=True)
        if not dry_run:
            _alerter_le_superieur(company, escalades, palier_superieur)
    return nb
