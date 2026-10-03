"""AGR201-AGR205 — le moteur PUR ``economie_pompage`` (économie DÉCLARÉE).

Tous les cas sont des ``SimpleTestCase`` : le module est PUR (une requête en
base lèverait ici), et chaque valeur attendue est recalculée À LA MAIN dans le
test, jamais recopiée d'une sortie du moteur.

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_agr_economie_pompage -v 2
"""
from pathlib import Path

from django.test import SimpleTestCase

from apps.ventes import economie_pompage as E
from apps.ventes.economie import EconomieInvalide


def _saisie(valeur, date='2026-09-12'):
    return {'valeur': valeur, 'saisi_le': date}


def _energie(valeur, date='2026-09-12'):
    return {'valeur': valeur,
            'provenance': {'origine': 'saisie', 'detail': None, 'date': date}}


def _mois(mois, origine='saisie', detail=None):
    return {'mois': list(mois),
            'provenance': {'origine': origine, 'detail': detail,
                           'date': '2026-09-12'}}


def saisies_carburant(*, energie='butane', quantite=2, unite='bouteille_12kg',
                      periode='jour_irrigation', jours=3, prix=50.0,
                      mois=(6, 7), entretien=None):
    s = {
        'energie_actuelle': _energie(energie),
        'consommation': {'quantite': quantite, 'unite': unite,
                         'periode': periode,
                         'jours_irrigation_par_semaine': jours,
                         'saisi_le': '2026-09-12'},
        'depense_unitaire_payee': (None if prix is None else _saisie(prix)),
        'mois_irrigation': _mois(mois),
        'coherence_confirmee': False,
    }
    if entretien is not None:
        s['entretien_paye_mad_an'] = _saisie(entretien)
    return s


