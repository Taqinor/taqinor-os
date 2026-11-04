# flake8: noqa  (sonde de contre-visite vérifie ADEV, rejouable par scripts/sonde.py — AMET93)
"""ADEV100 : le générateur C&I ouvert depuis un lead sème le kWh du lead dans le champ ANNUEL de l'écran
(`profilCi.js` envoie `{kwh_mensuels: null, kwh_annuel: <valeur>}`) et joint `lead` au corps. Si la
commerciale corrige ce kWh, l'étude doit suivre la valeur tapée (corps > devis > lead). On rejoue la
résolution serveur réelle (`etude_ci.resoudre_entrees` puis `etude_ci._consommation`)."""
SONDE = {"constat": "C-ADEV-VER-002", "sha": "e62ca97aa",
         "attendu": "kWh tapé 96 000/an ignoré : 12 × 4 000 retenus, feuille kwh_mensuel_declare (lead)"}


def sonde(ctx):
    from decimal import Decimal
    from authentication.models import Company
    from apps.crm.models import Lead
    from apps.ventes.domain import etude_ci
    co = Company.objects.create(nom='Sonde ADEV VER-002', slug='sonde-adev-ver-002')
    lead = Lead.objects.create(company=co, nom='Pro sonde ADEV100', type_installation='commercial',
                               ville='Casablanca', conso_mensuelle_kwh=Decimal('4000'),
                               categorie_commerciale='bureau')
    corps = {'lead': lead.id, 'consommation': {'kwh_mensuels': None, 'kwh_annuel': 96000,
                                               'factures_mad': []}}
    res = etude_ci.resoudre_entrees(corps, lead=lead)
    conso, feuille = etude_ci._consommation(res, {}, [], [])
    total = sum(conso) if isinstance(conso, list) else conso
    print(f'saisi kwh_annuel=96000 ; retenu total={total} feuille={feuille}')
    return {'repro': feuille == 'kwh_mensuel_declare' and abs(float(total) - 48000) < 1,
            'total_retenu': float(total), 'feuille': feuille}
