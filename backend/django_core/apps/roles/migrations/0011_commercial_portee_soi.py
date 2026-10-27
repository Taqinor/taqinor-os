# Fondateur 26/10/2026 — « un membre d'équipe ne voit pas les leads de ses
# coéquipiers ; seuls le responsable d'équipe et le directeur les voient
# tous ». Le rôle SYSTÈME « Commercial » passe de ``records_scope_equipe``
# (soi + pairs de même superviseur) à ``records_scope_soi`` (soi + les
# personnes qu'il encadre, jamais ses pairs).
#
# Aller : sur le seul rôle système « Commercial » de chaque société, le
# marqueur ``records_scope_equipe`` est remplacé à sa place par
# ``records_scope_soi``. Un rôle personnalisé, ou un Commercial dont la
# portée a été changée à la main (pas de ``records_scope_equipe``), ne bouge
# pas. Retour : l'inverse, sur ce même rôle. Idempotente.

from django.db import migrations

ANCIEN = 'records_scope_equipe'
NOUVEAU = 'records_scope_soi'


def _remplacer(apps, de, vers):
    Role = apps.get_model('roles', 'Role')
    for role in Role.objects.filter(est_systeme=True, nom='Commercial').iterator():
        avant = role.permissions if isinstance(role.permissions, list) else []
        if de not in avant:
            continue
        apres = []
        for code in avant:
            code = vers if code == de else code
            if code not in apres:
                apres.append(code)
        role.permissions = apres
        role.save(update_fields=['permissions'])


def aller(apps, schema_editor):
    _remplacer(apps, ANCIEN, NOUVEAU)


def retour(apps, schema_editor):
    _remplacer(apps, NOUVEAU, ANCIEN)


class Migration(migrations.Migration):

    dependencies = [
        ('roles', '0010_asec50_responsable_exports'),
    ]

    operations = [
        migrations.RunPython(aller, retour),
    ]
