# Hand-written migration (QX43 — mode commercial de bout en bout).
# Additif & réversible : AlterField sur Devis.mode_installation pour élargir la
# liste de choix — ajout de 'commercial' et renommage du label 'industriel'
# ('Industriel / Commercial' → 'Industriel'). Aucune donnée touchée : les choix
# ne sont validés qu'à l'écriture, les devis existants restent valides.
# Byte-identique tant qu'aucun devis commercial n'est créé.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventes', '0086_xsal14_ligne_section_note'),
    ]

    operations = [
        migrations.AlterField(
            model_name='devis',
            name='mode_installation',
            field=models.CharField(
                blank=True,
                choices=[
                    ('residentiel', 'Résidentiel'),
                    ('industriel', 'Industriel'),
                    ('commercial', 'Commercial'),
                    ('agricole', 'Agricole (pompage)'),
                ],
                max_length=20,
                null=True,
            ),
        ),
        # DevisPreset partage l'enum Devis.ModeInstallation — élargir aussi son
        # champ (sinon makemigrations --check détecte une dérive modèle↔migration).
        migrations.AlterField(
            model_name='devispreset',
            name='mode_installation',
            field=models.CharField(
                blank=True,
                choices=[
                    ('residentiel', 'Résidentiel'),
                    ('industriel', 'Industriel'),
                    ('commercial', 'Commercial'),
                    ('agricole', 'Agricole (pompage)'),
                ],
                max_length=20,
                null=True,
                verbose_name="Mode d'installation",
            ),
        ),
    ]