class DepenseActuelleTests(SimpleTestCase):
    """AGR201 — la dépense ACTUELLE vient des chiffres déclarés, jamais × 12."""

    def test_bouteilles_par_jour_d_irrigation_au_centime(self):
        dep = E.depense_actuelle(saisies_carburant())
        attendu = (2 * 3 * 30 / 7 + 2 * 3 * 31 / 7) * 50
        self.assertEqual(dep['statut'], 'calcule')
        self.assertEqual(dep['cas'], E.CAS_CARBURANT)
        self.assertEqual(dep['depense_actuelle']['annuelle_mad'],
                         round(attendu, 2))
        par_mois = dep['depense_actuelle']['par_mois']
        self.assertEqual(par_mois[5], round(2 * 3 * 30 / 7 * 50, 2))
        self.assertEqual(par_mois[6], round(2 * 3 * 31 / 7 * 50, 2))
        self.assertEqual(sum(1 for v in par_mois if v), 2)

    def test_par_mois_sur_quatre_mois_vaut_8000_jamais_24000(self):
        # 40 L/mois × 50 MAD = 2 000 MAD par mois coché.
        dep = E.depense_actuelle(saisies_carburant(
            energie='diesel', quantite=40, unite='litre', periode='mois',
            jours=None, prix=50.0, mois=(5, 6, 7, 8)))
        self.assertEqual(dep['depense_actuelle']['annuelle_mad'], 8000.0)
        self.assertNotEqual(dep['depense_actuelle']['annuelle_mad'], 24000.0)

    def test_par_semaine(self):
        dep = E.depense_actuelle(saisies_carburant(
            energie='diesel', quantite=70, unite='litre', periode='semaine',
            jours=None, prix=10.0, mois=(2,)))
        self.assertEqual(dep['depense_actuelle']['annuelle_mad'],
                         round(70 * 28 / 7 * 10, 2))

    def test_facture_bimestrielle_moins_part_fixe(self):
        dep = E.depense_actuelle({
            'energie_actuelle': _energie('electrique'),
            'facture_reseau': {'montant_mad': 1200,
                               'periodicite': 'bimestrielle',
                               'part_fixe_mad_mois': 50,
                               'saisi_le': '2026-09-12'},
            'mois_irrigation': _mois((6, 7, 8)),
        })
        self.assertEqual(dep['cas'], E.CAS_RESEAU)
        self.assertEqual(dep['depense_actuelle']['annuelle_mad'],
                         (600 - 50) * 3)

    def test_facture_sans_part_fixe_est_omise_et_nommee(self):
        dep = E.depense_actuelle({
            'energie_actuelle': _energie('electrique'),
            'facture_reseau': {'montant_mad': 1200,
                               'periodicite': 'mensuelle',
                               'saisi_le': '2026-09-12'},
            'mois_irrigation': _mois((6,)),
        })
        self.assertEqual(dep['statut'], 'omis')
        self.assertTrue(any('part fixe' in m for m in dep['motifs']))

    def test_entretien_paye_declare_s_ajoute(self):
        dep = E.depense_actuelle(saisies_carburant(entretien=1500))
        attendu = (2 * 3 * 30 / 7 + 2 * 3 * 31 / 7) * 50 + 1500
        self.assertEqual(dep['depense_actuelle']['annuelle_mad'],
                         round(attendu, 2))
        self.assertEqual(dep['depense_actuelle']['entretien_mad_an'], 1500)

    def test_aucune_energie_est_un_nouveau_forage_sans_depense(self):
        dep = E.depense_actuelle({'energie_actuelle': _energie('aucune')})
        self.assertEqual(dep['cas'], E.CAS_NOUVEAU_FORAGE)
        self.assertIsNone(dep['depense_actuelle'])

    def test_prix_absent_omis_avec_motif_nomme(self):
        dep = E.depense_actuelle(saisies_carburant(prix=None))
        self.assertEqual(dep['statut'], 'omis')
        self.assertIn('prix payé non déclaré', dep['motifs'])
        self.assertIsNone(dep['depense_actuelle'])

    def test_jours_d_irrigation_manquants_pour_une_periode_journaliere(self):
        dep = E.depense_actuelle(saisies_carburant(jours=None))
        self.assertEqual(dep['statut'], 'omis')
        self.assertIn("jours d'irrigation par semaine non déclarés",
                      dep['motifs'])

    def test_rien_declare_nomme_les_quatre_saisies(self):
        bloc = E.economie_pompage({})
        self.assertEqual(bloc['statut'], 'omis')
        self.assertFalse(bloc['publiable_client'])
        self.assertIsNone(bloc['cas'])
        self.assertEqual(bloc['motifs_non_publiable'], [
            'énergie actuelle non déclarée', 'consommation non déclarée',
            'prix payé non déclaré', "mois d'irrigation non déclarés"])

    def test_aucun_prix_n_est_pre_rempli(self):
        """Q17 : une énergie sans prix ne reçoit JAMAIS de prix de repli."""
        dep = E.depense_actuelle(saisies_carburant(prix=None))
        self.assertIsNone(dep['valeur_unitaire'])

    def test_une_saisie_invalide_est_refusee_en_nommant_le_champ(self):
        with self.assertRaises(EconomieInvalide) as ctx:
            E.depense_actuelle(saisies_carburant(quantite=-1))
        self.assertEqual(ctx.exception.champ, 'consommation.quantite')

    def test_entrees_declarees_et_mention(self):
        dep = E.depense_actuelle(saisies_carburant())
        cles = [e['cle'] for e in dep['entrees_declarees']]
        self.assertEqual(cles, [
            'energie_actuelle', 'consommation', 'jours_irrigation_par_semaine',
            'depense_unitaire_payee', 'mois_irrigation'])
        self.assertEqual(E.mention_declaration(dep['entrees_declarees'][1]),
                         'déclaré par le client le 12/09')

    def test_mois_du_calendrier_de_culture_publies_comme_tels(self):
        s = saisies_carburant()
        s['mois_irrigation'] = _mois((6, 7), origine='calculee',
                                     detail='calendrier_culture')
        dep = E.depense_actuelle(s)
        entree = [e for e in dep['entrees_declarees']
                  if e['cle'] == 'mois_irrigation'][0]
        self.assertEqual(entree['provenance']['detail'], 'calendrier_culture')
        self.assertEqual(E.mention_declaration(entree),
                         'pré-cochés selon le calendrier de culture')

    def test_l_ancienne_cle_fuel_spend_current_n_est_jamais_lue(self):
        source = Path(E.__file__).read_text(encoding='utf-8')
        for interdit in ("'fuel_spend_current'", 'force_motrice'):
            self.assertFalse(interdit in source, interdit)

    def test_module_pur_sans_modele(self):
        source = Path(E.__file__).read_text(encoding='utf-8')
        for interdit in ('.objects', 'import models', 'prix_achat'):
            self.assertFalse(interdit in source, interdit)


# ── AGR202 ──────────────────────────────────────────────────────────────────

CHARGES = {'charges_pompage_solaire': [
    {'libelle': 'Nettoyage des panneaux et visite annuelle',
     'montant_mad_an': 600.0, 'source': 'barème société'}]}
