"""MRY0 — ``MetaLeadMirror.origine`` : webhook temps réel vs pull de rattrapage.

Purement ADDITIF (CharField(16) vide par défaut, aucune contrainte) : les
lignes existantes gardent une origine vide (« inconnue »), ce qui est la
vérité — avant cette colonne, les deux chemins étaient indiscernables.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adsengine', '0052_rulepolicy_template_key_derive_catalogue'),
    ]

    operations = [
        migrations.AddField(
            model_name='metaleadmirror',
            name='origine',
            field=models.CharField(
                blank=True, default='', max_length=16,
                choices=[('webhook', 'Webhook temps réel'),
                         ('pull', 'Pull de rattrapage')],
                verbose_name='Origine du miroir'),
        ),
    ]
