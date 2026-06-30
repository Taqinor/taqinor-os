# FG22 — verrouillage de compte : compteur d'échecs + date de fin de verrou.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0013_customuser_poste_ref"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="failed_login_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="customuser",
            name="locked_until",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
