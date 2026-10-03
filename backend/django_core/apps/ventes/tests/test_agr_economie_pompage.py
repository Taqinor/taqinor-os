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
        self.assertNotIn("'fuel_spend_current'", source)
        self.assertNotIn('force_motrice', source)

    def test_module_pur_sans_modele(self):
        source = Path(E.__file__).read_text(encoding='utf-8')
        self.assertNotIn('.objects', source)
        self.assertNotIn('import models', source)
        self.assertNotIn('prix_achat', source)
