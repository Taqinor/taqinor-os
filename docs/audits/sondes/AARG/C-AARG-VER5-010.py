# flake8: noqa  (sonde de contre-visite VER5 lot 2 — AARG62, rejouable par scripts/sonde.py)
"""AARG62 (C-AARG-VER1-304) : « Relancer » manuel avec `envoyer_email: true` joint le PDF de la facture.
(a) PDF réel : 1 mail, 1 PJ application/pdf commençant par %PDF, EmailLog « envoyé », 1 RelanceLog.
(b) PDF impossible (`_document_pdf` → (None, None), injection de panne sur le seul rendu) : le Then dit
« EmailLog échec, réponse qui le dit » — on mesure le code HTTP, ce que la réponse dit de l'échec, le nombre
de RelanceLog consignés (un niveau consommé sans mail parti ?) et le prochain niveau de la cadence.
`repro` = vrai quand (a) est faux OU quand (b) consomme un niveau / ne dit rien de l'échec. Transaction annulée."""
SONDE = {"constat": "C-AARG-VER1-304", "sha": "2781a2049",
         "attendu": "(a) 1 mail + PJ %PDF, EmailLog envoye ; (b) 0 mail, EmailLog echec, reponse qui le dit, aucun niveau consomme",
         "modeles": ["authentication.Company", "ventes.Facture", "ventes.EmailLog", "ventes.RelanceLog"]}


def sonde(ctx):
    from datetime import timedelta
    from decimal import Decimal
    from unittest.mock import patch
    from django.core import mail
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import EmailLog, Facture, LigneFacture, RelanceLog
    from apps.ventes import scheduled
    from apps.ventes.domain.facturation_ops import emettre_facture
    from apps.ventes.domain.recouvrement import prochain_niveau
    from apps.ventes.recouvrement import ensure_default_followup_levels
    co = Company.objects.create(nom='Sonde VER5-010', slug='sonde-ver5-010')
    u = get_user_model().objects.create_user(username='sonde-v5010', password='x', role_legacy='admin', company=co)
    cl = Client.objects.create(company=co, nom='Tazi', prenom='Salma', email='v5010@example.invalid',
                               telephone='+212600005010')
    p = Produit.objects.create(company=co, nom='Kit', sku='SONDE-V5010', prix_vente=Decimal('1000'), quantite_stock=0)
    today = scheduled.casablanca_today()
    ensure_default_followup_levels(co)

    def ob():
        return getattr(mail, 'outbox', [])

    def facture(ref):
        f = Facture.objects.create(company=co, reference=f'BROUILLON-{ref}', client=cl, statut=Facture.Statut.BROUILLON,
                                   taux_tva=Decimal('20'), created_by=u)
        LigneFacture.objects.create(facture=f, produit=p, designation='Kit', quantite=Decimal('1'),
                                    prix_unitaire=Decimal('1000'), taux_tva=Decimal('20'))
        emettre_facture(Facture.objects.get(pk=f.pk), source='sonde')
        Facture.objects.filter(pk=f.pk).update(date_emission=today - timedelta(days=40),
                                               date_echeance=today - timedelta(days=10),
                                               statut=Facture.Statut.EN_RETARD)
        return Facture.objects.get(pk=f.pk)

    api = APIClient()
    api.force_authenticate(u)
    H = dict(format='json', HTTP_HOST='localhost')
    obs = {}
    f1, f2 = facture('V5010-1'), facture('V5010-2')
    # (a) PDF réel
    avant = len(ob())
    r = api.post(f'/api/django/ventes/factures/{f1.id}/relancer/', {'envoyer_email': True}, **H)
    envoyes = ob()[avant:]
    obs['a_http'] = r.status_code
    obs['a_mails'] = len(envoyes)
    obs['a_pj'] = [[(nom, mime, bytes(c[:4]) == b'%PDF' if isinstance(c, (bytes, bytearray)) else None)
                    for nom, c, mime in m.attachments] for m in envoyes]
    obs['a_emaillog'] = list(EmailLog.objects.filter(facture=f1).values_list('statut', 'piece_jointe', 'erreur'))
    obs['a_relancelog'] = RelanceLog.objects.filter(facture=f1).count()
    # (b) PDF impossible
    niveau_avant, _t = prochain_niveau(Facture.objects.get(pk=f2.pk))
    obs['b_niveau_avant'] = getattr(niveau_avant, 'ordre', None)
    avant = len(ob())
    with patch('apps.ventes.email_service._document_pdf', return_value=(None, None)):
        r = api.post(f'/api/django/ventes/factures/{f2.id}/relancer/', {'envoyer_email': True}, **H)
    obs['b_http'] = r.status_code
    data = r.data if isinstance(r.data, dict) else {}
    obs['b_reponse_cles_email'] = {k: data.get(k) for k in data if 'mail' in k or 'envoi' in k or 'erreur' in k or k == 'detail'}
    obs['b_mails'] = len(ob()) - avant
    obs['b_emaillog'] = list(EmailLog.objects.filter(facture=f2).values_list('statut', 'erreur'))
    obs['b_relancelog'] = list(RelanceLog.objects.filter(facture=f2).values_list('niveau', 'compte_dans_cadence'))
    niveau_apres, _t = prochain_niveau(Facture.objects.get(pk=f2.pk))
    obs['b_niveau_apres'] = getattr(niveau_apres, 'ordre', None)
    print(obs)
    a_ok = (obs['a_http'] == 200 and obs['a_mails'] == 1 and len(obs['a_pj']) == 1 and len(obs['a_pj'][0]) == 1
            and obs['a_pj'][0][0][1] == 'application/pdf' and obs['a_pj'][0][0][2] is True
            and obs['a_emaillog'] and obs['a_emaillog'][0][0] == EmailLog.Statut.ENVOYE)
    b_echec_logue = (obs['b_mails'] == 0 and len(obs['b_emaillog']) == 1
                     and obs['b_emaillog'][0][0] == EmailLog.Statut.ECHEC)
    b_niveau_consomme = obs['b_niveau_apres'] != obs['b_niveau_avant']
    b_reponse_muette = not any(v for k, v in obs['b_reponse_cles_email'].items() if k != 'email_log_id')
    return {'repro': (not a_ok) or (not b_echec_logue) or b_niveau_consomme or b_reponse_muette,
            'a_ok': a_ok, 'b_echec_logue': b_echec_logue, 'b_niveau_consomme': b_niveau_consomme,
            'b_reponse_muette': b_reponse_muette, **obs}
