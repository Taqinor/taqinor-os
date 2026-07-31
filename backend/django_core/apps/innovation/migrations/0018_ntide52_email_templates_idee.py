"""NTIDE52 — gabarits e-mail personnalisables (Paramètres → Avancé) pour les
3 étapes clés du cycle de vie d'une idée : réception (bienvenue), retenue,
réalisée. Additif : 6 colonnes ``blank=True, default=''`` sur
``InnovationSettings`` — vide = gabarit par défaut
(``models.EMAIL_IDEE_DEFAULTS``), aucun changement de comportement pour une
société qui n'a rien personnalisé.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        # Renumérotée 0012 -> 0018 à l'intégration : une lane soeur (NTIDE42-51)
        # avait déjà pris 0012..0017 sur cette app. On chaîne donc sur SA feuille.
        ('innovation', '0017_ntide48_idees_clients'),
    ]

    operations = [
        migrations.AddField(
            model_name='innovationsettings',
            name='email_recue_sujet',
            field=models.CharField(
                blank=True, default='', max_length=255,
                verbose_name='Sujet e-mail — idée reçue'),
        ),
        migrations.AddField(
            model_name='innovationsettings',
            name='email_recue_corps',
            field=models.TextField(
                blank=True, default='',
                verbose_name='Corps e-mail — idée reçue'),
        ),
        migrations.AddField(
            model_name='innovationsettings',
            name='email_retenue_sujet',
            field=models.CharField(
                blank=True, default='', max_length=255,
                verbose_name='Sujet e-mail — idée retenue'),
        ),
        migrations.AddField(
            model_name='innovationsettings',
            name='email_retenue_corps',
            field=models.TextField(
                blank=True, default='',
                verbose_name='Corps e-mail — idée retenue'),
        ),
        migrations.AddField(
            model_name='innovationsettings',
            name='email_realisee_sujet',
            field=models.CharField(
                blank=True, default='', max_length=255,
                verbose_name='Sujet e-mail — idée réalisée'),
        ),
        migrations.AddField(
            model_name='innovationsettings',
            name='email_realisee_corps',
            field=models.TextField(
                blank=True, default='',
                verbose_name='Corps e-mail — idée réalisée'),
        ),
    ]
