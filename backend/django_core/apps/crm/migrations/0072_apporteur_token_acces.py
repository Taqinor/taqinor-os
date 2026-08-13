# NTCRM21 — Token d'accès dédié au portail apporteur (lecture seule),
# additif et nullable (les apporteurs existants sans token n'ont simplement
# pas encore de portail actif ; posé automatiquement au prochain `save()`).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0071_apporteur_deal_enregistre'),
    ]

    operations = [
        migrations.AddField(
            model_name='apporteur',
            name='token_acces',
            field=models.CharField(
                blank=True, editable=False, max_length=64, null=True,
                unique=True, verbose_name="Token d'accès portail"),
        ),
    ]
