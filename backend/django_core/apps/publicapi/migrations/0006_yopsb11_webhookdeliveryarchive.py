from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("publicapi", "0005_webhookdelivery_event_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="WebhookDeliveryArchive",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID"),
                ),
                (
                    "original_id",
                    models.BigIntegerField(
                        help_text="PK de la WebhookDelivery d'origine "
                                  "(table vive)."),
                ),
                ("company_id", models.BigIntegerField(blank=True, null=True)),
                ("webhook_id", models.BigIntegerField(blank=True, null=True)),
                ("event", models.CharField(max_length=50)),
                ("event_id", models.CharField(
                    blank=True, default="", max_length=36)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("status", models.CharField(max_length=10)),
                ("response_status", models.IntegerField(blank=True, null=True)),
                ("error", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField()),
                ("archived_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Livraison webhook (archive)",
                "verbose_name_plural": "Livraisons webhook (archive)",
            },
        ),
    ]
