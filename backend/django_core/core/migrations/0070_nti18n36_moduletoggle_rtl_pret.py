# NTI18N36 — drapeau `rtl_pret` par module sur `ModuleToggle` : la bascule RTL
# devient progressive (module par module) au lieu d'un interrupteur unique.
# Champ ADDITIF à défaut False : aucun module ne devient rétroactivement RTL,
# donc comportement strictement inchangé.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0069_ntwfl25_workflow_versioning'),
    ]

    operations = [
        migrations.AddField(
            model_name='moduletoggle',
            name='rtl_pret',
            field=models.BooleanField(
                default=False,
                help_text="Coché, ce module s'affiche en RTL pour un "
                          'utilisateur en langue de droite à gauche ; sinon '
                          'il reste en LTR.',
                verbose_name='Prêt pour le RTL'),
        ),
    ]
