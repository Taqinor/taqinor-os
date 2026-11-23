"""CALX300 — la section « Chaîne de pertes » du rapport, séquentielle, en table.

Ce qui est prouvé ici, sur la cascade du CONTRAT
(``contract_samples/calepinage_pertes_cascade.json``, CALX141) :

* la DERNIÈRE valeur ``kwh_apres`` imprimée est exactement celle du contrat —
  aucune arithmétique locale : ni arrondi (``15792.34`` s'imprime
  ``15792,34``), ni total recalculé (un ``total_pct`` servi incohérent est
  imprimé TEL QUEL) ;
* six colonnes, de l'irradiance incidente à l'énergie livrée, plus la ligne de
  total ;
* un poste NON SOURCÉ est imprimé hachuré ET nommé (« source non
  renseignée »), jamais masqué ; une étape omise s'imprime « omis » avec son
  motif, jamais « 0 » ; un gain garde son signe servi ;
* sans cascade, la section imprime la liste plate EN DISANT que la cascade
  n'a pas été produite — jamais une table vide ; sans l'une ni l'autre, la
  phrase de motif ;
* dans le rapport assemblé, la section passe par ce rédacteur et sa feuille
  est posée dans le ``<head>``.

Run :
    cd backend/django_core
    python -m pytest apps/calepinage/tests/test_calx300_section_pertes.py -q
"""
import copy
import json
import pathlib
import re
import unittest
from html import escape
from types import SimpleNamespace

from apps.calepinage.services.rapport import (
    construire_rapport, html_de_rapport, nombre_tel_que_servi,
)
from apps.calepinage.services.rapport.pertes import (
    MENTION_CASCADE_ABSENTE, _energie_livree, html_de_section,
)

RACINE_APP = pathlib.Path(__file__).resolve().parents[1]


def _charger(nom):
    return json.loads((RACINE_APP / 'contract_samples' / nom)
                      .read_text(encoding='utf-8'))


CASCADE = _charger('calepinage_pertes_cascade.json')
RESULTAT = _charger('calepinage_resultat.json')
MOTIF = ("Ni cascade de pertes ni poste de perte déclaré : lancez la "
         "simulation (étape Résultats), ou déclarez les postes dans "
         "l'éditeur de pertes.")


def contexte(resultat, langue='fr'):
    return {'resultat': resultat, 'langue': langue,
            'section': {'code': 'pertes', 'motif_si_absent': MOTIF}}


def cascade_du_contrat():
    return copy.deepcopy(CASCADE['exemple']['cascade'])


def cellules(html, classe):
    """Le texte des cellules ``classe`` (sans leur ligne de détail)."""
    brutes = re.findall(r'<td class="kwh %s">(.*?)</td>' % classe, html)
    return [re.sub(r'<span class="detail">.*?</span>', '', c).strip()
            for c in brutes]


class AucuneArithmetiqueTest(unittest.TestCase):
    def test_la_derniere_energie_imprimee_est_celle_du_contrat(self):
        cascade = cascade_du_contrat()
        html = html_de_section(contexte({'cascade': cascade}))
        imprimees = [c for c in cellules(html, 'kwh-apres') if c != '—']
        attendue = [e['kwh_apres'] for e in cascade['etapes']
                    if e['kwh_apres'] is not None][-1]
        self.assertEqual(imprimees[-1], nombre_tel_que_servi(attendue))
        self.assertEqual(imprimees[-1], '15 792,3')  # R3-18
        self.assertEqual(_energie_livree(cascade), attendue)

    def test_aucun_arrondi(self):
        cascade = cascade_du_contrat()
        # La DERNIÈRE étape chiffrée (une étape omise peut la suivre).
        [e for e in cascade['etapes']
         if e['kwh_apres'] is not None][-1]['kwh_apres'] = 15792.34
        html = html_de_section(contexte({'cascade': cascade}))
        self.assertEqual([c for c in cellules(html, 'kwh-apres')
                          if c != '—'][-1], '15 792,34')

    def test_le_total_imprime_est_celui_servi_jamais_recalcule(self):
        cascade = cascade_du_contrat()
        cascade['total_pct'] = 99.9      # volontairement incohérent
        html = html_de_section(contexte({'cascade': cascade}))
        total = re.search(r'<tr class="total">.*?</tr>', html).group(0)
        self.assertIn('<td>99,9</td>', total)

    def test_l_irradiance_incidente_est_le_premier_kwh_avant(self):
        html = html_de_section(contexte({'cascade': cascade_du_contrat()}))
        total = re.search(r'<tr class="total">.*?</tr>', html).group(0)
        self.assertIn('16 800,0', total)  # R3-18 : milliers groupés
        self.assertIn('Irradiance incidente', total)
        self.assertIn('Énergie livrée', total)


