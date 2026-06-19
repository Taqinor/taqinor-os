"""
Create default system roles for every company and migrate users.

Idempotent + additive. Seeds the SEVEN canonical roles (Feature D) plus the two
legacy system roles kept for existing accounts/data, then maps existing users so
nobody loses access:
  * role-less accounts → their legacy system role (Administrateur/Responsable/
    Utilisateur), exactly as before;
  * owners (is_protected) and superusers with a company → Directeur, so every
    company has at least one Directeur;
  * users on a custom « Commercial(e) » role → the new system « Commercial » role.

Run after applying migrations:
  docker compose exec django_core python manage.py init_roles
"""
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = ('Seed the canonical system roles per company and map existing '
            'users (Feature D) — idempotent and additive.')

    @transaction.atomic
    def handle(self, *args, **options):
        from authentication.models import Company, CustomUser
        from apps.roles.models import (
            Role,
            CANONICAL_SYSTEM_ROLES,
            RESPONSABLE_PERMISSIONS,
            UTILISATEUR_PERMISSIONS,
            ADMIN_PERMISSIONS,
        )

        # role_legacy → (nom du rôle système, permissions) pour les comptes
        # encore sans rôle fin.
        LEGACY_MAP = {
            CustomUser.ROLE_ADMIN: ('Administrateur', ADMIN_PERMISSIONS),
            CustomUser.ROLE_RESPONSABLE: ('Responsable', RESPONSABLE_PERMISSIONS),
            CustomUser.ROLE_NORMAL: ('Utilisateur', UTILISATEUR_PERMISSIONS),
        }

        companies = Company.objects.all()
        if not companies.exists():
            self.stdout.write(self.style.WARNING('Aucune entreprise trouvée.'))
            return

        for company in companies:
            self.stdout.write(f'\n── Entreprise : {company.nom}')

            roles = {}
            for nom, perms in CANONICAL_SYSTEM_ROLES:
                role, created = Role.objects.get_or_create(
                    company=company,
                    nom=nom,
                    defaults={'permissions': list(perms), 'est_systeme': True},
                )
                # Auto-réparation (N103) : une ligne du même nom laissée
                # ``est_systeme=False`` (mapping rétroactif / rôle personnalisé
                # ayant heurté un nom canonique) résoudrait à tort au palier
                # limité — un Directeur/Administrateur perdrait alors l'accès aux
                # écrans Utilisateurs/Rôles. On la promeut en rôle système.
                # Additif : ne supprime rien.
                if not created and not role.est_systeme:
                    role.est_systeme = True
                    role.save(update_fields=['est_systeme'])
                if not created and role.est_systeme and \
                        role.permissions != list(perms):
                    role.permissions = list(perms)
                    role.save(update_fields=['permissions'])
                roles[nom] = role
                self.stdout.write(
                    f'  Rôle "{nom}" : {"créé" if created else "à jour"}')

            # 1) Comptes sans rôle fin → rôle système selon role_legacy.
            for legacy_key, (nom, _perms) in LEGACY_MAP.items():
                updated = CustomUser.objects.filter(
                    company=company, role_legacy=legacy_key, role__isnull=True,
                ).update(role=roles[nom])
                if updated:
                    self.stdout.write(
                        f'  {updated} compte(s) {legacy_key} → {nom}')

            # Comptes restants sans rôle ni legacy → Utilisateur.
            fallback = roles['Utilisateur']
            updated = CustomUser.objects.filter(
                company=company, role__isnull=True,
            ).update(role=fallback)
            if updated:
                self.stdout.write(
                    f'  {updated} compte(s) sans rôle → {fallback.nom}')

            # 2) Propriétaires / superusers de la société → Directeur (au moins
            # un Directeur par société). Additif : Directeur ⊇ Administrateur.
            from django.db.models import Q
            directeur = roles['Directeur']
            owners = CustomUser.objects.filter(company=company).filter(
                Q(is_protected=True) | Q(is_superuser=True)
            ).exclude(role=directeur)
            for owner in owners:
                owner.role = directeur
                owner.role_legacy = CustomUser.ROLE_ADMIN
                owner.save(update_fields=['role', 'role_legacy'])
                self.stdout.write(f'  Propriétaire {owner.username} → Directeur')

            # 3) Comptes sur un rôle « Commercial(e) » personnalisé → le nouveau
            # rôle système « Commercial » (best-effort, additif).
            commercial = roles['Commercial']
            custom_comm = CustomUser.objects.filter(
                company=company, role__est_systeme=False,
                role__nom__icontains='commercial',
            )
            for u in custom_comm.exclude(role=commercial):
                u.role = commercial
                u.role_legacy = CustomUser.ROLE_NORMAL
                u.save(update_fields=['role', 'role_legacy'])
                self.stdout.write(f'  {u.username} → Commercial')

        self.stdout.write(self.style.SUCCESS('\nMigration des rôles terminée.'))
