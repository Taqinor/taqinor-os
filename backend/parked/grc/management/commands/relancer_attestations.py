"""NTGRC21 — relance des attestations de politique manquantes.

Une politique publiée que la moitié de l'effectif n'a pas lue n'est pas une
politique, c'est un document. Ce balayage identifie, par politique PUBLIÉE et
pour sa version COURANTE, les employés visés qui n'ont pas encore attesté
(``grc.selectors.attestations_manquantes``) et leur envoie UNE relance.

IDEMPOTENT — au plus une relance par (personne, politique, version) et par
jour. La déduplication se lit sur les notifications DÉJÀ émises (même
destinataire, même lien du jour) : pas de table de suivi supplémentaire à
maintenir, et relancer la commande trois fois dans la même journée ne produit
pas trois notifications.

Outil MANUEL (ou appelable depuis n'importe quel ordonnanceur déjà en place) :
il ne se déclare pas périodique et n'exige donc aucune entrée d'ordonnancement.

Aucune donnée personnelle n'est écrite ni journalisée : la commande ne
manipule que des identifiants de dossiers et des comptes utilisateurs.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from authentication.selectors import active_companies


def lien_attestation(politique, version):
    """Lien profond vers la politique à attester (sert AUSSI de clé de dédup)."""
    return f'/grc/politiques/{politique.pk}?attester=1&version={version}'


def relancer_societe(company, *, aujourdhui=None, envoyer=True):
    """Relance les attestations manquantes d'UNE société.

    Renvoie ``(relances, ignorees)`` : le nombre de notifications émises, et le
    nombre de destinataires sautés (déjà relancés aujourd'hui, ou sans compte
    utilisateur — on ne notifie personne qui ne peut pas se connecter).
    """
    from apps.notifications.models import EventType, Notification
    from apps.notifications.services import notify
    from apps.rh.selectors import dossiers_actifs

    from apps.grc.selectors import attestations_manquantes

    jour = aujourdhui or timezone.now().date()
    dus = attestations_manquantes(company)
    if not dus:
        return 0, 0

    # Un seul aller-retour pour la correspondance dossier → compte : le
    # balayage tourne sur tout l'effectif, pas sur une fiche.
    comptes = {
        dossier_id: user_id
        for dossier_id, user_id in dossiers_actifs(company).values_list(
            'id', 'user_id')
    }

    relances = ignorees = 0
    for entree in dus:
        politique = entree['politique']
        version = entree['version']
        lien = lien_attestation(politique, version)
        titre = f'Politique à attester : {politique.titre} (v{version})'
        corps = (
            'Cette politique est publiée et vous n\'avez pas encore attesté '
            'l\'avoir lue. Ouvrez-la et saisissez votre nom pour attester.')
        for dossier_id in entree['manquants']:
            user_id = comptes.get(dossier_id)
            if not user_id:
                ignorees += 1
                continue
            deja = Notification.objects.filter(
                company=company, recipient_id=user_id,
                event_type=EventType.ANNONCE_READ_REMINDER,
                link=lien, created_at__date=jour).exists()
            if deja:
                ignorees += 1
                continue
            if envoyer:
                from django.contrib.auth import get_user_model

                user = get_user_model().objects.filter(pk=user_id).first()
                if user is None:
                    ignorees += 1
                    continue
                notify(user, EventType.ANNONCE_READ_REMINDER, titre,
                       body=corps, link=lien, company=company)
            relances += 1
    return relances, ignorees


class Command(BaseCommand):
    help = ('NTGRC21 — relance les employés qui n\'ont pas attesté la version '
            'courante d\'une politique publiée (idempotent, une relance par '
            'personne et par jour).')

    def add_arguments(self, parser):
        parser.add_argument(
            '--company', type=int, default=None,
            help='ID de société (défaut : toutes les sociétés actives).')
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Compte les relances sans envoyer aucune notification.')

    def handle(self, *args, **options):
        company_id = options.get('company')
        societes = active_companies()
        if company_id:
            societes = societes.filter(pk=company_id)

        total = ignorees = 0
        for company in societes:
            envoyees, sautees = relancer_societe(
                company, envoyer=not options.get('dry_run'))
            total += envoyees
            ignorees += sautees
        prefixe = '[simulation] ' if options.get('dry_run') else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefixe}Relances d\'attestation : {total} envoyée(s), '
            f'{ignorees} ignorée(s).'))
