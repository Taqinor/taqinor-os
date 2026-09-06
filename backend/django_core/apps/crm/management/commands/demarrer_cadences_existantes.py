"""MRY23 — Reprise des dossiers DÉJÀ dans l'ERP le jour de la mise en service.

Sans elle, le moteur ne démarrerait que sur les leads arrivés APRÈS le déploiement :
tout le portefeuille en cours resterait sans cadence, et le bénéfice n'arriverait
qu'au fil des semaines. Cette commande rattrape trois populations :

  1. les devis ENVOYÉS depuis moins de 14 jours et TOUJOURS en attente de
     réponse (statut « envoyé ») → cadence « après devis », datée depuis
     l'envoi RÉEL, avec les touches déjà passées SAUTÉES (les rejouer
     enverrait aujourd'hui le message du J+1 d'il y a dix jours) ;
  2. les leads NEUFS jamais contactés, créés depuis moins de 5 jours →
     cadence « contact », avec les MÊMES gardes que MRY6 ;
  3. les dormants (COLD, ou devis sans suite depuis 30 jours) → cadence
     « réveil », ÉTALÉE dans le temps.

L'étalement n'est pas un détail : lancer 400 réveils le même matin
saturerait la journée de Meryem et ferait partir 400 messages en rafale
depuis le même numéro — le meilleur moyen de se faire signaler comme spam.
Les leads partent donc par paquets, les meilleurs scores d'abord.

DRY-RUN PAR DÉFAUT. Rien n'est écrit sans ``--apply``.

    python manage.py demarrer_cadences_existantes --company <slug> \\
        [--apply] [--par-jour 10]
"""
import datetime
import logging

from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)

#: Un devis envoyé il y a plus de 14 jours a déjà épuisé sa cadence : la
#: relancer aujourd'hui serait un message hors sujet.
FENETRE_DEVIS_JOURS = 14
#: Au-delà de 5 jours, un lead « neuf » ne l'est plus : lui envoyer le message
#: « vous venez de nous laisser une demande » serait faux.
FENETRE_LEAD_JOURS = 5
#: Silence à partir duquel un dossier en cours est considéré comme dormant.
FENETRE_DORMANCE_JOURS = 30


class Command(BaseCommand):
    help = ('MRY23 — Démarre les cadences sur les dossiers DÉJÀ présents '
            '(dry-run par défaut).')

    def add_arguments(self, parser):
        parser.add_argument('--company', dest='company', required=True,
                            help='Slug ou id de la société cible.')
        parser.add_argument('--apply', action='store_true',
                            help='Écrit réellement (sinon : simulation).')
        parser.add_argument('--par-jour', dest='par_jour', type=int,
                            default=10,
                            help='Réveils démarrés par jour (défaut 10).')

    def handle(self, *args, **options):
        from authentication.models import Company

        brut = options['company']
        company = Company.objects.filter(slug=brut).first()
        if company is None and str(brut).isdigit():
            company = Company.objects.filter(pk=int(brut)).first()
        if company is None:
            raise CommandError(
                f'Société introuvable : {brut!r} (slug ou id attendu).')

        rapport = demarrer_cadences_existantes(
            company, apply_changes=options.get('apply', False),
            par_jour=max(1, options.get('par_jour') or 10))

        prefixe = '' if options.get('apply') else '[dry-run] '
        for cle, libelle in (
                ('apres_devis', 'Devis récents → cadence après devis'),
                ('contact', 'Leads neufs → cadence de contact'),
                ('reveil', 'Dormants → cadence de réveil')):
            bloc = rapport[cle]
            self.stdout.write(
                f'{prefixe}{libelle} : {bloc["nb"]} '
                f'(ex. {", ".join(str(i) for i in bloc["exemples"]) or "—"})')
        if rapport['ignores']:
            self.stdout.write(self.style.WARNING(
                f'{prefixe}{rapport["ignores"]} dossier(s) écarté(s) par les '
                'gardes (perdu, archivé, ne plus contacter, doublon, sans '
                'numéro).'))
        if not options.get('apply'):
            self.stdout.write(self.style.WARNING(
                'Simulation — AUCUNE écriture. Relancer avec --apply.'))
        else:
            self.stdout.write(self.style.SUCCESS('Reprise appliquée.'))


def _bloc():
    return {'nb': 0, 'exemples': []}


def _noter(bloc, lead_id):
    bloc['nb'] += 1
    if len(bloc['exemples']) < 5:
        bloc['exemples'].append(lead_id)


