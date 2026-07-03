# XKB9 — Sections Espace de travail / Privé / Partagé + ACL par utilisateur.
# ``KbArticle.visibilite`` (défaut ``workspace`` — RÉTRO-COMPATIBLE, comportement
# historique inchangé) + ``KbArticleAcl.utilisateur`` nullable (ACL nominative,
# en plus de l'ACL par-rôle KB7 déjà existante ; ``role`` devient blank pour
# les lignes par-utilisateur). Entièrement additive, réversible par
# ``git revert`` / ``migrate kb 0008``.
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("kb", "0008_kbarticle_parent_ordre"),
    ]

    operations = [
        migrations.AddField(
            model_name="kbarticle",
            name="visibilite",
            field=models.CharField(
                choices=[
                    ("workspace", "Espace de travail"),
                    ("prive", "Privé"),
                    ("partage", "Partagé"),
                ],
                default="workspace",
                max_length=10,
                verbose_name="Visibilité",
            ),
        ),
        migrations.AlterField(
            model_name="kbarticleacl",
            name="role",
            field=models.CharField(
                blank=True,
                choices=[
                    ("admin", "Administrateur"),
                    ("responsable", "Responsable"),
                    ("normal", "Utilisateur"),
                ],
                default="",
                max_length=20,
                verbose_name="Palier de rôle autorisé",
            ),
        ),
        migrations.AddField(
            model_name="kbarticleacl",
            name="utilisateur",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="kb_app_acls",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Utilisateur autorisé",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="kbarticleacl",
            unique_together={
                ("article", "role", "niveau"),
                ("article", "utilisateur", "niveau"),
            },
        ),
    ]
