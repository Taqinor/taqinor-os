# flake8: noqa  (sonde de contre-visite vérifie AANA, rejouable par scripts/sonde.py — AMET93)
"""AANA19 (jumeau crm) : `apps/crm/clients_selectors.py::_devis_compte_comme_signe` compte « accepté ET is_active » ;
une V1 acceptée révisée en V2 brouillon compte pour `reporting.pipeline._devis_signes` (VNT22,
`devis_signes_en_vigueur`) mais vaut 0 dans `ca_signe_periode` (objectifs, défis, « Mes équipes »).
Fonctions réelles, transaction annulée."""
SONDE = {"constat": "C-AANA-VER-004", "sha": "32375fe65",
         "attendu": "V1 acceptée révisée en V2 brouillon : _devis_signes compte V1, ca_signe_periode crm = 0"}


def sonde(ctx):
    from datetime import date
    from decimal import Decimal
    from authentication.models import Company
    from apps.crm import stages
    from apps.crm.models import Client, Lead
    from apps.crm.clients_selectors import ca_signe_periode
    from apps.reporting.pipeline import _devis_signes
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis
    co = Company.objects.create(nom='Sonde AANA VER-004', slug='sonde-aana-ver-004')
    cl = Client.objects.create(company=co, nom='Cli', prenom='V004', email='sonde-aana-ver-004@example.invalid')
    lead = Lead.objects.create(company=co, nom='Lead V004', stage=stages.SIGNED)
    p = Produit.objects.create(company=co, nom='Kit', sku='SONDE-AANA-004', prix_vente=Decimal('1000'), quantite_stock=0)
    v1 = Devis.objects.create(company=co, reference='DEV-SONDE-AANA-004-V1', client=cl, lead=lead,
                              statut=Devis.Statut.ACCEPTE, date_acceptation=date.today())
    LigneDevis.objects.create(devis=v1, produit=p, designation='Kit', quantite=Decimal('10'),
                              prix_unitaire=Decimal('1000'))
    v2 = Devis.objects.create(company=co, reference='DEV-SONDE-AANA-004-V2', client=cl, lead=lead,
                              statut=Devis.Statut.BROUILLON, version=2, version_parent=v1)
    Devis.objects.filter(pk=v1.pk).update(is_active=False, superseded_by=v2)
    reporting = list(_devis_signes({'company': co}).values_list('pk', flat=True))
    crm = ca_signe_periode(co, None, date.today().replace(day=1), date.today())
    print(f'_devis_signes={reporting} (V1={v1.pk}) ca_signe_periode={crm}')
    return {'repro': v1.pk in reporting and not crm, 'reporting': reporting, 'crm_ca_signe': str(crm)}
