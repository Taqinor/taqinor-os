# flake8: noqa  (sonde de contre-visite VER1 lot 3 — AARG58, rejouable par scripts/sonde.py)
"""AARG58 (C-AARG-019) : le mail de relance du beat `relance_reminders()` part avec le PDF de la facture en pièce
jointe (octets réellement PDF, type application/pdf), EmailLog « envoyé » ; PDF impossible (`_document_pdf` →
(None, None)) : aucun mail, EmailLog « échec », niveau NON consommé (pas de RelanceLog), relance reportée.
Le beat réel est restreint à la société de la sonde. Observation en plus : la relance manuelle
`factures/<id>/relancer/` (facture_recouvrement.py) joint-elle le PDF ? Transaction annulée, mail en mémoire."""
SONDE = {"constat": "C-AARG-019", "sha": "06ced8b1a",
         "attendu": "beat → 1 mail avec 1 PJ application/pdf commençant par %PDF, EmailLog envoyé, RelanceLog créé ; PDF impossible → 0 mail, EmailLog échec, 0 RelanceLog, prochaine_relance reportée",
         "modeles": ["authentication.Company", "ventes.Facture", "ventes.EmailLog", "ventes.RelanceLog"]}


def sonde(ctx):
    from datetime import timedelta
    from decimal import Decimal
    from unittest.mock import patch
    from django.core import mail
    from django.contrib.auth import get_user_model
    from rest_framework.test import APIClient
    from authentication.models import Company
    import authentication.selectors as sel
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import EmailLog, Facture, LigneFacture, RelanceLog
    from apps.ventes import scheduled
    from apps.ventes.domain.facturation_ops import emettre_facture
    co = Company.objects.create(nom='Sonde VER1-304', slug='sonde-ver1-304')
    u = get_user_model().objects.create_user(username='sonde-v304', password='x', role_legacy='responsable', company=co)
    cl = Client.objects.create(company=co, nom='Chraibi', prenom='Hamza', email='v304@example.invalid',
                               telephone='+212600000304')
    p = Produit.objects.create(company=co, nom='Kit', sku='SONDE-V304', prix_vente=Decimal('1000'), quantite_stock=0)
    today = scheduled.casablanca_today()

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
                                               prochaine_relance=today)
        return Facture.objects.get(pk=f.pk)

    f1, f2 = facture('V304-1'), facture('V304-2')
    vrai = sel.active_company_ids
    sel.active_company_ids = lambda *a, **k: [co.pk]
    obs = {}
    try:
        avant = len(ob())
        # (a) PDF réel (MinIO + WeasyPrint dans la pile) ; sinon on le note
        try:
            n = scheduled.relance_reminders()
        except Exception as exc:  # noqa
            n = f'EXC {type(exc).__name__}: {exc}'
        envoyes = ob()[avant:]
        obs['a_relances'] = n
        obs['a_mails'] = len(envoyes)
        obs['a_pj'] = [[(nom, len(contenu), mime, bytes(contenu[:4]) == b'%PDF' if isinstance(contenu, (bytes, bytearray)) else None)
                        for nom, contenu, mime in m.attachments] for m in envoyes]
        obs['a_emaillog'] = list(EmailLog.objects.filter(facture__in=[f1, f2]).values_list('facture__reference', 'statut', 'piece_jointe', 'erreur'))
        obs['a_relancelog'] = RelanceLog.objects.filter(facture__in=[f1, f2]).count()
        # (b) PDF impossible : on remet les deux factures en cadence puis on coupe _document_pdf
        Facture.objects.filter(pk__in=[f1.pk, f2.pk]).update(prochaine_relance=today)
        RelanceLog.objects.filter(facture__in=[f1, f2]).delete()
        EmailLog.objects.filter(facture__in=[f1, f2]).delete()
        avant = len(ob())
        with patch('apps.ventes.email_service._document_pdf', return_value=(None, None)):
            n2 = scheduled.relance_reminders()
        obs['b_relances'] = n2
        obs['b_mails'] = len(ob()) - avant
        obs['b_emaillog'] = list(EmailLog.objects.filter(facture__in=[f1, f2]).values_list('statut', 'erreur'))
        obs['b_relancelog'] = RelanceLog.objects.filter(facture__in=[f1, f2]).count()
        obs['b_prochaine_relance'] = [str(Facture.objects.get(pk=x.pk).prochaine_relance) for x in (f1, f2)]
        # (c) relance MANUELLE (jumeau) : joint-elle le PDF ?
        api = APIClient()
        api.force_authenticate(u)
        EmailLog.objects.filter(facture__in=[f1, f2]).delete()
        avant = len(ob())
        r = api.post(f'/api/django/ventes/factures/{f1.id}/relancer/', {'canal': 'email'}, format='json',
                     HTTP_HOST='localhost')
        obs['c_manuelle_http'] = r.status_code
        obs['c_manuelle_pj'] = [[nom for nom, _c, _m in m.attachments] for m in ob()[avant:]]
    finally:
        sel.active_company_ids = vrai
    print(obs)
    a_ok = (obs['a_mails'] == 2 and all(len(pj) == 1 and pj[0][2] == 'application/pdf' and pj[0][3] for pj in obs['a_pj'])
            and obs['a_relancelog'] == 2 and all(s == 'envoye' or s == EmailLog.Statut.ENVOYE for _r, s, _p, _e in obs['a_emaillog']))
    b_ok = (obs['b_mails'] == 0 and obs['b_relancelog'] == 0
            and all(s == EmailLog.Statut.ECHEC for s, _e in obs['b_emaillog']) and len(obs['b_emaillog']) == 2
            and all(x != str(today) for x in obs['b_prochaine_relance']))
    return {'repro': not (a_ok and b_ok), 'a_ok': a_ok, 'b_ok': b_ok, **obs}
