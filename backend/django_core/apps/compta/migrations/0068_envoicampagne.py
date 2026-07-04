"""XMKT2 — Journal d'envoi par destinataire (trace de campagne).

Additif : ``EnvoiCampagne``, une ligne par destinataire réel d'une campagne.
Ne modifie aucun modèle existant ; les compteurs de ``Campagne`` restent tels
quels (ils deviendront dérivés côté service, sans migration nécessaire).
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
        ('compta', '0067_inscriptionsequence_executionetapesequence'),
    ]

    operations = [
        migrations.CreateModel(
            name='EnvoiCampagne',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('destinataire', models.CharField(max_length=255, verbose_name='Destinataire (email/téléphone)')),
                ('contact_ref', models.CharField(blank=True, default='', max_length=255, verbose_name='Référence contact (lead/client, opaque)')),
                ('statut', models.CharField(choices=[('queued', 'En file'), ('envoye', 'Envoyé'), ('delivre', 'Délivré'), ('ouvert', 'Ouvert'), ('clique', 'Cliqué'), ('rebond', 'Rebond'), ('desinscrit', 'Désinscrit')], db_index=True, default='queued', max_length=12, verbose_name='Statut')),
                ('raison_smtp', models.CharField(blank=True, default='', max_length=255, verbose_name='Raison SMTP')),
                ('envoye_le', models.DateTimeField(blank=True, null=True, verbose_name='Envoyé le')),
                ('ouvert_le', models.DateTimeField(blank=True, null=True, verbose_name='Ouvert le')),
                ('clique_le', models.DateTimeField(blank=True, null=True, verbose_name='Cliqué le')),
                ('date_creation', models.DateTimeField(auto_now_add=True, verbose_name='Créée le')),
                ('campagne', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='envois', to='compta.campagne', verbose_name='Campagne')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='envois_campagne', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Envoi de campagne (destinataire)',
                'verbose_name_plural': 'Envois de campagne (destinataires)',
                'ordering': ['-date_creation'],
            },
        ),
    ]
