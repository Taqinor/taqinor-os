// EZ1 — Le popover d'appel devient LE planificateur.
// ----------------------------------------------------------------------------
// Deux defauts VERIFIES sont corriges, et ce sont eux que ce fichier verrouille :
//   1. l'ECRASEMENT SILENCIEUX — une relance deja posee etait remplacee sans
//      jamais avoir ete lue ni affichee ;
//   2. les TROIS surfaces rivales de « planifier la suite » (chips du popover /
//      LeadsPage qui ouvrait juste la fiche / PlanActiviteDialog et ses
//      gabarits) — il n'en reste qu'UNE pour la planification rapide.
//   node --test src/features/crm/CallPlanner.ez1.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const lf = (s) => s.replace(/\r\n/g, '\n')
const lire = (p) => lf(readFileSync(join(HERE, p), 'utf8'))

const POPOVER = lire('CallLogPopover.jsx')
const LEADS = lire('../../pages/crm/leads/LeadsPage.jsx')
const PLAN_DIALOG = lire('../../pages/crm/leads/PlanActiviteDialog.jsx')
const RECORDS_API = lire('../../api/recordsApi.js')
const PLATFORM = lf(readFileSync(
  join(HERE, '../../../../backend/django_core/apps/crm/platform.py'), 'utf8'))

/* ── La regle de conflit, rejouee : c'est LA logique qui empeche l'ecrasement
      silencieux, donc elle merite d'etre testee sur des cas reels. ── */
const conflit = (relanceActuelle, dateRelance, choix) => {
  const existante = relanceActuelle ? String(relanceActuelle).slice(0, 10) : null
  const enConflit = !!existante && !!dateRelance && dateRelance !== existante
  return { enConflit, ecrasera: enConflit ? choix === 'remplacer' : !!dateRelance }
}

test('EZ1 : sans relance existante, une date choisie s\'ecrit directement', () => {
  const r = conflit(null, '2026-08-10', 'garder')
  assert.equal(r.enConflit, false)
  assert.equal(r.ecrasera, true)
})

test('EZ1 : une relance existante n\'est JAMAIS ecrasee sans choix explicite', () => {
  // Defaut = « garder » : le comportement par defaut ne detruit rien.
  const defaut = conflit('2026-08-03', '2026-08-10', 'garder')
  assert.equal(defaut.enConflit, true)
  assert.equal(defaut.ecrasera, false, 'le defaut ne doit JAMAIS ecraser')
  // ... et « remplacer » est le seul chemin vers l'ecriture.
  assert.equal(conflit('2026-08-03', '2026-08-10', 'remplacer').ecrasera, true)
})

test('EZ1 : re-choisir la MEME date n\'est pas un conflit (rien ne change)', () => {
  const r = conflit('2026-08-10', '2026-08-10', 'garder')
  assert.equal(r.enConflit, false)
  assert.equal(r.ecrasera, true) // ecriture idempotente, aucune decision a prendre
})

test('EZ1 : aucune date choisie = aucune ecriture de relance', () => {
  assert.equal(conflit('2026-08-03', '', 'remplacer').ecrasera, false)
  assert.equal(conflit(null, '', 'garder').ecrasera, false)
})

test('EZ1 : la copie de logique de ce test est fidele a la source', () => {
  assert.match(POPOVER, /const enConflit = !!relanceExistante && !!dateRelance && dateRelance !== relanceExistante/)
  assert.match(POPOVER, /const ecrasera = enConflit \? conflit === 'remplacer' : !!dateRelance/)
  // Le defaut est « garder » — la valeur initiale ET la reinitialisation.
  assert.match(POPOVER, /useState\('garder'\)/)
  assert.match(POPOVER, /setConflit\('garder'\)/)
})

