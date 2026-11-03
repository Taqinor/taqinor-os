"""ENF15 — l'unicité de la clé d'un item de checklist n'est plus globale.

``key`` perdait son ``unique=True`` (un champ unique sans portée société, signalé
par ``scripts/check_unique_scoping.py``). Deux contraintes la remplacent :
unicité (company, key) et — pour les items de catalogue, ``company`` NULL — une
contrainte partielle sur ``key`` seul (en SQL, NULL ≠ NULL : sans elle, la clé
d'un item partagé pourrait être dupliquée). Aucune donnée n'est touchée : les
clés existantes sont déjà uniques.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('onboarding', '0008_reseed_libelle_premier_devis'),
    ]

    operations = [
        migrations.AlterField(
            model_name='onboardingchecklistitem',
            name='key',
            field=models.SlugField(
                help_text="Clé stable (jamais renommée) — identifiant d'auto-complétion.",
                max_length=80),
        ),
        migrations.AddConstraint(
            model_name='onboardingchecklistitem',
            constraint=models.UniqueConstraint(
                fields=('company', 'key'),
                name='onboarding_item_cle_societe_unique'),
        ),
        migrations.AddConstraint(
            model_name='onboardingchecklistitem',
            constraint=models.UniqueConstraint(
                condition=models.Q(('company__isnull', True)),
                fields=('key',), name='onboarding_item_cle_catalogue_unique'),
        ),
    ]
