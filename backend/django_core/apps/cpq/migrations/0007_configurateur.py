import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0023_yhard1_encrypt_totp_secret"),
        ("ventes", "0087_ntcpq4_listeprix_segment"),
        ("cpq", "0006_approbation_remise"),
    ]

    operations = [
        migrations.CreateModel(
            name="QuestionConfigurateur",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID"),
                ),
                ("ordre", models.PositiveIntegerField(default=0)),
                ("texte", models.CharField(max_length=255)),
                ("type", models.CharField(
                    choices=[
                        ("CHOIX_UNIQUE", "Choix unique"),
                        ("CHOIX_MULTIPLE", "Choix multiple"),
                        ("NUMERIQUE", "Numérique"),
                    ],
                    default="CHOIX_UNIQUE", max_length=20)),
                ("options", models.JSONField(blank=True, default=dict)),
                ("actif", models.BooleanField(default=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cpq_questions_configurateur",
                        to="authentication.company"),
                ),
            ],
            options={
                "verbose_name": "Question configurateur",
                "verbose_name_plural": "Questions configurateur",
                "ordering": ["ordre", "id"],
            },
        ),
        migrations.CreateModel(
            name="SessionConfigurateur",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID"),
                ),
                ("token", models.UUIDField(
                    default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="cpq_sessions_configurateur",
                        to="authentication.company"),
                ),
                (
                    "devis",
                    models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="cpq_sessions_configurateur",
                        to="ventes.devis"),
                ),
            ],
            options={
                "verbose_name": "Session configurateur",
                "verbose_name_plural": "Sessions configurateur",
                "ordering": ["-created_at", "id"],
            },
        ),
        migrations.CreateModel(
            name="ReponseConfigurateur",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True,
                        serialize=False, verbose_name="ID"),
                ),
                ("valeur", models.JSONField(blank=True, null=True)),
                (
                    "question",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reponses",
                        to="cpq.questionconfigurateur"),
                ),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reponses",
                        to="cpq.sessionconfigurateur"),
                ),
            ],
            options={
                "verbose_name": "Réponse configurateur",
                "verbose_name_plural": "Réponses configurateur",
                "ordering": ["session_id", "question_id"],
            },
        ),
        migrations.AddIndex(
            model_name="questionconfigurateur",
            index=models.Index(
                fields=["company", "actif"], name="cpq_question_co_act"),
        ),
        migrations.AddIndex(
            model_name="sessionconfigurateur",
            index=models.Index(
                fields=["company", "updated_at"], name="cpq_session_co_upd"),
        ),
        migrations.AddConstraint(
            model_name="reponseconfigurateur",
            constraint=models.UniqueConstraint(
                fields=["session", "question"],
                name="cpq_reponse_unique_sess_q"),
        ),
    ]
