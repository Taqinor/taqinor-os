# flake8: noqa  (sonde de vérification AMOT VER4, contre-visite fraîche, rejouable par scripts/sonde.py — AMET93)
"""C-AMOT-VER4-011 — `apps/ventes/horaire/batterie_lignes.py::ROLES_ONDULEUR` = ('onduleur_hybride', 'onduleur_reseau')
alors que `domain/catalogue.py::classer_produit` rend AUSSI 'onduleur_offgrid' : `puissances_batterie_des_lignes`
ignore donc le PORT BATTERIE (`bat_max_decharge_kw` / `bat_max_charge_kw` de la fiche onduleur) d'un onduleur
hors réseau → `ond_decharge_kw=None` et `charge_kw` = packs seuls → `etude_horaire.py::simuler_batterie_pas_fins`
(`if borne_port > 0`) et `simuler_batterie_jour` (borne de charge) ne bornent plus au port.
Même devis deux fois (onduleur « off-grid » vs « hybride », MÊME fiche : port 3 kW ; 2 packs × 5 kW), puis le
VRAI `etude_horaire_pour_devis` (lecture des lignes par `puissance_batterie_du_devis`, seuls le CRM — factures,
localisation, conso — et, en variante b, les équipements du lead sont simulés). Trois variantes : (a) sans
équipement (chemin horaire : seule la borne de CHARGE joue), (b) clim 6 kW déclarée (pas fins : borne de
DÉCHARGE), (c) cas extrême 4 packs / 12 kWc / clim 8 kW + VE 7,4 kW le soir (ampleur). `repro: true` = l'économie annuelle « avec batterie » de l'off-grid dépasse celle de l'hybride.
Société neuve, transaction annulée. Jamais contre la prod."""
SONDE = {"constat": "C-AMOT-VER4-011", "sha": "ecd7fcf40",
         "attendu": "off-grid : ond_decharge_kw None, charge_kw 10 (packs) ; hybride : ond_decharge_kw 3, charge_kw 3 ; économie annuelle avec batterie off-grid > hybride",
         "modeles": ["authentication.Company", "stock.Produit", "stock.FicheTechnique", "ventes.Devis", "ventes.LigneDevis"]}


