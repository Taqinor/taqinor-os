from django.db import migrations, models


class Migration(migrations.Migration):
    """L-2OPT — ``LigneDevis.variante`` : à quelle option la ligne appartient.

    ADDITIVE ONLY, et volontairement la plus plate possible : une colonne
    ``varchar(8)`` par défaut VIDE, sans index, sans contrainte d'unicité et
    SANS AUCUN backfill. Toute ligne existante vaut donc '' = « commune aux
    deux options », c'est-à-dire EXACTEMENT le comportement d'aujourd'hui :
    aucun devis déjà en base ne change de contenu, de total ni de rendu.

    Entièrement révertable (``RemoveField`` inverse automatique).
    """

    dependencies = [
        ('ventes', '0101_l_sect_sections'),
    ]

    operations = [
        migrations.AddField(
            model_name='lignedevis',
            name='variante',
            field=models.CharField(
                max_length=8, blank=True, default='',
                choices=[
                    ('', 'Commune aux deux options'),
                    ('sans', 'Option « sans batterie » seulement'),
                    ('avec', 'Option « avec batterie » seulement'),
                ],
                help_text="Option à laquelle la ligne appartient : vide = "
                          "commune aux deux options (défaut), « sans » ou "
                          "« avec » = propre à cette option-là."),
        ),
    ]
