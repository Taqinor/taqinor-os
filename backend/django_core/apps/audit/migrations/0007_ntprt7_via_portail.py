"""NTPRT7 — Audit des accès portail.

Migration STRICTEMENT ADDITIVE : un nouveau champ ``via_portail`` (défaut
``False`` — aucune ligne existante ne change de sens), un nouveau choix
``payment`` sur ``action`` (paiement initié depuis le portail — jamais une
transaction financière réelle), un index composite pour l'onglet « Accès
portail » du journal. Aucune donnée déplacée, aucun 2e système d'audit créé.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('audit', '0006_auditlog_hash_chain'),
    ]

    operations = [
        migrations.AlterField(
            model_name='auditlog',
            name='action',
            field=models.CharField(
                choices=[
                    ('create', 'Création'), ('update', 'Modification'),
                    ('delete', 'Suppression'),
                    ('status', 'Changement de statut'),
                    ('login', 'Connexion'), ('logout', 'Déconnexion'),
                    ('login_failed', 'Échec de connexion'),
                    ('security_alert', 'Alerte de sécurité'),
                    ('pdf', 'PDF généré'), ('email', 'Email envoyé'),
                    ('whatsapp', 'WhatsApp envoyé'), ('export', 'Export'),
                    ('accept', 'Devis accepté'), ('refuse', 'Devis refusé'),
                    ('notify', 'Notification envoyée'),
                    ('switch_company', 'Changement de société active'),
                    ('payment', 'Paiement'),
                ],
                db_index=True, max_length=20),
        ),
        migrations.AddField(
            model_name='auditlog',
            name='via_portail',
            field=models.BooleanField(
                default=False, db_index=True, verbose_name='Via portail'),
        ),
        # L'index (company, via_portail, -timestamp) est posé par 0008 en
        # CONCURRENT (YOPSB6) : audit_auditlog est une table vivante, un
        # AddIndex nu la verrouillerait en écriture pendant la construction.
    ]
