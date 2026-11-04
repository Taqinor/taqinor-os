# flake8: noqa  (sonde d'audit, contre-visite de clôture ADEV 04/11, rejouable par scripts/sonde.py — AMET93)
"""ADEV32 jumeau oublié : `domain/creation.py::create_devis_upsell_from_intervention` écrit encore un texte
d'ORIGINE interne (« Devis d'upsell généré depuis une intervention sur place. / Chantier : CHT-… / Type
d'intervention : … ») dans `Devis.note` (texte CLIENT) ; la garde AST de `test_adev32_note_client_sans_marqueur`
l'exempte (EXEMPTIONS). Chaîne réelle : service de création puis payload public `GET /ventes/proposal/<token>/`
(`public_views.proposal_data` → `note_client`). Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ADEV-VER4-020", "sha": "fcbed3760",
         "attendu": "devis d'upsell créé depuis une intervention : Devis.note contient « Devis d'upsell généré … Chantier : CHT-… » et le payload public sert ce texte en note_client (attendu sain : note vide, origine au chatter)",
         "modeles": ["authentication.Company", "ventes.Devis", "ventes.LigneDevis", "ventes.ShareLink",
                     "installations.Installation", "installations.Intervention", "crm.Client"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.installations.models import Installation, Intervention
    from apps.ventes.models import Devis, LigneDevis, ShareLink
    from apps.ventes.services import create_devis_upsell_from_intervention
    co = Company.objects.create(nom='Sonde ADEV-VER4-020', slug='sonde-adev-ver4-020')
    u = get_user_model().objects.create_user(username='sonde-adev-ver4-020', password='x',
                                             role_legacy='responsable', company=co)
    cl = Client.objects.create(company=co, nom='Client', prenom='Upsell', email='upsell-v4-020@example.invalid',
                               telephone='+212600004020')
    inst = Installation.objects.create(company=co, reference='CHT-SONDE-V4020', client=cl)
    itv = Intervention.objects.create(company=co, installation=inst, type_intervention='controle', created_by=u)
    devis = create_devis_upsell_from_intervention(intervention=itv, user=u)
    devis.refresh_from_db()
    note_base = devis.note or ''
    # Le moteur refuse un devis sans onduleur : on complète le brouillon (comme le test ADEV32 pour la réserve).
    for nom, sku, qte, pu in (('Panneau Canadien Solar 710W', 'V4020-PV', '10', '1000'),
                              ('Onduleur réseau Huawei 5kW', 'V4020-OND', '1', '3000')):
        p = Produit.objects.create(company=co, nom=nom, sku=sku, prix_vente=Decimal(pu),
                                   prix_achat=Decimal('1'), quantite_stock=100)
        LigneDevis.objects.create(devis=devis, produit=p, designation=nom, quantite=Decimal(qte),
                                  prix_unitaire=Decimal(pu), remise=Decimal('0'))
    Devis.objects.filter(pk=devis.pk).update(statut=Devis.Statut.ENVOYE)
    lien = ShareLink.for_devis(devis)
    r = APIClient().get(f'/api/django/ventes/proposal/{lien.token}/', HTTP_HOST='localhost')
    note_client = r.data.get('note_client') if r.status_code == 200 and hasattr(r, 'data') else None
    obs = {'reference': devis.reference, 'note_en_base': note_base, 'public_status': r.status_code,
           'note_client_publique': note_client}
    print(f'obs={obs}')
    repro = ("Devis d'upsell" in note_base and 'CHT-SONDE-V4020' in note_base
             and note_client is not None and "Devis d'upsell" in note_client)
    return {'repro': repro, **obs}
