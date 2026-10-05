# Storyboard: "Five hundred milliseconds"

**Logline.** In March 2024 a developer noticed that a failed SSH login took half a second too long.
Pulling on that thread exposed a backdoor that a contributor persona had spent two and a half years
putting into xz-utils, shipped only in the release tarballs. The film follows the half second
backwards: from the stopwatch, to the years of trust-building, to the tarball that differed from
git, to the dependency chain that carried it into sshd, and back to the half second that gave it away.

**Format.** 1920×1080, 30 fps, 89.0 s (2670 frames). Remotion composition `FiveHundredMs`.
Final timings live in `src/cues.json` (shared with the audio script); this table matches the final cut.
Sources for every claim: `SOURCES.md`.

**Unforgettable moment.** 0:01–0:04, and again at 1:04–1:06: a stopwatch for a failed login reaches
its usual 0.299 s, seems to stop, and keeps going, the bar turning from ice to white-hot until it
lands at 0.807 s. The second time, the same meter is measured with a cold caliper: the tell becomes
the evidence.

**Colour meaning (trust is temperature).** The backdoor path runs hot (ironbow ramp: the persona's
access line, the hidden m4 macro, the heat travelling up the dependency chain, the extra 508 ms).
Discovery and the fix run cold (the caliper, the disclosure, the rollback, the lessons). Neutral
structure is steel line work on the indigo void. A small thermal scale bar sits on the right edge
of every shot (top right) as a legend: hostile at the top, verified at the bottom; its pointer
follows the temperature of the current shot.

**Type.** Titles: Martian Mono, width 112.5, weight 250, characters arriving white-hot and settling
to frost over 13 frames while their width axis opens from 75 to 112.5. Code and numbers: Martian
Mono width 100, weight 400. Captions: Schibsted Grotesk 500 at 52–60 px so they survive a phone
screen (a 1920 px frame shown 390 px wide is a 0.2× scale).

## Shot list

