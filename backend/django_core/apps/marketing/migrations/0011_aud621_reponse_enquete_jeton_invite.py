# AUD621 — trace du jeton d'invitation consommé par une soumission d'enquête.
#
# En mode invités-seulement, `tentatives_max` n'était appliqué que si
# `contact_ref` était fourni — un champ LIBRE du POST, jamais vérifié contre
# une identité réelle : l'omettre ou le changer contournait la limite, et le
# jeton `?invite=` lui-même n'était jamais consommé (réutilisable à l'infini).
# Le compte des tentatives se fait désormais sur ce jeton, émis par l'ERP.
#
# Additive et revertable (colonne texte vide par défaut + index).
#
# Écrite à la main (la chaîne d'import WeasyPrint bloque makemigrations sur
# cet hôte — voir 0006_ntmkt16_dernier_numero_version.py).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('marketing', '0010_aud618_enquete_nps_unique_chantier'),
    ]

    operations = [
        migrations.AddField(
            model_name='reponseenquete',
            name='jeton_invite',
            field=models.CharField(
                blank=True, db_index=True, default='', max_length=64,
                verbose_name="Jeton d'invitation consommé (ZMKT11/AUD621)"),
        ),
    ]
