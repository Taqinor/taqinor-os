"""XMKT3 — Désinscription un clic + liste de suppression globale.

Additif : ``SuppressionMarketing`` (une ligne par destinataire supprimé,
unique par société+destinataire — preuve loi 09-08). Ne touche à aucun
modèle existant.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('compta', '0068_envoicampagne'),
    ]

    operations = [
        migrations.CreateModel(
            name='SuppressionMarketing',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('destinataire', models.CharField(max_length=255, verbose_name='Destinataire (email/téléphone normalisé)')),
                ('motif', models.CharField(choices=[('desinscrit', 'Désinscription volontaire'), ('rebond_dur', 'Rebond dur'), ('plainte', 'Plainte spam'), ('import', "Liste d'opposition importée")], default='desinscrit', max_length=12, verbose_name='Motif')),
                ('source', models.CharField(blank=True, default='', max_length=255, verbose_name='Source')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créée le')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='suppressions_marketing', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Suppression marketing',
                'verbose_name_plural': 'Suppressions marketing',
                'ordering': ['-date_creation'],
            },
        ),
        migrations.AddConstraint(
            model_name='suppressionmarketing',
            constraint=models.UniqueConstraint(fields=('company', 'destinataire'), name='uniq_suppression_marketing_par_destinataire'),
        ),
    ]
