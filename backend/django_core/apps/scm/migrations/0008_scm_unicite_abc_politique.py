# NTSCM4/NTSCM6 (revue orchestrateur) — unicite (company, produit) sur
# ClassificationABC et PolitiqueStock.
#
# `selectors.classifier_abc` fait un update_or_create(company, produit) et
# `services.recalculer_politiques_stock` un get_or_create(company, produit) :
# sans contrainte d'unicite en base, deux recalculs concurrents inserent DEUX
# lignes pour le meme produit et le point de commande devient non
# deterministe. C'est exactement ce que la garde check_get_or_create surveille.
#
# L'app `scm` est creee dans ce meme lot et n'a jamais ete deployee : les tables
# sont vides en production. La deduplication ci-dessous protege les bases de
# developpement deja migrees, en gardant la ligne la PLUS RECENTE par couple.
from django.db import migrations, models


def dedupe(apps, schema_editor):
    for nom, champs in (('ClassificationABC', ('company_id', 'produit_id')),
                        ('PolitiqueStock', ('company_id', 'produit_id'))):
        modele = apps.get_model('scm', nom)
        vus = set()
        for ligne in modele.objects.order_by('-id').iterator():
            cle = tuple(getattr(ligne, champ) for champ in champs)
            if cle in vus:
                ligne.delete()
            else:
                vus.add(cle)


class Migration(migrations.Migration):

    dependencies = [
        ('scm', '0007_ligneoffresop'),
    ]

    operations = [
        migrations.RunPython(dedupe, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='classificationabc',
            constraint=models.UniqueConstraint(
                fields=['company', 'produit'],
                name='scm_classificationabc_co_produit_uniq'),
        ),
        migrations.AddConstraint(
            model_name='politiquestock',
            constraint=models.UniqueConstraint(
                fields=['company', 'produit'],
                name='scm_politiquestock_co_produit_uniq'),
        ),
    ]
