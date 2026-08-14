"""NTWMS8 — code de check-in chauffeur sur le rendez-vous transporteur.

Additif et réversible : une colonne texte à défaut vide, plus une unicité
CONDITIONNELLE (code non vide) par société — les rendez-vous historiques sans
code ne s'entre-bloquent donc jamais. Le code est généré côté serveur
(``secrets``) au premier ``save()``.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0090_ntwms7_quai_rendez_vous'),
    ]

    operations = [
        migrations.AddField(
            model_name='rendezvoustransporteur',
            name='code_checkin',
            field=models.CharField(blank=True, default='', max_length=12),
        ),
        migrations.AddConstraint(
            model_name='rendezvoustransporteur',
            constraint=models.UniqueConstraint(
                condition=models.Q(('code_checkin', ''), _negated=True),
                fields=('company', 'code_checkin'),
                name='stock_rdvtransporteur_code_checkin_uniq'),
        ),
    ]
