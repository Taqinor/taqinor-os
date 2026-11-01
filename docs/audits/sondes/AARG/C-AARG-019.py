# flake8: noqa  (sonde d'audit parcours PA4, rejouable par scripts/sonde.py — AMET93)
"""K19 : le mail de relance automatique par défaut (`recouvrement.py::NIVEAUX_RELANCE_DEFAUT` niveau 1, envoyé par
`scheduled.py::relance_reminders` → `_dispatch_relance_canal` → `email_service.py::send_relance_email` /
`composer_relance_email`) ne porte ni montant dû, ni échéance, dit « la facture ci-dessus » sans rien au-dessus
(aucune pièce jointe : attach_pdf=False) et double le « Bonjour » (salut + message du niveau qui commence par
« Bonjour, »). Le beat RÉEL est lancé, restreint à la société de la sonde en remplaçant
`authentication.selectors.active_company_ids` (lu dans la fonction) pour ne pas relancer toute la base locale.
Transaction annulée, mail en mémoire. Jamais contre la prod."""
SONDE = {"constat": "C-AARG-019", "sha": "56d5b623a",
         "attendu": "facture 1 200 TTC, paiement 500 (dû 700), échue, prochaine_relance = aujourd'hui ; beat → 1 mail : « 700 » absent, échéance absente, « ci-dessus » présent, « Bonjour » ×2, aucune pièce jointe",
         "modeles": ["authentication.Company", "facturation.Facture", "facturation.Paiement", "ventes.EmailLog"]}


def sonde(ctx):
    from datetime import timedelta
    from decimal import Decimal
    from django.core import mail
    from authentication.models import Company
    import authentication.selectors as sel
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Facture, LigneFacture, Paiement, EmailLog
    from apps.ventes import scheduled
    co = Company.objects.create(nom='Sonde AARG-019', slug='sonde-aarg-019')
    cl = Client.objects.create(company=co, nom='Benali', prenom='Karim', email='k19-aarg@example.invalid')
    p = Produit.objects.create(company=co, nom='Kit', sku='SONDE-AARG-019', prix_vente=Decimal('1000'), quantite_stock=0)
    today = scheduled.casablanca_today()
    f = Facture.objects.create(company=co, reference='FAC-SONDE-AARG19', client=cl, statut=Facture.Statut.EMISE,
                               date_emission=today - timedelta(days=40), date_echeance=today - timedelta(days=10),
                               prochaine_relance=today)
    LigneFacture.objects.create(facture=f, produit=p, designation='Kit', quantite=Decimal('1'), prix_unitaire=Decimal('1000'),
                                taux_tva=Decimal('20'))
    Paiement.objects.create(company=co, facture=f, client=cl, montant=Decimal('500'), date_paiement=today - timedelta(days=5),
                            mode='virement')
    f = Facture.objects.get(pk=f.pk)
    du = f.montant_du
    vrai = sel.active_company_ids
    sel.active_company_ids = lambda *a, **k: [co.pk]
    avant = len(getattr(mail, 'outbox', []))
    try:
        envoyes = scheduled.relance_reminders()
    finally:
        sel.active_company_ids = vrai
    mails = [m for m in getattr(mail, 'outbox', [])[avant:] if 'k19-aarg@example.invalid' in (m.to or [])]
    log = EmailLog.objects.filter(facture=f).order_by('-pk').first()
    corps = log.corps if log else (mails[0].body if mails else '')
    sujet = log.sujet if log else (mails[0].subject if mails else '')
    ech = f.date_echeance
    formes_du = ['700', '700,00', '700.00']
    obs = {'envoyes': envoyes, 'mails_outbox': len(mails), 'emaillog': bool(log), 'du': str(du), 'sujet': sujet,
           'corps': corps, 'montant_present': any(x in corps for x in formes_du),
           'echeance_presente': any(x in corps for x in (ech.isoformat(), ech.strftime('%d/%m/%Y'))),
           'ci_dessus': 'ci-dessus' in corps, 'nb_bonjour': corps.lower().count('bonjour'),
           'pieces_jointes': [len(m.attachments) for m in mails]}
    print(obs)
    repro = bool(corps) and not obs['montant_present'] and not obs['echeance_presente'] and obs['ci_dessus']
    return {'repro': repro, **obs}
