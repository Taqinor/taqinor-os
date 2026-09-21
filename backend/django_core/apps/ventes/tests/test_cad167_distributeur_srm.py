# -*- coding: utf-8 -*-
"""CAD167 — les SRM régionales, et « autre » qui cassait la courbe.

DÉCISION FONDATEUR DU 21/09/2026 (Q16) : « il n'y a plus désormais que SRM au
Maroc ». Trois choses en découlent, et ce module les verrouille.

1. **La liste devient les SRM régionales** — une par région du découpage de
   2015 — et **ONEE, Lydec, Redal, Amendis restent des libellés HISTORIQUES**,
   en lecture seule : une valeur déjà enregistrée ne disparaît jamais d'une
   fiche.
2. **La SRM se DÉDUIT de la ville** plutôt que d'être demandée. Une ville
   inconnue de la table ne produit AUCUNE déduction — on n'invente pas un
   rattachement régional (règle « checked facts »).
3. **Un distributeur inconnu résout sur la grille NATIONALE.** C'était le
   défaut le plus coûteux : ``autre`` n'était pas dans ``UTILITY_TABLES``,
   l'inversion retombait sur un prix plat inventé et se déclarait
   « estimation » — et la proposition publique MASQUE sa courbe dans ce cas.
   Nommer un distributeur faisait donc DISPARAÎTRE le graphe du client.

GARDE-FOU VÉRIFIÉ ICI AUSSI : la VALEUR du distributeur ne change AUCUN prix.
Le barème est national et unique (décision Q7 du 20/08/2026).
"""
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from authentication.models import Company
from apps.crm import srm_regions
from apps.crm.models import Lead
from apps.ventes.quote_engine import pricing


class LaListeDevientLesSrmRegionales(SimpleTestCase):
    def test_les_douze_regions_sont_proposees(self):
        valeurs = [v for v, _ in Lead.Distributeur.choices]
        for code in srm_regions.SRM_PAR_REGION:
            self.assertIn(code, valeurs, code)
        self.assertEqual(len(srm_regions.SRM_PAR_REGION), 12)

    def test_les_libelles_historiques_restent_lisibles(self):
        """Une fiche déjà saisie garde sa valeur : rien n'est retiré."""
        valeurs = [v for v, _ in Lead.Distributeur.choices]
        for code in ('onee', 'lydec', 'redal', 'autre'):
            self.assertIn(code, valeurs, code)
        libelles = dict(Lead.Distributeur.choices)
        self.assertIn('historique', libelles['onee'].lower())

    def test_amendis_rejoint_les_libelles_historiques(self):
        self.assertIn('amendis', [v for v, _ in Lead.Distributeur.choices])
        self.assertTrue(srm_regions.est_historique('amendis'))
        self.assertFalse(srm_regions.est_historique('srm_casablanca'))

    def test_chaque_code_tient_dans_la_colonne(self):
        longueur = Lead._meta.get_field('distributeur').max_length
        for code, _ in Lead.Distributeur.choices:
            self.assertLessEqual(len(code), longueur, code)

    def test_chaque_code_porte_un_libelle_francais(self):
        for code, _ in Lead.Distributeur.choices:
            self.assertTrue(srm_regions.libelle_distributeur(code), code)


class LaSrmSeDeduitDeLaVille(SimpleTestCase):
    def test_une_ville_connue_donne_sa_srm(self):
        self.assertEqual(srm_regions.srm_depuis_ville('Casablanca'),
                         'srm_casablanca')
        self.assertEqual(srm_regions.srm_depuis_ville('Agadir'), 'srm_souss')
        self.assertEqual(srm_regions.srm_depuis_ville('Oujda'),
                         'srm_oriental')

    def test_la_deduction_ignore_casse_et_accents(self):
        for ecriture in ('FÈS', 'fes', ' Fès '):
            self.assertEqual(srm_regions.srm_depuis_ville(ecriture),
                             'srm_fes', ecriture)

    def test_une_ville_inconnue_ne_deduit_RIEN(self):
        """Checked facts : pas de rattachement inventé, une omission."""
        for ville in (None, '', '   ', 'Ville Qui N Existe Pas'):
            self.assertIsNone(srm_regions.srm_depuis_ville(ville),
                              repr(ville))

    def test_chaque_ville_de_la_table_pointe_sur_une_SRM_declaree(self):
        for code in srm_regions.VILLES_PAR_SRM:
            self.assertIn(code, srm_regions.SRM_PAR_REGION, code)

    def test_aucune_ville_n_est_rattachee_a_DEUX_regions(self):
        vues = {}
        for code, villes in srm_regions.VILLES_PAR_SRM.items():
            for ville in villes:
                cle = srm_regions._normaliser(ville)
                self.assertNotIn(cle, vues,
                                 f'{ville} : {vues.get(cle)} et {code}')
                vues[cle] = code


