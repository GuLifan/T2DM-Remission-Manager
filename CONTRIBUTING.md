# Contributing and branch permissions

Future development targets `develop`. Use a temporary `codex/` branch when useful, update the relevant specifications first, and validate the change before a requested push. Commit messages and PR titles/descriptions are English.

The owner explicitly authorized both `main` and `develop` for the initial 0.4.2 publication. That is not continuing permission: any later `main` push requires a new explicit instruction. `origin` is a remote name, not an extra release branch. Do not publish to other branches, tags or GitHub Releases, change visibility, rewrite history or force push without authorization.

Use `git push origin HEAD:develop` only when a development push is authorized; avoid broad `--all`, `--mirror`, implicit refspecs and forced updates. Check the remote URL and expected branch heads before publication. Prefer a GitHub noreply author email.

Keep test data synthetic and isolated. Never commit secrets, operational credentials, databases, runtime data, logs or private evidence originals. Existing history was preserved by request; deleting a file in a new commit does not remove it from old history.
