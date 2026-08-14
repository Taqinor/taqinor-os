# NTMFG2 (revue orchestrateur) — `OperationGamme` porte desormais sa PROPRE FK
# `company` (heritage de core.models.TenantModel) au lieu d'etre scopee
# indirectement via `gamme.company`. Motif : la garde SCA4 exige qu'un
# ModelViewSet en ecriture herite de CompanyScopedModelViewSet, ce qui suppose
# une colonne `company` sur le modele.
#
# L'app `mrp` est CREEE dans ce meme lot et n'a jamais ete deployee : la table
# est donc vide en production. Le backfill ci-dessous couvre neanmoins les bases
# de developpement/test deja migrees, en reprenant la societe de la gamme
# parente — jamais une societe arbitraire.
import django.db.models.deletion
from django.db import migrations, models


def backfill_company(apps, schema_editor):
    OperationGamme = apps.get_model('mrp', 'OperationGamme')
    for operation in OperationGamme.objects.filter(company__isnull=True).iterator():
        operation.company_id = operation.gamme.company_id
        operation.save(update_fields=['company'])


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0014_customuser_account_lockout'),
        ('mrp', '0008_coutstandard'),
    ]

    operations = [
        migrations.AddField(
            model_name='operationgamme',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name='operationgamme',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, null=True),
        ),
        migrations.AddField(
            model_name='operationgamme',
            name='company',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='%(app_label)s_%(class)s_set',
                to='authentication.company',
                verbose_name='Société'),
        ),
        migrations.RunPython(backfill_company, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='operationgamme',
            name='company',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='%(app_label)s_%(class)s_set',
                to='authentication.company',
                verbose_name='Société'),
        ),
    ]
