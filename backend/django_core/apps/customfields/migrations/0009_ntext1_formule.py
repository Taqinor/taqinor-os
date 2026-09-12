"""NTEXT1 — champ personnalisé CALCULÉ (type FORMULA).

Purement ADDITIF et RÉVERSIBLE : un ``TextField`` vide par défaut (donc aucun
changement de comportement sur l'existant — un champ n'est calculé que si un
admin choisit le type ``formula`` et renseigne une formule). ``type`` reste un
``CharField(max_length=12)`` : ``'formula'`` (7 caractères) y tient déjà, pas
d'``AlterField`` nécessaire.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customfields', '0008_ntext38_verrouille'),
    ]

    operations = [
        migrations.AddField(
            model_name='customfielddef',
            name='formule',
            field=models.TextField(
                blank=True, default='', verbose_name='Formule'),
        ),
    ]
