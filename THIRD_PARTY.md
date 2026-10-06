# Attribution and licenses

- **Plenio Music Production System**, copyright 2026 Johannes Plenio, Apache-2.0: https://github.com/jplenio/Plenio-Music-Production-System. License and notice are reproduced under `licenses/`. `workflows/comfyui/` contains unmodified upstream templates at the commit in `workflows/upstream.json`. `workflows/profiles.json` contains expanded execution graphs adapted from those workflows with generic text, empty source selection, cleared Song Sheet documents/approvals, and zeroed seeds. Node classes, connections, and generation settings are retained from the working local profiles. `patches/nominal-24gb-vram.patch` is an optional local modification to the VRAM threshold, not an upstream change. `patches/original-lyrics.patch` is a GimmeMusic modification of Plenio’s transcription and alignment code under Apache-2.0; it adds optional source-word alignment and leaves default behavior intact. `patches/original_lyrics.py` is original GimmeMusic integration code.
- **ComfyUI**, GPL-3.0: https://github.com/Comfy-Org/ComfyUI. Installed separately; no source or runtime is redistributed here.
- **React**, **Vite**, and **Playwright**: MIT; **Lucide**: ISC. Licenses are supplied by their packages through npm.
- **DM Sans** and **Space Grotesk**: SIL Open Font License 1.1, distributed through `@fontsource`; licenses are included in those packages.
- **Gimmesamoa brand assets** in `public/assets/`: supplied for GimmeMusic by its owner; excluded from the software MIT license. No separate permission to reuse the logo, artwork, or brand is granted.
- Model weights are not included. Download URLs do not grant a license; each model's upstream terms apply. See Plenio's documentation for YuE2 and supporting models.

The interface was inspired by [ACE-Step Studio](https://github.com/timoncool/ACE-Step-Studio). No ACE-Step Studio source code is included, and GimmeMusic is not affiliated with that project.
