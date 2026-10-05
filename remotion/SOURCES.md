# Sources: "Five hundred milliseconds"

Every on-screen claim maps to one of these. Checked 2026-10-03.

## Primary

1. **Andres Freund, "backdoor in upstream xz/liblzma leading to ssh server compromise"**,
   oss-security mailing list, Fri 29 Mar 2024 08:51 -0700.
   https://www.openwall.com/lists/oss-security/2024/03/29/4
   - Versions 5.6.0 and 5.6.1; "One portion of the backdoor is *solely in the distributed tarballs*";
     the injecting line is in `m4/build-to-host.m4`, which "is *not* in the upstream source of
     build-to-host, nor is build-to-host used by xz in git".
   - Bulk of the payload in `tests/files/bad-3-corrupt_lzma2.xz` and
     `tests/files/good-large_compressed.lzma`, committed upstream; "the files were not even used
     for any 'tests' in 5.6.0".
   - Conditions: x86-64 Linux, gcc + GNU ld, inside a Debian or RPM package build; likely glibc only.
   - Symptoms: "logins with ssh taking a lot of CPU, valgrind errors" on Debian sid.
   - Timing: `time ssh nonexistant@localhost` (his spelling): `real 0m0.299s` before,
     `real 0m0.807s` after, same "Permission denied (publickey)" result. (0.807 − 0.299 = 0.508 s.)
   - "openssh does not directly use liblzma. However debian and several other distributions patch
     openssh to support systemd notification, and libsystemd does depend on lzma."
   - Parsing symbol tables in memory "is the quite slow step that made me look into the issue".
   - The backdoor redirects `RSA_public_decrypt@....plt` to its own code; it runs in a
     pre-authentication context.
   - "Luckily xz 5.6.0 and 5.6.1 have not yet widely been integrated by linux distributions, and
     where they have, mostly in pre-release versions."

2. **CVE-2024-3094** (CNA: Red Hat; published 2024-03-29), "Xz: malicious code in distributed source".
   https://www.cve.org/CVERecord?id=CVE-2024-3094 (API: https://cveawg.mitre.org/api/cve/CVE-2024-3094)
   - "Malicious code was discovered in the upstream tarballs of xz, starting with version 5.6.0 …
     the liblzma build process extracts a prebuilt object file from a disguised test file existing
     in the source code, which is then used to modify specific functions in the liblzma code."
   - CVSS 3.1 base score 10.0 (critical), vector AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H.

3. **Red Hat, "Urgent security alert for Fedora Linux 40 and Fedora Rawhide users"**, 29 Mar 2024.
   https://www.redhat.com/en/blog/urgent-security-alert-fedora-41-and-rawhide-users
   - Malicious code in xz 5.6.0 and 5.6.1; "only included in full in the download package - the Git
     distribution lacks the M4 macro that triggers the build"; "interferes with authentication in
     sshd via systemd"; Fedora Rawhide and Fedora 40 beta received the versions;
     "No versions of Red Hat Enterprise Linux (RHEL) are affected".

   - Rollback: "Fedora Rawhide will be reverted to xz-5.4.x shortly" and, for Fedora 40, "An update
     that reverts xz to 5.4.x has recently been published" (post updated 30 Mar 2024). With Debian's
     same-day revert below, this supports the film's "within days, distributions rolled back to xz 5.4.x".
4. **Debian, DSA-5649-1 xz-utils**, 29 Mar 2024.
   https://lists.debian.org/debian-security-announce/2024/msg00057.html
   - "Right now no Debian stable versions are known to be affected. Compromised packages were part
     of the Debian testing, unstable and experimental distributions"; reverted to upstream 5.4.5
     code (`5.6.1+really5.4.5-1`).

5. **Andres Freund on Mastodon**, 29 Mar 2024.
   https://mastodon.social/@AndresFreundTec/112180406142695845
   - "I was doing some micro-benchmarking at the time … Saw sshd processes were using a surprising
     amount of CPU, despite immediately failing because of wrong usernames etc. Profiled sshd,
     showing lots of cpu time in liblzma … Recalled that I had seen an odd valgrind complaint in
     automated testing of postgres, a few weeks earlier … Really required a lot of coincidences."

## Timeline and analysis

6. **Russ Cox, "Timeline of the xz open source attack"**. https://research.swtch.com/xz-timeline
   - 2021-10-29 Jia Tan's first, innocuous patch (`.editorconfig`).
   - 2022-04-22 "Jigar Kumar": "Patches spend years on this mailing list."
   - 2022-06-08 Lasse Collin: "… my ability to care has been fairly limited mostly due to longterm
     mental health issues … It's also good to keep in mind that this is an unpaid hobby project."
     (The film quotes only the last sentence.)
   - 2022-06-29 Collin: Jia Tan "is practically a co-maintainer already".
   - Cox on Jigar Kumar and Dennis Ens: "It seems likely that they were fakes created to push Lasse
     to give Jia more control." (The film says only "new accounts".)
   - 2023-03-18 Jia Tan tags the first release they made, v5.4.2.
   - 2024-02-23 backdoor test files committed; 2024-02-24 v5.6.0; 2024-03-09 v5.6.1.
   - 2024-03-28 Freund reports privately to Debian and distros@openwall; 2024-03-29 public post.
7. **Gynvael Coldwind, "xz/liblzma: Bash-stage obfuscation explained"**.
   https://gynvael.coldwind.pl/?lang=en&id=782 (the `gl_path_map` and `gl_[$1]_config` lines).
8. **Julien Malka, "How NixOS could have detected the XZ supply-chain attack"**.
   https://luj.fr/blog/how-nixos-could-have-detected-xz.html (the `gl_am_configmake` grep line;
   rebuilding from the git archive and comparing bytes as a detection method).
9. **oss-security follow-up with the diff of the tampered `m4/build-to-host.m4` against gnulib**,
   30 Mar 2024. https://www.openwall.com/lists/oss-security/2024/03/30/14
   - The exact lines shown in shot 4: the `gl_am_configmake` grep, `gl_path_map`, `gl_[$1]_prefix`,
     `gl_[$1]_config`, and `AC_CONFIG_COMMANDS([build-to-host], [eval $gl_config_gt | $SHELL 2>/dev/null], …)`.
10. **GitHub, tukaani-project/xz at tag v5.6.0** (file layout shown in the git column).
   https://github.com/tukaani-project/xz/tree/v5.6.0/m4

## What the film deliberately does not claim

- Who was behind "Jia Tan". The film calls it a contributor persona and stops there.
- Exactly what the payload allowed. It says the backdoor "redirects RSA_public_decrypt to its own
  code, which runs before authentication", as in the disclosure, and nothing about attacker keys.
- That any stable Debian or RHEL release shipped it (they did not).
