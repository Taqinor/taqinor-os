"""DC32 — le compte portail client se lie à ``crm.Client`` PAR FK et réutilise
l'email du client (fin de la 2ᵉ copie d'identité).

L'ancien champ ``client_id`` (PositiveIntegerField) contenait déjà la PK du
client : on le renomme temporairement, on ajoute la vraie FK ``client``, on
recopie la valeur (même PK), puis on retire la colonne temporaire et l'ancien
champ ``email`` dupliqué. Réversible.
"""
from django.db import migrations, models
import django.db.models.deletion


def copier_client_pk(apps, schema_editor):
    ComptePortailClient = apps.get_model('compta', 'ComptePortailClient')
    for compte in ComptePortailClient.objects.all().iterator():
        compte.client_id = compte.client_pk_tmp
        compte.save(update_fields=['client'])


def recopier_client_pk(apps, schema_editor):
    ComptePortailClient = apps.get_model('compta', 'ComptePortailClient')
    for compte in ComptePortailClient.objects.all().iterator():
        compte.client_pk_tmp = compte.client_id
        compte.save(update_fields=['client_pk_tmp'])


class Migration(migrations.Migration):

    dependencies = [
        ('compta', '0042_ecriture_validation_sod'),
        ('crm', '0001_initial'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='compteportailclient',
            name='uniq_compte_portail_client',
        ),
        migrations.RenameField(
            model_name='compteportailclient',
            old_name='client_id',
            new_name='client_pk_tmp',
        ),
        migrations.AddField(
            model_name='compteportailclient',
            name='client',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='comptes_portail',
                to='crm.client',
                verbose_name='Client'),
        ),
        migrations.RunPython(copier_client_pk, recopier_client_pk),
        migrations.RemoveField(
            model_name='compteportailclient',
            name='client_pk_tmp',
        ),
        migrations.RemoveField(
            model_name='compteportailclient',
            name='email',
        ),
        migrations.AlterField(
            model_name='compteportailclient',
            name='client',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='comptes_portail',
                to='crm.client',
                verbose_name='Client'),
        ),
        migrations.AddConstraint(
            model_name='compteportailclient',
            constraint=models.UniqueConstraint(
                fields=['company', 'client'],
                name='uniq_compte_portail_client'),
        ),
    ]
