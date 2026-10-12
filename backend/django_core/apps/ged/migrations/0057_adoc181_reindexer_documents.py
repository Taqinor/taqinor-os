"""ADOC181 — indexe une fois les documents GED existants dont `search_vector`
est NULL (créés avant ADOC24 / ADOC180), sans rien changer d'autre.

Réutilise `services.update_search_vector` (une seule implémentation du
vecteur) : il ne met à jour QUE la colonne `search_vector` (`UPDATE … SET
search_vector`), donc `updated_at` et les autres colonnes restent intacts.
Idempotent (le filtre `search_vector IS NULL` exclut ce qui est déjà indexé) ;
inverse no-op. Les documents en corbeille (`supprime_le`) ne sont pas touchés."""
from django.db import migrations

LOT = 200


def reindexer_documents(apps, schema_editor):
    from apps.ged.services import update_search_vector

    Document = apps.get_model('ged', 'Document')
    qs = Document.objects.filter(
        search_vector__isnull=True, supprime_le__isnull=True,
    ).only('pk', 'description', 'custom_data')
    for document in qs.iterator(chunk_size=LOT):
        update_search_vector(document)


class Migration(migrations.Migration):

    dependencies = [
        ('ged', '0056_adoc75_routages_defaut'),
    ]

    operations = [
        migrations.RunPython(reindexer_documents, migrations.RunPython.noop),
    ]