class TableTest(unittest.TestCase):
    def setUp(self):
        self.html = html_de_section(contexte({'cascade': cascade_du_contrat()}))

    def test_six_colonnes_et_une_ligne_par_etape_plus_le_total(self):
        entete = re.search(r'<table class="pertes-cascade"><tr>(.*?)</tr>',
                           self.html).group(1)
        self.assertEqual(entete.count('<th'), 6)
        self.assertEqual(len(re.findall(r'<tr[^>]*data-etape=', self.html)),
                         len(cascade_du_contrat()['etapes']))
        self.assertEqual(self.html.count('<tr class="total">'), 1)

    def test_un_poste_non_source_est_hachure_et_nomme(self):
        ligne = re.search(r'<tr class="[^"]*non-source[^"]*" '
                          r'data-etape="indisponibilite">.*?</tr>',
                          self.html)
        self.assertIsNotNone(ligne, 'poste non sourcé masqué ou non hachuré')
        self.assertIn('source non renseignée', ligne.group(0))
        self.assertIn('Indisponibilité réseau et maintenance', ligne.group(0))

    def test_une_etape_omise_dit_omis_et_son_motif_jamais_zero(self):
        ligne = re.search(r'<tr[^>]*data-etape="spectral">.*?</tr>',
                          self.html).group(0)
        self.assertIn('<td>omis</td>', ligne)
        self.assertNotIn('CALX', ligne)  # R3-19 : jamais un code de tâche
        self.assertIn('Le spectral figure dans la cascade', ligne)
        self.assertNotIn('<td>0</td>', ligne)

    def test_un_gain_garde_son_signe_servi(self):
        ligne = re.search(r'<tr[^>]*data-etape="bifacial">.*?</tr>',
                          self.html).group(0)
        self.assertIn('-3,0 (gain)', ligne)

    def test_la_source_et_sa_reference_sont_imprimees(self):
        ligne = re.search(r'<tr[^>]*data-etape="irradiation_plan">.*?</tr>',
                          self.html).group(0)
        self.assertIn('PVGIS', ligne)
        self.assertIn('PVGIS-SARAH3', ligne)

    def test_les_postes_non_sources_sont_rappeles(self):
        self.assertIn('availability', self.html)

    def test_les_en_tetes_suivent_la_langue(self):
        html = html_de_section(contexte({'cascade': cascade_du_contrat()},
                                        langue='en'))
        self.assertIn('Energy out (kWh)', html)
        self.assertIn('Chain total', html)


class SchemaEnergieTest(unittest.TestCase):
    """ACAL773 — « où va l'énergie » sous le diagramme de la cascade."""

    def test_le_schema_d_energie_est_imprime_apres_la_cascade(self):
        from apps.calepinage.services.diagramme_energie import svg_d_energie
        from apps.calepinage.services.diagramme_pertes import (
            svg_embarquable,
        )
        resultat = copy.deepcopy(RESULTAT['exemple'])
        html = html_de_section(contexte(resultat))
        attendu = svg_embarquable(svg_d_energie(resultat, langue='fr'))
        self.assertIn(attendu, html)
        self.assertIn("Où va l'énergie".replace("'", '&#x27;'), html)
        self.assertLess(html.index('diagramme-pertes'),
                        html.index('diagramme-energie'))

    def test_titre_en_anglais(self):
        html = html_de_section(contexte(
            copy.deepcopy(RESULTAT['exemple']), langue='en'))
        self.assertIn('Where the energy goes', html)

    def test_sans_postes_lisibles_le_motif_remplace_le_schema(self):
        resultat = copy.deepcopy(RESULTAT['exemple'])
        del resultat['cascade']['postes_lisibles']
        html = html_de_section(contexte(resultat))
        self.assertIn('Aucune cascade regroup', html)
        self.assertNotIn('class="bloc"', html)
        self.assertIn('pertes-cascade', html)    # la table reste


