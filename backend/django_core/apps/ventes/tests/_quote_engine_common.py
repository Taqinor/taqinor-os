"""Fixtures partagées de la suite `test_quote_engine*`.

Extraites TELLES QUELLES de `test_quote_engine.py` le 2026-08-19, quand ce
module de 3 704 lignes (146,9 s en CI, 10 % de toute la suite backend, et à
lui seul le plancher du shardage : aucun nombre de lanes ne descend sous le
module le plus lourd) a été scindé en quatre parties par surface exercée.

Le préfixe `_` garde ce fichier HORS de la découverte Django (`test*.py`) :
il ne porte aucun test, seulement les fabriques utilisées par les quatre
parties ET par une douzaine d'autres modules de test de l'application, qui
les importent historiquement depuis `test_quote_engine` (ce module continue
de les ré-exporter pour eux — aucun import à réécrire).

Aucun helper n'a changé d'un octet : mêmes objets, mêmes valeurs.
"""

import itertools
from decimal import Decimal

from django.contrib.auth import get_user_model

from apps.crm.models import Client
from apps.stock.models import Produit
from apps.ventes.models import Devis, LigneDevis


User = get_user_model()


# Compteur de tenants : une société NEUVE à chaque appel sans argument.
_company_seq = itertools.count(1)


def make_company(slug=None, nom=None):
    """Une société neuve par appel — passer ``slug`` pour la nommer.

    Sans compteur, ce helper faisait un ``get_or_create`` sur un slug
    FIXE ('test-qe-co') : deux appels rendaient la MÊME ligne, et un test
    écrivant ``other = make_company()`` croyait fabriquer un second
    tenant sans en fabriquer aucun (assertion cross-tenant vide de sens).
    """
    from authentication.models import Company
    n = next(_company_seq)
    company, _ = Company.objects.get_or_create(
        slug=slug or f'test-qe-co-{n}',
        defaults={'nom': nom or f'Test QE Co {n}'},
    )
    return company


def make_user(company):
    return User.objects.create_user(
        username='test_qe_user', password='x', role_legacy='responsable',
        company=company,
    )


def make_client(company):
    return Client.objects.create(
        company=company, nom='Alaoui', prenom='Karim',
        email='k@example.com', telephone='+212600000000',
        adresse='Hay Riad, Rabat',
    )


def make_produit(company, nom, sku, prix):
    return Produit.objects.create(
        company=company, nom=nom, sku=sku,
        prix_vente=Decimal(prix), prix_achat=Decimal('1'),
        quantite_stock=100,
    )


# PV86 — DÉCLARATION d'alternative. Un document à deux options n'existe que
# lorsque le devis l'exprime : le générateur persiste TOUJOURS ce choix dans
# ``etude_params['scenario']`` (garantie QF7). Sans déclaration, un devis qui
# porte les deux onduleurs en lignes non optionnelles est un ARTEFACT de
# données (une seule réalité, total = somme de TOUTES ses lignes) — cf.
# ``test_pv86_verite_unique_devis``. Les fixtures ci-dessous qui testent
# réellement le DOCUMENT À DEUX OPTIONS déclarent donc ce que le générateur
# écrit en production ; leur rendu est inchangé au bit près.
DEUX_OPTIONS = {'scenario': 'Les deux (Sans + Avec)'}


def make_devis(company, user, client, lignes, remise_globale='0',
               reference='DEV-QE-0001', etude_params=None):
    devis = Devis.objects.create(
        company=company, reference=reference, client=client,
        statut='brouillon', taux_tva=Decimal('20.00'),
        remise_globale=Decimal(remise_globale), created_by=user,
        etude_params=etude_params,
    )
    for ligne in lignes:
        # (desig, qty, pu) historique ou (desig, qty, pu, taux_tva) réforme
        desig, qty, pu = ligne[:3]
        taux = Decimal(ligne[3]) if len(ligne) > 3 else None
        # SKU unique par devis pour éviter les collisions (company, sku)
        sku = f"{reference[-6:]}-{desig[:13]}"
        LigneDevis.objects.create(
            devis=devis, produit=make_produit(company, desig, sku, pu),
            designation=desig, quantite=Decimal(qty),
            prix_unitaire=Decimal(pu), remise=Decimal('0'),
            taux_tva=taux,
        )
    return devis


