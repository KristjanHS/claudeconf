# Running GitHub Actions jobs locally with `act` (no Docker-in-Docker)

Validates the **workflow YAML itself** — checkout, `setup-node`, `npm ci`, the job's own step
sequence — which running the underlying test command directly never exercises. Useful before a
self-hosted runner is registered, and as a cheap pre-push gate on workflow edits.

## The host-exec technique

```bash
act -W .github/workflows/<file>.yml -j <job> \
    -P <runner-label>=-self-hosted \
    --no-cache-server
```

- **`-P <label>=-self-hosted` runs the job's steps DIRECTLY ON THE HOST** — no container, no
  Docker-in-Docker, no socket mount. Anything the job reaches on the host (a local DB stack on a
  fixed port, a toolchain already on `PATH`) works unchanged. This is what makes a
  `runs-on: [self-hosted, linux]` job reproducible locally; it also sidesteps the DinD fragility
  that container-mode + a mounted host socket otherwise forces you to design around.
  Map the label the workflow actually declares — for `runs-on: [self-hosted, linux]`, `-P self-hosted=-self-hosted`.
- **`--no-cache-server` is effectively mandatory** when the job uses `actions/setup-node` with
  `cache: npm`. Without it, act starts a cache backend and the setup-node *post* step tars the whole
  npm cache (multi-GB) on every run. Worse, a timeout mid-tar surfaces as a **job failure even though
  every test passed** — the green suite scrolls past and the exit code lies about why.

## Reading the result

`🏁 Job succeeded` + exit 0 is the pass. A non-zero exit *after* a green test summary is almost always
the post-step cache tar, not the suite — check which step the failure is attributed to before
debugging tests that already passed.

## What it does not cover

Runner *registration*, secrets wired through GitHub, and `${{ secrets.* }}` resolution (pass with
`-s NAME=value` or a `.secrets` file). Concurrency/matrix semantics are approximated, not identical.
