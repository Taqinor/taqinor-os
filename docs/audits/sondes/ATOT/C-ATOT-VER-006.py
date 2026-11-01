# flake8: noqa  (sonde de contre-visite vérifie ATOT, rejouable par scripts/sonde.py — AMET93)
"""ATOT6 (jumeau) : `apps/ventes/exports.py::_grand_livre_rows_reconstitues` (et `export_journal_ventes`) n'importent que
Facture et Avoir : la TVA collectée d'une note de débit émise est absente du grand livre reconstitué et du résumé TVA.
Facture émise + note de débit totale par la vraie route ; fonction d'export réelle. Transaction annulée."""
SONDE = {"constat": "C-ATOT-VER-006", "sha": "b72cda218",
         "attendu": "note de débit émise : aucune ligne ni TVA dans le grand livre reconstitué de la période"}


def sonde(ctx):
    from datetime import date, timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Facture, LigneFacture
    from apps.ventes.exports import _grand_livre_rows_reconstitues
    co = Company.objects.create(nom='Sonde ATOT VER-006', slug='sonde-atot-ver-006')
    u = get_user_model().objects.create_user(username='sonde-atot-ver-006', password='x', company=co, role_legacy='admin')
    cl = Client.objects.create(company=co, nom='Client', prenom='V006', email='sonde-atot-ver-006@example.invalid')
    p = Produit.objects.create(company=co, nom='Kit', sku='SONDE-ATOT-006', prix_vente=Decimal('1000'), quantite_stock=10)
    f = Facture.objects.create(company=co, reference='FAC-SONDE-ATOT-006', client=cl, statut=Facture.Statut.EMISE,
                               taux_tva=Decimal('20.00'), created_by=u)
    LigneFacture.objects.create(facture=f, produit=p, designation='Kit', quantite=Decimal('1'),
                                prix_unitaire=Decimal('1000'), taux_tva=Decimal('20.00'))
    api = APIClient()
    api.force_authenticate(u)
    debut = date.today() - timedelta(days=31)
    fin = date.today() + timedelta(days=2)
    rows_avant, _ = _grand_livre_rows_reconstitues(co, debut, fin)
    r = api.post(f'/api/django/ventes/factures/{f.pk}/creer-note-debit/', {'motif': 'Pénalité de retard', 'lignes': [{'produit': p.id, 'designation': 'Pénalité', 'quantite': '1', 'prix_unitaire': '100', 'taux_tva': '20'}]},
                 format='json', HTTP_HOST='localhost')
    rows_apres, tot = _grand_livre_rows_reconstitues(co, debut, fin)
    print(f'note_debit={r.status_code} {str(getattr(r, "data", ""))[:160]} lignes_gl avant={len(rows_avant)} '
          f'apres={len(rows_apres)} totaux={tot}')
    return {'repro': r.status_code in (200, 201) and len(rows_apres) == len(rows_avant),
            'note_debit': r.status_code, 'lignes_avant': len(rows_avant), 'lignes_apres': len(rows_apres)}