def _residential_sample_data():
    """A minimal residential two-option quote dict for the residential renderer
    (built without the DB so the layout can be tested in isolation). Mirrors the
    shape `builder.build_quote_data` produces for a residentiel quote."""
    def _item(desig, q, ht, taux=20.0, marque=""):
        return {"designation": desig, "marque": marque, "description": "",
                "garantie": "", "quantite": float(q), "prix_unit_ht": float(ht),
                "prix_unit_ttc": round(float(ht) * (1 + taux / 100), 2),
                "taux_tva": float(taux)}

    def _totaux(rows):
        ht = round(sum(r["quantite"] * r["prix_unit_ht"] for r in rows), 2)
        buckets = {}
        for r in rows:
            buckets[r["taux_tva"]] = (
                buckets.get(r["taux_tva"], 0.0) + r["quantite"] * r["prix_unit_ht"])
        tpt = [{"taux": t, "montant": round(b * t / 100, 2), "ht_net": round(b, 2)}
               for t, b in sorted(buckets.items())]
        tva = round(sum(x["montant"] for x in tpt), 2)
        return {"ht_brut": ht, "remise": 0.0, "ht_net": ht, "tva": tva,
                "tva_par_taux": tpt, "ttc": round(ht + tva)}

    shared = [
        _item("Installation", 1, 6000), _item("Transport", 1, 1000),
        _item("Smart Meter", 1, 1500, marque="Huawei"),
        _item("Clé Wifi (dongle)", 1, 900, marque="Huawei"),
        _item("Structures acier", 16, 417),
        _item("Panneau Canadien Solar 710W", 16, 1272.73, 10, marque="Canadian Solar"),
    ]
    sans = shared + [_item("Onduleur réseau Huawei 10kW Triphasé", 1, 16667, marque="Huawei")]
    avec = shared + [_item("Onduleur hybride Deye 10kW Triphasé", 1, 23333, marque="Deye"),
                     _item("Batterie Dyness 10 kWh", 1, 25000, marque="Dyness")]
    eco = 20953
    sf = [0.053, 0.062, 0.083, 0.098, 0.114, 0.116, 0.116, 0.101, 0.087, 0.070, 0.052, 0.048]
    eco_m = [round(eco * f) for f in sf]
    return {
        "ref": "DEV-202606-0071", "date": "21/06/2026",
        # deliberately lower-case + empty address to prove the display fixes
        "client_name": "meryem hida", "client_full": "meryem hida",
        "client_addr": "", "client_city": "Casablanca",
        "client_phone": "+212600000000", "inst_type": "Résidentielle",
        "puissance_kwc": 11.36, "nb_panneaux": 16, "watt_par_panneau": 710,
        "prod_kwh": 14086,
        "total_sans": _totaux(sans)["ttc"], "total_avec": _totaux(avec)["ttc"],
        "totaux_sans": _totaux(sans), "totaux_avec": _totaux(avec),
        "roi_s": 4.7, "roi_a": 5.1,
        "eco_s_ann": eco, "eco_a_ann": eco, "eco_a_cumul": eco,
        "eco_s_monthly": eco_m, "eco_a_monthly": eco_m,
        "factures_mensuelles": [round(v / 0.85) for v in eco_m],
        "sans_items": sans, "avec_items": avec,
        "sans_bullets": ["16 panneaux 710 W", "Onduleur réseau Huawei 10kW Triphasé",
                         "Smart Meter + monitoring"],
        "avec_bullets": ["16 panneaux 710 W", "Onduleur hybride Deye 10kW Triphasé",
                         "Batterie Dyness 10 kWh"],
        "scenario": "Les deux (Sans + Avec)", "recommended": "Avec batterie",
        "tva_note": "TVA : 10% panneaux photovoltaïques · 20% autres équipements et prestations",
        "payment_terms": {"acompte": 30, "materiel": 60, "solde": 10},
        "discount_pct": 0.0, "taux_tva": 20.0,
    }
