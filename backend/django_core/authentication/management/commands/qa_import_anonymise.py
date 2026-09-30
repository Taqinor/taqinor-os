"""Charge un instantané anonymisé dans la société LOCALE ``taqinor-anon``.

DEV SEULEMENT (même garde que seed_demo, ERR88) : refusé hors ``DEBUG`` — il
crée le compte ``anon_admin`` à mot de passe connu. Aucun ``--force``.

Ne touche QU'À la société cible (slug contenant « anon », garde-fou anti-
effacement d'une société réelle). Idempotent : un ré-import VIDE cette société
(ORM uniquement, ``reset_demo_company._delete_cascading``) puis la recharge.
Toutes les clés primaires/étrangères sont remappées ; les références gardées
restent uniques (société neuve ; une valeur unique GLOBALE qui entrerait en
collision est préfixée).

AUCUNE notification pendant l'import : les lignes sont insérées par
``bulk_create`` (ni ``save()`` ni signaux pre/post_save → ni chatter, ni
``notify()``, ni e-mail, ni webhook, ni événement de domaine ``devis_accepted``,
émis uniquement par les vues/services). Détail : ``authentication/anonymise.py``.

Une ligne que la base refuse est IGNORÉE (savepoint) et comptée par NOM DE
CONTRAINTE (ex. ``IntegrityError[uniq_lead_external_ref]=80`` ; repli : la classe
de l'exception), jamais par sa valeur — un nom de contrainte est du schéma.

Run :
  docker compose cp var/anon/latest.anon.json.gz django_core:/tmp/latest.anon.json.gz
  docker compose exec -T django_core python manage.py qa_import_anonymise --in /tmp/latest.anon.json.gz
  (ou --in - avec le fichier sur stdin)

Login : anon_admin / Anon@2026!   (administrateur — DEV uniquement)
"""
import sys

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from authentication import anonymise

ANON_USERNAME = 'anon_admin'
ANON_PASSWORD = 'Anon@2026!'
DEFAULT_SLUG = 'taqinor-anon'


class Command(BaseCommand):
    help = ("Importe un instantané anonymisé dans la société locale "
            "taqinor-anon (DEBUG seulement, idempotent).")

    def add_arguments(self, parser):
        parser.add_argument('--in', dest='src', required=True,
                            help="Fichier '*.anon.json.gz', ou '-' (stdin).")
        parser.add_argument('--company-slug', default=DEFAULT_SLUG,
                            help='Slug de la société cible (doit contenir '
                                 "'anon' ; défaut taqinor-anon).")

    def handle(self, *args, **options):
        # ERR88 — même garde que seed_demo : compte à mot de passe connu.
        if not settings.DEBUG:
            raise CommandError(
                "qa_import_anonymise est refusé hors DEBUG : il crée le compte "
                "anon_admin à mot de passe connu. Réservé à la stack locale.")
        slug = options['company_slug']
        if 'anon' not in slug.lower():
            raise CommandError(
                f"Refus : le slug « {slug} » ne contient pas 'anon' "
                "(garde-fou : seule une société anonymisée est vidée).")
        try:
            payload = anonymise.read_snapshot(
                options['src'], sys.stdin.buffer if options['src'] == '-'
                else None)
        except (OSError, ValueError) as exc:
            raise CommandError(
                f"Instantané illisible ({type(exc).__name__}).") from exc

        with transaction.atomic():
            company, admin = self._reset_company(slug)
            created, skipped = anonymise.import_payload(payload, company, admin)

        verbosity = options.get('verbosity', 1)
        if verbosity >= 1:
            total = sum(created.values())
            self.stdout.write(self.style.SUCCESS(
                f'Instantané anonymisé importé dans « {slug} » : {total} '
                'lignes créées.'))
            for label, n in created.items():
                self.stdout.write(f'  {label}: {n}')
            for label, reasons in skipped.items():
                # Par NOM DE CONTRAINTE de base (repli : classe d'exception),
                # les plus fréquentes d'abord — jamais une valeur.
                detail = ', '.join(
                    f'{k}={v}' for k, v in sorted(
                        reasons.items(), key=lambda kv: (-kv[1], kv[0])))
                self.stdout.write(self.style.WARNING(
                    f'  ignorées {label}: {detail}'))
            self.stdout.write(f'Login : {ANON_USERNAME} (mot de passe dans '
                              'qa_import_anonymise.py — DEV seulement).')

    def _reset_company(self, slug):
        from authentication.models import Company, CustomUser
        from authentication.management.commands.reset_demo_company import (
            _delete_cascading,
        )
        from authentication.management.commands.seed_demo_company import (
            Command as SeedDemoCompany,
        )
        from django.apps import apps as django_apps

        existing = CustomUser.objects.filter(username=ANON_USERNAME).first()
        old = Company.objects.filter(slug=slug).first()
        if existing is not None and existing.company_id not in (
                None, getattr(old, 'pk', None)):
            raise CommandError(
                f"Refus : le compte {ANON_USERNAME} appartient à une autre "
                'société — rien n’est touché.')
        if old is not None:
            # CustomUser.company est SET_NULL → supprimer d'abord les comptes
            # de la société anonymisée (sinon orphelins), puis la société.
            CustomUser.objects.filter(company=old).delete()
            _delete_cascading(old)
        CustomUser.objects.filter(username=ANON_USERNAME,
                                  company__isnull=True).delete()

        company = Company.objects.create(
            slug=slug, nom='TAQINOR Anonymisé (QA)')
        profile_model = django_apps.get_model('parametres', 'CompanyProfile')
        profile = profile_model.get(company)
        profile.nom = 'TAQINOR Anonymisé (QA)'
        profile.email = 'anon@taqinor.local'
        profile.save()

        admin = CustomUser.objects.create(
            username=ANON_USERNAME,
            email='anon_admin@taqinor.local',
            role_legacy=CustomUser.ROLE_ADMIN,
            company=company,
            is_staff=True,
        )
        admin.set_password(ANON_PASSWORD)
        admin.is_protected = True
        admin.save()
        # Rôles système + types d'activité + niveaux de relance (idempotent,
        # mêmes gestes que seed_demo / seed_demo_company).
        call_command('init_roles', verbosity=0)
        SeedDemoCompany()._ensure_activity_scaffolding(company)
        return company, admin
