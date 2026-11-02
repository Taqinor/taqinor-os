# flake8: noqa  (sonde d'audit parcours PA4, rejouable par scripts/sonde.py — AMET93)
"""G1 : une créance NEUVE adossée à une facture ancienne hérite de l'échéance d'ORIGINE.
(A) `views/facture_rectificatifs.py::creer_note_debit` accepte une facture `payee`, puis
`domain/encaissements.py::recalculer_statut_paiement` ne lit que `facture.date_echeance` → EN_RETARD tout de suite ;
`facturation/models.py::Facture.jours_retard` compte depuis l'échéance d'origine ; `recouvrement.py::_current_level`
→ niveau le plus haut + pénalité. (B) `views/facture_encaissement.py::liberer_retenue` : la retenue libérée
aujourd'hui est jugée en retard depuis l'ancienne échéance par `scheduled.py::check_overdue_factures`.
Chaîne API réelle (responsable), beat restreint à la société de la sonde (`active_company_ids` remplacé).
Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AARG-060", "sha": "56d5b623a",
         "attendu": "A : facture 1 200 émise J-120, échue J-90, payée J-85 ; note de débit 500 HT aujourd'hui → sain : statut emise, jours_retard 0, aucun niveau ; observé : en_retard, jours_retard 90, niveau 3 + pénalité. B : retenue 120 libérée aujourd'hui → beat → sain : emise, jours_retard 0 ; observé : en_retard, 90 j",
         "modeles": ["authentication.Company", "facturation.Facture", "facturation.Paiement", "ventes.NoteDebit",
                     "facturation.FollowupLevel"]}


def sonde(ctx):
    from datetime import timedelta
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    import authentication.selectors as sel
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Facture, LigneFacture, Paiement, FollowupLevel
    from apps.ventes import scheduled
    from apps.ventes.recouvrement import _current_level, _levels
    co = Company.objects.create(nom='Sonde AARG-060', slug='sonde-aarg-060')
    u = get_user_model().objects.create_user(username='sonde-aarg-060', password='x', role_legacy='responsable', company=co)
    cl = Client.objects.create(company=co, nom='Alaoui', prenom='Sara', email='g1-aarg060@example.invalid')
    p = Produit.objects.create(company=co, nom='Kit', sku='SONDE-AARG-060', prix_vente=Decimal('1000'), quantite_stock=0)
    for ordre, nom, delai, taux, frais in ((1, 'Rappel', 7, 0, 0), (2, 'Relance', 15, 0, 0), (3, 'Ferme', 30, Decimal('12'), Decimal('100'))):
        FollowupLevel.objects.create(company=co, ordre=ordre, nom=nom, delai_jours=delai,
                                     taux_interet_annuel=taux, frais_fixes=frais)
    today = scheduled.casablanca_today()
    adm = get_user_model().objects.create_user(username='sonde-aarg-060-adm', password='x', role_legacy='admin', company=co)
    api = APIClient()
    api.force_authenticate(u)
    api_adm = APIClient()
    api_adm.force_authenticate(adm)  # creer-note-debit = IsAdminRole
    B = '/api/django/ventes'

    def facture(ref, retenue=None):
        f = Facture.objects.create(company=co, reference=ref, client=cl, statut=Facture.Statut.EMISE,
                                   date_emission=today - timedelta(days=120), date_echeance=today - timedelta(days=90),
                                   retenue_garantie_mad=retenue)
        LigneFacture.objects.create(facture=f, produit=p, designation='Kit', quantite=Decimal('1'),
                                    prix_unitaire=Decimal('1000'), taux_tva=Decimal('20'))
        return Facture.objects.get(pk=f.pk)

    def payer(f, montant):
        r = api.post(f'{B}/factures/{f.pk}/enregistrer-paiement/',
                     {'montant': str(montant), 'date_paiement': (today - timedelta(days=85)).isoformat(), 'mode': 'virement'},
                     format='json', HTTP_HOST='localhost')
        return r.status_code, (r.data if r.status_code >= 400 else None)

    def etat(f):
        f = Facture.objects.get(pk=f.pk)
        jr = f.jours_retard
        niv = _current_level(jr, _levels(co), montant_du=f.montant_exigible)
        return {'statut': f.statut, 'montant_du': str(f.montant_du), 'exigible': str(f.montant_exigible),
                'date_echeance': f.date_echeance.isoformat() if f.date_echeance else None,
                'jours_retard': jr, 'niveau': niv, 'prochaine_relance': str(f.prochaine_relance)}

    obs = {'today': today.isoformat()}
    # ── A : note de débit sur facture payée ──
    fa = facture('FAC-SONDE-AARG60-A')
    obs['A_total_ttc'] = str(fa.total_ttc)
    obs['A_paiement'] = payer(fa, fa.montant_du)
    obs['A_apres_paiement'] = etat(fa)
    with mock.patch('apps.ventes.utils.pdf.generate_note_debit_pdf', lambda *a, **k: None):
        r = api_adm.post(f'{B}/factures/{fa.pk}/creer-note-debit/',
                     {'montant': '500.00', 'taux_tva': '20', 'motif': 'Travaux supplementaires'},
                     format='json', HTTP_HOST='localhost')
    obs['A_note_debit'] = (r.status_code, (r.data if r.status_code >= 400 else r.data.get('montant_ttc')))
    obs['A_apres_note'] = etat(fa)
    r = api.get(f'{B}/relances/', HTTP_HOST='localhost')
    ligne = [x for x in (r.data if r.status_code == 200 else []) if x['id'] == fa.pk]
    obs['A_relances_list'] = (r.status_code, ligne[0] if ligne else None)
    # ── B : retenue de garantie libérée aujourd'hui ──
    fb = facture('FAC-SONDE-AARG60-B', retenue=Decimal('120'))
    obs['B_paiement'] = payer(fb, Decimal('1080'))
    obs['B_apres_paiement'] = etat(fb)
    r = api.post(f'{B}/factures/{fb.pk}/liberer-retenue/', {'date': today.isoformat()}, format='json', HTTP_HOST='localhost')
    obs['B_liberer'] = r.status_code
    obs['B_apres_liberation'] = etat(fb)
    vrai = sel.active_company_ids
    sel.active_company_ids = lambda *a, **k: [co.pk]
    try:
        obs['B_beat_flipped'] = scheduled.check_overdue_factures()
    finally:
        sel.active_company_ids = vrai
    obs['B_apres_beat'] = etat(fb)
    print(obs)
    a = obs['A_apres_note']
    b = obs['B_apres_beat']
    repro = (a['statut'] == 'en_retard' and a['jours_retard'] >= 85) or (b['statut'] == 'en_retard' and b['jours_retard'] >= 85)
    return {'repro': repro, **obs}