class UnDistributeurInconnuResoutSurLaGrilleNationale(SimpleTestCase):
    """Le cœur du correctif : plus aucun prix plat inventé sur ce chemin."""

    FACTURE = 1200.0

    def _sonde(self, utility):
        return pricing.kwh_from_bill(self.FACTURE, utility=utility,
                                     facture_totale=True)

    def test_une_SRM_regionale_donne_les_MEMES_kwh_que_l_historique(self):
        """La valeur est un LIBELLÉ : elle ne change aucun prix."""
        reference = self._sonde('onee')
        for code in srm_regions.SRM_PAR_REGION:
            self.assertEqual(self._sonde(code)['kwh_mensuel'],
                             reference['kwh_mensuel'], code)

    def test_une_SRM_regionale_n_est_JAMAIS_une_estimation(self):
        """Avant CAD167 : table None → estimation → courbe publique MASQUÉE."""
        for code in srm_regions.SRM_PAR_REGION:
            self.assertFalse(self._sonde(code)['estimation'], code)
            self.assertFalse(self._sonde(code)['approximatif'], code)

    def test_autre_cesse_de_casser_la_courbe(self):
        sonde = self._sonde('autre')
        self.assertFalse(sonde['estimation'])
        self.assertEqual(sonde['kwh_mensuel'],
                         self._sonde('onee')['kwh_mensuel'])

    def test_les_libelles_historiques_gardent_EXACTEMENT_leur_courbe(self):
        """Non-régression : les trois délégataires déjà tabulés ne bougent
        pas d'un kWh."""
        reference = self._sonde('onee')['kwh_mensuel']
        for code in ('lydec', 'redal'):
            self.assertEqual(self._sonde(code)['kwh_mensuel'], reference, code)

    def test_SANS_distributeur_le_comportement_d_avant_est_conserve(self):
        """Non-régression assumée : aucun distributeur NOMMÉ ⇒ le repli
        historique reste tel quel. C'est la déduction depuis la ville qui
        remplit le champ, pas ce module."""
        sonde = self._sonde(None)
        self.assertTrue(sonde['estimation'])

    def test_une_surcharge_societe_prime_toujours(self):
        """La grille éditable par société garde la main sur tout code."""
        table = [(100, 1.0), (None, 2.0)]
        sonde = pricing.kwh_from_bill(self.FACTURE, utility='srm_casablanca',
                                      tranches_override=table)
        self.assertNotEqual(sonde['kwh_mensuel'],
                            self._sonde('srm_casablanca')['kwh_mensuel'])


class LeCheminCompletDepuisLaFiche(TestCase):
    """Le Done de la tâche, bout en bout : la fiche → la courbe publique.

    Ces tests ont besoin de l'ORM (les leads sont des lignes) — ils sont
    ÉCRITS ici et exécutés par la CI."""

    def setUp(self):
        self.company = Company.objects.create(nom='CAD167 Co',
                                              slug='cad167-co')

    def _lead(self, **kwargs):
        champs = dict(company=self.company, nom='Prospect',
                      facture_hiver=Decimal('1200'))
        champs.update(kwargs)
        return Lead.objects.create(**champs)

    def _devis_duck(self, lead):
        """Objet minimal portant un lead — `lead_bills_for_devis` ne lit que
        `.lead` (et `.client_id` en repli)."""
        class _Devis:
            pass
        devis = _Devis()
        devis.lead = lead
        devis.client_id = None
        devis.company_id = self.company.pk
        devis.company = self.company
        return devis

    def test_un_lead_SANS_distributeur_obtient_sa_SRM_depuis_sa_ville(self):
        from apps.crm.selectors import lead_bills_for_devis
        lead = self._lead(ville='Casablanca', distributeur=None)
        bills = lead_bills_for_devis(self._devis_duck(lead))
        self.assertEqual(bills['distributeur'], 'srm_casablanca')

    def test_et_sa_courbe_publique_EXISTE(self):
        from apps.crm.selectors import lead_bills_for_devis
        lead = self._lead(ville='Agadir', distributeur=None)
        bills = lead_bills_for_devis(self._devis_duck(lead))
        sonde = pricing.kwh_from_bill(bills['facture_hiver'],
                                      utility=bills['distributeur'],
                                      facture_totale=True)
        self.assertFalse(sonde['estimation'])
        self.assertGreater(sonde['kwh_mensuel'], 0)

    def test_un_libelle_HISTORIQUE_garde_sa_valeur_ET_sa_courbe(self):
        from apps.crm.selectors import lead_bills_for_devis
        lead = self._lead(ville='Casablanca', distributeur='onee')
        bills = lead_bills_for_devis(self._devis_duck(lead))
        # La déduction n'écrase JAMAIS une valeur saisie.
        self.assertEqual(bills['distributeur'], 'onee')
        sonde = pricing.kwh_from_bill(bills['facture_hiver'], utility='onee',
                                      facture_totale=True)
        self.assertFalse(sonde['estimation'])

    def test_une_ville_inconnue_ne_deduit_rien_et_ne_ment_pas(self):
        from apps.crm.selectors import lead_bills_for_devis
        lead = self._lead(ville='Village Sans Rattachement Connu',
                          distributeur=None)
        bills = lead_bills_for_devis(self._devis_duck(lead))
        self.assertIsNone(bills['distributeur'])

    def test_la_deduction_n_ECRIT_rien_sur_la_fiche(self):
        """Lecture seule : le sélecteur ne persiste pas la déduction."""
        from apps.crm.selectors import lead_bills_for_devis
        lead = self._lead(ville='Fès', distributeur=None)
        lead_bills_for_devis(self._devis_duck(lead))
        lead.refresh_from_db()
        self.assertIsNone(lead.distributeur)
