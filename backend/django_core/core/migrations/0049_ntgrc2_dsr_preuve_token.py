# NTGRC2 — portail PUBLIC de dépôt d'une demande de personne concernée.
#
# Deux champs ADDITIFS sur `core.DataSubjectRequest`, tous deux optionnels :
#   * `preuve`      — JSON de preuve du dépôt public (horodatage serveur, IP,
#                     user-agent). Vide pour une demande saisie en interne :
#                     le comportement historique est strictement inchangé.
#   * `token_suivi` — jeton opaque de suivi, DISTINCT de l'identifiant réel
#                     (aucune énumération possible).
#
# L'unicité de `token_suivi` est posée en DEUX TEMPS (jamais un
# `AddField(unique=True)` sur une table déjà peuplée, qui pose la contrainte et
# réécrit la table en un seul verrou) :
#   1. AddField nullable SANS unicité — instantané, aucune ligne touchée ;
#   2. AlterField(unique=True) — toutes les lignes existantes valent NULL et
#      Postgres autorise autant de NULL qu'on veut sous une unicité : aucun
#      backfill n'est nécessaire et aucune collision n'est possible.
# Réversible : les deux champs se retirent sans perte (rien d'existant ne les
# porte).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0048_aud820_sharingrule_unique'),
    ]

    operations = [
        migrations.AddField(
            model_name='datasubjectrequest',
            name='preuve',
            field=models.JSONField(
                blank=True, default=dict,
                help_text='Horodatage serveur, IP et user-agent du dépôt '
                          'public.',
                verbose_name='Preuve de dépôt'),
        ),
        # Étape 1 — colonne nullable, sans contrainte d'unicité.
        migrations.AddField(
            model_name='datasubjectrequest',
            name='token_suivi',
            field=models.CharField(
                blank=True, max_length=64, null=True,
                help_text="Jeton opaque de suivi public (jamais "
                          "l'identifiant réel).",
                verbose_name='Jeton de suivi'),
        ),
        # Étape 2 — l'unicité, sur une colonne entièrement NULL.
        migrations.AlterField(
            model_name='datasubjectrequest',
            name='token_suivi',
            field=models.CharField(
                blank=True, max_length=64, null=True, unique=True,
                help_text="Jeton opaque de suivi public (jamais "
                          "l'identifiant réel).",
                verbose_name='Jeton de suivi'),
        ),
    ]
