"""
Récupération du compte propriétaire — à lancer SUR LE SERVEUR via SSH.

La racine de confiance de la récupération est « vous avez un accès SSH au
serveur » (que seul Reda possède), PAS un secret en dur dans le code. Cette
commande ne contient AUCUN mot de passe par défaut, aucun compte caché.

Elle garantit qu'il existe toujours au moins un propriétaire actif :
  * si le compte existe : réinitialise son mot de passe (fourni ou généré),
    réactive le compte, lui rend le rôle propriétaire (admin) et le marque
    protégé ;
  * s'il a disparu : le recrée dans la société indiquée (ou la seule société
    existante), puis applique la même remise en état.

Exemples :
    # Réinitialiser demo_admin avec un mot de passe GÉNÉRÉ (affiché une fois)
    python manage.py recover_owner

    # Préciser un compte et un mot de passe
    python manage.py recover_owner --username reda --password 'NouveauMdp!2026'

    # Recréer le propriétaire dans une société précise
    python manage.py recover_owner --username reda --company taqinor-demo
"""
import secrets

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = (
        "Réinitialise / re-crée le compte propriétaire (admin) — à lancer "
        "sur le serveur. Aucun secret en dur ; mot de passe fourni ou généré."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--username', default='demo_admin',
            help="Nom d'utilisateur du propriétaire (défaut : demo_admin).",
        )
        parser.add_argument(
            '--password', default=None,
            help="Nouveau mot de passe. Omis → un mot de passe fort est "
                 "généré et affiché une seule fois.",
        )
        parser.add_argument(
            '--company', default=None,
            help="Slug de la société (utile uniquement à la re-création). "
                 "Par défaut : la société existante du compte, sinon l'unique "
                 "société de la base.",
        )
        parser.add_argument(
            '--email', default=None,
            help="Email à poser à la re-création (facultatif).",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        from django.core.management import call_command
        from authentication.models import Company, CustomUser

        username = opts['username']
        password = opts['password'] or secrets.token_urlsafe(12)
        generated = opts['password'] is None

        user = CustomUser.objects.filter(username=username).first()

        if user is None:
            # Re-création : il faut une société.
            company = None
            if opts['company']:
                company = Company.objects.filter(slug=opts['company']).first()
                if company is None:
                    raise CommandError(
                        f"Société '{opts['company']}' introuvable.")
            else:
                companies = list(Company.objects.all()[:2])
                if len(companies) == 1:
                    company = companies[0]
                elif len(companies) == 0:
                    raise CommandError(
                        "Aucune société en base — précisez --company ou "
                        "lancez seed_demo d'abord.")
                else:
                    raise CommandError(
                        "Plusieurs sociétés existent — précisez --company "
                        "<slug> pour savoir où recréer le propriétaire.")
            user = CustomUser.objects.create(
                username=username,
                email=opts['email'] or '',
                company=company,
                is_staff=True,
            )
            self.stdout.write(self.style.WARNING(
                f"Compte '{username}' recréé dans la société "
                f"'{company.slug}'."))
        else:
            if opts['email']:
                user.email = opts['email']

        # Remise en état du propriétaire.
        user.is_active = True
        user.role_legacy = CustomUser.ROLE_ADMIN
        user.is_protected = True
        user.set_password(password)
        user.save()

        # Rendre le rôle propriétaire (FK Role 'Administrateur' de la société).
        # init_roles crée/rattache les rôles système par société, idempotent.
        try:
            call_command('init_roles')
        except Exception as exc:  # pragma: no cover - défensif
            self.stdout.write(self.style.WARNING(
                f"init_roles non exécuté ({exc}). Le rôle legacy admin "
                f"suffit déjà à garantir l'accès propriétaire."))

        # Si la société a un rôle 'Administrateur', s'assurer qu'il est attaché.
        if user.company_id:
            from apps.roles.models import Role
            admin_role = Role.objects.filter(
                company=user.company,
                permissions__contains=['roles_gerer'],
            ).first()
            if admin_role and user.role_id != admin_role.id:
                user.role = admin_role
                user.save(update_fields=['role'])

        self.stdout.write(self.style.SUCCESS(
            f"Propriétaire '{username}' rétabli (actif, admin, protégé)."))
        if generated:
            self.stdout.write(self.style.SUCCESS(
                f"Mot de passe généré (à noter MAINTENANT) : {password}"))
        else:
            self.stdout.write(
                "Mot de passe mis à jour avec la valeur fournie.")
