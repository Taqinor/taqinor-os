"""HT24 — ordre du fondateur du 24/11/2026, deux gestes sur les bases EXISTANTES
(le seeder, lui, ne touche jamais un prix ni une valeur saisie).

1. Batterie ``BAT-DYN-HV-16`` (« add 30% on top and add the right prices ») :
   prix de vente 40 000,00 HT (le pack AVEC sa part du boîtier de contrôle et
   du rack) → 36 400,00 HT (achat 28 000 HT du devis Solarex Maroc n°
   S26/001708 du 27/07/2026 + 30 %) ; boîtier et rack deviennent des articles
   à part. Gardes : SKU exact ET prix EXACTEMENT 40 000,00 (un prix retouché à
   la main n'est jamais réécrit) ; la ligne de description d'origine, mot pour
   mot, est remplacée par la nouvelle. ``prix_achat`` jamais touché.

2. Hybride 80 kW (« pour l'onduleur 80kw fais ça toi-même, quitte à supprimer
   cet onduleur et en recréer un nouveau ») : l'article saisi à la main par le
   fondateur (SKU ``DEYE SUN-80K-SG02HP3-EU-EM6``) est ADOPTÉ par le catalogue —
   rien n'est supprimé, rien n'est fusionné. Seulement dans une société qui
   n'a PAS déjà ``OND-H-DEY-80T`` : SKU → ``OND-H-DEY-80T`` et nom → celui du
   catalogue ; prix, stock, rôle, catégorie restent les siens. Sa fiche : les
   champs VIDES sont comblés avec les valeurs de la datasheet (copie figée ici,
   jamais importée du seeder), UNE exception dite : ``ond_dc_max_kwc`` saisi à
   140,00 passe à 160,00 (« Puissance d'accès PV max. » 160 000 W ; fondateur :
   « met 160 kw »). Base neuve (aucun article) ou les deux SKU présents : rien.

Réversible : les mêmes gardes à l'envers (prix 36 400,00 → 40 000,00, ligne
nouvelle → ancienne ; SKU et nom rendus, puissance PV 160,00 → 140,00 sur
l'article ré-indexé). Les champs de fiche comblés restent (des ajouts, sans
perte d'une valeur saisie).
"""
from decimal import Decimal

from django.db import migrations

SKU_BATTERIE = 'BAT-DYN-HV-16'
PRIX_AVANT, PRIX_APRES = Decimal('40000.00'), Decimal('36400.00')
LIGNE_AVANT = 'Rack et control box inclus dans le prix de la tranche'
LIGNE_APRES = 'Rack, câbles et boîtier de contrôle haute tension chiffrés à part (un jeu par grappe)'

SKU_FONDATEUR = 'DEYE SUN-80K-SG02HP3-EU-EM6'
SKU_CATALOGUE = 'OND-H-DEY-80T'
NOM_CATALOGUE = 'Onduleur hybride Deye 80kW Triphasé'
DC_SAISI, DC_FICHE = Decimal('140.00'), Decimal('160.00')
#: Fiche datasheet du 80 kW (SUN-60/70/75/80K-SG02HP3-EU-EM6, fr, 2025-10-30 ;
#: brochure « 60-80kW C&I Hybrid Inverter Solution », août 2026) — les champs
#: comblés s'ils sont vides (mêmes valeurs que ``seed_catalogue``).
FICHE_80K = {
    'ond_n_mppt': 6, 'ond_chaines_max_par_mppt': 2,
    'ond_mppt_v_min': Decimal('150.0'), 'ond_mppt_v_max': Decimal('850.0'),
    'ond_v_max_abs': Decimal('1000.0'), 'ond_v_demarrage_v': Decimal('180.0'),
    'ond_i_max_mppt_a': Decimal('36.0'), 'ond_isc_max_mppt_a': Decimal('54.0'),
    'ond_ac_kw': Decimal('80'), 'ond_s_max_kva': Decimal('88.00'), 'ond_phases': 3,
    'ond_rendement_max_pct': Decimal('98.7'), 'ond_rendement_euro_pct': Decimal('98.1'),
    'ond_dc_max_kwc': DC_FICHE, 'ond_bat_v_min': Decimal('160'), 'ond_bat_v_max': Decimal('1000'),
    'ond_bat_nb_entrees': 2, 'ond_bat_i_max_a': Decimal('80.0'), 'ond_max_parallele': 10,
}


