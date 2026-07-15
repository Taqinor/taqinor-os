# Hand-written migration (XSAL14 — lignes de section et de note dans le devis).
# Additif & réversible :
#   • type_ligne (produit [défaut] / section / note) + ordre (défaut 0) : toute
#     ligne existante devient une ligne 'produit' d'ordre 0 → rendu et totaux
#     octet-identiques quand aucune section/note n'est utilisée.
#   • produit / quantite / prix_unitaire deviennent nullables : une ligne de
#     section/note ne porte NI produit NI prix NI quantité. Les lignes produit
#     existantes restent renseignées (aucune donnée modifiée).
#   • Meta.ordering = ['ordre', 'id'] : ordre d'affichage déterministe ;
#     ordre=0 partout → tri par id = ordre d'insertion historique.
# Entièrement réversible.
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0085_xsal5_ligne_optionnelle'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='lignedevis',
            options={
                'ordering': ['ordre', 'id'],
                'verbose_name': 'Ligne de Devis',
                'verbose_name_plural': 'Lignes de Devis',
            },
        ),
        migrations.AddField(
            model_name='lignedevis',
            name='type_ligne',
            field=models.CharField(
                choices=[('produit', 'Produit'), ('section', 'Section'),
                         ('note', 'Note')],
                default='produit', max_length=10,
                help_text='Type de ligne : produit (défaut), section '
                          '(intertitre) ou note (texte sans prix).'),
        ),
        migrations.AddField(
            model_name='lignedevis',
            name='ordre',
            field=models.PositiveIntegerField(
                default=0,
                help_text="Position d'affichage de la ligne (sections/notes "
                          'incluses). 0 par défaut = ordre historique (par id).'),
        ),
        migrations.AlterField(
            model_name='lignedevis',
            name='produit',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='lignes_devis', to='stock.produit'),
        ),
        migrations.AlterField(
            model_name='lignedevis',
            name='quantite',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AlterField(
            model_name='lignedevis',
            name='prix_unitaire',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=10, null=True),
        ),
    ]
