# CAD158 (décision fondateur du 21/09/2026, Q24) — `facture_hiver` porte
# enfin sa question d'appel en `help_text` (mois ou deux mois ? le montant
# enregistré est toujours MENSUEL). AlterField de métadonnée pure : aucune
# colonne, aucune donnée touchée.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0111_cad144_contact_secondaire'),
    ]

    operations = [
        migrations.AlterField(
            model_name='lead',
            name='facture_hiver',
            field=models.DecimalField(blank=True, decimal_places=2, help_text="Question à l'appel : « Votre facture d'électricité, elle est de combien ? Elle couvre un mois ou deux mois ? » — le montant ENREGISTRÉ est toujours MENSUEL : une facture de deux mois est divisée par deux à la saisie.", max_digits=10, null=True),
        ),
    ]
