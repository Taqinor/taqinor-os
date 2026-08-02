// ORDRE FONDATEUR 2026-08-01 — « les leads doivent pouvoir REVENIR EN ARRIÈRE
// d'étape, avec une confirmation avant ». Contrat de la FENÊTRE LEAD (le board
// et la liste ont leurs propres sondes).
//
// Ce que ce fichier verrouille, et pourquoi chaque point compte :
//   1. la QUESTION se pose dans LeadWorkspace, pas dans StageControl — c'est
//      le seul point par lequel passent les DEUX entrées du contrôle (menu
//      d'étape LW16 et raccourcis « 1-4 » LW23), et StageControl reste ce que
//      son contrat annonce : un déclencheur qui ne patche jamais ;
//   2. le MOTEUR (useLeadDraft) ne pose pas la question, il transporte la
//      réponse jusqu'au corps du PATCH — il n'a pas d'UI ;
//   3. le marqueur est OMIS quand il est faux : une avancée reste un PATCH nu ;
//   4. la formulation vient de la source PARTAGÉE (features/crm/confirmRecul),
//      jamais d'un window.confirm ni d'un texte recopié.
// Vérifié contre la SOURCE (pas de node_modules dans les lanes worktree) —
// même convention que les autres sondes du dossier.
//   node --test src/features/crm/workspace/StageBackwardConfirm.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const lf = (s) => s.replace(/\r\n/g, '\n')
const WORKSPACE = lf(readFileSync(join(HERE, 'LeadWorkspace.jsx'), 'utf8'))
const DRAFT = lf(readFileSync(join(HERE, 'useLeadDraft.js'), 'utf8'))
const CONTROL = lf(readFileSync(join(HERE, 'StageControl.jsx'), 'utf8'))
const CONFIRM = lf(readFileSync(join(HERE, '..', 'confirmRecul.js'), 'utf8'))

test('la question se pose dans LeadWorkspace, sur le chemin commun aux DEUX entrées', () => {
  assert.match(WORKSPACE, /import \{ useConfirmerRecul \} from '\.\.\/confirmRecul'/)
  assert.match(WORKSPACE, /import \{ isStageMoveBackward \} from '\.\.\/stages'/)
  const start = WORKSPACE.indexOf('const changeStageConfirme = useCallback(')
  assert.ok(start > 0, 'changeStageConfirme introuvable')
  const body = WORKSPACE.slice(start, WORKSPACE.indexOf('\n  }, [', start))
  // Une AVANCÉE part directement : rien à demander.
  assert.match(body, /if \(!isStageMoveBackward\(stageCourant, cible\)\) return changeStage\(cible\)/)
  // Un RECUL demande, et n'appelle le moteur qu'après un oui.
  assert.match(body, /const ok = await confirmerRecul\(/)
  assert.match(body, /if \(!ok\) return undefined/)
  assert.match(body, /return changeStage\(cible, \{ confirmeRecul: true \}\)/)
  // C'est bien CETTE fonction que l'action des rails appelle.
  assert.match(WORKSPACE, /case 'change-stage': return changeStageConfirme\(payload\)/)
})

test("StageControl reste un DÉCLENCHEUR : il ne juge pas le sens et ne patche pas", () => {
  assert.doesNotMatch(CONTROL, /isStageMove(Allowed|Backward)/)
  assert.doesNotMatch(CONTROL, /confirmeRecul|confirme_recul/)
  assert.doesNotMatch(CONTROL, /crmApi|updateLead/)
  // Les DEUX entrées passent bien par la même prop (donc par la question).
  assert.match(CONTROL, /LEAD_STAGE_SHORTCUTS\.map\(\(s\) => \[s\.key, \(\) => onChangeStage\(s\.stage\)\]\)/)
  assert.match(CONTROL, /else onChangeStage\(key\)/)
})

test("le moteur TRANSPORTE la réponse jusqu'au corps du PATCH, il ne la produit pas", () => {
  const start = DRAFT.indexOf('const changeStage = useCallback(')
  assert.ok(start > 0, 'changeStage introuvable')
  const body = DRAFT.slice(start, DRAFT.indexOf('\n  }, [flush])', start))
  assert.match(body, /async \(newStage, \{ confirmeRecul = false \} = \{\}\)/)
  assert.match(body, /const corps = \{ stage: newStage \}/)
  // OMIS quand il est faux : une avancée reste un PATCH nu.
  assert.match(body, /if \(confirmeRecul\) corps\.confirme_recul = true/)
  assert.match(body, /crmApi\.updateLead\(st\.leadId, corps\)/)
  // Le moteur n'a pas d'UI : il ne pose aucune question.
  assert.doesNotMatch(body, /confirm\(|useConfirmerRecul|window\.confirm/)
})

test('UNE seule formulation, partagée par les trois surfaces', () => {
  // Elle NOMME le lead et les DEUX étapes (« êtes-vous sûr ? » ne se relit pas).
  assert.match(CONFIRM, /Ramener « \$\{lead\?\.nom \|\| 'ce lead'\} » de/)
  assert.match(CONFIRM, /\$\{libelle\(lead\?\.stage\)\} à \$\{libelle\(cible\)\}/)
  // Pas destructive : rien n'est supprimé, on remonte le pipeline — un rouge
  // d'alerte ici banaliserait le vrai rouge des suppressions.
  assert.match(CONFIRM, /destructive: false/)
  assert.match(CONFIRM, /confirmLabel: 'Ramener'/)
  // Libellés d'étape depuis stages.js UNIQUEMENT (règle #2) : aucune clé en dur.
  assert.match(CONFIRM, /import \{ STAGE_LABELS \} from '\.\/stages'/)
  for (const cle of ['NEW', 'CONTACTED', 'QUOTE_SENT', 'FOLLOW_UP', 'SIGNED', 'COLD']) {
    assert.doesNotMatch(CONFIRM, new RegExp(`'${cle}'`))
  }
})
