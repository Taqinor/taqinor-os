// ENF19 — la mécanique d'envoi partagée des formulaires.
//   node --test src/lib/soumission.test.mjs
import test, { mock } from 'node:test'
import assert from 'node:assert/strict'
import { creerSoumission, creerSoumissionNomRequis } from './soumission.js'

const geste = () => ({ preventDefault: mock.fn() })
const appels = (fn) => fn.mock.calls.map((c) => c.arguments)
const dernier = (fn) => appels(fn).at(-1)

test('valide : occupé pendant l’envoi, relâché après', async () => {
  const setOccupe = mock.fn()
  const envoyer = mock.fn(async () => {
    assert.deepEqual(dernier(setOccupe), [true])
  })
  const e = geste()
  await creerSoumission(() => true, setOccupe, envoyer, mock.fn())(e)
  assert.equal(e.preventDefault.mock.callCount(), 1)
  assert.equal(envoyer.mock.callCount(), 1)
  assert.deepEqual(dernier(setOccupe), [false])
})

test('un true synchrone pose « occupé » dans le même tour que le geste', () => {
  const setOccupe = mock.fn()
  creerSoumission(() => true, setOccupe, async () => {}, mock.fn())(geste())
  assert.deepEqual(appels(setOccupe), [[true]])
})

test('invalide (synchrone ou promesse) : rien n’est envoyé, jamais occupé', async () => {
  for (const verdict of [false, Promise.resolve(false)]) {
    const setOccupe = mock.fn()
    const envoyer = mock.fn()
    await creerSoumission(() => verdict, setOccupe, envoyer, mock.fn())(geste())
    assert.equal(envoyer.mock.callCount(), 0)
    assert.equal(setOccupe.mock.callCount(), 0)
  }
})

test('verdict en promesse positive : envoie', async () => {
  const envoyer = mock.fn()
  await creerSoumission(() => Promise.resolve(true), mock.fn(), envoyer, mock.fn())(geste())
  assert.equal(envoyer.mock.callCount(), 1)
})

test('échec d’envoi : surErreur reçoit l’erreur, occupé relâché', async () => {
  const setOccupe = mock.fn()
  const surErreur = mock.fn()
  const boum = new Error('boum')
  await creerSoumission(() => true, setOccupe, async () => { throw boum }, surErreur)(geste())
  assert.deepEqual(appels(surErreur), [[boum]])
  assert.deepEqual(dernier(setOccupe), [false])
})

test('nom requis : nom vide = bandeau, nom saisi = envoi ; échec dans le bandeau', async () => {
  const setError = mock.fn()
  const envoyer = mock.fn()
  const options = { setError, setBusy: mock.fn(), envoyer, messageErreur: () => 'raté' }
  await creerSoumissionNomRequis({ ...options, nom: '  ' })(geste())
  assert.deepEqual(dernier(setError), ['Le nom est requis.'])
  assert.equal(envoyer.mock.callCount(), 0)

  await creerSoumissionNomRequis({ ...options, nom: 'Amal' })(geste())
  assert.deepEqual(dernier(setError), [null])
  assert.equal(envoyer.mock.callCount(), 1)

  envoyer.mock.mockImplementationOnce(async () => { throw new Error('x') }, 1)
  await creerSoumissionNomRequis({ ...options, nom: 'Amal' })(geste())
  assert.deepEqual(dernier(setError), ['raté'])
})