test('EZ1 : la relance existante est AFFICHEE (elle n\'etait jamais lue)', () => {
  assert.match(POPOVER, /Une relance est déjà prévue le <strong>\{formatFr\(relanceExistante\)\}<\/strong>/)
  assert.match(POPOVER, /Garder le \{formatFr\(relanceExistante\)\}/)
  assert.match(POPOVER, /Remplacer par le \{formatFr\(dateRelance\)\}/)
  // ... et transmise par les deux sites de nudge.
  const carte = lire('../../pages/crm/leads/views/LeadCard.jsx')
  const liste = lire('../../pages/crm/leads/views/ListView.jsx')
  assert.match(carte, /relanceActuelle=\{lead\.relance_date \?\? null\}/)
  assert.match(liste, /relanceActuelle=\{nudgeLead\.relance_date \?\? null\}/)
})

test('EZ1 : UNE seule valeur de date — les 4 offsets REMPLISSENT la date libre', () => {
  // Avant : `nextActionDays` (un index) vivait a cote de rien d'autre. Le
  // champ libre et les chips ecrivent desormais le MEME etat.
  assert.doesNotMatch(POPOVER, /nextActionDays/)
  assert.match(POPOVER, /onClick=\{\(\) => setDateRelance\(\(cur\) => \(cur === iso \? '' : iso\)\)\}/)
  assert.match(POPOVER, /onChange=\{\(d\) => setDateRelance\(ymd\(d\)\)\}/)
})

test('EZ1 : PAS D\'HEURE — relance_date et due_date sont des DateField', () => {
  // Poser une heure demanderait une tache SCHEMA dediee ; on n'invente pas.
  const code = POPOVER.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')
  assert.doesNotMatch(code, /type="datetime-local"/)
  // `toISOString()` decalerait d'un jour le soir en heure marocaine : la date
  // est formatee en LOCAL (`ymd`).
  assert.doesNotMatch(code, /toISOString\(\)/)
  assert.match(POPOVER, /function ymd\(d\) \{/)
})

test('EZ1 : un OBJET cree une vraie activite datee — zero backend', () => {
  assert.match(POPOVER, /recordsApi\.createActivity\(\{\s*\n\s*model: 'crm\.lead',\s*\n\s*id: leadId,\s*\n\s*summary: objet\.trim\(\),\s*\n\s*due_date: dateRelance,/)
  // Le client existait deja...
  assert.match(RECORDS_API, /createActivity: \(data\) => api\.post\('\/records\/activities\/', data\)/)
  // ... et la cible `crm.lead` est deja declaree cote serveur.
  assert.match(PLATFORM, /crm\.lead/)
  // Sans objet, aucune activite n'est creee (une relance suffit souvent).
  assert.match(POPOVER, /if \(objet\.trim\(\) && dateRelance\) \{/)
})

test('EZ1 : LeadsPage pointe CE popover, il n\'ouvre plus la fiche entiere', () => {
  assert.match(LEADS, /const onPlanifierRelance = useCallback\(\(lead\) => \{\s*\n\s*setRelanceLead\(lead\)\s*\n\s*\}, \[\]\)/)
  assert.match(LEADS, /<CallLogPopover\s*\n\s*key=\{relanceLead\.id\}/)
  assert.match(LEADS, /mode="planification"/)
  assert.match(LEADS, /relanceActuelle=\{relanceLead\.relance_date \?\? null\}/)
})

test('EZ1 : en planification pure, l\'issue d\'appel n\'est ni demandee ni exigee', () => {
  // Il n'y a pas eu d'appel : exiger une issue serait un mensonge de plus dans
  // le chatter.
  assert.match(POPOVER, /\{!planificationSeule && \(/)
  assert.match(POPOVER, /if \(!planificationSeule && !outcome\) return/)
  assert.match(POPOVER, /if \(planificationSeule && !dateRelance\) return/)
  assert.match(POPOVER, /disabled=\{busy \|\| \(planificationSeule \? !dateRelance : !outcome\)\}/)
})

test('EZ1 : PlanActiviteDialog garde son role, DOCUMENTE (plus un rival)', () => {
  assert.match(PLAN_DIALOG, /RÔLE DOCUMENTÉ/)
  assert.match(PLAN_DIALOG, /appliquer_plan_activite/)
  // Il ne pose toujours pas de date libre : son domaine reste le gabarit.
  assert.doesNotMatch(PLAN_DIALOG, /relance_date/)
})
