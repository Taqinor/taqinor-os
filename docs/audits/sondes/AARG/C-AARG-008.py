# flake8: noqa  (sonde du parcours PA4 « Argent », rejouable par scripts/sonde.py — AMET93)
"""K08 : paiements, avoirs, notes de débit, bons de commande et promesses de paiement sont listés à TOUT rôle interne
(`apps/ventes/views/paiement.py::PaiementViewSet.get_permissions`, `views/avoir.py::AvoirViewSet.get_permissions` et
`NoteDebitViewSet.get_permissions`, `views/bon_commande.py::BonCommandeViewSet.get_permissions`,
`recouvrement.py::PromessePaiementViewSet.get_permissions` → `IsAnyRole` en lecture), alors que la liste des factures
exige un droit de lecture ventes (`LectureFactures`). Rôle canonique Admin RH (aucun code ventes). Vraies routes,
transaction annulée."""
SONDE = {"constat": "C-AARG-008", "sha": "56d5b623a",
         "attendu": "Admin RH : GET /ventes/factures/ 403 (témoin) mais GET paiements / avoirs / notes-debit / "
                    "bons-commande / promesses-paiement 200 avec les lignes d'argent de la société",
         "modeles": ["Company", "Role", "CustomUser", "Client", "Produit", "Facture", "LigneFacture", "Paiement",
                     "Devis", "BonCommande", "PromessePaiement"]}


def sonde(ctx):
    from datetime import date, timedelta
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.roles.models import Role
    from apps.roles import permissions_registre as reg
    from apps.stock.models import Produit
    from apps.ventes.models import BonCommande, Devis, Facture, LigneFacture, PromessePaiement
    User = get_user_model()
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde AARG 008', slug='sonde-aarg-008')
    r_dir = Role.objects.create(company=co, nom='Directeur', permissions=list(reg.DIRECTEUR_PERMISSIONS),
                                est_systeme=True)
    r_rh = Role.objects.create(company=co, nom='Admin RH', permissions=list(reg.ADMIN_RH_PERMISSIONS),
                               est_systeme=True, perimetre=reg.PERIMETRE_RH)
    dirc = User.objects.create_user(username='sonde-aarg008-dir', password='x', company=co, role=r_dir)
    rh = User.objects.create_user(username='sonde-aarg008-rh', password='x', company=co, role=r_rh)
    cl = Client.objects.create(company=co, nom='Argent', prenom='K08', email='sonde-aarg-008@example.invalid')
    p = Produit.objects.create(company=co, nom='Kit K08', sku='SONDE-AARG-008', prix_vente=Decimal('1000'),
                               quantite_stock=10)
    f = Facture.objects.create(company=co, reference='FAC-SONDE-AARG-008', client=cl, statut=Facture.Statut.EMISE,
                               taux_tva=Decimal('20.00'), created_by=dirc)
    LigneFacture.objects.create(facture=f, produit=p, designation='Centrale', quantite=Decimal('1'),
                                prix_unitaire=Decimal('1000'), taux_tva=Decimal('20.00'))
    d = Devis.objects.create(company=co, client=cl, reference='DEV-SONDE-AARG-008', statut='accepte',
                             taux_tva=Decimal('20'), created_by=dirc)
    BonCommande.objects.create(company=co, reference='BC-SONDE-AARG-008', devis=d, client=cl)
    PromessePaiement.objects.create(company=co, facture=f, montant_promis=Decimal('500'),
                                    date_promise=date.today() + timedelta(days=10), created_by=dirc)
    api_d = APIClient()
    api_d.force_authenticate(dirc)
    rp = api_d.post(f'/api/django/ventes/factures/{f.id}/enregistrer-paiement/',
                    {'montant': '200', 'date_paiement': date.today().isoformat(), 'mode': 'virement'},
                    format='json', **H)
    api = APIClient()
    api.force_authenticate(rh)

    def lire(url):
        r = api.get(url, **H)
        n = None
        if r.status_code == 200 and hasattr(r, 'data'):
            data = r.data
            n = data.get('count', len(data.get('results', []))) if isinstance(data, dict) else len(data)
        return [r.status_code, n]

    temoin = lire('/api/django/ventes/factures/')
    portes = {k: lire(f'/api/django/ventes/{k}/') for k in
              ('paiements', 'avoirs', 'notes-debit', 'bons-commande', 'promesses-paiement')}
    print(f'setup_paiement_directeur={rp.status_code} temoin_factures={temoin} portes={portes}')
    ouvertes = [k for k, (s, _n) in portes.items() if s == 200]
    return {'repro': temoin[0] == 403 and bool(ouvertes), 'setup_paiement': rp.status_code,
            'temoin_factures': temoin, 'portes': portes, 'ouvertes': ouvertes}
