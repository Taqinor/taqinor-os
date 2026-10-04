# AGR401 (Groupe AGR, 02/10/2026) — ``pompe_cv`` décrit la pompe ACTUELLE :
# renommé ``pompe_actuelle_cv`` sur Lead et SiteProfile. Les données sont
# conservées (elles décrivent déjà la pompe existante). Réversible : le retour
# arrière renomme dans l'autre sens. Aucun devis n'est touché (D-AGR-13).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0118_agr400_lead_pompage'),
    ]

    operations = [
        migrations.RenameField(
            model_name='lead',
            old_name='pompe_cv',
            new_name='pompe_actuelle_cv',
        ),
        migrations.AlterField(
            model_name='lead',
            name='pompe_actuelle_cv',
            field=models.DecimalField(blank=True, decimal_places=2, help_text="Question à l'appel : « Votre pompe actuelle fait combien de chevaux ? C'est écrit sur sa plaque. » (vide = pas encore posée).", max_digits=6, null=True, verbose_name='Pompe actuelle (CV)'),
        ),
        migrations.RenameField(
            model_name='siteprofile',
            old_name='pompe_cv',
            new_name='pompe_actuelle_cv',
        ),
        migrations.AlterField(
            model_name='siteprofile',
            name='pompe_actuelle_cv',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True, verbose_name='Pompe actuelle (CV)'),
        ),
    ]
