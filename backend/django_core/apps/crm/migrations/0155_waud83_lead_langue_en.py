"""WAUD83 (D-WAUD-14=a) — ``Lead.langue_preferee`` accepte « en ».

Un lead venu d'une page anglaise était rangé SANS langue (relance en français
sans que rien ne le dise). « en » est un marqueur : seule la liste des choix
change, aucune donnée n'est touchée. Retour arrière : sans danger (les valeurs
« en » déjà écrites resteraient lisibles, hors liste de choix).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0154_acvi6_empreintes_opposition_existantes'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lead',
            name='langue_preferee',
            field=models.CharField(
                blank=True, null=True, max_length=10,
                choices=[('fr', 'Français'), ('darija', 'Darija'),
                         ('en', 'English')]),
        ),
    ]
