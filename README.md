# Rusty APT

Signed Ubuntu packages for pigtail and canvaz, reusing their GitHub Release
Debian assets. Intended URL: https://rustypig91.github.io/rusty-apt/ (available
after owner setup and the first successful deployment).

## Install on Ubuntu 22.04 or newer (amd64)

```bash
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://rustypig91.github.io/rusty-apt/rusty.asc | sudo tee /etc/apt/keyrings/rusty.asc >/dev/null
sudo chmod 644 /etc/apt/keyrings/rusty.asc
echo 'deb [signed-by=/etc/apt/keyrings/rusty.asc] https://rustypig91.github.io/rusty-apt stable main' | sudo tee /etc/apt/sources.list.d/rusty.list
sudo apt update
sudo apt install pigtail canvaz
```

Use `sudo apt update && sudo apt upgrade` for upgrades. Remove applications
with `sudo apt remove pigtail canvaz`. Separately remove the source with:

```bash
sudo rm -f /etc/apt/sources.list.d/rusty.list /etc/apt/keyrings/rusty.asc
sudo apt update
```

## Owner setup

1. Create an empty public GitHub repository `rustypig91/rusty-apt`. Commit these
   files on `main`, add `https://github.com/rustypig91/rusty-apt.git` as origin,
   and push. Commit and push the companion changes in both application repos.
2. In Settings → Pages select **GitHub Actions** as the source. Enable Actions.
   Allow the publishing workflow's explicit `contents: write`, `pages: write`,
   and `id-token: write` permissions. Permit its GITHUB_TOKEN to push the
   `apt-data` branch (exclude that generated branch from mandatory PR rules).
   Keep `main` protected and restrict who can change workflows.
3. Generate a dedicated signing key on a trusted machine. Supply your own
   name/email, use a strong passphrase, and record its full fingerprint:
   ```bash
   gpg --quick-generate-key 'APT Maintainer <YOUR_EMAIL>' rsa4096 sign 2y
   gpg --list-secret-keys --keyid-format long
   ```
   Set repository Actions variable `APT_GPG_FINGERPRINT` to that full fingerprint
   under **Settings > Secrets and variables > Actions > Variables**. This must
   be a variable, not a secret: the workflow reads `vars.APT_GPG_FINGERPRINT`.
   To display the full fingerprint, run `gpg --fingerprint --list-secret-keys`.
   Store the complete ASCII-armored output of
   `gpg --armor --export-secret-keys YOUR_FINGERPRINT` in the repository Actions
   secret `APT_GPG_PRIVATE_KEY`; put its passphrase in `APT_GPG_PASSPHRASE`.
   Transfer the export directly to GitHub secrets; never save it in a checkout,
   commit it, or paste it into logs. Back up the key securely. Renew before its
   expiry and update the secret; keep the same key for existing installations.
4. Create a fine-grained PAT restricted to **rustypig91/rusty-apt only**, with
   **Actions: write** (Metadata: read is automatic). Store it as the Actions
   secret `APT_PUBLISH_TOKEN` in each application repository. It dispatches
   `publish-apt.yml` on `main`; it needs no Contents write permission. A GitHub
   App installation token with the same repository/Actions permission is also
   suitable if you arrange token minting. No credential reads private source
   repositories: the configured application releases must be public.
5. The `github-pages` environment is used for deployment. Allow `main` to deploy
   there; optional required reviewers will pause publication. Signing secrets
   above are repository secrets, not application-repository secrets.
6. Run **Publish APT** manually. There must be at least one canonical Debian
   asset; release the updated Canvaz to make its canonical asset available.
   Existing legacy Canvaz display-title assets are intentionally skipped.
7. Test the install commands above in a clean Ubuntu 22.04 amd64 VM/container.
   Confirm `test -x /usr/bin/pigtail` and `test -x /usr/bin/canvaz`.
   The workflow already tests signed APT update and installation in Ubuntu
   before saving or deploying metadata. It does not launch GUI applications.

## Operation and retention

The existing application workflows dispatch publication only after all release
jobs succeed on a version tag. Branch/manual draft builds do not dispatch.
A six-hour reconciliation schedule recovers missed dispatches, partially
completed releases, and externally published releases. GitHub schedules may be
delayed or disabled for inactive repositories; manual dispatch is the recovery.

Every run lists **all** stable releases from both explicitly allowlisted sources,
including paginated results, and imports canonical `.deb` assets. Stable tags
must be `vMAJOR.MINOR.PATCH` (or without `v`). Prereleases and build metadata are
excluded rather than guessing Debian ordering. Existing package versions are
retained on `apt-data`; equal identity/version/architecture with different bytes
fails instead of silently replacing packages. Never rebuild and overwrite a
published version: release a new version. Pool filenames come from validated
Debian metadata; package control versions and dependencies remain unchanged.
Normal numeric Debian version ordering supports upgrades.

`dpkg-scanpackages --multiversion` and `apt-ftparchive` generate standard indices,
then GPG generates `InRelease`, `Release.gpg`, and public `rusty.asc`. Native
architectures found in the pool receive indices (amd64 is always present).
Current application workflows build amd64; additional native architecture
installation tests should be added when those builds are enabled.

One workflow-level concurrency group serializes read/update/save/deploy.
Even if GitHub replaces a pending run, the next run reconciles both sources.
The durable branch is updated before Pages deployment, so failed deployments
can be retried without losing packages. No cleanup policy deletes old packages.
Back up `apt-data`: GitHub Releases can be deleted upstream. GitHub file/repository
and Pages size limits still apply; monitor growth before adding large histories.
Metadata deliberately has no Valid-Until because publishing is release-driven.

## Validation

Run `python3 tests/test_repository.py` (Python, dpkg-dev, apt-utils, GPG required).
CI also validates real application packages and installs them in Ubuntu before
publication. The package producers retain existing dependency discovery,
resources, desktop entries, icons and licenses; Canvaz adds its LICENSE and a
canonical package identity without changing its original bundles.
