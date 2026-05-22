"""
Create default system roles for every company and migrate users.

Run after applying migrations:
  docker compose exec django_core python manage.py init_roles
"""
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Create default system roles per company and migrate users from role_legacy.'

    @transaction.atomic
    def handle(self, *args, **options):
        from authentication.models import Company, CustomUser
        from apps.roles.models import (
            Role,
            ALL_PERMISSIONS,
            RESPONSABLE_PERMISSIONS,
            UTILISATEUR_PERMISSIONS,
        )

        LEGACY_MAP = {
            CustomUser.ROLE_ADMIN: ('Administrateur', ALL_PERMISSIONS),
            CustomUser.ROLE_RESPONSABLE: ('Responsable', RESPONSABLE_PERMISSIONS),
            CustomUser.ROLE_NORMAL: ('Utilisateur', UTILISATEUR_PERMISSIONS),
        }

        companies = Company.objects.all()
        if not companies.exists():
            self.stdout.write(
                self.style.WARNING('Aucune entreprise trouvée.')
            )
            return

        for company in companies:
            self.stdout.write(f'\n── Entreprise : {company.nom}')

            roles = {}
            for legacy_key, (nom, perms) in LEGACY_MAP.items():
                role, created = Role.objects.get_or_create(
                    company=company,
                    nom=nom,
                    defaults={'permissions': perms, 'est_systeme': True},
                )
                if not created:
                    # Update permissions in case they changed
                    if role.permissions != perms and role.est_systeme:
                        role.permissions = perms
                        role.save(update_fields=['permissions'])
                roles[legacy_key] = role
                status_str = 'créé' if created else 'existant'
                self.stdout.write(f'  Rôle "{nom}" : {status_str}')

            for legacy_key, role in roles.items():
                updated = CustomUser.objects.filter(
                    company=company,
                    role_legacy=legacy_key,
                    role__isnull=True,
                ).update(role=role)
                if updated:
                    self.stdout.write(
                        f'  {updated} utilisateur(s) migrés → {role.nom}'
                    )

            # Users without role_legacy default to Utilisateur
            fallback = roles[CustomUser.ROLE_NORMAL]
            updated = CustomUser.objects.filter(
                company=company,
                role__isnull=True,
            ).update(role=fallback)
            if updated:
                self.stdout.write(
                    f'  {updated} utilisateur(s) sans rôle → {fallback.nom}'
                )

        # Superusers without a company get no role (they bypass checks anyway)
        self.stdout.write(
            self.style.SUCCESS('\nMigration des rôles terminée.')
        )
