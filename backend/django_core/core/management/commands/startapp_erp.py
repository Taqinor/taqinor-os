"""ARC42 — Scaffolder ``startapp_erp`` : générer un module ERP prêt à câbler.

Constat (scout noyau §11) : créer un module coûtait ~8 points de câblage manuels
et le re-codage d'un modèle/viewset/chatter/numérotation. Cette commande étend le
``startapp`` de Django avec le template ``backend/django_core/app_template/`` : elle
génère une app RÉELLE qui vise déjà les primitives fondation (``TenantModel``
ARC1, ``CompanyScopedModelViewSet`` ARC2, ``core.numbering`` ARC6, manifeste
``module_manifest`` ODX2 + ``platform.py`` ARC28), puis IMPRIME la checklist des
câblages qui restent forcément manuels (settings, urls, importlinter, roles,
permissions, manifestes) — pour qu'aucun ne soit oublié.

Usage ::

    python manage.py startapp_erp demo            # → apps/demo/
    python manage.py startapp_erp demo --dry-run  # checklist seule, rien créé

``core`` reste fondation : cette commande n'importe aucune app métier (elle ne
manipule que des chemins de fichiers + le ``startapp`` de Django).
"""
from __future__ import annotations

import os
import re

from django.core.management.commands.startapp import Command as StartAppCommand
from django.core.management.base import CommandError

# Racine du template d'app (à côté de ``core`` dans ``backend/django_core``).
_DJANGO_CORE_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_TEMPLATE_DIR = os.path.join(_DJANGO_CORE_ROOT, 'app_template')

_LABEL_RE = re.compile(r'^[a-z][a-z0-9_]*$')


def _wiring_checklist(label):
    """Les 8 points de câblage manuels restants (scout noyau §11).

    Renvoie une liste de (titre, détail) — imprimée après la génération pour
    qu'aucun câblage ne soit oublié.
    """
    dotted = f'apps.{label}'
    return [
        ("1. settings/base.py — INSTALLED_APPS",
         f"   Ajouter '{dotted}' à INSTALLED_APPS "
         "(erp_agentique/settings/base.py)."),
        ("2. erp_agentique/urls.py — include des routes",
         f"   path('api/django/{label}/', include('{dotted}.urls'))."),
        ("3. .importlinter — frontières d'app",
         "   Si le module doit rester découplé (string-FK only) ou est une "
         "couche fondation, ajouter/étendre un contrat dans "
         "backend/django_core/.importlinter."),
        ("4. roles/models.py — ALL_PERMISSIONS",
         f"   Ajouter les codes de permission ('{label}_voir', "
         f"'{label}_gerer', …) à ALL_PERMISSIONS (apps/roles/models.py) si le "
         "module gate lecture/écriture."),
        ("5. Manifeste module — module_manifest (ODX2)",
         f"   Généré dans {dotted}/apps.py : ajuster key/label/categorie/"
         "depends/installable au vrai module."),
        ("6. core/permissions.py — PREFIX_TO_MODULE",
         "   Seulement si le 2ᵉ segment d'URL diffère de la clé de module "
         "(ex. 'gestion-projet' → 'gestion_projet') ; sinon rien à faire "
         "(l'enforcement 404 des modules OFF dérive du segment)."),
        ("7. Frontend — module.config.jsx",
         f"   Créer frontend/src/features/{label}/module.config.jsx "
         "(nav Sidebar + routes lazy, auto-enregistré par moduleRoutes.jsx)."),
        ("8. platform.py (ARC28) + code métier",
         f"   Généré dans {dotted}/platform.py (surfaces vides) : remplir "
         "chaque surface QUAND elle est réellement câblée (recherche, chatter, "
         "customfields, import, agent, automation, KPI). Puis coder "
         f"modèle(s)/serializer/viewset/tests + makemigrations {label}."),
    ]


class Command(StartAppCommand):
    help = (
        "Génère un module ERP (apps/<label>/) prêt à câbler, visant les "
        "primitives fondation (TenantModel/viewset/numbering/manifeste/"
        "platform), et imprime la checklist des 8 câblages manuels restants."
    )
    # Ne pas hériter du texte d'aide « app » de Django pour l'argument.
    missing_args_message = "Indiquez le label du module, ex. « demo »."

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            '--dry-run', action='store_true',
            help="N'écrit rien : imprime seulement la checklist de câblage.")

    def handle(self, **options):
        label = options.get('name')
        if not _LABEL_RE.match(label or ''):
            raise CommandError(
                f"Label de module invalide : « {label} ». Utilisez un "
                "identifiant minuscule (lettres/chiffres/_, commençant par une "
                "lettre), ex. « demo » ou « gestion_projet ».")

        dry_run = options.pop('dry_run', False)
        checklist = _wiring_checklist(label)

        if not dry_run:
            apps_root = os.path.join(_DJANGO_CORE_ROOT, 'apps')
            target = os.path.join(apps_root, label)
            if os.path.exists(target):
                raise CommandError(
                    f"Le dossier « apps/{label} » existe déjà — choisissez un "
                    "autre label ou supprimez-le d'abord.")
            os.makedirs(target)

            # Bridge vers ``startapp`` de Django : il pope ``name`` + ``directory``
            # des options, force notre template, et injecte ``app_label`` dans le
            # contexte de rendu (dispo en {{ app_label }} dans les .py-tpl).
            # ``name`` reste le label NU (Django exige un identifiant valide, sans
            # point) ; le chemin pointé ``apps.<label>`` est construit dans les
            # gabarits via le préfixe ``apps.`` + {{ app_label }}.
            options['name'] = label
            options['directory'] = target
            options['template'] = _TEMPLATE_DIR
            options['app_label'] = label
            super().handle(**options)

            self.stdout.write(self.style.SUCCESS(
                f"\nModule généré : apps/{label}/ "
                f"(nom d'app : apps.{label})."))

        # Checklist des câblages manuels restants (les 8 points).
        titre = ("Checklist de câblage" if dry_run
                 else "Câblages manuels restants")
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n=== {titre} (8 points — ARC42) ==="))
        for titre_point, detail in checklist:
            self.stdout.write(self.style.HTTP_INFO(titre_point))
            self.stdout.write(detail)
        self.stdout.write("")
