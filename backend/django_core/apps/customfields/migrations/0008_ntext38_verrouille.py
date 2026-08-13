"""NTEXT38 — verrou anti-casse sur les objets/champs personnalisés.

Purement ADDITIF et RÉVERSIBLE : deux booléens ``default=False`` (donc aucun
changement de comportement sur l'existant — rien n'est verrouillé avant qu'un
admin ou une install de package ne le demande).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customfields', '0007_xplt17_champ_ia'),
    ]

    operations = [
        migrations.AddField(
            model_name='customfielddef',
            name='verrouille',
            field=models.BooleanField(default=False, verbose_name='Verrouillé'),
        ),
        migrations.AddField(
            model_name='customobjectdef',
            name='verrouille',
            field=models.BooleanField(default=False, verbose_name='Verrouillé'),
        ),
    ]
