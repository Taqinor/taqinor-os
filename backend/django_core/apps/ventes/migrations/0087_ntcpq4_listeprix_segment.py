from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ventes", "0086_xsal14_ligne_section_note"),
    ]

    operations = [
        migrations.AddField(
            model_name="listeprix",
            name="segment_client",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
    ]
