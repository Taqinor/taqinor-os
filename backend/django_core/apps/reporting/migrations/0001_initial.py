import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authentication", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationPreference",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(choices=[("activites_en_retard", "Activités en retard"), ("garanties_expirantes", "Garanties expirant bientôt"), ("factures_impayees", "Factures impayées / en retard"), ("chantiers_a_planifier", "Chantiers à planifier / poser"), ("maintenance_due", "Visites de maintenance dues"), ("tickets_ouverts", "Tickets SAV ouverts"), ("stock_bas", "Stock bas")], max_length=40)),
                ("in_app", models.BooleanField(default=True)),
                ("company", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="notification_preferences", to="authentication.company")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notification_preferences", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Préférence de notification",
                "verbose_name_plural": "Préférences de notification",
                "unique_together": {("user", "event_type")},
            },
        ),
    ]
