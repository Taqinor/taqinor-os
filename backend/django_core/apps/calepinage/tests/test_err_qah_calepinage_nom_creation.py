"""ERR-QAH-CALEPINAGE-NOM-CREATION-PERDU — trouvé par qa-explorer le
2026-09-28 (``docs/ERROR_PLAN.md``).

Ce qui est prouvé ici : le nom SAISI à la création (``titre``, le champ
RÉEL — ``nom`` n'existe pas en écriture, le serveur l'ignorait donc en
silence : 201 avec ``titre: ''``, « Calepinage #N » partout) est bien
persisté, et rendu sous la MÊME clé ``nom`` par la création elle-même, le
DÉTAIL et la LISTE — l'écran (atelier ET liste) ne lit qu'une seule clé.

Run :
    python manage.py test \
        apps.calepinage.tests.test_err_qah_calepinage_nom_creation -v2
"""
from apps.calepinage.models import Calepinage

from .test_api_liste import URL, BaseApiCalepinage, url_detail


class NomPersisteTest(BaseApiCalepinage):
    """Le nom saisi à la création survit partout, jamais un repli deviné."""

    def test_titre_saisi_a_la_creation_est_persiste_et_rendu_partout(self):
        reponse = self.api.post(
            URL, {'lead': self.lead.pk, 'titre': 'MON-ETUDE'}, format='json')
        self.assertEqual(reponse.status_code, 201, reponse.data)
        pk = reponse.data['id']

        # La création elle-même rend déjà le nom saisi (jamais « Calepinage
        # #N » — la valeur qu'aurait rendue le bug, `nom` ignoré en silence).
        self.assertEqual(reponse.data['nom'], 'MON-ETUDE')

        calepinage = Calepinage.objects.get(pk=pk)
        self.assertEqual(calepinage.titre, 'MON-ETUDE')

        detail = self.api.get(url_detail(pk))
        self.assertEqual(detail.data['nom'], 'MON-ETUDE')

        liste = self.api.get(URL)
        ligne = next(ligne for ligne in self._lignes(liste)
                     if ligne['id'] == pk)
        self.assertEqual(ligne['nom'], 'MON-ETUDE')

    def test_sans_titre_saisi_le_repli_est_le_meme_partout(self):
        """Aucun nom saisi : le MÊME repli pour TOUTES les portes (ACAL182 —
        ``POST calepinages/``, ``depuis-lead``, ``depuis-modele`` sans modèle
        passent par ``services/creation.py``), et le même partout ensuite —
        création, détail, liste."""
        from apps.crm.models import Lead

        lead_3 = Lead.objects.create(company=self.company,
                                     nom='Toiture Ain Diab')
        portes = (
            (URL, {'lead': self.lead.pk}, self.lead),
            (f'{URL}depuis-lead/', {'lead': self.lead_2.pk}, self.lead_2),
            (f'{URL}depuis-modele/', {'lead_id': lead_3.pk}, lead_3),
        )
        for url, corps, lead in portes:
            with self.subTest(porte=url):
                reponse = self.api.post(url, corps, format='json')
                self.assertEqual(reponse.status_code, 201, reponse.data)
                pk = reponse.data.get('id') or reponse.data.get('calepinage')
                attendu = f'Calepinage {lead.nom}'
                self.assertEqual(Calepinage.objects.get(pk=pk).titre,
                                 attendu)
                self.assertEqual(self.api.get(url_detail(pk)).data['nom'],
                                 attendu)
                ligne = next(ligne for ligne in
                             self._lignes(self.api.get(URL))
                             if ligne['id'] == pk)
                self.assertEqual(ligne['nom'], attendu)
