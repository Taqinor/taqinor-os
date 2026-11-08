# AMON93 — certificat carbone annulable (motif, auteur, date) puis
# ré-émissible : colonnes additives, contraintes d'unicité limitées aux
# certificats ÉMIS (un certificat annulé ne bloque plus sa période).
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('monitoring', '0012_underperformanceflag_cloture_par'),
    ]

    operations = [
        migrations.AddField(
            model_name='certificatcarbone',
            name='statut',
            field=models.CharField(
                choices=[('emis', 'Émis'), ('annule', 'Annulé')],
                default='emis', max_length=8),
        ),
        migrations.AddField(
            model_name='certificatcarbone',
            name='motif_annulation',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
        migrations.AddField(
            model_name='certificatcarbone',
            name='annule_le',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='certificatcarbone',
            name='annule_par',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+', to=settings.AUTH_USER_MODEL),
        ),
        migrations.RemoveConstraint(
            model_name='certificatcarbone',
            name='monitoring_certifco2_site_uniq',
        ),
        migrations.RemoveConstraint(
            model_name='certificatcarbone',
            name='monitoring_certifco2_cli_uniq',
        ),
        migrations.AddConstraint(
            model_name='certificatcarbone',
            constraint=models.UniqueConstraint(
                condition=models.Q(installation_id__isnull=False,
                                   statut='emis'),
                fields=('company', 'installation_id', 'periode_debut',
                        'periode_fin'),
                name='monitoring_certifco2_site_uniq'),
        ),
        migrations.AddConstraint(
            model_name='certificatcarbone',
            constraint=models.UniqueConstraint(
                condition=models.Q(client_id__isnull=False, statut='emis'),
                fields=('company', 'client_id', 'periode_debut',
                        'periode_fin'),
                name='monitoring_certifco2_cli_uniq'),
        ),
    ]
