"""MRY17 — Digest 08:30 : « vous avez N relance(s) à faire aujourd'hui ».

Le panneau « Relances du jour » du Cockpit ne sert à rien si personne ne
l'ouvre. Cette commande, planifiée à 08:30 (Celery Beat
``crm.notifier_relances_dues``), envoie à CHAQUE commercial le compte de ses
touches dues — une seule fois par jour, quel que soit le nombre d'exécutions.

CAD116 — le message ne donne plus qu'un NOMBRE. Face à trente touches, « 30
relance(s) à faire » ne donne aucune prise : il ne cite aucun nom et ne dit
pas par où commencer. Le corps porte donc, en plus du total, les DEUX OU TROIS
dossiers à ouvrir en premier. Ils ne sont pas choisis par un calcul neuf :
c'est l'ordre de la file elle-même (``relance_etapes_dues`` → en retard
d'abord, puis l'heure, puis la priorité et le score), donc la même requête,
seul le texte change.

CAD116 (second angle mort) — un lead SANS propriétaire, ou dont le
propriétaire est DÉSACTIVÉ, n'apparaissait dans AUCUN digest : les
destinataires sont les owners actifs, et ces dossiers n'en ont pas. Leur
compte part au RESPONSABLE PAR DÉFAUT de la société (Paramètres →
« Responsable par défaut ») — jamais un prénom codé en dur.

Idempotence par jour ET par destinataire : une ``Notification`` `relance_due`
déjà créée aujourd'hui pour cette personne bloque la suivante. Sans cela, un
beat rejoué (``acks_late`` : une tâche PEUT être relancée après un crash
worker) enverrait deux fois le même digest.

Best-effort par société et par destinataire : un échec n'interrompt jamais
les suivants.

N3 (décision fondateur du 25/09/2026 — « la notification de 8 h 30 de Meryem
a disparu ») : le digest se TAISAIT quand aucune touche n'était due, et ce
silence se lisait comme une panne. Désormais :

  * chaque commercial qui a des leads ACTIFS le reçoit CHAQUE jour ouvré, y
    compris « Aucune relance due aujourd'hui — N touche(s) à venir cette
    semaine » ;
  * les étapes de VISITE (planifier, confirmer la veille, débrief) et de
    DEVIS (préparer et envoyer) sont comptées à part : ce sont des
    ``RelanceEtape`` comme les autres, déjà dans le total ;
  * aucun digest un jour NON ouvré (dimanche, férié) : la fenêtre des
    messages de la société (``crm.horaires``) fait foi — le lundi, les
    touches du week-end ressortent « en retard ».

    python manage.py notifier_relances_dues [--dry-run]
"""
import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

#: CAD116 — combien de dossiers le digest CITE nommément. Deux ou trois : au
#: delà, le message redevient une liste qu'on ne lit pas.
DIGEST_DOSSIERS_CITES = 3

#: CAD116 — la phrase d'invitation, inchangée, qui suit désormais les dossiers
#: cités au lieu de tenir seule le corps du message.
DIGEST_INVITATION = ('Ouvrez le Cockpit CRM pour voir vos touches du jour et '
                     'celles en retard.')

#: N3 — le titre du digest quand rien n'est dû : le silence ne se lit plus
#: comme une panne.
DIGEST_ZERO_TITRE = "Aucune relance due aujourd'hui"

#: N3 — la fenêtre qui décide si le jour est ouvré : celle des MESSAGES
#: (le digest est un message interne, comme les notifications — N1).
_CANAL_DIGEST = 'whatsapp'


def _jour_ouvre(company, aujourdhui):
    """N3 — ``aujourdhui`` est-il un jour ouvré pour la société (fenêtre des
    messages : jours ouvrés, fériés, Ramadan) ? Best-effort : en cas de doute
    le digest part (jamais un silence de plus)."""
    try:
        from apps.crm import horaires
        return horaires.fenetre_du_jour(
            aujourdhui, company, canal=_CANAL_DIGEST) is not None
    except Exception:  # noqa: BLE001 — jamais bloquant
        logger.warning('notifier_relances_dues: jour ouvré illisible '
                       '(société %s)', getattr(company, 'pk', '?'),
                       exc_info=True)
        return True