def batterie_corrigee(prix, description, sens=1):
    """``{champ: valeur}`` à écrire sur la batterie (vide = rien) : prix exact
    et ligne d'origine mot pour mot seulement ; ``sens`` -1 = retour arrière."""
    de, vers = (PRIX_AVANT, PRIX_APRES) if sens > 0 else (PRIX_APRES, PRIX_AVANT)
    l_de, l_vers = (LIGNE_AVANT, LIGNE_APRES) if sens > 0 else (LIGNE_APRES, LIGNE_AVANT)
    champs = {}
    if prix is not None and Decimal(prix) == de:
        champs['prix_vente'] = vers
    if description and l_de in description:
        champs['description'] = description.replace(l_de, l_vers)
    return champs


def a_adopter(skus_de_la_societe, sens=1):
    """Vrai si la société a l'article à ré-indexer et PAS déjà sa cible."""
    de, vers = (SKU_FONDATEUR, SKU_CATALOGUE) if sens > 0 else (SKU_CATALOGUE, SKU_FONDATEUR)
    return de in skus_de_la_societe and vers not in skus_de_la_societe


def fiche_completee(valeurs):
    """``{champ: valeur}`` à écrire sur la fiche du 80 kW adopté : les champs
    VIDES (``None``), et la puissance PV saisie à 140,00 → 160,00."""
    champs = {c: v for c, v in FICHE_80K.items() if valeurs.get(c) is None}
    if valeurs.get('ond_dc_max_kwc') is not None and Decimal(valeurs['ond_dc_max_kwc']) == DC_SAISI:
        champs['ond_dc_max_kwc'] = DC_FICHE
    return champs


def _batterie(apps, sens):
    Produit = apps.get_model('stock', 'Produit')
    for p in Produit.objects.filter(sku=SKU_BATTERIE).iterator():
        champs = batterie_corrigee(p.prix_vente, p.description, sens)
        if champs:
            for champ, valeur in champs.items():
                setattr(p, champ, valeur)
            p.save(update_fields=list(champs))


def _adopter(apps, sens):
    Produit = apps.get_model('stock', 'Produit')
    FicheTechnique = apps.get_model('stock', 'FicheTechnique')
    de = SKU_FONDATEUR if sens > 0 else SKU_CATALOGUE
    for p in list(Produit.objects.filter(sku=de)):
        skus = set(Produit.objects.filter(company_id=p.company_id).values_list('sku', flat=True))
        if not a_adopter(skus, sens):
            continue
        p.sku, p.nom = (SKU_CATALOGUE, NOM_CATALOGUE) if sens > 0 else (SKU_FONDATEUR, SKU_FONDATEUR)
        p.save(update_fields=['sku', 'nom'])
        fiche = FicheTechnique.objects.filter(produit=p, type_fiche='onduleur').first()
        if fiche is None:
            continue
        if sens > 0:
            champs = fiche_completee({c: getattr(fiche, c) for c in FICHE_80K})
        else:
            champs = {'ond_dc_max_kwc': DC_SAISI} if fiche.ond_dc_max_kwc == DC_FICHE else {}
        for champ, valeur in champs.items():
            setattr(fiche, champ, valeur)
        if champs:
            fiche.save(update_fields=list(champs))


def appliquer(apps, schema_editor):
    _batterie(apps, 1)
    _adopter(apps, 1)


def annuler(apps, schema_editor):
    _batterie(apps, -1)
    _adopter(apps, -1)


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0188_fiche_haute_tension_grappe'),
    ]

    operations = [
        migrations.RunPython(appliquer, annuler),
    ]
