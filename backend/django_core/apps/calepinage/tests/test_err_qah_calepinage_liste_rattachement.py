"""ERR-QAH-CALEPINAGE-LISTE-SANS-RATTACHEMENT — trouvé par qa-explorer le
2026-09-28 (``docs/ERROR_PLAN.md``).

Ce qui est prouvé ici :

* la LISTE publie le lead rattaché en ``{id, nom, ville}``, comme le détail
  — plus un identifiant opaque qui faisait afficher « Sans rattachement »
  faute de nom ;
* la LISTE retombe sur le responsable DU LEAD quand le calepinage n'a
  personne d'assigné en propre — le MÊME repli que le détail (CALX406) — et
  garde l'identifiant SAISI en priorité quand il existe (aucune requête de
  plus dans ce cas) ;
* un calepinage rattaché à un CLIENT (pas de lead) garde ``lead: null``,
  inchangé.

Run :
    python manage.py test \
        apps.calepinage.tests.test_err_qah_calepinage_liste_rattachement -v2
"""
from django.contrib.auth import get_user_model

from apps.calepinage.models import Calepinage

from .test_api_liste import URL, BaseApiCalepinage, url_detail

User = get_user_model()


class ListeRattachementTest(BaseApiCalepinage):
    """La liste et le détail publient la MÊME forme de rattachement."""

    def setUp(self):
        super().setUp()
        self.porteur = User.objects.create_user(
            username='cal_liste_porteur', password='x',
            company=self.company, role=self.role)
        self.lead.owner = self.porteur
        self.lead.save(update_fields=['owner'])

    def test_la_liste_publie_le_lead_imbrique_comme_le_detail(self):
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Toiture Anfa')

        liste = self.api.get(URL)
        ligne = next(ligne for ligne in self._lignes(liste)
                     if ligne['id'] == calepinage.pk)
        detail = self.api.get(url_detail(calepinage.pk))

        self.assertIsInstance(ligne['lead'], dict)
        self.assertEqual(ligne['lead']['id'], self.lead.pk)
        self.assertEqual(ligne['lead'], detail.data['lead'])

    def test_la_liste_retombe_sur_le_responsable_du_lead_sans_saisie(self):
        """Aucun ``responsable`` SAISI : la liste ne dit plus « Sans
        responsable » quand le lead, lui, en a un. ACAL297 — ce n'est plus un
        repli de LECTURE : la porte de création STOCKE le propriétaire du
        lead, et la liste comme le détail publient la colonne."""
        from apps.calepinage.services.creation import (
            ouvrir_ou_creer_pour_lead,
        )

        calepinage, _cree = ouvrir_ou_creer_pour_lead(
            self.lead.pk, self.company, user=self.user, titre='Toiture Anfa')
        self.assertEqual(calepinage.responsable_id, self.porteur.pk)

        liste = self.api.get(URL)
        ligne = next(ligne for ligne in self._lignes(liste)
                     if ligne['id'] == calepinage.pk)
        detail = self.api.get(url_detail(calepinage.pk))

        self.assertEqual(ligne['responsable'], self.porteur.pk)
        self.assertEqual(ligne['responsable_nom'], self.porteur.username)
        self.assertEqual(detail.data['responsable']['id'], self.porteur.pk)

    def test_le_responsable_saisi_garde_la_priorite(self):
        """Un responsable SAISI reste celui rendu — inchangé, aucun repli."""
        autre = User.objects.create_user(
            username='cal_liste_autre', password='x', company=self.company,
            role=self.role)
        calepinage = Calepinage.objects.create(
            company=self.company, lead_id=self.lead.pk, titre='Toiture Anfa',
            responsable=autre)

        ligne = next(ligne for ligne in self._lignes(self.api.get(URL))
                     if ligne['id'] == calepinage.pk)
        self.assertEqual(ligne['responsable'], autre.pk)
        self.assertEqual(ligne['responsable_nom'], autre.username)

    def test_calepinage_sur_client_garde_lead_a_null(self):
        calepinage = Calepinage.objects.create(
            company=self.company, client=self.client_a, titre='Usine Atlas')

        ligne = next(ligne for ligne in self._lignes(self.api.get(URL))
                     if ligne['id'] == calepinage.pk)
        self.assertIsNone(ligne['lead'])
