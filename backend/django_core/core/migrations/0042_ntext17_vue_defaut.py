# NTEXT17 — vue par DÉFAUT d'une liste : `est_defaut` + `role_tier` optionnel
# sur VuePersonnalisee. Purement ADDITIF (défauts False / '' : aucune vue
# existante ne devient un défaut) + un index de résolution.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0041_ntext16_vuepersonnalisee'),
    ]

    operations = [
        migrations.AddField(
            model_name='vuepersonnalisee',
            name='est_defaut',
            field=models.BooleanField(
                default=False,
                help_text="Vue chargée automatiquement à l'ouverture de la "
                          "liste, pour la portée de cette ligne.",
                verbose_name='Vue par défaut'),
        ),
        migrations.AddField(
            model_name='vuepersonnalisee',
            name='role_tier',
            field=models.CharField(
                blank=True, default='',
                help_text='Palier de rôle visé par le défaut (« normal », '
                          '« responsable », « admin »). Vide = défaut '
                          'société.',
                max_length=40, verbose_name='Palier de rôle'),
        ),
        migrations.AddIndex(
            model_name='vuepersonnalisee',
            index=models.Index(fields=['company', 'cible', 'est_defaut'],
                               name='core_vueperso_defaut_idx'),
        ),
    ]
