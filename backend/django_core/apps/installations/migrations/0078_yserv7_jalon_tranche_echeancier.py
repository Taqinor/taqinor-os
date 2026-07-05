from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('installations', '0077_yserv6_intervention_annulee'),
    ]

    operations = [
        migrations.AddField(
            model_name='jalonprojet',
            name='tranche_echeancier',
            field=models.CharField(
                blank=True, null=True, max_length=20,
                choices=[
                    ('acompte', 'Acompte'),
                    ('intermediaire', 'Intermédiaire'),
                    ('solde', 'Solde'),
                ]),
        ),
        migrations.AddField(
            model_name='jalonprojet',
            name='rappel_facturation_envoye',
            field=models.BooleanField(default=False),
        ),
    ]
