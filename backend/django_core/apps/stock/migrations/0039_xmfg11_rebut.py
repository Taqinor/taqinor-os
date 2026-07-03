from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0038_xpur10_tolerances_exceptions'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mouvementstock',
            name='type_mouvement',
            field=models.CharField(choices=[('entree', 'Entrée'), ('sortie', 'Sortie'), ('transfert', 'Transfert'), ('ajustement', 'Ajustement'), ('rebut', 'Rebut')], max_length=20),
        ),
        migrations.AddField(
            model_name='mouvementstock',
            name='motif_rebut',
            field=models.CharField(blank=True, choices=[('casse', 'Casse'), ('defaut', 'Défaut'), ('erreur', 'Erreur'), ('autre', 'Autre')], max_length=10, null=True),
        ),
        migrations.AddField(
            model_name='kitcomposant',
            name='taux_perte_pct',
            field=models.DecimalField(decimal_places=2, default=0, help_text='Taux de perte attendu (%) — gonfle le besoin planifié.', max_digits=5),
        ),
    ]
