# flake8: noqa  (sonde d'audit parcours PA4, rejouable par scripts/sonde.py — AMET93)
"""K18 : D-AFAC-89 (08/10/2026, réponse a : drapeau « contestée » qui suspend les relances) n'est pas construit :
aucun champ `contest*` sur `apps/facturation/models.py::Facture`, `recouvrement.py::STATUTS_NON_RELANCABLES` =
(payee, annulee, brouillon), `recouvrement.py::facture_relancable` ne connaît aucune contestation ; le seul levier est
`exclu_relances` (booléen sans motif). Une facture échue que le client conteste est relancée par le beat RÉEL
`scheduled.py::relance_reminders` (restreint à la société de la sonde via `authentication.selectors.active_company_ids`).
Transaction annulée, mail en mémoire. Jamais contre la prod."""
SONDE = {"constat": "C-AARG-018", "sha": "56d5b623a",
         "attendu": "Facture sans champ contest* ; STATUTS_NON_RELANCABLES sans contestée ; facture échue (que le client conteste) → beat : 1 relance envoyée + RelanceLog",
         "modeles": ["authentication.Company", "facturation.Facture", "facturation.RelanceLog", "ventes.EmailLog"]}


def sonde(ctx):
    from datetime import timedelta
    from decimal import Decimal
    from django.core import mail
    from authentication.models import Company
    import authentication.selectors as sel
    from apps.crm.models import Client
    from apps.stock.models import Produit
    from apps.ventes.models import Facture, LigneFacture, RelanceLog
    from apps.ventes import scheduled
    from apps.ventes.recouvrement import STATUTS_NON_RELANCABLES, facture_relancable
    champs = [fld.name for fld in Facture._meta.get_fields() if 'contest' in fld.name.lower() or 'litige' in fld.name.lower()]
    co = Company.objects.create(nom='Sonde AARG-018', slug='sonde-aarg-018')
    cl = Client.objects.create(company=co, nom='Client conteste', email='k18-aarg@example.invalid')
    p = Produit.objects.create(company=co, nom='Kit', sku='SONDE-AARG-018', prix_vente=Decimal('1000'), quantite_stock=0)
    today = scheduled.casablanca_today()
    f = Facture.objects.create(company=co, reference='FAC-SONDE-AARG18', client=cl, statut=Facture.Statut.EN_RETARD,
                               date_emission=today - timedelta(days=40), date_echeance=today - timedelta(days=10),
                               prochaine_relance=today)
    LigneFacture.objects.create(facture=f, produit=p, designation='Kit', quantite=Decimal('1'), prix_unitaire=Decimal('1000'))
    vrai = sel.active_company_ids
    sel.active_company_ids = lambda *a, **k: [co.pk]
    avant = len(getattr(mail, 'outbox', []))
    try:
        envoyes = scheduled.relance_reminders()
    finally:
        sel.active_company_ids = vrai
    mails = [m for m in getattr(mail, 'outbox', [])[avant:] if 'k18-aarg@example.invalid' in (m.to or [])]
    logs = list(RelanceLog.objects.filter(facture=f).values_list('niveau', 'niveau_nom'))
    obs = {'champs_contest_sur_Facture': champs, 'STATUTS_NON_RELANCABLES': list(STATUTS_NON_RELANCABLES),
           'relancable': facture_relancable(Facture.objects.get(pk=f.pk)), 'envoyes': envoyes,
           'mails': len(mails), 'relance_logs': logs}
    print(obs)
    return {'repro': not champs and bool(logs or mails), **obs}