def sonde(ctx):
    import hashlib
    import inspect
    from decimal import Decimal
    from unittest import mock
    from authentication.models import Company
    from apps.crm.models import Client
    from apps.stock.models import FicheTechnique, Produit
    from apps.ventes.models import Devis, LigneDevis
    from apps.ventes import etude_horaire as eh
    from apps.ventes.horaire import batterie_lignes as bl
    from apps.ventes.domain.catalogue import classer_produit
    from apps.ventes.courbes_journalieres import _equipements
    from apps.ventes.quote_engine.pricing import compute_cashflow_payback
    import apps.crm.selectors as crm_sel

    src = inspect.getsource(bl)
    obs = {'roles_onduleur': list(bl.ROLES_ONDULEUR),
           'batterie_lignes_sha1': hashlib.sha1(src.encode()).hexdigest()[:12]}
    c = Company.objects.create(nom='Sonde AMOT VER4 011', slug='sonde-amot-ver4-011')
    cl = Client.objects.create(company=c, nom='Isolé', prenom='V4', email='sonde-amot-ver4-011@example.invalid')

    def produit(nom, sku, **fiche):
        p = Produit.objects.create(company=c, nom=nom, sku=sku, prix_vente=Decimal('10000'),
                                   prix_achat=Decimal('0'), quantite_stock=0)
        FicheTechnique.objects.create(company=c, produit=p, **fiche)
        return p
    port = dict(type_fiche='onduleur', ond_ac_kw=Decimal('6'), ond_phases=1,
                ond_bat_max_decharge_kw=Decimal('3'), ond_bat_max_charge_kw=Decimal('3'))
    ond_off = produit('Onduleur off-grid Deye 6kW', 'SONDE-V4011-OFF', **port)
    ond_hyb = produit('Onduleur hybride Deye 6kW', 'SONDE-V4011-HYB', **port)
    bat = produit('Batterie lithium 5 kWh', 'SONDE-V4011-BAT', type_fiche='batterie',
                  bat_kwh_nominal=Decimal('5.12'), bat_kwh_usable=Decimal('5'), bat_v_nominal=Decimal('51.2'),
                  bat_max_decharge_kw=Decimal('5'), bat_max_charge_kw=Decimal('5'))
    obs['classes'] = {p.nom: classer_produit(p.nom) for p in (ond_off, ond_hyb, bat)}

    def devis(ref, ond, packs=2):
        dv = Devis.objects.create(company=c, reference=ref, client=cl, statut='brouillon',
                                  taux_tva=Decimal('20.00'), remise_globale=Decimal('0'),
                                  mode_installation='residentiel')
        for o, (p, q) in enumerate(((ond, 1), (bat, packs))):
            LigneDevis.objects.create(devis=dv, produit=p, designation=p.nom, quantite=Decimal(q),
                                      prix_unitaire=p.prix_vente, remise=Decimal('0'), ordre=o)
        return dv
    dv_off = devis('DEV-SONDE-V4011-OFF', ond_off)
    dv_hyb = devis('DEV-SONDE-V4011-HYB', ond_hyb)
    dv_off4 = devis('DEV-SONDE-V4011-OFF4', ond_off, packs=4)
    dv_hyb4 = devis('DEV-SONDE-V4011-HYB4', ond_hyb, packs=4)
    obs['puissances'] = {k: {cle: v for cle, v in bl.puissance_batterie_du_devis(dv).items()}
                         for k, dv in (('offgrid', dv_off), ('hybride', dv_hyb))}

    conso = [900, 850, 900, 950, 1100, 1300, 1500, 1550, 1300, 1000, 900, 950]
    equip_clim = _equipements({'clim': True, 'clim_kw': 6})
    data = {'client_city': 'Casablanca', 'mode_installation': 'residentiel'}
    resultats = {}
    equip_stress = _equipements({'clim': True, 'clim_kw': 8, 'clim_creneau': 'soir', 'voiture_electrique': True,
                                 've_km_semaine': 300, 've_chargeur_kw': 7.4, 've_creneau': 'soir'})
    cas = (('a_sans_equipement', {}, dv_off, dv_hyb, 8, 10),
           ('b_clim_6kw', equip_clim, dv_off, dv_hyb, 8, 10),
           ('c_stress_4packs_clim8_soir_ve_soir', equip_stress, dv_off4, dv_hyb4, 12, 20))
    for variante, equip, d_off, d_hyb, kwc, cap in cas:
        with mock.patch.object(crm_sel, 'lead_bills_for_devis', return_value={}), \
                mock.patch.object(crm_sel, 'site_location_for_devis', return_value={'site_ville': 'Casablanca'}), \
                mock.patch.object(eh, 'profil_conso_du_devis', return_value=(conso, 'sonde', {})), \
                mock.patch.object(eh, 'equipements_du_devis', return_value=equip):
            par = {}
            for k, dv in (('offgrid', d_off), ('hybride', d_hyb)):
                try:
                    bloc = eh._etude_horaire_pour_devis(dv, kwc=kwc, batterie_kwh_utile=cap, data=dict(data))
                except Exception as e:
                    par[k] = {'erreur': repr(e)[:300]}
                    continue
                if bloc is None:
                    par[k] = {'bloc': None}
                    continue
                an = bloc['annuel']
                eco = an.get('economie_avec_mad')
                pb = compute_cashflow_payback(60000.0, float(eco or 0), battery=True)
                par[k] = {'equipements_actifs': bloc.get('equipements_actifs'),
                          'source_production': bloc.get('source_production'),
                          'autoconso_sans_kwh': round(an.get('autoconsomme_sans_kwh') or 0, 1),
                          'autoconso_avec_kwh': round(an.get('autoconsomme_avec_kwh') or 0, 1),
                          'economie_sans_mad': round(an.get('economie_sans_mad') or 0, 2),
                          'economie_avec_mad': round(eco or 0, 2),
                          'payback_60k_ans': pb.get('payback_years'),
                          'cumul_25_ans': round((pb.get('cumulative') or [0])[-1], 0)}
            if 'economie_avec_mad' in par.get('offgrid', {}) and 'economie_avec_mad' in par.get('hybride', {}):
                par['ecart_economie_avec_mad'] = round(par['offgrid']['economie_avec_mad']
                                                       - par['hybride']['economie_avec_mad'], 2)
            resultats[variante] = par
    obs['etudes'] = resultats
    print(obs)
    p_off, p_hyb = obs['puissances']['offgrid'], obs['puissances']['hybride']
    ecarts = [v.get('ecart_economie_avec_mad') or 0 for v in resultats.values()]
    repro = (obs['classes'][ond_off.nom] == 'onduleur_offgrid' and p_off.get('ond_decharge_kw') is None
             and (p_hyb.get('ond_decharge_kw') or 0) > 0 and any(e > 0 for e in ecarts))
    return {'repro': repro, **obs}
