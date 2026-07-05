# XKB34 — S'abonner aux enregistrements (followers). Nouveau modèle générique
# `records.Follower` (même mécanisme ContentType qu'Activity/Comment). Purement
# additif : aucune table/colonne existante modifiée.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("authentication", "0008_customuser_avatar_key_customuser_poste"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("records", "0009_activitytype_enchainement"),
    ]

    operations = [
        migrations.CreateModel(
            name="Follower",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("object_id", models.PositiveIntegerField()),
                ("sous_type", models.CharField(blank=True, default="", max_length=40)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="followers", to="authentication.company")),
                ("content_type", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="contenttypes.contenttype")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="enregistrements_suivis", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Abonné (follower)",
                "verbose_name_plural": "Abonnés (followers)",
                "ordering": ["-created_at", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="follower",
            index=models.Index(fields=["content_type", "object_id"], name="records_follower_ct_oid_idx"),
        ),
        migrations.AddIndex(
            model_name="follower",
            index=models.Index(fields=["user"], name="records_follower_user_idx"),
        ),
        migrations.AlterUniqueTogether(
            name="follower",
            unique_together={("user", "content_type", "object_id", "sous_type")},
        ),
    ]
