# flake8: noqa  (sonde d'audit de parcours PF2 « Socle », rejouable par scripts/sonde.py — METHODE §C.4)
"""K23 — balayages quotidiens sans marqueur par occurrence. 1 équipement EN SERVICE (chantier, technicien
responsable T), garantie finissant à J+60 ; `_sweep_warranty_expiring` joué à J, J+1, J+2 (horloge
`sweeps.date.today` avancée) -> notifications `warranty_expiring` pour le MÊME équipement et la même fin.
Jumeau : 1 chantier SIGNE pose J+10 -> `_sweep_chantier_due` J, J+1, J+2 -> par manager.
(T) témoin APAR23 : facture en retard, `_sweep_facture_overdue` rejoué 2x le MÊME jour -> 1 seule."""
SONDE = {"constat": "C-ASOC-006", "sha": "c514bd8ba",
         "attendu": "repro si garantie : 3 notifications pour 1 équipement (même occurrence) ; chantier : 3 par "
                    "manager ; T : 1",
         "modeles": ["notifications.Notification", "sav.Equipement", "installations.Installation", "ventes.Facture"]}


def sonde(ctx):
    from datetime import date, timedelta
    from decimal import Decimal
    from unittest import mock
    from django.contrib.auth import get_user_model
    from django.test import TestCase, override_settings
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.installations.models import Installation
    from apps.notifications import sweeps
    from apps.notifications.models import Notification
    from apps.sav.models import Equipement
    from apps.stock.models import Produit
    from apps.ventes.models import Facture
    U = get_user_model()
    c = Company.objects.create(nom='Sonde ASOC 006', slug='sonde-asoc-006')
    tech = U.objects.create_user(username='sonde-asoc-006-tech', password='x', role_legacy='normal', company=c)
    m1 = U.objects.create_user(username='sonde-asoc-006-m1', password='x', role_legacy='admin', company=c)
    m2 = U.objects.create_user(username='sonde-asoc-006-m2', password='x', role_legacy='responsable', company=c)
    j0 = date.today()
    cl = Client.objects.create(company=c, nom='Client', prenom='K23', email='k23@example.invalid')
    p = Produit.objects.create(company=c, nom='Onduleur', sku='ASOC006-OND', prix_vente=Decimal('5000'),
                               prix_achat=Decimal('3000'), tva=Decimal('20'))
    inst = Installation.objects.create(company=c, reference='CHT-ASOC006', client=cl,
                                       statut=Installation.Statut.CLOTURE, technicien_responsable=tech)
    eq = Equipement.objects.create(company=c, produit=p, installation=inst, numero_serie='SN-ASOC006',
                                   statut=Equipement.Statut.EN_SERVICE, date_pose=j0 - timedelta(days=300))
    Equipement.objects.filter(pk=eq.pk).update(date_fin_garantie=j0 + timedelta(days=60))
    ch = Installation.objects.create(company=c, reference='CHT-ASOC006-B', client=cl,
                                     statut=Installation.Statut.SIGNE, date_pose_prevue=j0 + timedelta(days=10))

    class FD(date):
        jour = j0

        @classmethod
        def today(cls):
            return cls.jour

    obs = {'jours': []}
    with override_settings(NOTIFICATIONS_QUIET_HOURS_ENABLED=False), mock.patch.object(sweeps, 'date', FD):
        with TestCase.captureOnCommitCallbacks(execute=True):
            for k in range(3):
                FD.jour = j0 + timedelta(days=k)
                w = sweeps._sweep_warranty_expiring(c)
                cd = sweeps._sweep_chantier_due(c)
                obs['jours'].append({'jour': FD.jour.isoformat(), 'warranty_count': w, 'chantier_count': cd})
    gar = Notification.objects.filter(company=c, event_type='warranty_expiring')
    chd = Notification.objects.filter(company=c, event_type='chantier_due')
    obs['garantie'] = {'total': gar.count(), 'vers_tech': gar.filter(recipient=tech).count(),
                       'corps_distincts': len(set(gar.values_list('body', flat=True)))}
    obs['chantier_due'] = {'total': chd.count(), 'vers_m1': chd.filter(recipient=m1).count(),
                           'vers_m2': chd.filter(recipient=m2).count()}
    # T — témoin APAR23 (marqueur par jour) : facture en retard rejouée 2x le même jour
    f = Facture.objects.create(company=c, reference='FAC-ASOC006', client=cl, statut='emise',
                               taux_tva=Decimal('20'), montant_ht=Decimal('1000'), montant_tva=Decimal('200'),
                               montant_ttc=Decimal('1200'), date_emission=j0 - timedelta(days=40),
                               date_echeance=j0 - timedelta(days=10), created_by=m1)
    with override_settings(NOTIFICATIONS_QUIET_HOURS_ENABLED=False):
        with TestCase.captureOnCommitCallbacks(execute=True):
            sweeps._sweep_facture_overdue(c)
            sweeps._sweep_facture_overdue(c)
    obs['T_facture_overdue_meme_jour'] = Notification.objects.filter(company=c, event_type='facture_overdue').count()
    print(obs)
    defaut = obs['garantie']['vers_tech'] == 3 and obs['chantier_due']['vers_m1'] == 3
    obs['repro'] = bool(defaut and obs['T_facture_overdue_meme_jour'] == 1)
    return obs
