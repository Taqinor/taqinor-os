# flake8: noqa  (sonde d'audit de parcours PF2 « Socle », rejouable par scripts/sonde.py — METHODE §C.4)
"""K73 — les métriques gouvernées « Chiffre d'affaires HT/TTC » et « Panier moyen » ignorent les avoirs,
alors que le tableau de bord reporting les déduit (AANA55).

(A) facture 10 000 HT émise + avoir geste commercial 2 000 HT ; (B) facture 1 000 HT soldée par un
avoir TOTAL et passée « payée ». Métriques semées par `seed_metriques` (`_semer`), lues par
`semantic.services.resolve_metric_valeur` (le chemin des widgets Direction/Finance/Commerce et des
alertes KPI) ; tableau de bord par la VRAIE route `GET reporting/dashboard/` (ca_paye + ca_attente)."""
SONDE = {"constat": "C-ASOC-065", "sha": "c514bd8ba",
         "attendu": "repro si ca_ht métrique = 11 000 alors que dashboard ca_paye+ca_attente = 8 000",
         "modeles": ["facturation.Facture", "facturation.Avoir", "semantic.MetricDefinition"]}


def sonde(ctx):
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Avoir, Facture, LigneAvoir, LigneFacture
    from apps.semantic.management.commands.seed_metriques import Command as SeedMetriques
    from apps.semantic.services import resolve_metric_valeur
    H = {'HTTP_HOST': 'localhost'}
    co = Company.objects.create(nom='Sonde ASOC 065', slug='sonde-asoc-065')
    u = get_user_model().objects.create_user(username='sonde_asoc_065', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    SeedMetriques()._semer(co)
    cl = Client.objects.create(company=co, nom='Client 065')
    p = Produit.objects.create(company=co, nom='Kit', sku='ASOC065-P', prix_vente=Decimal('1000'), quantite_stock=0)

    def facture(ref, ht):
        f = Facture.objects.create(company=co, reference=ref, client=cl, statut=Facture.Statut.EMISE)
        LigneFacture.objects.create(facture=f, produit=p, designation='Kit', quantite=Decimal('1'),
                                    prix_unitaire=Decimal(ht))
        return f

    def avoir(f, ht, ref):
        a = Avoir.objects.create(company=co, reference=ref, facture=f, client=cl)
        LigneAvoir.objects.create(avoir=a, designation='Avoir', quantite=Decimal('1'), prix_unitaire=Decimal(ht))
        return a

    fa = facture('FAC-ASOC065-A', '10000')
    avoir(fa, '2000', 'AV-ASOC065-A')
    fb = facture('FAC-ASOC065-B', '1000')
    avoir(fb, '1000', 'AV-ASOC065-B')
    Facture.objects.filter(pk=fb.pk).update(statut=Facture.Statut.PAYEE)
    fa.refresh_from_db()
    fb.refresh_from_db()
    obs = {'facture_A': {'total_ht': str(fa.total_ht), 'montant_du': str(fa.montant_du), 'statut': fa.statut},
           'facture_B': {'total_ht': str(fb.total_ht), 'montant_du': str(fb.montant_du), 'statut': fb.statut}}
    for cle in ('ca_ht', 'ca_ttc', 'panier_moyen'):
        try:
            v = resolve_metric_valeur(co, u, cle)
            obs[f'metrique_{cle}'] = str(v) if v is not None else None
        except Exception as exc:  # noqa
            obs[f'metrique_{cle}'] = f'err {exc!r}'[:160]
    d = api.get('/api/django/reporting/dashboard/', **H)
    obs['dashboard_http'] = d.status_code
    if d.status_code == 200:
        k = d.data['kpis']
        obs['dashboard_ca_paye'] = k.get('ca_paye')
        obs['dashboard_ca_attente'] = k.get('ca_attente')
    print(obs)
    try:
        m = Decimal(obs['metrique_ca_ht'])
        dash = Decimal(str(obs['dashboard_ca_paye'])) + Decimal(str(obs['dashboard_ca_attente']))
        obs['ecart_ht'] = str(m - dash)
        obs['repro'] = bool(m == Decimal('11000') and abs(dash - Decimal('8000')) < Decimal('0.05'))
    except Exception as exc:  # noqa
        obs['repro'] = False
        obs['err_comparaison'] = repr(exc)[:120]
    return obs