| # | Time | Shot | Reads (on-screen text) | Motion and transition |
|---|------|------|------------------------|-----------------------|
| 1 | 0:00.0–0:09.5 | **The tell.** A big counter and a latency meter (0 to 1.0 s, ticks every 0.1 s). An ice ghost marker at 0.299 s labelled "usual". Terminal line typing at top left. | `$ time ssh nonexistant@localhost` (verbatim from the disclosure), then `Permission denied (publickey).` and `real 0m0.807s`. Bracket: `+0.508 s`. Caption: "Same failed login. Half a second slower." | Counter starts at frame 0 (hook). Eases out into 0.299 s, holds 8 frames as if done, then accelerates on; fill shifts ice to ironbow by overshoot; stops at 0.807 with a spring overshoot. 0:06.0 the meter rises and shrinks; title "Five hundred milliseconds" settles in, subtitle "How an extra half second exposed the xz-utils backdoor, CVE-2024-3094." Exit: thermal scan wipe (cold band) left to right, 0:09.0. |
| 2 | 0:09.0–0:15.0 | **One library.** liblzma hex at centre; six dependents (dpkg, rpm, libsystemd, kmod, python3, libarchive) fan out on drawn lines. | "xz-utils makes .xz files. Its library, liblzma, sits under package managers, systemd and more." then "An unpaid hobby project, maintained largely by one person." with the name "Lasse Collin" set small beside a single cold node. | Lines draw with stroke-dash, dependents spring in with overshoot. Second caption: dependents dim, the maintainer node lights. Exit: the liblzma hex shrinks into the first event marker on the timeline (morph). |
| 3 | 0:14.5–0:33.5 | **The long game.** Timeline ribbon Oct 2021 to Apr 2024 (4.2 px per day; the camera pans so each event sits under a fixed playhead). A stepped hot line above the axis for the persona's access; a cold line below for the maintainer. | Seven cards (first at 0:14.75): 29 Oct 2021 "A new contributor, “Jia Tan”, sends a first, harmless patch." / Apr to Jun 2022 "New accounts on the mailing list press the maintainer to move faster." + chip “Patches spend years on this mailing list.” / 8 Jun 2022 maintainer quote “It's also good to keep in mind that this is an unpaid hobby project.” / 29 Jun 2022 "The maintainer calls Jia Tan “practically a co-maintainer already.”" / 18 Mar 2023 "Jia Tan tags a release for the first time: 5.4.2." / 23 Feb 2024 "Test files carrying a hidden payload are committed." / 24 Feb 2024 "xz 5.6.0 is released. 5.6.1 follows on 9 March." | Camera eases between event x positions; each card rises out of a mask, the previous dims. The access line steps up (contributor, commits merged, co-maintainer, release manager) and heats along the ironbow ramp. Pressure chips (envelopes) fly in hot and pile up on the cold maintainer line. Exit: the 5.6.0 marker flares white-hot and the frame wipes on it. |
| 4 | 0:33.0–0:47.5 | **What shipped.** Split screen. Left "git repository: what reviewers read"; right "xz-5.6.0.tar.gz: what distributions built". Real file names. | Generated files (`configure`, `Makefile.in`, `m4/libtool.m4`, `m4/gettext.m4`) in steel on the right only; `m4/build-to-host.m4` only on the right; the two test files on both sides, warm, "in git too; no test used them". Caption: "Release tarballs usually carry generated build files git doesn't have. One more didn't stand out." Then a code panel with the five real lines added to the macro (from the oss-security diff), and under it the pipeline they expand to, from the disclosure: `sed rpath …/bad-3-corrupt_lzma2.xz` (read the “corrupt” test file), `tr` (swap characters back), `xz -d` (decompress), `/bin/bash` (run the script). Captions: "During configure, a script hidden in a “corrupt” test file splices a prebuilt object into liblzma." / "Only on x86-64 Linux, with gcc and GNU ld, inside a Debian or RPM package build." | A vertical thermal scan sweeps both columns; rows resolve from noise to text as the scan passes; the m4 file ignites with a white-hot core. The file row grows into the code panel and its name travels to the panel header (morph, not a cut); pipeline boxes spring in with flow dots. Exit: hot wipe. |
| 5 | 0:47.0–0:58.5 | **Into sshd.** Dependency chain left to right: `sshd` links `libsystemd` links `liblzma`. | "OpenSSH's server, sshd, doesn't use liblzma directly." (0:47.8) / "But Debian and other distributions patch sshd to notify systemd, and libsystemd links liblzma." (0:50.1) / "Inside sshd, it hijacks RSA_public_decrypt, before anyone has authenticated." (0:53.2) / "Setting that up meant parsing symbol tables in memory each time sshd started. That was the slow part." (0:55.6) | Dashed direct link sshd to liblzma drawn and struck through (cold). libsystemd drops in with overshoot; link arrows draw. Then heat travels against the arrows, right to left, pulses along the links; the `RSA_public_decrypt` slot inside sshd is re-routed by a hot curve into liblzma. Exit: cold scan wipe (0:58.0). |
| 6 | 0:58.0–1:12.0 | **Half a second.** Discovery, all cold. | "March 2024. Andres Freund, a PostgreSQL developer, is micro-benchmarking on Debian unstable." (0:58.35) / profile bar (proportions labelled illustrative), liblzma segment `[unknown]`: "sshd burned CPU even on logins that failed at once. The profiler pointed into liblzma, at code with no symbol name." (0:59.35) / meter replay 1:03.9–1:05.7 with ice caliper "+508 ms" closing 1:05.8–1:06.35: "He remembered an odd valgrind error from a few weeks earlier, and kept digging." / dates (1:07.3): "28 Mar 2024 Private report to Debian and the distros mailing list." "29 Mar 2024 Public disclosure on oss-security. CVE-2024-3094, CVSS 10.0." / quote (1:09.4) “Really required a lot of coincidences.” Andres Freund, 29 March 2024 | Profile segments slide in; liblzma segment is hot. The meter replays 0.299 to 0.807, then an ice caliper closes on the gap (the unforgettable moment, replayed cold). Dates tick in on a short cold ribbon. |
| 7 | 1:11.5–1:17.5 | **Caught early.** Grid of distribution chips. | Warm: "Fedora Rawhide", "Fedora 40 beta", "Debian testing", "Debian unstable", "Debian experimental". Cold: "Debian stable", "Red Hat Enterprise Linux". Captions: "It reached development and pre-release versions, not Debian stable or Red Hat Enterprise Linux." / "Within days, distributions rolled back to xz 5.4.x." | A cold wave sweeps across the grid (1:14.3–1:15.6); affected chips cool from heat-2 to ice and draw a check mark. |
| 8 | 1:17.0–1:25.0 | **What to change.** | Headline: "What shipped wasn't what was reviewed." Three cold cards: "Reproducible builds" / "Rebuild from source, get the same bytes."; "Check artefacts against source" / "A tarball that differs from git is a question."; "Support maintainers" / "One tired volunteer shouldn't be the last line." Then: "Whether a person or a model reviews the change, verify what actually ships." | Kinetic headline ("shipped" settles hot, "reviewed" settles ice); cards spring up in sequence with overshoot; a cold check mark draws on each. Fades out 1:24.5. |
| 9 | 1:25.0–1:29.0 | **End card.** | "More than two years of patient work." / "Given away by half a second." Small: "Five hundred milliseconds" and the sources line. | First line mist, second line settles white-hot then ice; the slim latency meter fills to 0.807 underneath as an echo of the title. Hold to last frame. |

## Chapters (for the page)

| Time | Chapter |
|------|---------|
| 0:00 | The tell |
| 0:09 | One library |
| 0:14.5 | The long game |
| 0:33 | What shipped |
| 0:47 | Into sshd |
| 0:58 | Half a second |
| 1:11.5 | Caught early |
| 1:17 | What to change |

## Transitions

- **Thermal scan wipe** (1→2 cold, 3→4 hot, 4→5 hot, 5→6 cold): a vertical band 120 px wide sweeps across; the band is
  tinted coldbow when the next shot is cold, ironbow when it is hot; the incoming shot is revealed
  behind it with a clip-path.
- **Morphs** (2→3 hex into the first timeline marker; inside 4, file row into code panel; 1 title over the slimmed meter; 9 meter echo).
- **Cross-dissolves** only between 6→7, 7→8 and 8→9, where the cold palette carries through.

## Sound

Synthesised offline by `scripts/make-audio.mjs` (seeded, no samples): a low pad that gains odd
harmonics in the hot shots and thins to sine in the cold ones, one tick per 0.1 s as the meter
passes each mark, a soft thump when it lands, filtered-noise sweeps under the scan wipes. Cue times
come from `src/cues.json`, which the composition also reads, so picture and sound share one clock.
