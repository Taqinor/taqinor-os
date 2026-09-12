"""CHT10 — ``JalonChantierPortail`` gagne une clé de phase stable.

``JalonChantierPortail`` (FG232) portait ``libelle``/``ordre``/``atteint``/
``date_jalon`` mais AUCUNE clé stable identifiant la PHASE (étude, commande,
installation, ...) : aucune écriture idempotente n'était possible depuis un
autre service (impossible de savoir si un jalon existe déjà pour une phase
donnée sans deviner sur le libellé, fragile et non traduit-stable).

Cette migration ajoute ``cle_phase`` (nullable — les jalons legacy créés à la
main via l'écran admin restent NULL, intacts) et une contrainte d'unicité
PARTIELLE ``(company, chantier, cle_phase)`` qui ne s'applique que lorsque
``cle_phase`` est renseignée : ``apps.portail.services.upsert_jalon_chantier``
(CHT10) s'appuie dessus pour publier un jalon de façon idempotente, sans
jamais toucher aux lignes legacy sans clé.

ADDITIF STRICT : aucune donnée existante n'est modifiée ni supprimée.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portail', '0007_documentclientportail_fichier_filename_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='jalonchantierportail',
            name='cle_phase',
            field=models.CharField(
                blank=True, max_length=60, null=True,
                verbose_name='Clé de phase (portail)'),
        ),
        migrations.AddConstraint(
            model_name='jalonchantierportail',
            constraint=models.UniqueConstraint(
                condition=~models.Q(cle_phase__isnull=True)
                & ~models.Q(cle_phase=''),
                fields=('company', 'chantier', 'cle_phase'),
                name='uniq_jalon_chantier_portail_cle_phase',
            ),
        ),
    ]