def _a_des_leads_actifs(owner, company):
    """N3 — le commercial tient-il au moins un dossier VIVANT (ni archivé, ni
    perdu, ni « ne plus contacter », ni clos — clés de ``STAGES.py``) ? C'est
    ce qui lui vaut le digest même à zéro touche due."""
    from apps.crm.models import Lead
    from apps.crm.stages import COLD, SIGNED
    return Lead.objects.filter(
        company=company, owner=owner, is_archived=False, perdu=False,
        ne_plus_contacter=False,
    ).exclude(stage__in=[SIGNED, COLD]).exists()


def _familles_de_libelles():
    """N3 — ``(libellés de visite, libellés de devis)`` : les constantes du
    moteur de suivi (``crm.services``), jamais un second littéral. Les
    étapes de visite portent la cadence ``apres_devis`` (ordre 90-92), celles
    de devis la cadence ``generique`` — le LIBELLÉ est ce qui les distingue
    sans ambiguïté. En cas d'échec d'import, deux ensembles vides : le total
    reste juste, seule la ventilation disparaît."""
    try:
        from apps.crm import services as crm_services
        visites = frozenset({
            crm_services.VISITE_FILET_LIBELLE,
            crm_services.VISITE_CONFIRMATION_LIBELLE,
            crm_services.VISITE_DEBRIEF_LIBELLE,
        })
        devis = frozenset({
            crm_services.FILET_JOINT_LIBELLE,
            crm_services._FILET_JOINT_LIBELLE_ANCIEN,
            # « Préparer le devis modifié » (débrief qui renvoie au devis) :
            # c'est un devis à PRÉPARER, compté comme tel.
            crm_services.VISITE_DEVIS_LIBELLE,
        })
        return visites, devis
    except Exception:  # noqa: BLE001 — la ventilation est un bonus
        logger.warning('notifier_relances_dues: libellés de familles '
                       'illisibles', exc_info=True)
        return frozenset(), frozenset()


def _compter_familles(dues):
    """N3 — ``(nb étapes de visite, nb étapes de devis)`` parmi les touches
    dues (``dues`` : la file DÉJÀ calculée, aucune requête métier neuve)."""
    visites, devis = _familles_de_libelles()
    nb_visites = nb_devis = 0
    for libelle in dues.values_list('libelle', flat=True):
        libelle = (libelle or '').strip()
        if libelle in visites:
            nb_visites += 1
        elif libelle in devis:
            nb_devis += 1
    return nb_visites, nb_devis


def _ligne_familles(nb_visites, nb_devis):
    """N3 — « Dont 2 étape(s) de visite et 1 étape(s) de devis. » (vide si
    aucune des deux)."""
    parties = []
    if nb_visites:
        parties.append(f'{nb_visites} étape(s) de visite')
    if nb_devis:
        parties.append(f'{nb_devis} étape(s) de devis')
    if not parties:
        return ''
    return 'Dont ' + ' et '.join(parties) + '.'


def _corps_zero(a_venir):
    """N3 — le corps du digest quand rien n'est dû aujourd'hui."""
    return (f"{DIGEST_ZERO_TITRE} — {a_venir} touche(s) à venir cette "
            'semaine. ' + DIGEST_INVITATION)


def _ligne_dossier(etape, aujourdhui):
    """CAD116 — UN dossier à ouvrir, en une ligne lisible.

    Le nom du lead, ce qu'il y a à faire, et « en retard » quand l'échéance
    est passée. Aucune donnée qui ne soit pas déjà chargée par la file
    (``select_related('lead')``), aucun chiffre inventé.
    """
    lead = getattr(etape, 'lead', None)
    nom = (getattr(lead, 'nom', '') or '').strip() or f'Lead #{etape.lead_id}'
    quoi = (etape.libelle or '').strip() or etape.get_canal_display()
    retard = (' — en retard' if etape.due_date and etape.due_date < aujourdhui
              else '')
    return f'{nom} : {quoi}{retard}'


