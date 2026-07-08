# TEST_AUTHORING_CONTRACT.md — the test-authoring contract

Every lane agent writing tests in this repo follows these rules. Each exists
because it broke CI for real in 2026-07.

Note: `docs/TESTING.md` already exists (testing-strategy doc) — this file was
named `TESTING.md` in the original request, but that name collided with an
existing file, so it landed here instead. See report for details.

## Unique references

Never hardcode reference literals like `reference='FAC-1'` or
`'BUDGET-0000'` — 78 such landmines exist in the suite today, and
`BUDGET-0000` collided in real CI under repeated test runs. Generate unique
values from a shared `itertools.count()` or via `testkit/factories.py` instead.

## Pin wall-clock time

Any assertion sensitive to "now" must pin time explicitly — pass
`maintenant=`/datetime params into the code under test, or use `freezegun`
if it's added as a dependency. The xmkt1 test broke CI twice from clock
drift: a fixed "today at noon" assertion ran before an "afternoon" row was
created, so the query returned an empty list and raised `IndexError`.

## No threads inside `TestCase`

Never spawn `threading.Thread` inside a `django.test.TestCase` — its
per-test transaction/connection isn't thread-safe and will deadlock. Use
`TransactionTestCase` instead, and use unique temp paths (e.g.
`tempfile.mkstemp()`), never a fixed path like `/tmp/x.pdf`.

## Shared fixtures in `setUpTestData`

Put shared fixtures in class-scoped `setUpTestData`, not per-test `setUp`.
Django wraps `setUpTestData` rows in a savepoint reused per test — a huge
suite-time win. 212 files in this repo got this wrong.

## Tag slow/IO tests

Any new test touching boto3/MinIO/weasyprint/matplotlib (or similar slow
I/O) must carry `@tag('slow')` or `@tag('pdf')`, or it runs in the fast
merge gate. `scripts/check_test_tags.py` guards this in CI.

## Warm caches before counting queries

Query-count assertions (`assertNumQueries`) must warm the ContentType and
company caches first — an uncached first hit is a 1-query cold-start
artifact that falsely reads as an N+1. See the 2026-07-07 stage_since /
ContentType-prewarm fixes.

## Use `testkit/factories.py`

Use the shared factories (`make_company`, `make_user`, …) in
`testkit/factories.py` for common rows instead of hand-rolling a local helper.
One place to fix when a model gains a required field — today there are 135
hand-rolled helpers doing the same job.
