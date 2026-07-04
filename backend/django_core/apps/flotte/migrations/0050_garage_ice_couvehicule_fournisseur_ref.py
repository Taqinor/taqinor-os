from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flotte', '0049_relevetelematique_codes_defaut'),
    ]

    operations = [
        migrations.AddField(
            model_name='garage',
            name='ice',
            field=models.CharField(
                blank=True, max_length=15,
                help_text="Identifiant Commun de l'Entreprise (15 chiffres).",
                verbose_name='ICE'),
        ),
        migrations.AddField(
            model_name='garage',
            name='identifiant_fiscal',
            field=models.CharField(
                blank=True, max_length=20, verbose_name='Identifiant fiscal (IF)'),
        ),
        migrations.AddField(
            model_name='coutvehicule',
            name='fournisseur_id_ref',
            field=models.PositiveIntegerField(
                blank=True, null=True,
                verbose_name='Fournisseur (référentiel stock)'),
        ),
        migrations.AlterField(
            model_name='coutvehicule',
            name='fournisseur',
            field=models.CharField(
                blank=True, max_length=150,
                help_text='Repli en saisie libre pour un fournisseur ponctuel — '
                          'préférer `fournisseur_id` (référentiel '
                          'stock.Fournisseur, qui porte déjà ICE/IF/RC/RIB) '
                          'quand il existe.',
                verbose_name='Fournisseur'),
        ),
    ]
