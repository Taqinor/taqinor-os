# NTPAY8 — `ParametrePaie` et `BaremeIR` rattachés à `PaysPaie`.
#
# Les deux jeux versionnés étaient IMPLICITEMENT marocains. Le champ `pays` est
# NULLABLE : toutes les lignes existantes restent à NULL (= jeu marocain non
# étiqueté) et la résolution `services._filtrer_par_pays` continue de les
# servir aux profils sans pays comme aux profils MA — comportement mono-pays
# strictement identique.
#
# L'unicité passe de (société, date d'effet) à (société, PAYS, date d'effet),
# pour que deux pays actifs aient chacun leur jeu au 1ᵉʳ janvier. Postgres
# considérant deux NULL comme distincts, la garantie historique est REPRISE à
# l'identique par une contrainte PARTIELLE sur les lignes sans pays : aucune
# protection n'est perdue.
#
# Migration ADDITIVE (un champ nullable + des contraintes) : aucune donnée
# réécrite, aucun jeu existant modifié.
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('paie', '0050_ntpay7_pays_paie'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='parametrepaie',
            unique_together=set(),
        ),
        migrations.AlterUniqueTogether(
            name='baremeir',
            unique_together=set(),
        ),
        migrations.AddField(
            model_name='parametrepaie',
            name='pays',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='parametres', to='paie.payspaie',
                verbose_name='Pays de paie'),
        ),
        migrations.AddField(
            model_name='baremeir',
            name='pays',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='baremes_ir', to='paie.payspaie',
                verbose_name='Pays de paie'),
        ),
        migrations.AddConstraint(
            model_name='parametrepaie',
            constraint=models.UniqueConstraint(
                fields=('company', 'pays', 'date_effet'),
                name='uniq_parametre_paie_pays_date'),
        ),
        migrations.AddConstraint(
            model_name='parametrepaie',
            constraint=models.UniqueConstraint(
                condition=models.Q(('pays__isnull', True)),
                fields=('company', 'date_effet'),
                name='uniq_parametre_paie_date_sans_pays'),
        ),
        migrations.AddConstraint(
            model_name='baremeir',
            constraint=models.UniqueConstraint(
                fields=('company', 'pays', 'date_effet'),
                name='uniq_bareme_ir_pays_date'),
        ),
        migrations.AddConstraint(
            model_name='baremeir',
            constraint=models.UniqueConstraint(
                condition=models.Q(('pays__isnull', True)),
                fields=('company', 'date_effet'),
                name='uniq_bareme_ir_date_sans_pays'),
        ),
    ]
