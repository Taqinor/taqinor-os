import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """T-TRACE — traçage des visiteurs EXTERNES (finalité anti-fraude).

    Additif et rétro-compatible :
      * ``crm.VisiteExterne`` — table NEUVE (ses index naissent avec elle,
        jamais un verrou sur une table peuplée) ;
      * ``crm.Lead.appareil_id`` — colonne NULLABLE, sans défaut : aucune
        réécriture des lignes existantes, aucun backfill. NULL = appareil
        inconnu (anciens leads, imports, saisie manuelle).

    L'index ``(company, appareil_id)`` sur la table PEUPLÉE ``crm_lead`` est
    délibérément posé À PART, en CONCURRENT (migration 0083) : le poser ici
    verrouillerait ``crm_lead`` en écriture pendant toute la construction.
    """

    dependencies = [
        ('authentication', '0028_company_tours_actifs'),
        ('crm', '0081_l_quest_questionnaire_lien'),
        ('entites', '0001_initial'),
        ('tiers', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='VisiteExterne',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('point', models.CharField(choices=[('visite_site', 'Visite du site'), ('tunnel_lead', 'Demande de devis (tunnel)'), ('proposition', 'Ouverture de proposition'), ('questionnaire', 'Réponse au questionnaire'), ('booking', 'Réservation de visite')], default='visite_site', max_length=20, verbose_name='Point de contact')),
                ('contexte', models.CharField(blank=True, default='', max_length=200, verbose_name='Page / contexte')),
                ('token_suffixe', models.CharField(blank=True, default='', max_length=6, verbose_name='Suffixe du jeton')),
                ('ip', models.CharField(blank=True, default='', max_length=64, verbose_name='Adresse IP')),
                ('user_agent', models.CharField(blank=True, default='', max_length=255, verbose_name='Navigateur (tronqué)')),
                ('langue', models.CharField(blank=True, default='', max_length=10, verbose_name='Langue affichée')),
                ('appareil_id', models.CharField(blank=True, db_index=True, default='', max_length=64, verbose_name='Identifiant d’appareil')),
                ('duree_s', models.PositiveIntegerField(default=0, verbose_name='Durée sur la page (s)')),
                ('terminee', models.BooleanField(default=False, verbose_name='Visite terminée')),
            ],
            options={
                'verbose_name': 'Visite externe (anti-fraude)',
                'verbose_name_plural': 'Visites externes (anti-fraude)',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddField(
            model_name='lead',
            name='appareil_id',
            field=models.CharField(blank=True, max_length=64, null=True, verbose_name='Identifiant d’appareil (traçage)'),
        ),
        migrations.AddField(
            model_name='visiteexterne',
            name='company',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='authentication.company', verbose_name='Société'),
        ),
        migrations.AddField(
            model_name='visiteexterne',
            name='lead',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='visites_externes', to='crm.lead', verbose_name='Lead rattaché'),
        ),
        migrations.AddIndex(
            model_name='visiteexterne',
            index=models.Index(fields=['company', 'appareil_id'], name='crm_visite_comp_app_idx'),
        ),
        migrations.AddIndex(
            model_name='visiteexterne',
            index=models.Index(fields=['company', 'ip'], name='crm_visite_comp_ip_idx'),
        ),
    ]
