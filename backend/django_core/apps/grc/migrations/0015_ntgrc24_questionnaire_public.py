# NTGRC24 — portail PUBLIC fournisseur : jeton d'accès opaque à durée de vie
# bornée + preuve de soumission. Quatre champs ADDITIFS, tous nullables ou à
# défaut vide : les questionnaires existants restent valides et sans lien
# public (aucun n'est exposé par accident).
#
# `token_acces` est ajouté SANS contrainte d'unicité, puis l'unicité est posée
# par un `AlterField` séparé — jamais un `AddField(unique=True)` d'un seul
# tenant sur une table déjà peuplée (piège connu du dépôt : la migration
# échoue en production dès qu'il existe plus d'une ligne). Aucun backfill
# n'est nécessaire ici : la colonne naît NULL partout et Postgres n'agrège
# jamais les NULL dans un index unique.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('grc', '0014_ntgrc23_modele_questionnaire'),
    ]

    operations = [
        migrations.AddField(
            model_name='questionnairefournisseur',
            name='token_acces',
            field=models.CharField(
                blank=True,
                help_text="Jeton opaque du portail fournisseur (jamais l'id "
                          'réel).',
                max_length=64, null=True,
                verbose_name="Jeton d'accès public"),
        ),
        migrations.AlterField(
            model_name='questionnairefournisseur',
            name='token_acces',
            field=models.CharField(
                blank=True,
                help_text="Jeton opaque du portail fournisseur (jamais l'id "
                          'réel).',
                max_length=64, null=True, unique=True,
                verbose_name="Jeton d'accès public"),
        ),
        migrations.AddField(
            model_name='questionnairefournisseur',
            name='token_expire_le',
            field=models.DateTimeField(
                blank=True,
                help_text='Passée cette date le lien ne répond plus : un lien '
                          'de collecte de données qui vit éternellement est '
                          'une porte ouverte.',
                null=True, verbose_name='Expiration du lien public'),
        ),
        migrations.AddField(
            model_name='questionnairefournisseur',
            name='date_soumission',
            field=models.DateTimeField(
                blank=True,
                help_text='Horodatage SERVEUR de la soumission publique.',
                null=True, verbose_name='Soumis le'),
        ),
        migrations.AddField(
            model_name='questionnairefournisseur',
            name='preuve_soumission',
            field=models.JSONField(
                blank=True, default=dict,
                help_text='IP et user-agent du fournisseur, posés côté '
                          'serveur.',
                verbose_name='Preuve de soumission'),
        ),
    ]
