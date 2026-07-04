# YEVNT5 — ajoute le choix d'action NOTIFY au Journal d'activité (chaque
# notification émise par notifications.notify() laisse une entrée d'audit).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0002_auditlog_security_alert"),
    ]

    operations = [
        migrations.AlterField(
            model_name="auditlog",
            name="action",
            field=models.CharField(
                choices=[
                    ("create", "Création"),
                    ("update", "Modification"),
                    ("delete", "Suppression"),
                    ("status", "Changement de statut"),
                    ("login", "Connexion"),
                    ("logout", "Déconnexion"),
                    ("login_failed", "Échec de connexion"),
                    ("security_alert", "Alerte de sécurité"),
                    ("pdf", "PDF généré"),
                    ("email", "Email envoyé"),
                    ("whatsapp", "WhatsApp envoyé"),
                    ("export", "Export"),
                    ("accept", "Devis accepté"),
                    ("refuse", "Devis refusé"),
                    ("notify", "Notification envoyée"),
                ],
                db_index=True,
                max_length=20,
            ),
        ),
    ]
