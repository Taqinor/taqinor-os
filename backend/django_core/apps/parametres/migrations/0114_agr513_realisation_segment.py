# AGR513 (Groupe AGR, 02/10/2026 ; D-AGR-10) — colonne `segment` NULLABLE sur
# `Realisation` : la preuve J4 est filtrée dans les deux sens (un lead agricole
# ne voit qu'une réalisation agricole, un lead non agricole jamais une
# agricole). Migration additive et réversible ; aucune donnée n'est écrite.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parametres', '0113_agr208_reperes_energie_agricole'),
    ]

    operations = [
        migrations.AddField(
            model_name='realisation',
            name='segment',
            field=models.CharField(
                blank=True,
                choices=[
                    ('residentiel', 'Résidentiel'),
                    ('commercial', 'Commercial'),
                    ('industriel', 'Industriel'),
                    ('agricole', 'Agricole (pompage)'),
                ],
                help_text="Type d'installation. Une réalisation agricole "
                          "n'est montrée qu'à un lead agricole, et "
                          "inversement.",
                max_length=20, null=True, verbose_name='Segment'),
        ),
    ]
