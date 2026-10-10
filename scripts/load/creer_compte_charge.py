"""ENF12 — compte de CHARGE des tests de performance nocturnes (k6, Locust).

À lancer depuis ``backend/django_core`` sur la base JETABLE du job :
    LOAD_USERNAME=charge LOAD_PASSWORD=... python ../../scripts/load/creer_compte_charge.py

Avant ENF12, les deux jobs de charge tournaient à 100 % d'échecs, masqués :
Locust visait ``/api/django/auth/login/`` (404) avec l'e-mail comme
identifiant, k6 n'avait AUCUN compte ``loadtest`` — toutes les requêtes
mesurées étaient des 401 de 3 ms. Ce script crée un vrai compte : société
dédiée, rôle administrateur (rôles système via ``init_roles``, comme le compte
de fuzz d'ENF1), mot de passe fourni par le workflow. Refuse hors DEBUG.
"""
from __future__ import annotations

import os
import sys


def main() -> int:
    sys.path.insert(0, os.getcwd())
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp_agentique.settings.dev')
    import django
    django.setup()

    from django.apps import apps
    from django.conf import settings
    from django.core.management import call_command

    if not settings.DEBUG:
        print('Refusé : compte de charge réservé à une base jetable (DEBUG).')
        return 1
    username = os.environ.get('LOAD_USERNAME', 'charge')
    password = os.environ.get('LOAD_PASSWORD')
    if not password:
        print('LOAD_PASSWORD manquant.')
        return 1

    company_model = apps.get_model('authentication', 'Company')
    user_model = apps.get_model('authentication', 'CustomUser')
    company, _ = company_model.objects.get_or_create(nom='[CHARGE] Load smoke')
    user, _ = user_model.objects.get_or_create(
        username=username,
        defaults={'email': f'{username}@taqinor.local', 'company': company})
    user.company = company
    user.role_legacy = user_model.ROLE_ADMIN
    user.is_active = True
    user.set_password(password)
    user.save()
    user.societes_autorisees.add(company)
    call_command('init_roles')
    print(f'Compte de charge « {username} » prêt (société {company.pk}).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
