"""NTI18N34 — langue de secours (fallback), distincte du FR codé en dur.

Additif : défaut 'fr' = comportement historique inchangé pour toute société
existante. Consommé par `apps.parametres.i18n_resolver.resolve_langue_sortie`
(NTI18N4), qui la lisait déjà défensivement avant l'arrivée de ce champ.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0092_nti18n26_templates_en_ar'),
    ]

    operations = [
        migrations.AddField(
            model_name='companyprofile',
            name='langue_repli',
            field=models.CharField(
                choices=[('fr', 'Français'), ('en', 'English'),
                         ('ar', 'العربية')],
                default='fr', max_length=2,
                help_text='Langue de repli des documents générés (PDF) '
                          'quand ni une langue explicite ni la langue du '
                          'client ne sont connues. Défaut FR (comportement '
                          'historique).',
                verbose_name='Langue de secours'),
        ),
    ]
