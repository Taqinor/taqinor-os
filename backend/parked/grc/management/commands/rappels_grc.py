"""NTGRC34 — rappels d'échéances GRC (exécutable par Celery beat).

Balaye, société active par société active, les CINQ familles d'échéances de
conformité et émet une notification par échéance :

  1. demandes de droits (DSR) proches de leur délai légal ou dépassées ;
  2. violations de données encore non notifiées sous 72 h ;
  3. revues de risque dues ;
  4. contrôles internes dont le test est dû ;
  5. politiques publiées non attestées.

IDEMPOTENT — au plus UNE notification par destinataire, par échéance et par
jour. La clé de déduplication est le LIEN profond de l'échéance : deux
lancements le même jour ne produisent pas deux notifications, et le rappel de
politique partage sa clé avec ``relancer_attestations`` (NTGRC21) — lancer les
deux le même jour n'en émet qu'une.

« Sans planificateur requis pour la démo » : la commande tourne À LA MAIN
exactement comme en production. Quand Celery beat est provisionné, il appelle
la tâche ``grc.rappels_grc`` (``apps/grc/tasks.py``), qui ne fait que relayer
ici — une seule logique, un seul comportement.

Destinataires : les destinataires routés de la société (règles de routage
``notifications``, repli sur les responsables). Le PROPRIÉTAIRE d'un risque ou
d'un contrôle est un nom LIBRE, pas un compte : on le NOMME dans le corps du
message au lieu d'inventer une correspondance nom→utilisateur qui se
tromperait de personne.

Aucune donnée personnelle n'est écrite dans les notifications : références,
comptes et échéances — jamais l'identité d'une personne concernée.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from authentication.selectors import active_companies

#: Fenêtre d'anticipation par défaut, en jours.
FENETRE_JOURS = 7


def _echeances_societe(company, within_days, maintenant):
    """Les échéances GRC dues d'une société : ``[(lien, titre, corps)]``."""
    from core.dsr import demandes_proches_echeance

    from ...selectors import (
        attestations_manquantes, controles_a_tester,
        risques_a_revoir, violations_echeance_72h_depassee,
    )

    jour = maintenant.date()
    echeances = []

    for demande in demandes_proches_echeance(
            company, within_days=within_days, now=maintenant):
        retard = demande.date_echeance < maintenant
        echeances.append((
            f'/grc/demandes-droit/{demande.pk}',
            ('Demande de droits EN RETARD' if retard
             else 'Demande de droits à traiter'),
            (f'Demande « {demande.get_kind_display()} » — échéance légale le '
             f'{demande.date_echeance:%d/%m/%Y}.'),
        ))

    for violation in violations_echeance_72h_depassee(company, now=maintenant):
        echeances.append((
            f'/grc/violations/{violation.pk}',
            'Violation de données non notifiée sous 72 h',
            (f'{violation.reference} — échéance de notification CNDP '
             f'dépassée depuis le '
             f'{violation.date_echeance_72h:%d/%m/%Y %H:%M}.'),
        ))

    for risque in risques_a_revoir(company, within=within_days,
                                   aujourdhui=jour):
        echeances.append((
            f'/grc/risques/{risque.pk}',
            'Revue de risque due',
            (f'{risque.reference or risque.titre} — revue prévue le '
             f'{risque.date_revue_prevue:%d/%m/%Y}'
             + (f', propriétaire : {risque.proprietaire}.'
                if risque.proprietaire else '.')),
        ))

    for entree in controles_a_tester(company, within=within_days,
                                     aujourdhui=jour):
        controle = entree['controle']
        echeance = entree['echeance']
        echeances.append((
            f'/grc/controles/{controle.pk}',
            'Contrôle interne à tester',
            (f'{controle.code} — {controle.intitule} ('
             + ('jamais testé' if echeance is None
                else f'dû depuis le {echeance:%d/%m/%Y}')
             + (f', propriétaire : {controle.proprietaire}' if
                controle.proprietaire else '')
             + ').'),
        ))

    for entree in attestations_manquantes(company):
        politique = entree['politique']
        version = entree['version']
        echeances.append((
            f'/grc/politiques/{politique.pk}?attester=1&version={version}',
            'Politique publiée non attestée',
            (f'{politique.titre} (v{version}) — {len(entree["manquants"])} '
             'personne(s) n\'ont pas encore attesté.'),
        ))

    return echeances


def rappeler_societe(company, *, within_days=FENETRE_JOURS, now=None,
                     envoyer=True):
    """Émet les rappels GRC d'UNE société. Renvoie ``(envoyees, ignorees)``."""
    from apps.notifications.models import EventType, Notification
    from apps.notifications.services import notify, resolve_recipients

    maintenant = now or timezone.now()
    jour = maintenant.date()
    echeances = _echeances_societe(company, within_days, maintenant)
    if not echeances:
        return 0, 0

    destinataires = list(resolve_recipients(company, EventType.DIGEST))
    if not destinataires:
        return 0, len(echeances)

    envoyees = ignorees = 0
    for lien, titre, corps in echeances:
        for user in destinataires:
            deja = Notification.objects.filter(
                company=company, recipient=user, link=lien,
                created_at__date=jour).exists()
            if deja:
                ignorees += 1
                continue
            if envoyer:
                notify(user, EventType.DIGEST, titre, body=corps, link=lien,
                       company=company)
            envoyees += 1
    return envoyees, ignorees


class Command(BaseCommand):
    help = ('NTGRC34 — rappelle les échéances GRC (DSR, violations 72 h, '
            'revues de risque, contrôles à tester, politiques non attestées). '
            'Idempotent : une notification par échéance et par jour. '
            'Plannifiable par Celery beat (tâche grc.rappels_grc).')

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', type=int, default=None,
            help='ID de société (défaut : toutes les sociétés actives).')
        parser.add_argument(
            '--within', type=int, default=FENETRE_JOURS,
            help=f"Fenêtre d'anticipation en jours (défaut {FENETRE_JOURS}).")
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Compte les rappels sans envoyer aucune notification.')

    def handle(self, *args, **options):
        societes = active_companies()
        company_id = options.get('company')
        if company_id:
            societes = societes.filter(pk=company_id)

        total = ignorees = 0
        for company in societes:
            envoyees, sautees = rappeler_societe(
                company, within_days=options.get('within') or FENETRE_JOURS,
                envoyer=not options.get('dry_run'))
            total += envoyees
            ignorees += sautees
        prefixe = '[simulation] ' if options.get('dry_run') else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefixe}Rappels GRC : {total} envoyé(s), '
            f'{ignorees} ignoré(s).'))
