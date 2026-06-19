# Generated for L579 — tag de TYPE d'équipement additif (nullable) sur Categorie.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0019_retourfournisseur_ligneretourfournisseur'),
    ]

    operations = [
        migrations.AddField(
            model_name='categorie',
            name='type_equipement',
            field=models.CharField(
                blank=True,
                choices=[
                    ('panneau', 'Panneau'),
                    ('onduleur', 'Onduleur'),
                    ('batterie', 'Batterie'),
                    ('structure', 'Structure'),
                    ('cable', 'Câble'),
                    ('protection', 'Protection'),
                    ('pompe', 'Pompe'),
                    ('variateur', 'Variateur'),
                    ('compteur', 'Compteur'),
                    ('accessoire', 'Accessoire'),
                ],
                help_text="Type d'équipement (optionnel) pour filtrer les "
                          "slots de chantier par TYPE, quel que soit le "
                          "libellé de la catégorie. Vide = non typée "
                          "(comportement historique).",
                max_length=20,
                null=True,
            ),
        ),
    ]
