"""PVLV (fondateur 21/08/2026) — les prix Deye 15/20 kW étaient ceux des LV.

« The prices that were there were for 15kw and 20kw LV inverters » : les
36 000/48 000 TTC portés depuis l'origine par les SKU « Onduleur hybride Deye
15kW/20kW Triphasé » (OND-H-DEY-15T/20T, identifiés SG01HP3 HAUTE TENSION)
sont en réalité les prix fondateur des jumeaux BASSE TENSION SG05LP3
(OND-DEY-15K-LV/20K-LV, créés le 18/08 à prix vide). Cette migration opère le
TRANSFERT sur les bases existantes, par société :

  * la paire n'est transférée QUE si le HV porte un prix (> 0) ET que le LV
    n'en porte pas encore — un prix déjà saisi par le fondateur sur le LV
    gagne TOUJOURS (rien n'est alors touché, ni d'un côté ni de l'autre) ;
  * le transfert copie les VALEURS RÉELLES du HV (prix_vente ET prix_achat,
    telles qu'elles sont en base — jamais des constantes recopiées du
    seeder : si le fondateur a ajusté un prix depuis, c'est SON prix qui
    voyage) ;
  * le HV repasse ensuite à 0/0 : grisé « prix à renseigner » (même garde que
    les pompes OSP) tant qu'un vrai prix HAUTE TENSION n'existe pas — les
    36 000/48 000 n'ont jamais été les siens ;
  * un LV absent de la base est CRÉÉ (même patron que le seeder : catégorie
    du produit HV, TVA 20 %, stock/seuil du seeder) puis reçoit le transfert.

Les lignes de devis existantes ne bougent pas : elles portent leurs propres
prix (instantanés à la création). Seuls les prochains chiffrages voient le
changement — et composent enfin un 15/20 kW hybride triphasé compatible avec
les batteries Dyness 51,2 V (plage 40-60 V du SG05LP3).

RÉVERSIBLE : non — ``noop`` (même doctrine que 0125 : impossible de
distinguer, après coup, un prix transféré d'un prix ressaisi entre temps).
Les nouvelles bases n'ont pas besoin d'elle : le seeder porte désormais les
prix sur les SKU LV directement.
"""
from decimal import Decimal

from django.db import migrations

#: (sku HV « donneur », sku LV « receveur », stock/seuil du seeder pour une
#: création éventuelle du LV)
_PAIRES = (
    ('OND-H-DEY-15T', 'OND-DEY-15K-LV',
     'Onduleur hybride Deye 15kW Triphasé Basse Tension', 500, 5),
    ('OND-H-DEY-20T', 'OND-DEY-20K-LV',
     'Onduleur hybride Deye 20kW Triphasé Basse Tension', 500, 5),
)


def _sans_prix(valeur):
    return valeur is None or valeur <= 0


def transferer_prix_lv(apps, schema_editor):
    Produit = apps.get_model('stock', 'Produit')

    for sku_hv, sku_lv, nom_lv, qte, seuil in _PAIRES:
        for hv in Produit.objects.filter(sku=sku_hv).iterator():
            if _sans_prix(hv.prix_vente):
                continue  # rien à transférer pour cette société
            lv = Produit.objects.filter(
                company=hv.company, sku=sku_lv).first()
            if lv is None:
                # Filet de sécurité (base jamais re-seedée depuis le 18/08) :
                # stock à ZÉRO — une migration ne crée pas 500 unités sans
                # mouvement de stock ; le seeder, lui, journalise les siennes.
                lv = Produit.objects.create(
                    company=hv.company, nom=nom_lv, sku=sku_lv,
                    categorie=hv.categorie,
                    prix_vente=Decimal('0'), prix_achat=Decimal('0'),
                    quantite_stock=0, seuil_alerte=seuil,
                    tva=Decimal('20.00'),
                )
            if not _sans_prix(lv.prix_vente):
                continue  # le fondateur a déjà prixé le LV : sa saisie gagne
            lv.prix_vente = hv.prix_vente
            lv.prix_achat = hv.prix_achat
            lv.save(update_fields=['prix_vente', 'prix_achat'])
            hv.prix_vente = Decimal('0')
            hv.prix_achat = Decimal('0')
            hv.save(update_fields=['prix_vente', 'prix_achat'])


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0125_pvfch_combler_fiches_manquantes'),
    ]

    operations = [
        migrations.RunPython(transferer_prix_lv, migrations.RunPython.noop),
    ]