def _corps_digest(dues, aujourdhui, familles=''):
    """CAD116 — le corps du digest : les premiers dossiers, puis l'invitation.

    ``dues`` est la file DÉJÀ TRIÉE (en retard d'abord, puis l'heure, puis la
    priorité et le score) : « par où commencer » est donc sa tête, jamais un
    classement réinventé ici. N3 — ``familles`` (``_ligne_familles``) s'insère
    avant l'invitation quand il y a des étapes de visite ou de devis.
    """
    invitation = (f'{familles} ' if familles else '') + DIGEST_INVITATION
    premiers = list(dues[:DIGEST_DOSSIERS_CITES])
    if not premiers:
        return invitation
    lignes = [_ligne_dossier(e, aujourdhui) for e in premiers]
    return ('À ouvrir en premier — ' + ' · '.join(lignes) + '. '
            + invitation)


def _compter_leads_sans_responsable(company, aujourdhui):
    """CAD116 — combien de dossiers DUS n'ont aucun responsable joignable.

    Sans propriétaire, ou avec un propriétaire DÉSACTIVÉ : dans les deux cas
    le dossier n'entre dans aucun digest, puisque les destinataires sont les
    owners ACTIFS. Compté par LEAD (un dossier à dix touches reste un
    dossier), et seulement sur des leads encore vivants.
    """
    from django.db.models import Q

    from apps.crm.models import RelanceEtape

    return (RelanceEtape.objects
            .filter(company=company, statut=RelanceEtape.Statut.A_FAIRE,
                    due_date__lte=aujourdhui, lead__is_archived=False)
            .filter(Q(lead__owner__isnull=True)
                    | Q(lead__owner__is_active=False))
            .values('lead_id').distinct().count())


def _ligne_sans_responsable(nombre):
    """CAD116 — la ligne adressée au responsable par défaut."""
    return (f'{nombre} lead(s) sans responsable ont une relance due : '
            "personne ne les voit dans son digest tant qu'ils ne sont pas "
            'attribués.')


def _responsable_defaut(company):
    """CAD116 — le responsable par défaut de la société, ou ``None``.

    Lu dans le réglage existant (``CompanyProfile.responsable_defaut_leads``,
    Paramètres → « Responsable par défaut ») : aucun prénom codé en dur, et
    aucun destinataire inventé quand le réglage est vide.
    """
    from apps.parametres.models import CompanyProfile

    profil = CompanyProfile.objects.filter(company=company).first()
    responsable = getattr(profil, 'responsable_defaut_leads', None)
    if responsable is not None and not getattr(responsable, 'is_active', True):
        return None
    return responsable


class Command(BaseCommand):
    help = ("MRY17 — Notifie chaque commercial du nombre de touches de "
            "relance dues aujourd'hui (idempotent par jour).")

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Compte sans notifier ni écrire en base.')

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        envoyes, destinataires = notifier_relances_dues(dry_run=dry_run)
        prefixe = '[dry-run] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefixe}{envoyes} digest(s) envoyé(s) à '
            f'{destinataires} destinataire(s) éligible(s).'))


