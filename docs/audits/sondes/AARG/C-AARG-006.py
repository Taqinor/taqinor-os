# flake8: noqa  (sonde PA4 « Argent », rejouable par scripts/sonde.py — AMET93)
"""K06 : l'import de relevé bancaire (`apps/ventes/paiement_import.py::dry_run` / `::commit`) ne filtre que les statuts
ÉMISE / EN RETARD et n'appelle jamais la porte AFAC9 `domain/encaissements.py::motif_non_encaissable` (délai légal
J+7 du démarchage à domicile, CAD122 / loi 31-08 art. 49-50). Un acompte d'un BC signé au domicile AUJOURD'HUI est
encaissé par le relevé. Services réels (dry_run + commit), société neuve, transaction annulée."""
SONDE = {"constat": "C-AARG-006", "sha": "56d5b623a",
         "attendu": "acompte d'un BC signé au domicile aujourd'hui : motif_non_encaissable ≠ None ET l'import du relevé (référence exacte) ne crée aucun Paiement",
         "modeles": ["ventes.Facture", "ventes.Paiement", "ventes.BonCommande", "ventes.ReleveImportSession"]}


def sonde(ctx):
    import csv, io
    from decimal import Decimal
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.ventes.models import Devis, Facture, Paiement, BonCommande
    from apps.ventes.domain.encaissements import motif_non_encaissable
    from apps.ventes.paiement_import import dry_run, commit
    today = timezone.now().date()
    co = Company.objects.create(nom='Sonde AARG 006', slug='sonde-aarg-006')
    u = get_user_model().objects.create_user(username='sonde_aarg_006', password='x', role_legacy='admin', company=co)
    cl = Client.objects.create(company=co, nom='Client', prenom='AARG006', email='sonde-aarg-006@example.invalid')
    dv = Devis.objects.create(company=co, reference='DEV-SONDE-AARG-006', client=cl,
                              statut=Devis.Statut.ACCEPTE, taux_tva=Decimal('20'))
    BonCommande.objects.create(company=co, reference='BC-SONDE-AARG-006', devis=dv, client=cl,
                               signe_au_domicile=True, date_signature_domicile=today)
    ref = 'FAC-SONDE-AARG-006'
    fa = Facture.objects.create(company=co, devis=dv, client=cl, reference=ref,
                                type_facture=Facture.TypeFacture.ACOMPTE, statut=Facture.Statut.EMISE,
                                taux_tva=Decimal('20'), montant_ht=Decimal('2500'), montant_tva=Decimal('500'),
                                montant_ttc=Decimal('3000'), date_emission=today)
    motif = motif_non_encaissable(Facture.objects.get(pk=fa.pk), today)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=['date', 'reference', 'montant', 'mode'], delimiter=';')
    w.writeheader()
    w.writerow({'date': today.isoformat(), 'reference': ref, 'montant': '3000', 'mode': 'virement'})
    apercu = dry_run(buf.getvalue().encode('utf-8'), 'releve.csv', co, user=u)
    lignes_apercu = [{k: l.get(k) for k in ('ligne', 'statut', 'facture_reference', 'match_type') if k in l}
                     for l in (apercu.get('preview') or [])]
    res = commit(co, u, apercu['token'])
    fa = Facture.objects.get(pk=fa.pk)
    pays = [(str(p.montant), str(p.date_paiement)) for p in Paiement.objects.filter(company=co, facture=fa)]
    obs = {'motif_non_encaissable': motif, 'apercu': lignes_apercu, 'commit_created': res.get('created'),
           'commit_results': res.get('results'), 'paiements': pays, 'statut_facture': fa.statut,
           'montant_du': str(fa.montant_du)}
    print(obs)
    obs['repro'] = bool(motif) and bool(pays)
    return obs
