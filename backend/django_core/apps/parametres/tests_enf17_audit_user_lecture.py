"""ENF17 — journal d'audit des paramètres : la FK ``user`` n'est pas
inscriptible.

``SettingsAuditLogSerializer`` est un sérialiseur de SORTIE (liste du journal,
aucune écriture API) ; sa FK ``user`` restait pourtant inscriptible, donc
résolvable vers l'utilisateur de n'importe quelle société si un jour une vue
l'utilisait en écriture. Elle est désormais en lecture seule : un ``user``
fourni dans un corps est ignoré, la sortie expose toujours l'id de l'auteur.

Run:
    python manage.py test apps.parametres.tests_enf17_audit_user_lecture -v 2
"""
from django.test import SimpleTestCase

from apps.parametres.serializers_audit import SettingsAuditLogSerializer


class SettingsAuditLogUserLectureSeuleTests(SimpleTestCase):
    def test_user_en_lecture_seule(self):
        champ = SettingsAuditLogSerializer().fields['user']
        self.assertTrue(champ.read_only)

    def test_user_ignore_en_entree(self):
        ser = SettingsAuditLogSerializer(
            data={'section': 's', 'field': 'f', 'user': 99999999},
            partial=True)
        self.assertTrue(ser.is_valid(), ser.errors)
        self.assertNotIn('user', ser.validated_data)
