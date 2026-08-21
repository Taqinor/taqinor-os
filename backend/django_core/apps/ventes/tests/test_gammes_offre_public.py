"""GAMMES — 3. Charge utile publique.

Partie 3 sur 8 de l'ancien `test_gammes_offre.py`, scindé PAR CLASSE le
2026-08-21 (voir `_gammes_offre_common.py`). Aucune assertion n'a changé.

Ce que garde cette partie : ce qui franchit (ou non) la frontière publique —
bloc `gammes`, comparatif ligne à ligne, écart en MAD, et l'interdiction
absolue de laisser fuir `prix_achat`/marge.

Lancer :
    docker compose exec django_core python manage.py test \
        apps.ventes.tests.test_gammes_offre_public -v 2
"""
from decimal import Decimal

from rest_framework.test import APIClient

from apps.ventes.models import LigneDevis, ShareLink
from apps.ventes.public_views import _gammes_public, _variant_summaries
from apps.ventes.services import (
    GAMME_ENVOI_LES_DEUX, GAMME_ENVOI_SEULE, regler_envoi_gamme,
)
from apps.ventes.tests._gammes_offre_common import (
    GammeBase, add_ligne, make_devis, make_produit, url_proposal,
)


class TestPayloadPublic(GammeBase):

    def test_les_deux_expose_la_soeur(self):
        source, soeur = self._paire('DEV-GAM-030', nom='Premium')
        bloc = _gammes_public(source)
        self.assertIsNotNone(bloc)
        self.assertEqual(bloc['envoi'], GAMME_ENVOI_LES_DEUX)
        self.assertEqual(bloc['courante']['nom'], 'Essentielle')
        self.assertTrue(bloc['courante']['recommandee'])
        self.assertEqual(bloc['soeur']['nom'], 'Premium')
        self.assertEqual(bloc['soeur']['reference'], soeur.reference)
        self.assertIn('/proposition/', bloc['soeur']['proposition_path'])

    def test_ecart_en_mad_absolus_signe(self):
        """L'écart est un MONTANT signé en MAD (sœur − gamme affichée), jamais
        un pourcentage : la page l'affiche « + X MAD » / « − X MAD »."""
        source, soeur = self._paire('DEV-GAM-031')
        # La sœur est renchérie : son écart doit être POSITIF.
        for ligne in soeur.lignes.all():
            ligne.prix_unitaire = ligne.prix_unitaire + Decimal('1000')
            ligne.save(update_fields=['prix_unitaire'])
        bloc = _gammes_public(source)
        self.assertIsNotNone(bloc['soeur']['ecart_ttc'])
        self.assertGreater(bloc['soeur']['ecart_ttc'], 0)
        self.assertAlmostEqual(
            bloc['soeur']['ecart_ttc'],
            bloc['soeur']['total_ttc'] - bloc['courante']['total_ttc'], places=2)

    def test_les_deux_totaux_sortent_de_la_MEME_fonction(self):
        """L'écart n'a de sens que si les deux côtés sont commensurables.

        Le total courant venait de ``data['display_total']`` (total SANS
        batterie dès qu'un devis porte deux options, total AVEC quand il n'en
        porte qu'une) tandis que la sœur passait par ``display_totals`` : un
        devis bi-option comparé à un devis mono-option soustrayait deux
        compositions différentes. Les deux côtés lisent maintenant
        ``display_totals`` — donc, à composition identique, écart NUL."""
        from apps.ventes.quote_engine.builder import display_totals

        source, soeur = self._paire('DEV-GAM-039')
        bloc = _gammes_public(source)
        # Le total publié pour la gamme courante EST celui de display_totals.
        self.assertAlmostEqual(
            bloc['courante']['total_ttc'],
            round(float(display_totals(source)['total']), 2), places=2)
        self.assertAlmostEqual(
            bloc['soeur']['total_ttc'],
            round(float(display_totals(soeur)['total']), 2), places=2)
        # Deux gammes clonées à l'identique : l'écart est ZÉRO, jamais un
        # montant fabriqué par la différence de sémantique des deux totaux.
        self.assertAlmostEqual(bloc['soeur']['ecart_ttc'], 0.0, places=2)

    def test_comparatif_ne_garde_que_les_lignes_qui_different(self):
        source, soeur = self._paire('DEV-GAM-032')
        ligne = soeur.lignes.filter(designation='Panneau 550W').first()
        ligne.quantite = Decimal('14')
        ligne.save(update_fields=['quantite'])
        bloc = _gammes_public(source)
        designations = [r['designation'] for r in bloc['comparatif']]
        self.assertEqual(designations, ['Panneau 550W'])
        self.assertEqual(bloc['comparatif'][0]['quantite'], 10.0)
        self.assertEqual(bloc['comparatif'][0]['quantite_soeur'], 14.0)

    def test_comparatif_couvre_une_ligne_absente_dune_gamme(self):
        source, soeur = self._paire('DEV-GAM-033')
        batterie = make_produit(self.company, 'Batterie 5 kWh', 'BAT-GAM',
                                '12000')
        add_ligne(soeur, batterie, qty='1', pu='12000')
        bloc = _gammes_public(source)
        rows = {r['designation']: r for r in bloc['comparatif']}
        self.assertIn('Batterie 5 kWh', rows)
        self.assertNotIn('quantite', rows['Batterie 5 kWh'])
        self.assertEqual(rows['Batterie 5 kWh']['quantite_soeur'], 1.0)

    def test_comparatif_agrege_une_designation_repetee(self):
        """Multi-villa (QJ29/QJ30) : la MÊME désignation apparaît une fois par
        groupe. Ne garder que la première publiait « 10 » là où le devis porte
        10 + 6 = 16 panneaux — un chiffre faux présenté comme la composition."""
        source, soeur = self._paire('DEV-GAM-060')
        # La gamme courante répartit ses panneaux sur DEUX villas (10 + 6).
        seconde = add_ligne(source, self.panneau, qty='6')
        seconde.groupe_index = 2
        seconde.groupe_label = 'Villa 2'
        seconde.save(update_fields=['groupe_index', 'groupe_label'])
        # La sœur porte les 16 mêmes panneaux sur une seule ligne.
        ligne_soeur = soeur.lignes.filter(designation='Panneau 550W').first()
        ligne_soeur.quantite = Decimal('16')
        ligne_soeur.save(update_fields=['quantite'])

        bloc = _gammes_public(source)

        # 16 des deux côtés ⇒ la ligne ne DIFFÈRE pas : elle sort du comparatif.
        designations = [r['designation'] for r in bloc['comparatif']]
        self.assertNotIn('Panneau 550W', designations)

    def test_comparatif_agrege_et_publie_la_somme_quand_ca_differe(self):
        source, soeur = self._paire('DEV-GAM-061')
        seconde = add_ligne(source, self.panneau, qty='6')
        seconde.groupe_index = 2
        seconde.save(update_fields=['groupe_index'])
        ligne_soeur = soeur.lignes.filter(designation='Panneau 550W').first()
        ligne_soeur.quantite = Decimal('20')
        ligne_soeur.save(update_fields=['quantite'])

        bloc = _gammes_public(source)

        rows = {r['designation']: r for r in bloc['comparatif']}
        self.assertIn('Panneau 550W', rows)
        self.assertEqual(rows['Panneau 550W']['quantite'], 16.0)
        self.assertEqual(rows['Panneau 550W']['quantite_soeur'], 20.0)

    def test_une_ligne_OPTIONNELLE_ne_franchit_pas_le_comparatif(self):
        """XSAL5 — un add-on est proposé HORS total. L'afficher à côté d'un
        ``total_ttc`` qui l'exclut faisait conclure au client que la gamme
        l'incluait à ce prix."""
        source, soeur = self._paire('DEV-GAM-062')
        batterie = make_produit(self.company, 'Batterie supplémentaire 5 kWh',
                                'BAT-OPT-GAM', '12000')
        add_on = add_ligne(soeur, batterie, qty='1', pu='12000')
        add_on.optionnelle = True
        add_on.save(update_fields=['optionnelle'])

        bloc = _gammes_public(source)

        designations = [r['designation'] for r in bloc['comparatif']]
        self.assertNotIn('Batterie supplémentaire 5 kWh', designations)

    def test_une_ligne_SECTION_ne_franchit_pas_le_comparatif(self):
        """XSAL14 — un intertitre n'est pas un composant (et sa quantité est
        nulle : il entrait au comparatif comme une « différence de matériel »
        présente d'un seul côté)."""
        source, soeur = self._paire('DEV-GAM-063')
        LigneDevis.objects.create(
            devis=soeur, designation='Lot 1 — Toiture principale',
            type_ligne=LigneDevis.TypeLigne.SECTION,
            quantite=None, prix_unitaire=None, remise=Decimal('0'), ordre=99)

        bloc = _gammes_public(source)

        designations = [r['designation'] for r in bloc['comparatif']]
        self.assertNotIn('Lot 1 — Toiture principale', designations)

    def test_mode_seule_ne_laisse_rien_passer(self):
        source, soeur = self._paire('DEV-GAM-034', nom='Premium')
        regler_envoi_gamme(source, GAMME_ENVOI_SEULE)
        source.refresh_from_db()
        self.assertIsNone(_gammes_public(source))
        # ... et la sœur ne réapparaît pas non plus par la bande
        # « Autres tailles proposées ».
        refs = [v['reference'] for v in _variant_summaries(source)]
        self.assertNotIn(soeur.reference, refs)

    def test_soeur_de_gamme_exclue_des_autres_tailles(self):
        """Même en mode « les_deux » : jamais de doublon avec le bloc gammes."""
        source, soeur = self._paire('DEV-GAM-035')
        refs = [v['reference'] for v in _variant_summaries(source)]
        self.assertNotIn(soeur.reference, refs)

    def test_payload_public_expose_gammes_et_jamais_prix_achat(self):
        source, soeur = self._paire('DEV-GAM-036', nom='Premium')
        link = ShareLink.for_devis(source)
        anon = APIClient()
        resp = anon.get(url_proposal(link.token))
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNotNone(resp.data.get('gammes'))
        self.assertEqual(resp.data['gammes']['soeur']['nom'], 'Premium')
        brut = str(resp.data)
        self.assertNotIn('prix_achat', brut)
        self.assertNotIn('marge', brut)

    def test_payload_public_mode_seule_sans_gammes(self):
        source, _ = self._paire('DEV-GAM-037')
        regler_envoi_gamme(source, GAMME_ENVOI_SEULE)
        link = ShareLink.for_devis(source)
        resp = APIClient().get(url_proposal(link.token))
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data.get('gammes'))

    def test_devis_sans_gamme_payload_inchange(self):
        d = make_devis(self.company, self.user, self.client_obj, 'DEV-GAM-038')
        add_ligne(d, self.panneau, qty='6')
        # Le moteur refuse (a raison) un devis a options sans onduleur : la
        # fixture doit porter une composition credible, pas un panneau seul.
        add_ligne(d, self.onduleur)
        link = ShareLink.for_devis(d)
        resp = APIClient().get(url_proposal(link.token))
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data.get('gammes'))