def _resultat_avec_iam(**entree):
    resultat = copy.deepcopy(RESULTAT['exemple'])
    etapes = [e for e in resultat['cascade']['etapes']
              if e.get('etape') != 'iam']
    # Les chiffres de l'étape sont ceux de la 1re étape de l'échantillon :
    # aucune perte chiffrée en dur (CAL238) ; seuls l'IAM et son entrée
    # sont propres au cas.
    iam = copy.deepcopy(resultat['cascade']['etapes'][0])
    iam.update(etape='iam', libelle='IAM', source='fiche', entree=entree)
    etapes.append(iam)
    resultat['cascade']['etapes'] = etapes
    return resultat


def _table_essai():
    return [{'angle_deg': a, 'facteur': round(1 - (a / 100) ** 2 / 10, 6)}
            for a in range(0, 100, 10)]


class TableIamTest(unittest.TestCase):
    """ACAL772 — la table IAM de l'étape, telle que servie."""

    def test_dix_lignes_et_legende_du_modele(self):
        table = _table_essai()
        html = html_de_section(contexte(_resultat_avec_iam(
            table_iam=table, modele='fresnel', indice_verre=1.526)))
        self.assertIn("Facteur d&#x27;incidence (IAM)", html)
        self.assertIn('Angle (°)', html)
        for ligne in table:
            self.assertIn('<td class="kwh">%s</td><td class="kwh">%s</td>' % (
                nombre_tel_que_servi(ligne['angle_deg']),
                nombre_tel_que_servi(ligne['facteur'])), html)
        self.assertIn('Modèle : Fresnel · indice du verre 1,526', html)
        self.assertLess(html.index('diagramme-pertes'), html.index('table-iam'))

    def test_ashrae_ajoute_b0_et_l_anglais_traduit_les_titres(self):
        html = html_de_section(contexte(_resultat_avec_iam(
            table_iam=_table_essai(), modele='ashrae', indice_verre=1.5,
            b0=0.05), langue='en'))
        self.assertIn('Model : ASHRAE · glass index 1.5 · b0 0.05', html)
        self.assertIn('Incidence angle modifier (IAM)', html)

    def test_etape_omise_ou_sans_table_n_imprime_rien(self):
        omise = _resultat_avec_iam(table_iam=_table_essai(), modele='fresnel')
        omise['cascade']['etapes'][-1]['motif_omission'] = 'Pas de verre.'
        self.assertNotIn('table-iam', html_de_section(contexte(omise)))
        sans = _resultat_avec_iam(modele='fresnel')
        self.assertNotIn('table-iam', html_de_section(contexte(sans)))


class MotifsLisiblesTest(unittest.TestCase):
    """R3-19 — un chemin interne ne s'imprime jamais ; le motif SERVI, relu
    par ``a_renseigner``, reste intact."""

    CHEMINS = ('simulation.salissure_mensuelle_pct', 'ombrage.shading12x24',
               'FicheTechnique.degradation_annuelle_pct',
               'serie.points[].t_cell_c', 'un.chemin_inconnu')

    def _html(self, champ):
        resultat = copy.deepcopy(RESULTAT)
        etape = resultat['exemple']['cascade']['etapes'][0]
        etape['motif_omission'] = 'Étape omise. Champ manquant : « %s ».' % (
            champ)
        return html_de_section(contexte(resultat['exemple'])), etape

    def test_aucun_chemin_brut_dans_le_rapport_et_le_motif_servi_est_intact(
            self):
        for champ in self.CHEMINS:
            with self.subTest(champ=champ):
                html, etape = self._html(champ)
                self.assertNotIn(champ, html)
                self.assertIn('Champ manquant : « %s ».' % champ,
                              etape['motif_omission'])

    def test_un_chemin_connu_imprime_son_intitule_un_inconnu_est_generique(
            self):
        html, _ = self._html('ombrage.shading12x24')
        self.assertIn('matrice d&#x27;ombrage 12 mois × 24 heures', html)
        html, _ = self._html('un.chemin_inconnu')
        self.assertIn('Une donnée manque', html)

    def test_liste_non_renseigne_et_reglage_de_la_societe(self):
        from apps.calepinage.services.rapport.champs_lisibles import (
            motif_lisible,
        )

        texte = motif_lisible(
            'Non renseigné(s) : « FicheTechnique.degradation_annuelle_pct »,'
            ' « FicheTechnique.degradation_annee1_pct ». Champ manquant : '
            '« simulation.salissure_mensuelle_pct ».')
        self.assertNotIn('FicheTechnique', texte)
        self.assertNotIn('simulation.', texte)
        self.assertIn('dégradation annuelle du module', texte)
        self.assertIn('Salissure, mois par mois', texte)
        # Une phrase sans chemin est rendue telle quelle.
        phrase = 'Un facteur 1 supposé se lirait « aucune ombre, vérifié ».'
        self.assertEqual(motif_lisible(phrase), phrase)


