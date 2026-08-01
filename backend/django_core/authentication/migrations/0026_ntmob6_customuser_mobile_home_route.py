"""NTMOB6 — sélecteur de démarrage par rôle : ``mobile_home_route``.

Additive : nouvelle colonne nullable sur ``CustomUser``, tri-état (NULL = pas
encore décidé, '' = opt-out explicite, sinon une route mobile mémorisée).
Aucune migration existante modifiée ; comportement inchangé pour tout compte
existant (NULL par défaut → aucun redémarrage automatique tant que
l'utilisateur ne se connecte pas d'un viewport mobile).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0025_company_est_demo_mode_presentation'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='mobile_home_route',
            field=models.CharField(
                blank=True, default=None, max_length=32, null=True),
        ),
    ]
