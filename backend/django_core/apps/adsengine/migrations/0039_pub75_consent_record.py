# PUB75 — Registre de consentement image/témoignage (CNDP loi 09-08) : modèle
# ConsentRecord + champs de liaison sur CreativeAsset (asset « client réel »
# bloqué en policy sans consentement actif ; révocation = retrait de rotation).
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adsengine', '0038_pub49_annotation'),
        ('authentication', '0025_company_est_demo_mode_presentation'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConsentRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('client_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='Client (référence lâche)')),
                ('client_nom', models.CharField(max_length=160, verbose_name='Nom du client / de la personne')),
                ('reference', models.CharField(blank=True, default='', max_length=40, verbose_name='Référence du lien de collecte')),
                ('canal', models.CharField(choices=[('whatsapp', 'Lien WhatsApp signé'), ('papier', 'Formulaire papier'), ('email', 'Email'), ('verbal', 'Accord verbal consigné'), ('autre', 'Autre')], default='whatsapp', max_length=12, verbose_name='Canal de recueil')),
                ('portee_photo', models.BooleanField(default=False, verbose_name='Photo autorisée')),
                ('portee_video', models.BooleanField(default=False, verbose_name='Vidéo autorisée')),
                ('portee_temoignage', models.BooleanField(default=False, verbose_name='Témoignage (nom/citation) autorisé')),
                ('portee_geo', models.BooleanField(default=False, verbose_name='Localisation / chantier géolocalisé autorisé')),
                ('date_consentement', models.DateField(verbose_name='Date de recueil du consentement')),
                ('expiration', models.DateField(blank=True, null=True, verbose_name="Date d'expiration (optionnelle)")),
                ('revoked_at', models.DateTimeField(blank=True, null=True, verbose_name='Révoqué le')),
                ('note', models.TextField(blank=True, default='', verbose_name='Note')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société')),
            ],
            options={
                'verbose_name': 'Consentement (CNDP)',
                'verbose_name_plural': 'Consentements (CNDP)',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddField(
            model_name='creativeasset',
            name='depicts_real_client',
            field=models.BooleanField(default=False, help_text="Vrai si l'asset montre un vrai client/chantier/visage/nom.", verbose_name='Montre un client réel'),
        ),
        migrations.AddField(
            model_name='creativeasset',
            name='consent_scopes_required',
            field=models.JSONField(blank=True, default=list, help_text='Clés parmi photo/video/temoignage/geo à couvrir (vide = un consentement actif suffit).', verbose_name='Portées de consentement requises'),
        ),
        migrations.AddField(
            model_name='creativeasset',
            name='consent',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assets', to='adsengine.consentrecord', verbose_name='Consentement (CNDP)'),
        ),
        migrations.AddIndex(
            model_name='consentrecord',
            index=models.Index(fields=['company', 'client_id'], name='adseng_consent_co_client_idx'),
        ),
    ]
