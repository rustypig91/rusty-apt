#!/usr/bin/env bash
set -euo pipefail
: "${APT_GPG_FINGERPRINT:?Set the Actions variable APT_GPG_FINGERPRINT to the full signing key fingerprint (not an Actions secret)}"
cd "${1:-site}"
mkdir -p dists/stable
mapfile -t architectures < <(find pool -name '*.deb' -exec dpkg-deb -f {} Architecture \; | sort -u)
((${#architectures[@]})) || { echo 'No packages'; exit 1; }
mapfile -t architectures < <(printf '%s\n' amd64 "${architectures[@]}" | grep -v '^all$' | sort -u)
rm -rf dists/stable/main
for arch in "${architectures[@]}"; do
  dir="dists/stable/main/binary-$arch"
  mkdir -p "$dir"
  dpkg-scanpackages --multiversion --arch "$arch" pool /dev/null > "$dir/Packages"
  gzip -n -9 -c "$dir/Packages" > "$dir/Packages.gz"
done
rm -f dists/stable/{InRelease,Release,Release.gpg}
apt-ftparchive -o APT::FTPArchive::Release::Origin=Rusty \
  -o APT::FTPArchive::Release::Label=Rusty \
  -o APT::FTPArchive::Release::Suite=stable \
  -o APT::FTPArchive::Release::Codename=stable \
  -o "APT::FTPArchive::Release::Architectures=${architectures[*]}" \
  -o APT::FTPArchive::Release::Components=main \
  release dists/stable > dists/stable/Release
printf '%s' "${APT_GPG_PASSPHRASE:-}" | gpg --batch --yes --pinentry-mode loopback \
  --passphrase-fd 0 --local-user "$APT_GPG_FINGERPRINT" --digest-algo SHA256 \
  --clearsign -o dists/stable/InRelease dists/stable/Release
printf '%s' "${APT_GPG_PASSPHRASE:-}" | gpg --batch --yes --pinentry-mode loopback \
  --passphrase-fd 0 --local-user "$APT_GPG_FINGERPRINT" --digest-algo SHA256 \
  --armor --detach-sign -o dists/stable/Release.gpg dists/stable/Release
gpg --armor --export "$APT_GPG_FINGERPRINT" > rusty.asc
gpg --verify dists/stable/InRelease
gpg --verify dists/stable/Release.gpg dists/stable/Release
touch .nojekyll