REGLE_FDA = {'regle_fda_pompage': {
    'taux_pct': 30, 'plafond_mad_par_ha': 3000, 'plafond_mad_par_kwc': 3000,
    'plafond_mad_par_projet': 30000, 'base': 'ttc',
    'source': 'Guide FDA édition 2024, p.20-23', 'releve_le': '2026-10-02'}}


def ligne(designation, pu, *, tva=0, quantite=1, type_equipement=None,
          role=None, garantie=None, optionnelle=False):
    return {'designation': designation, 'quantite': quantite,
            'prix_unitaire': pu, 'remise': 0, 'taux_tva': tva,
            'optionnelle': optionnelle, 'type_ligne': 'produit',
            'type_equipement': type_equipement, 'role_pompage': role,
            'garantie_mois': garantie}


def lignes_reference(*, garantie_variateur=None, tva_panneaux=20):
    """Investissement 50 000 TTC : pompe 8 000 TTC + 42 000 TTC autres."""
    lignes = [
        ligne('Pompe immergée', 8000, type_equipement='pompe'),
        ligne('Panneaux', 35000, tva=tva_panneaux),
    ]
    if garantie_variateur is not None:
        lignes[1] = ligne('Panneaux', 30000, tva=tva_panneaux)
        lignes.append(ligne('Variateur', 6000, role='variateur_pompage',
                            garantie=garantie_variateur))
    return lignes


def saisies_12000():
    """Diesel : 100 L par mois × 10 MAD × 12 mois = 12 000 MAD/an."""
    return saisies_carburant(energie='diesel', quantite=100, unite='litre',
                             periode='mois', jours=None, prix=10.0,
                             mois=range(1, 13))


ETUDE_COUVERTE = {'couverture_pct_mois': [120] * 12,
                  'pompe': {'mode': 'neuve'}}


