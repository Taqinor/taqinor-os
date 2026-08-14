# NTSCM34 — Activation par module SCM via `core.ModuleToggle`.
#
# Le module `scm` s'enregistre déjà dans le registre `core.ModuleToggle`
# depuis sa création (`apps/scm/apps.py::module_manifest`, clé `scm` — IDENTIQUE
# au 2ᵉ segment d'URL `api/django/scm/`, donc `core.permissions.
# DisabledModuleMiddleware` le couvre GÉNÉRIQUEMENT sans code supplémentaire
# ici : une société dont le module est désactivé reçoit déjà 404 sur tous les
# endpoints `scm/*`, comme n'importe quel autre module optionnel).
#
# Politique FG391 par défaut : absence de ligne `ModuleToggle` == module actif.
# Le module SCM existe cependant depuis plusieurs vagues (vagues 1-2, NTSCM1
# à NTSCM31 déjà en production) SANS jamais avoir été présenté comme un
# module à activer — l'exposer soudain comme actif-par-défaut à TOUTES les
# sociétés existantes serait une surprise, pas une nouvelle fonctionnalité
# opt-in. Cette migration de données pose donc EXPLICITEMENT `actif=False`
# pour chaque société déjà en base au moment du déploiement — jamais pour une
# société créée APRÈS cette migration (elle suit alors la politique FG391
# standard : absence de ligne == actif, comme tout module installable).
#
# "migration de données n'active rien" (plan NTSCM34) : cette migration ne
# fait qu'ÉCRIRE des lignes `actif=False` ; elle n'active jamais quoi que ce
# soit. `get_or_create` : idempotente si rejouée.
from django.db import migrations


def desactiver_scm_pour_societes_existantes(apps, schema_editor):
    Company = apps.get_model('authentication', 'Company')
    ModuleToggle = apps.get_model('core', 'ModuleToggle')
    for company_id in Company.objects.values_list('id', flat=True):
        ModuleToggle.objects.get_or_create(
            company_id=company_id, module='scm',
            defaults={
                'actif': False,
                'raison': (
                    'NTSCM34 : module SCM désactivé par défaut pour les '
                    'sociétés existantes — à activer depuis l\'écran Modules.'),
            },
        )


def _noop_reverse(apps, schema_editor):
    # Réversible sans effet : réactiver ne serait pas sûr par défaut (une
    # société ayant explicitement désactivé le module APRÈS coup ne doit pas
    # être réactivée par un rollback de migration).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('scm', '0010_ntscm33_ntscm36_parametresscm_reglages'),
        ('core', '0012_moduletoggle'),
        ('authentication', '0027_ntadm22_customuser_is_taqinor_support'),
    ]

    operations = [
        migrations.RunPython(
            desactiver_scm_pour_societes_existantes, _noop_reverse),
    ]