def notifier_relances_dues(dry_run=False, today=None):
    """Cœur de la commande — appelable directement (tests, tâche Celery).

    Renvoie ``(nb_digests, nb_destinataires_eligibles)``."""
    from django.contrib.auth import get_user_model

    # SCA19 — un tenant SUSPENDU ou en fermeture ne doit plus être
    # balayé ni notifié : on itère la source unique des sociétés
    # opérationnelles, jamais `Company.objects.all()`.
    from authentication.selectors import active_companies

    # CRX26 — la date « aujourd'hui » d'une décision métier (ici : quelles
    # touches sont dues) se lit dans le fuseau MÉTIER (Casablanca), jamais
    # via `timezone.localdate()` nu — CI (tests_crx26_timezone_casablanca)
    # interdit cette forme dans apps/crm.
    from core.dates import aujourd_hui_local

    from apps.crm.selectors import relance_etapes_dues
    from apps.notifications.models import EventType, Notification
    from apps.notifications.services import notify

    User = get_user_model()
    aujourdhui = today or aujourd_hui_local()
    nb_digests = 0
    nb_destinataires = 0

    for company in active_companies():
        # N3 — pas de digest un jour NON ouvré (dimanche, férié) : l'heure du
        # beat (08:30) reste, c'est le calendrier de la société qui décide.
        if not _jour_ouvre(company, aujourdhui):
            continue
        # CAD116 — les dossiers que PERSONNE ne verra (sans owner, ou owner
        # désactivé), comptés UNE fois pour la société.
        try:
            orphelins = _compter_leads_sans_responsable(company, aujourdhui)
            responsable_defaut = _responsable_defaut(company)
        except Exception:  # noqa: BLE001 — jamais bloquant pour les digests
            logger.warning(
                'notifier_relances_dues: comptage des leads sans responsable '
                'échoué (société %s)', getattr(company, 'pk', '?'),
                exc_info=True)
            orphelins, responsable_defaut = 0, None
        servis = set()
        # Les destinataires sont les OWNERS de leads, pas « tous les
        # utilisateurs » : un comptable n'a aucune relance à faire.
        proprietaires = User.objects.filter(
            company=company, is_active=True,
            leads_assignes__isnull=False).distinct()
        for owner in proprietaires:
            try:
                # `scope='all'` = dues aujourd'hui + en retard : c'est
                # exactement ce que le panneau affiche, jamais un compte qui
                # oublierait les touches en souffrance.
                dues = relance_etapes_dues(
                    company, owner, scope='all', owner=owner.pk,
                    today=aujourdhui)
                n = dues.count()
            except Exception:  # noqa: BLE001 — un owner en échec n'arrête rien
                logger.warning(
                    'notifier_relances_dues: comptage échoué pour %s',
                    owner.pk, exc_info=True)
                continue
            # N3 — à zéro touche due, le digest part QUAND MÊME à qui tient
            # des dossiers vivants : son silence se lisait comme une panne.
            if not n and not _a_des_leads_actifs(owner, company):
                continue
            nb_destinataires += 1
            deja = Notification.objects.filter(
                recipient=owner, event_type=EventType.RELANCE_DUE,
                created_at__date=aujourdhui).exists()
            if deja:
                continue
            nb_digests += 1
            servis.add(owner.pk)
            if dry_run:
                continue
            try:
                if n:
                    titre = f"{n} relance(s) à faire aujourd'hui"
                    corps = _corps_digest(
                        dues, aujourdhui,
                        _ligne_familles(*_compter_familles(dues)))
                else:
                    # `week` = retard + 7 prochains jours ; le retard est nul
                    # ici (n == 0), il ne reste que les touches à venir.
                    a_venir = relance_etapes_dues(
                        company, owner, scope='week', owner=owner.pk,
                        today=aujourdhui).count()
                    titre = DIGEST_ZERO_TITRE
                    corps = _corps_zero(a_venir)
                # CAD116 — le responsable par défaut porte AUSSI la ligne des
                # dossiers sans responsable : un seul message, pas deux.
                if (orphelins and responsable_defaut is not None
                        and owner.pk == responsable_defaut.pk):
                    corps += ' ' + _ligne_sans_responsable(orphelins)
                notify(
                    owner, EventType.RELANCE_DUE,
                    title=titre,
                    body=corps, link='/crm/cockpit', company=company)
            except Exception:  # noqa: BLE001 — best-effort
                logger.warning(
                    'notifier_relances_dues: notification échouée pour %s',
                    owner.pk, exc_info=True)

        # CAD116 — le responsable par défaut n'a pas forcément de lead à lui :
        # il reçoit alors la SEULE ligne des dossiers sans responsable, qui
        # sans cela ne serait lue par personne.
        if (orphelins and responsable_defaut is not None
                and responsable_defaut.pk not in servis):
            deja = Notification.objects.filter(
                recipient=responsable_defaut,
                event_type=EventType.RELANCE_DUE,
                created_at__date=aujourdhui).exists()
            if not deja:
                nb_destinataires += 1
                nb_digests += 1
                if not dry_run:
                    try:
                        notify(
                            responsable_defaut, EventType.RELANCE_DUE,
                            title=f'{orphelins} lead(s) sans responsable',
                            body=_ligne_sans_responsable(orphelins),
                            link='/crm/cockpit', company=company)
                    except Exception:  # noqa: BLE001 — best-effort
                        logger.warning(
                            'notifier_relances_dues: notification « sans '
                            'responsable » échouée pour %s',
                            responsable_defaut.pk, exc_info=True)
    return nb_digests, nb_destinataires