def demarrer_cadences_existantes(company, *, apply_changes=False,
                                 par_jour=10, now=None):
    """Cœur de la commande — appelable directement (tests, script).

    Renvoie ``{apres_devis, contact, reveil, ignores}``. IDEMPOTENTE :
    l'idempotence par cadence de `initialiser_plan_relance` (MRY5) fait qu'un
    second passage ne crée rien.

    Le DRY-RUN applique EXACTEMENT les mêmes gardes que ``--apply`` (via
    ``services._garde_cadence_contact``, fonction pure) : une simulation qui
    annonce plus de dossiers que la vraie exécution n'en traite ne sert à
    rien — et c'est sur ce chiffre que se décide le lancement."""
    from django.utils import timezone

    from apps.crm import stages
    from apps.crm.models import Lead, RelanceEtape
    from apps.crm.services import (
        _garde_cadence_contact, demarrer_cadence_contact,
        initialiser_plan_relance)

    maintenant = now or timezone.now()
    rapport = {'apres_devis': _bloc(), 'contact': _bloc(),
               'reveil': _bloc(), 'ignores': 0}

    # ── 1. Devis envoyés récemment ──────────────────────────────────────────
    depuis_devis = maintenant - datetime.timedelta(days=FENETRE_DEVIS_JOURS)
    for devis in _devis_envoyes_recents(company, depuis_devis):
        lead = Lead.objects.filter(
            pk=getattr(devis, 'lead_id', None), company=company).first()
        if lead is None:
            continue
        if lead.perdu or lead.is_archived or lead.ne_plus_contacter:
            rapport['ignores'] += 1
            continue
        if lead.relance_etapes.filter(cadence='apres_devis').exists():
            continue
        _noter(rapport['apres_devis'], lead.pk)
        if not apply_changes:
            continue
        etapes = initialiser_plan_relance(
            lead, None, cadence='apres_devis',
            depart=devis.date_envoi, devis=devis)
        # Les touches dont l'échéance est DÉJÀ passée sont sautées : les
        # rejouer enverrait aujourd'hui le message du J+1 d'il y a dix jours.
        RelanceEtape.objects.filter(
            pk__in=[e.pk for e in etapes], due_at__lt=maintenant,
            statut=RelanceEtape.Statut.A_FAIRE,
        ).update(statut=RelanceEtape.Statut.SAUTEE,
                 note='reprise : déjà passée', traite_le=maintenant)

    # ── 2. Leads neufs jamais contactés ─────────────────────────────────────
    depuis_lead = maintenant - datetime.timedelta(days=FENETRE_LEAD_JOURS)
    neufs = Lead.objects.filter(
        company=company, source=Lead.Source.OS_NATIVE, stage=stages.NEW,
        first_contacted_at__isnull=True, perdu=False, is_archived=False,
        ne_plus_contacter=False, date_creation__gte=depuis_lead,
    ).order_by('-score', 'pk')
    for lead in neufs:
        if lead.relance_etapes.filter(cadence='contact').exists():
            continue
        # MÊMES gardes que MRY6 (numéro exploitable, doublon vivant…) : la
        # reprise ne doit pas être une porte dérobée qui les contourne — ni,
        # en simulation, promettre des cadences qu'elles refuseront.
        if not apply_changes:
            if _garde_cadence_contact(lead) is None:
                _noter(rapport['contact'], lead.pk)
            else:
                rapport['ignores'] += 1
            continue
        if demarrer_cadence_contact(lead, origine='reprise MRY23'):
            _noter(rapport['contact'], lead.pk)
        else:
            rapport['ignores'] += 1

    # ── 3. Dormants → réveils ÉTALÉS ────────────────────────────────────────
    depuis_dormance = maintenant - datetime.timedelta(
        days=FENETRE_DORMANCE_JOURS)
    dormants = Lead.objects.filter(
        company=company, perdu=False, is_archived=False,
        ne_plus_contacter=False,
    ).filter(
        stage__in=[stages.COLD, stages.QUOTE_SENT, stages.FOLLOW_UP],
    ).order_by('-score', 'pk')
    rang = 0
    for lead in dormants:
        if lead.stage != stages.COLD:
            recente = lead.activites.filter(
                user__isnull=False, created_at__gte=depuis_dormance).exists()
            if recente:
                continue
        if lead.relance_etapes.filter(cadence='reveil').exists():
            continue
        _noter(rapport['reveil'], lead.pk)
        if not apply_changes:
            rang += 1
            continue
        # Lancer 400 réveils le même matin saturerait la journée de Meryem et
        # ferait partir 400 messages en rafale depuis le même numéro.
        depart = maintenant + datetime.timedelta(days=rang // par_jour)
        initialiser_plan_relance(
            lead, None, cadence='reveil', depart=depart)
        rang += 1
    return rapport


def _devis_envoyes_recents(company, depuis):
    """Devis ENVOYÉS **et toujours en attente** depuis ``depuis``, lus par le
    sélecteur de ``ventes`` — jamais un import de ``ventes.models``
    (frontière M3).

    Le statut compte autant que la date : ``devis_envoyes_periode`` ne filtre
    QUE ``date_envoi``, si bien que la reprise démarrait une cadence « après
    devis » sur des propositions déjà ACCEPTÉES, refusées ou expirées — et
    demandait « alors, ce PDF ? » trois jours après la signature."""
    try:
        from apps.ventes.selectors import devis_envoyes_en_attente
        return [d for d in devis_envoyes_en_attente(company, depuis)
                if getattr(d, 'lead_id', None)]
    except Exception:  # noqa: BLE001 — une reprise n'échoue jamais sur ce point
        logger.warning(
            'MRY23: devis récents illisibles (société %s)',
            getattr(company, 'pk', '?'), exc_info=True)
        return []