class FluxPompageTests(SimpleTestCase):
    """AGR202 — charges, remplacements au TTC réel, flux 10 ans, retour sans
    aide, par ``economie.flux_de_tresorerie``."""

    def bloc(self, **kw):
        kw.setdefault('sortie_etude', ETUDE_COUVERTE)
        kw.setdefault('lignes', lignes_reference())
        kw.setdefault('reglages', CHARGES)
        return E.economie_pompage(kw.pop('saisies', saisies_12000()), **kw)

    def test_cas_de_reference_recalcule_a_la_main(self):
        bloc = self.bloc()
        eco = bloc['economie']
        flux = [-50000.0] + [12000.0 - 600.0] * 10
        flux[7] -= 8000.0
        cumul, cumuls = 0.0, []
        for f in flux:
            cumul += f
            cumuls.append(cumul)
        retour = next(a for a, c in enumerate(cumuls) if c >= 0)
        self.assertEqual(eco['horizon_ans'], 10)
        self.assertEqual([lg['flux_mad'] for lg in eco['flux']],
                         [round(f, 2) for f in flux])
        self.assertEqual([lg['cumul_mad'] for lg in eco['flux']],
                         [round(c, 2) for c in cumuls])
        self.assertEqual(eco['retour_ans'], retour)
        self.assertEqual(retour, 5)
        self.assertIsNone(eco['van_mad'])
        self.assertTrue(bloc['publiable_client'])
        self.assertEqual(bloc['statut'], 'calcule')
        self.assertEqual(bloc['remplacements'][0], {
            'composant': 'pompe', 'annee': 7, 'montant_ttc_mad': 8000.0,
            'source': E.SOURCE_POMPE, 'motif': None})

    def test_hypotheses_horizon_indexation_degradation_sourcees(self):
        hyp = {h['cle']: h for h in self.bloc()['economie']['hypotheses']}
        self.assertEqual(hyp['horizon_ans']['source'], E.SOURCE_HORIZON)
        self.assertEqual(hyp['indexation_pct']['valeur'], 0.0)
        self.assertIn('il peut monter ou baisser',
                      hyp['indexation_pct']['source'])
        self.assertEqual(hyp['degradation_pct']['valeur'], 0.0)
        self.assertIn('sans objet', hyp['degradation_pct']['source'])

    def test_variateur_garantie_24_mois_remplace_en_annee_2(self):
        bloc = self.bloc(lignes=lignes_reference(garantie_variateur=24))
        var = [r for r in bloc['remplacements']
               if r['composant'] == 'variateur'][0]
        self.assertEqual(var['annee'], 2)
        self.assertEqual(var['montant_ttc_mad'], 6000.0)
        flux = bloc['economie']['flux']
        self.assertEqual(flux[2]['flux_mad'], round(12000 - 600 - 6000, 2))

    def test_variateur_garantie_vide_omission_nommee(self):
        bloc = self.bloc(lignes=lignes_reference(garantie_variateur=0))
        var = [r for r in bloc['remplacements']
               if r['composant'] == 'variateur'][0]
        self.assertIsNone(var['annee'])
        self.assertIn('garantie constructeur', var['motif'])
        self.assertIn('remplacement_variateur',
                      [o['cle'] for o in bloc['economie']['omissions']])

    def test_variateur_garantie_au_dela_de_10_ans_omise(self):
        bloc = self.bloc(lignes=lignes_reference(garantie_variateur=132))
        var = [r for r in bloc['remplacements']
               if r['composant'] == 'variateur'][0]
        self.assertIsNone(var['annee'])

    def test_pompe_existante_aucune_provision(self):
        bloc = self.bloc(sortie_etude={'couverture_pct_mois': [120] * 12,
                                       'pompe': {'mode': 'existante'}})
        pompe = bloc['remplacements'][0]
        self.assertIsNone(pompe['montant_ttc_mad'])
        self.assertEqual(pompe['motif'], 'pompe conservée dans les deux '
                                         'scénarios : aucune provision de '
                                         'remplacement')
        self.assertEqual(bloc['economie']['flux'][7]['flux_mad'], 11400.0)

    def test_bareme_vide_non_publiable(self):
        bloc = self.bloc(reglages={})
        self.assertFalse(bloc['publiable_client'])
        self.assertIn('barème des charges solaires non saisi',
                      bloc['motifs_non_publiable'])
        self.assertIsNone(bloc['charges_solaires'])

    def test_la_tva_d_une_ligne_ne_change_que_l_investissement(self):
        a = self.bloc(lignes=lignes_reference(tva_panneaux=20))
        b = self.bloc(lignes=lignes_reference(tva_panneaux=10))
        fa, fb = a['economie']['flux'], b['economie']['flux']
        self.assertEqual(fa[0]['flux_mad'], -50000.0)
        self.assertEqual(fb[0]['flux_mad'], -(8000.0 + 35000 * 1.1))
        self.assertEqual([lg['flux_mad'] for lg in fa[1:]],
                         [lg['flux_mad'] for lg in fb[1:]])
        self.assertEqual(a['remplacements'], b['remplacements'])

    def test_une_regle_fda_ne_change_pas_le_retour(self):
        sans = self.bloc()
        avec = self.bloc(reglages=dict(CHARGES, **REGLE_FDA))
        self.assertEqual(sans['economie']['retour_ans'],
                         avec['economie']['retour_ans'])
        self.assertEqual(sans['economie']['flux'], avec['economie']['flux'])

    def test_part_evitee_plafonnee_et_couverture_sans_courbe(self):
        etude = {'couverture_pct_mois': [50] * 12, 'pompe': {'mode': 'neuve'}}
        bloc = self.bloc(sortie_etude=etude)
        self.assertEqual(bloc['economie']['flux'][1]['economie_mad'], 6000.0)
        sans = self.bloc(sortie_etude={'pompe': {'mode': 'neuve'}})
        self.assertFalse(sans['couverture']['verifiee'])
        self.assertEqual(sans['couverture']['motif'],
                         'couverture non vérifiable : pompe sans courbe')
        self.assertEqual(sans['couverture']['part_evitee_par_mois'],
                         [1] * 12)

    def test_ligne_optionnelle_hors_investissement(self):
        lignes = lignes_reference() + [ligne('Sonde', 999, optionnelle=True)]
        self.assertEqual(self.bloc(lignes=lignes)['economie']['flux'][0]
                         ['flux_mad'], -50000.0)

    def test_passe_par_flux_de_tresorerie(self):
        from unittest import mock
        with mock.patch.object(E, 'flux_de_tresorerie',
                               wraps=E.flux_de_tresorerie) as espion:
            self.bloc()
        self.assertEqual(espion.call_count, 1)

    def test_aucune_logique_d_injection_en_agricole(self):
        import json
        bloc = self.bloc()
        texte = json.dumps(bloc, ensure_ascii=False).lower()
        self.assertNotIn('injection', texte)
        self.assertNotIn('autoconsomm', texte)
        # Aucune ligne « moins subvention » dans le flux (retour SANS aide).
        self.assertNotIn('subvention',
                         json.dumps(bloc['economie'], ensure_ascii=False))
