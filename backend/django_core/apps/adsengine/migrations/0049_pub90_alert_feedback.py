# PUB90 — retour utile/faux-positif sur les anomalies + précision par détecteur
# + throttle brake-only. Migration ADDITIVE (4 champs nullables/à défaut vide sur
# AnomalyEvent : jamais destructive, entièrement revertable).
#
# Renumérotée 0090 → 0049 au fold de lane X2 dans dev-pub2 (le 0090 était un
# placeholder orchestrateur évitant toute collision avec les migrations du lot 1
# de Groupe PUB en isolation) ; dépendance re-pointée sur la vraie tête de la
# chaîne adsengine (0048_pub82_script_beats).
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('adsengine', '0048_pub82_script_beats'),
    ]

    operations = [
        migrations.AddField(
            model_name='anomalyevent',
            name='detector',
            field=models.CharField(
                blank=True, default='', max_length=40,
                verbose_name='Détecteur'),
        ),
        migrations.AddField(
            model_name='anomalyevent',
            name='feedback',
            field=models.CharField(
                blank=True,
                choices=[('useful', 'Utile'),
                         ('false_positive', 'Faux positif')],
                default='', max_length=16,
                verbose_name='Retour utilisateur'),
        ),
        migrations.AddField(
            model_name='anomalyevent',
            name='feedback_at',
            field=models.DateTimeField(
                blank=True, null=True, verbose_name='Retour le'),
        ),
        migrations.AddField(
            model_name='anomalyevent',
            name='feedback_by',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='adsengine_anomaly_feedbacks',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Retour par'),
        ),
    ]
