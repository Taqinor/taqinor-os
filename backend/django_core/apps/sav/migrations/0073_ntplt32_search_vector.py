# NTPLT32 — colonne plein-texte ``search_vector`` (tsvector, NULL = pas encore
# indexée → la recherche applique ``icontains`` à la ligne). Nullable, sans
# défaut : ajout instantané, aucune réécriture de table. Remplissage :
# ``manage.py rebuild_search_index --app sav`` ; entretien : signal
# ``post_save`` (``core.recherche_fts``). Réversible.
import django.contrib.postgres.search
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sav', '0072_acsv55_equipement_garantie_plancher'),
    ]

    operations = [
        migrations.AddField(
            model_name='equipement',
            name='search_vector',
            field=django.contrib.postgres.search.SearchVectorField(
                blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='ticket',
            name='search_vector',
            field=django.contrib.postgres.search.SearchVectorField(
                blank=True, editable=False, null=True),
        ),
    ]
