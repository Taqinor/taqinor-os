# flake8: noqa  (sonde d'audit parcours PA4, rejouable par scripts/sonde.py — AMET93)
"""K13 : `apps/ventes/domain/imports.py::creer_facture_import` numérote une facture importée non-brouillon par
`core.numbering.create_with_reference(Facture, 'FAC', …)` — préfixe codé en dur, hors de la série configurée
(`company_settings.create_numbered` / `doc_prefixes`, utilisée par `numeroter_a_l_emission`) — et pose EMISE/PAYEE
sans `date_emission`, sans échéance et sans `facture_emise`. Transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AARG-013", "sha": "56d5b623a",
         "attendu": "doc_prefixes facture='FA' ; import ligne statut 'posted' → référence 'FAC-…' (pas 'FA-…'), statut emise, date_echeance None, 0 facture_emise ; témoin émission normale → 'FA-…' (date_emission = jour de l'import par défaut du modèle, pas None : volet réfuté)",
         "modeles": ["authentication.Company", "facturation.Facture"]}


def sonde(ctx):
    from decimal import Decimal
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.parametres.models import CompanyProfile
    from apps.ventes.models import Facture
    from apps.ventes.domain.imports import creer_facture_import
    from apps.ventes.domain.facturation_ops import emettre_facture
    from core.events import facture_emise
    co = Company.objects.create(nom='Sonde AARG-013', slug='sonde-aarg-013')
    prof = CompanyProfile.get(company=co)
    prof.doc_prefixes = {'facture': 'FA'}
    prof.save()
    cl = Client.objects.create(company=co, nom='Client K13', email='k13-aarg@example.invalid')
    recus = []

    def _r(sender, instance=None, **kw):
        if getattr(instance, 'company_id', None) == co.pk:
            recus.append(instance.pk)
    facture_emise.connect(_r, weak=False)
    try:
        statut_import, motif, f = creer_facture_import(
            co, {'statut': 'posted', 'client_email': cl.email, 'client_nom': cl.nom, 'reference_source': 'ODOO/2026/0042'})
        temoin = Facture.objects.create(company=co, client=cl, statut=Facture.Statut.BROUILLON, libelle='Témoin')
        temoin_err = None
        try:
            emettre_facture(temoin, source='sonde')
        except Exception as exc:
            temoin_err = f'{type(exc).__name__}: {str(exc)[:120]}'
        temoin.refresh_from_db()
    finally:
        facture_emise.disconnect(_r)
    obs = {'import': statut_import, 'motif': motif}
    if f is not None:
        f.refresh_from_db()
        obs.update({'ref_import': f.reference, 'statut_import': f.statut, 'date_emission_import': str(f.date_emission),
                    'date_echeance_import': str(f.date_echeance), 'facture_emise_import': f.pk in recus})
    obs.update({'ref_temoin': temoin.reference, 'statut_temoin': temoin.statut, 'temoin_erreur': temoin_err,
                'facture_emise_temoin': temoin.pk in recus})
    print(obs)
    repro = (f is not None and f.reference.startswith('FAC') and not f.reference.startswith('FA-')
             and f.statut == Facture.Statut.EMISE and f.date_echeance is None and f.pk not in recus
             and temoin.reference.startswith('FA-'))
    return {'repro': repro, **obs}
