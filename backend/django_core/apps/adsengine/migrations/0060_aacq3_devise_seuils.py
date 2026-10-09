"""AACQ3 — Devise des seuils (``RulePolicy``) et des plafonds
(``GuardrailConfig``), posée par le serveur à la saisie (D-AACQ-1 = a).

ADDITIVE : deux colonnes texte, défaut vide (= saisie antérieure, sémantique
MAD). Revertable : le retour arrière supprime les colonnes.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adsengine', '0059_aacq76_engineaction_approved_fingerprint'),
    ]

    operations = [
        migrations.AddField(
            model_name='guardrailconfig',
            name='ceiling_currency',
            field=models.CharField(
                blank=True, default='', max_length=3,
                verbose_name='Devise des plafonds (posée par le serveur)'),
        ),
        migrations.AddField(
            model_name='rulepolicy',
            name='threshold_currency',
            field=models.CharField(
                blank=True, default='', max_length=3,
                verbose_name='Devise des seuils (posée par le serveur)'),
        ),
    ]
