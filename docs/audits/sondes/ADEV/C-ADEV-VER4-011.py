# flake8: noqa  (sonde d'audit, contre-visite ADEV du 04/11, rejouable par scripts/sonde.py — AMET93)
"""ADEV9 — `selectors.devis_en_jeu` (= `is_active=True`) appliqué aux lectures des ACCEPTÉS de
`dashboard_view.py::dashboard_quote_to_cash` (`acceptes`, `devis_avec_facture`, cycle) : une vente
ACCEPTÉE puis révisée (`domain/revision.py::reviser_devis` → V1 `is_active=False`, V2 brouillon) sort
du tableau de bord tant que la V2 n'est pas acceptée (1 accepté → 0), contre la règle D-ADEV-1=a
(« la V1 compte tant que la V2 n'est pas acceptée »). Avant ADEV9 la V1 acceptée était comptée.
Chaîne réelle (service de révision + GET /ventes/dashboard/). Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-ADEV-VER4-011", "sha": "fcbed3760",
         "attendu": "dashboard devis.acceptes = 1 avant révision, 0 après « Réviser » (V2 brouillon) ; "
                    "attendu sain (D-ADEV-1=a) : 1 tant que la V2 n'est pas acceptée",
         "modeles": ["authentication.Company", "ventes.Devis", "ventes.LigneDevis"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Devis, LigneDevis
    from apps.ventes.domain.revision import reviser_devis
    co = Company.objects.create(nom='Sonde ADEV-VER4-011', slug='sonde-adev-ver4-011')
    u = get_user_model().objects.create_user(username='sonde-adev-ver4-011', password='x',
                                             role_legacy='responsable', company=co)
    cl = Client.objects.create(company=co, nom='Client ADEV9', email='adev9-ver4@example.invalid')
    p = Produit.objects.create(company=co, nom='Onduleur', sku='SONDE-ADEV-VER4-011',
                               prix_vente=Decimal('5000'), quantite_stock=0)
    v1 = Devis.objects.create(company=co, reference='DEV-SONDE-ADEV9-V1', client=cl, created_by=u,
                              statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'),
                              date_envoi=timezone.now())
    LigneDevis.objects.create(devis=v1, produit=p, designation='Onduleur', quantite=Decimal('2'),
                              prix_unitaire=Decimal('5000'))
    api = APIClient()
    api.force_authenticate(u)

    def lire():
        r = api.get('/api/django/ventes/dashboard/', HTTP_HOST='localhost')
        d = r.json().get('devis', {}) if r.status_code == 200 else {'status': r.status_code}
        return {k: d.get(k) for k in ('total', 'envoyes', 'acceptes', 'status')}

    avant = lire()
    v2 = reviser_devis(v1, user=u)
    v1.refresh_from_db()
    apres = lire()
    obs = {'avant': avant, 'apres': apres, 'v1_statut': v1.statut, 'v1_is_active': v1.is_active,
           'v2_statut': v2.statut, 'v2_is_active': v2.is_active}
    print(obs)
    repro = avant.get('acceptes') == 1 and apres.get('acceptes') == 0 and v1.statut == Devis.Statut.ACCEPTE
    return {'repro': repro, **obs}