class FamilleDeMotifsSansNomInterneTest(unittest.TestCase):
    """R3-19 (suite) — aucun motif que les services peuvent produire ne sort
    de ``motif_lisible`` avec un code de tâche, un chemin pointé, une clé en
    soulignés ou un index."""

    INTERDIT = re.compile(r'[A-Za-z]{2}\.[A-Za-z_]{2}|_|\[\]|\[\d+\]|::|CALX|ACAL|\bCAL\d')

    def test_les_motifs_du_contrat_et_des_services_sont_propres(self):
        import importlib
        import pkgutil

        from apps.calepinage import services
        from apps.calepinage.services.rapport.champs_lisibles import (
            motif_lisible,
        )

        phrases = set()
        for racine in (RACINE_APP / 'contract_samples').glob('*.json'):
            for motif in _motifs_du_json(json.loads(
                    racine.read_text(encoding='utf-8'))):
                phrases.add(motif)
        for info in pkgutil.walk_packages(services.__path__,
                                          services.__name__ + '.'):
            try:
                module = importlib.import_module(info.name)
            except Exception:  # noqa: BLE001 — un module sans dépendance locale
                continue
            for nom, valeur in vars(module).items():
                if nom.startswith('MOTIF') and isinstance(valeur, str):
                    phrases.add(valeur)
        self.assertGreater(len(phrases), 50)
        for phrase in sorted(phrases):
            with self.subTest(phrase=phrase[:60]):
                sortie = motif_lisible(phrase.replace('{', '').replace('}', ''))
                self.assertIsNone(self.INTERDIT.search(sortie), sortie)

    def test_les_exemples_du_rapport(self):
        from apps.calepinage.services.rapport.champs_lisibles import (
            motif_lisible,
        )

        attendus = {
            'Meeus par core.calepinage.soleil (CALX146).':
                'Meeus par position du soleil.',
            'Il faut la fiche (FicheTechnique.sous_chaines_par_module) et '
            "l'accès (solarAccess.bandes). L'un manque.":
                "Il faut la fiche et l'accès. L'un manque.",
            'Étape omise. Champ manquant : « un.chemin_inconnu ».':
                'Étape omise. Une donnée manque.',
            'Pertes non renseignées (salissure, lid, ohmique_dc) : non publiée.':
                'Pertes non renseignées (salissure, LID (première exposition), '
                'pertes ohmiques DC) : non publiée.',
        }
        for brut, propre in attendus.items():
            with self.subTest(brut=brut):
                self.assertEqual(motif_lisible(brut), propre)

    def test_les_postes_non_sources_s_impriment_par_leur_libelle(self):
        resultat = copy.deepcopy(RESULTAT['exemple'])
        resultat['cascade']['postes_non_sources'] = ['ohmique_dc', 'lid']
        html = html_de_section(contexte(resultat))
        self.assertNotIn('ohmique_dc,', html)
        self.assertIn('Pertes ohmiques DC, LID (première exposition)', html)

    def test_le_resultat_servi_porte_le_texte_lisible_a_cote_du_motif(self):
        from apps.calepinage.services.rapport.champs_lisibles import (
            avec_motifs_lisibles,
        )

        motif = 'Omis. Champ manquant : « ombrage.shading12x24 ».'
        resultat = {'cascade': {'etapes': [
            {'etape': 'a', 'motif_omission': motif},
            {'etape': 'b', 'motif_omission': ''}]}}
        servi = avec_motifs_lisibles(resultat)
        a, b = servi['cascade']['etapes']
        self.assertEqual(a['motif_omission'], motif)  # la donnée ne change pas
        self.assertIn("matrice d'ombrage", a['motif_lisible'])
        self.assertNotIn('shading12x24', a['motif_lisible'])
        self.assertNotIn('motif_lisible', b)
        self.assertNotIn('motif_lisible', resultat['cascade']['etapes'][0])
        self.assertEqual(avec_motifs_lisibles({'cascade': None}),
                         {'cascade': None})

    def test_l_echantillon_du_resultat_porte_le_texte_lisible(self):
        from apps.calepinage.services.rapport.champs_lisibles import (
            motif_lisible,
        )

        echantillon = json.loads((RACINE_APP / 'contract_samples'
                                  / 'calepinage_resultat.json').read_text(
                                      encoding='utf-8'))['exemple']
        for etape in echantillon['cascade']['etapes']:
            if etape.get('motif_omission'):
                self.assertEqual(etape['motif_lisible'],
                                 motif_lisible(etape['motif_omission']))

    def test_un_decimal_se_groupe_comme_un_nombre(self):
        from decimal import Decimal

        self.assertEqual(nombre_tel_que_servi(Decimal('39255')),
                         '39' + chr(0x202f) + '255')
        self.assertEqual(nombre_tel_que_servi(Decimal('1234')), '1234')


