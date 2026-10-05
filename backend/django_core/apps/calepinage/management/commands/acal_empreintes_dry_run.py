"""ACAL40 — DRY-RUN fondateur du recalcul des empreintes « imprimées ».

``python manage.py acal_empreintes_dry_run [--sens avant|arriere]``

N'ÉCRIT RIEN. Rejoue EXACTEMENT le plan de la migration
``calepinage/0018_acal40_empreinte_imprimee`` (même fonction
``plan_de_recalcul``, importée, jamais recopiée) et liste, pour le fondateur,
AVANT le merge (D-ACAL-4 / D-ACAL-21, mémoire
reconfirm-client-visible-repairs) :

* chaque ligne qui bougerait : table, id, ancienne → nouvelle empreinte ;
* pour chaque devis concerné (référence, statut) et son calepinage lié :
  l'effet sur le badge « à jour » de la fiche devis (``a_jour``), sur
  ``layout_stale`` (son reflet côté calepinage), sur la dédup des brouillons
  (``devis_brouillon_pour_layout``), sur l'empreinte d'étude électrique
  (``electrical_service.empreinte_entree`` lit ``layout_hash``) et sur la
  trace « corrigé après envoi » (une resynchronisation d'un ENVOYÉ devenu
  « non à jour » sera une correction TRACÉE).

Aucun envoyé n'est jamais réécrit côté lignes, PDF ou statut : seule la valeur
``layout_hash`` change, et seulement si elle dérive bien du document.
"""
from __future__ import annotations

import importlib

from django.apps import apps as registre
from django.core.management.base import BaseCommand

MIGRATION = 'apps.calepinage.migrations.0018_acal40_empreinte_imprimee'


def _court(empreinte):
    return (empreinte or '')[:12] or '∅'


def _a_jour(devis_hash, cal_hash):
    if not devis_hash or not cal_hash:
        return None
    return devis_hash == cal_hash


def _libelle(valeur):
    return {True: 'à jour', False: 'NON à jour', None: 'inconnu'}[valeur]


def effets(plan):
    """Les effets lisibles du plan, devis par devis (aucune écriture)."""
    Calepinage = registre.get_model('calepinage', 'Calepinage')
    Devis = registre.get_model('ventes', 'Devis')

    nouvelles = {(nom, pk): nouvelle for nom, pk, _a, nouvelle, _i in plan}
    devis_ids = {pk for nom, pk, *_ in plan if nom == 'Devis'}
    devis_ids |= {info.get('devis_id') for nom, _pk, _a, _n, info in plan
                  if nom == 'Calepinage' and info.get('devis_id')}
    lignes = []
    for devis in (Devis._base_manager.filter(pk__in=devis_ids)
                  .order_by('pk')):
        cal = (Calepinage._base_manager
               .filter(company_id=devis.company_id, devis_id=devis.pk)
               .order_by('-created_at', '-id').first())
        avant_devis = devis.layout_hash or ''
        apres_devis = nouvelles.get(('Devis', devis.pk), avant_devis)
        avant_cal = (cal.layout_hash or '') if cal else ''
        apres_cal = (nouvelles.get(('Calepinage', cal.pk), avant_cal)
                     if cal else '')
        a_jour_avant = _a_jour(avant_devis, avant_cal) if cal else None
        a_jour_apres = _a_jour(apres_devis, apres_cal) if cal else None
        change = apres_devis != avant_devis
        if devis.statut == 'brouillon' and change:
            dedup = ('rendu à la NOUVELLE empreinte' if a_jour_apres
                     else 'clé de dédup modifiée')
        else:
            dedup = 'sans effet'
        trace = ('une resynchronisation tracera « corrigé après envoi : '
                 'calepinage »'
                 if devis.statut == 'envoye' and a_jour_apres is False
                 and a_jour_avant is not False else 'aucune')
        lignes.append({
            'devis': devis.reference or f'#{devis.pk}',
            'statut': devis.statut,
            'actif': devis.is_active,
            'calepinage': cal.pk if cal else None,
            'devis_hash': (avant_devis, apres_devis),
            'calepinage_hash': (avant_cal, apres_cal),
            'a_jour': (a_jour_avant, a_jour_apres),
            'layout_stale': (None if a_jour_avant is None
                             else not a_jour_avant,
                             None if a_jour_apres is None
                             else not a_jour_apres),
            'dedup': dedup,
            'etude_electrique': ('empreinte d\'entrées modifiée → étude à '
                                 'recalculer'
                                 if change and devis.electrical_design_hash
                                 else 'sans effet'),
            'trace': trace,
        })
    return lignes


class Command(BaseCommand):
    help = ("ACAL40 — liste, SANS RIEN ÉCRIRE, les empreintes « imprimées » "
            "que la migration 0018 recalculerait et leurs effets.")

    def add_arguments(self, parser):
        parser.add_argument('--sens', choices=('avant', 'arriere'),
                            default='avant',
                            help="'avant' = migration, 'arriere' = reverse.")

    def handle(self, *args, **options):
        migration = importlib.import_module(MIGRATION)
        plan = migration.plan_de_recalcul(registre, sens=options['sens'])
        ecrire = self.stdout.write
        ecrire(f"ACAL40 dry-run (sens {options['sens']}) — AUCUNE écriture.")
        ecrire(f'{len(plan)} empreinte(s) stockée(s) changeraient.')
        for nom, pk, ancienne, nouvelle, info in plan:
            ecrire(f'  {nom} #{pk} : {_court(ancienne)} → {_court(nouvelle)}'
                   f'  {info}')
        lignes = effets(plan)
        ecrire(f'{len(lignes)} devis concerné(s) :')
        for ligne in lignes:
            avant, apres = ligne['a_jour']
            ecrire(
                f"  {ligne['devis']} ({ligne['statut']}"
                f"{'' if ligne['actif'] else ', inactif'}) — calepinage "
                f"{ligne['calepinage'] or '∅'} — devis "
                f"{_court(ligne['devis_hash'][0])}→"
                f"{_court(ligne['devis_hash'][1])}, calepinage "
                f"{_court(ligne['calepinage_hash'][0])}→"
                f"{_court(ligne['calepinage_hash'][1])} — badge "
                f"{_libelle(avant)} → {_libelle(apres)} ; dédup : "
                f"{ligne['dedup']} ; étude électrique : "
                f"{ligne['etude_electrique']} ; trace : {ligne['trace']}")
        ecrire('Rien n\'a été écrit. À soumettre au fondateur AVANT merge.')
