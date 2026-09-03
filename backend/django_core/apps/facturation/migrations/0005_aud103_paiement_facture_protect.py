import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """AUD103 (FICHE-DEL) — ``Paiement.facture`` passe de CASCADE à PROTECT.

    Supprimer une facture effaçait EN CASCADE ses ``Paiement`` : des MAD
    réellement encaissés partaient en silence, tandis que l'écriture au grand
    livre — qui n'est PAS liée par FK (``apps.compta`` la retrouve par
    ``source_type``/``source_id``) — survivait en orphelin. Le grand livre
    divergeait alors définitivement du registre des ventes.

    Un paiement est de l'argent : il ne disparaît jamais avec son document.
    Le viewset ne laisse plus supprimer qu'un BROUILLON sans aucun paiement ;
    ce PROTECT est le filet côté MODÈLE, qui couvre aussi l'admin Django, le
    shell et tout futur appelant.

    ``on_delete`` est appliqué par le collector Django, jamais par la base :
    cette migration ne touche AUCUNE donnée et ne change AUCUNE contrainte
    SQL (pas de ``ON DELETE`` côté Postgres ici) — c'est un changement d'état
    pur, réversible.
    """

    dependencies = [
        ('facturation', '0004_pvfresh_facture_pdf_render_meta'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paiement',
            name='facture',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='paiements',
                to='facturation.facture',
            ),
        ),
    ]