def _motifs_du_json(noeud):
    if isinstance(noeud, dict):
        for cle, valeur in noeud.items():
            if 'motif' in cle and isinstance(valeur, str):
                yield valeur
            else:
                yield from _motifs_du_json(valeur)
    elif isinstance(noeud, list):
        for valeur in noeud:
            yield from _motifs_du_json(valeur)


class SansCascadeTest(unittest.TestCase):
    def test_la_liste_plate_est_imprimee_en_le_disant(self):
        pertes = copy.deepcopy(RESULTAT['exemple']['pertes'])
        for cascade in (None, CASCADE['exemple_vide']['cascade']):
            with self.subTest(cascade=cascade):
                html = html_de_section(contexte({'cascade': cascade,
                                                 'pertes': pertes}))
                self.assertIn(escape(MENTION_CASCADE_ABSENTE), html)
                self.assertEqual(len(re.findall(r'<tr(?: class="non-source")?>'
                                                r'<td>', html)), len(pertes))
                self.assertNotIn('<tr class="total">', html)
        # Le poste sans source de la liste plate reste nommé, hachuré.
        self.assertIn('<tr class="non-source"><td>Indisponibilité', html)

    def test_ni_cascade_ni_liste_rend_le_motif_pas_une_table_vide(self):
        html = html_de_section(contexte({'cascade': None, 'pertes': []}))
        self.assertNotIn('<table', html)
        self.assertIn(escape(MOTIF), html)


class DansLeRapportTest(unittest.TestCase):
    def test_la_section_passe_par_ce_redacteur_et_sa_feuille_est_en_tete(self):
        rapport = construire_rapport(
            SimpleNamespace(company=None, client_id=None, lead_id=None,
                            titre='Villa', resultat=None, pk=None),
            resultat=copy.deepcopy(RESULTAT['exemple']),
            site={}, identite={}, styles={})
        html = html_de_rapport(rapport)
        section = re.search(r'<section class="section-rapport" '
                            r'data-section="pertes">.*?</section>',
                            html, re.S).group(0)
        self.assertIn('pertes-cascade', section)
        self.assertIn('repeating-linear-gradient', html.split('</head>')[0])
        self.assertNotIn('<style>', html.split('</head>')[1])


if __name__ == '__main__':  # pragma: no cover
    unittest.main()
