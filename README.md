# GimmeMusic

**Your sound, amplified.** A local music studio for Plenio + ComfyUI with a dark violet, pink, and cyan interface built around the Gimmesamoa identity.

Compose songs, make covers, hunt for a great seed, and browse the music you create from one studio interface.

## Features

- Song and cover creation using bundled YuE2 execution profiles.
- Sound descriptions, lyrics, cover audio uploads, and generation controls.
- Randomized seeds and batches of 1–8 takes.
- Generation queue and Song Sheet review/approval.
- Song naming and a dedicated Song Sheet page for title, style, lyrics, native ABC score, and artwork prompts, with automatic/manual document modes and Plenio validation.
- Workflow settings for schema-defined node controls: models, seeds, sampling, transcription, mixing, mastering, and export options. Connections remain read-only.
- Inspect saved release documents/reports and load their exact graph and documents into a new take; review Song Sheets from studio runs.
- Track three-dot menus with **Load in editor** and project assignment. Editing creates a new take without overwriting the source release.
- Local projects with grouped tracks, recent generations, naming, and saved drafts (including lyrics, settings, seeds, and batch size).
- Real Plenio exports with favorites, search, playback, waveforms, seeking, and downloads.
- Local operation and locally bundled fonts; no hosted account required.

## Built-in Plenio integration

Includes **song and cover API profiles**, all six upstream **ComfyUI workflow templates**, a **pinned Plenio installer**, and a **model-download manifest**. Setup fetches Plenio at the recorded upstream commit. Large models, ComfyUI, and Python runtimes are installed separately.

GimmeMusic submits copies of the graphs and changes only requested run inputs. It never rewrites saved workflows or the open ComfyUI canvas. Existing `data/profiles.json` takes precedence over bundled defaults, preserving local profiles during upgrades. Public profiles contain generic prompts, with no personal lyrics, source filenames, or old approvals.

## Windows setup

Requires Git, Node.js 20.19+ or 22.12+, and a recent working ComfyUI installation with YuE2 support and its Python environment. The tested ComfyUI commit is in `workflows/upstream.json`; older releases may lack required YuE2, text-generation, switch, or loop nodes.

```powershell
git clone https://github.com/SilverSix311/GimmeMusic.git
cd GimmeMusic
.\Setup-GimmeMusic.ps1 -ComfyRoot 'C:\ComfyUI_windows_portable\ComfyUI' -Python 'C:\ComfyUI_windows_portable\python_embeded\python.exe'
```

Setup installs Plenio if missing, installs studio/transcription dependencies into the specified Python environment, adds Plenio's import path for embedded-Python workers, copies templates into a new `workflows/GimmeMusic` folder without overwriting files, saves ignored local configuration, and builds the frontend. Setup applies the version-checked original-lyrics extension to Plenio. It preserves saved workflow files and existing unrelated patches; incompatible node versions fail before applying the patch. Use `-SkipDependencies` for an already provisioned runtime or `-SkipBuild` if already built.

Start ComfyUI on `127.0.0.1:8189`, then double-click **Start-GimmeMusic.bat**. Open **http://127.0.0.1:8195**. For another ComfyUI port, pass `-EngineUrl http://127.0.0.1:8188` during setup. ComfyUI must run on the same machine because the library uses its input/output folders.

The existing layout `GimmeMusic/` beside `Plenio-Portable/` also works without configuration. After setup, normal use needs neither npm nor internet access if models are already downloaded. `Stop-GimmeMusic.ps1` stops only the studio.

### Models

Review `workflows/models.json` and upstream model terms, then download missing song/cover models:

```powershell
& 'C:\ComfyUI_windows_portable\python_embeded\python.exe' scripts/download_models.py --comfy-root 'C:\ComfyUI_windows_portable\ComfyUI'
```

Uses curl, resumes partial downloads, and skips existing files. Downloads can be many gigabytes. Faster-whisper may additionally download weights on first use. Additional MiniMax, mastering, and DAW templates are for ComfyUI; the studio exposes only YuE2 song and cover profiles, and its manifest excludes MiniMax models.

### Optional nominal 24 GB card compatibility

`patches/nominal-24gb-vram.patch` lets cards reporting slightly below 24 GiB attempt transcription of sources longer than 300 seconds. It changes a capacity check to 23.5 GiB; it does not lower actual memory use or guarantee a long cover will fit. It is **not applied automatically**. In a clean Plenio checkout matching the pinned commit, use `git apply <absolute-path-to-patch>`. Existing installations with this fix need no action.

## Development and testing

**Editing:** use Song Sheet → Next take for documents, or Workflow settings for node controls. Drafts are saved in browser storage and apply to the next submission. Saved releases are immutable; **Use for next take** starts an editable draft using that release's graph. Set a sheet's review behavior to **stop for review** to pause generation for approval. **Validate Song Sheets** runs Plenio's document checks without submitting a render; automatic documents may remain unavailable until their upstream stages execute. Score editing uses native ABC text; graph rewiring and Plenio's visual piano roll remain in ComfyUI. Randomized seed hunting overrides individual seed values while enabled.

**Original cover lyrics:** choose Lyrics → Lyric source → **Provide original lyrics**, then paste the complete words for the exact recording or clip, including repeated choruses. Transcription still runs. Matching words supply timing anchors; unmatched supplied words use interpolated timing marked as uncertain. Plenio places those words into the final score’s sections. This is not acoustic forced alignment. Song Sheet → Run sheets shows the untouched transcript, word error rate, and estimated-word count. Review before rendering when timing matters. The existing Cover Brief mode controls whether the Song Sheet stops.

The backward-compatible extension adds an optional input to Transcribe Lyrics without rewiring graphs. Setup installs it automatically. Existing installations can run `python scripts/install_lyrics.py <Plenio-root>` using the studio Python, then restart ComfyUI. Supplied lyrics are stored in local drafts and run prompts, like other song inputs.

**Cover Brief:** Sound exposes title, template, description, genre, mood and harmony; Lyrics exposes vocals and all mode-dependent fields; Controls exposes workflow mode. Template text, choices and reset actions use Plenio’s own template rules.

**Replacement cover lyrics:** choose Lyrics → Use my own lyrics and paste section-tagged lyrics, or load a track in the editor and edit its lyrics document. Custom lyrics select a sung cover mode and replace the source words at the Song Sheet. Use validation to check their compatibility with the source score.

**Projects:** create a project from Projects, then choose it in the Generation project selector. New takes export under `plenio/gimmemusic-projects/<project-id>` and appear together, including approval continuations. Use a track's three-dot menu to assign existing releases without moving their audio. **Save draft** stores the current draft in the project; **Load saved draft** restores it. Saving drafts is explicit. Projects and assignments live in ignored `data/projects.json`, so they survive restarts and are not published to GitHub.

```powershell
npm ci
npm run build
python -m pip install -r requirements.txt
python server.py
python -m unittest discover -s tests -p 'test_*.py'
```

Use your ComfyUI Python executable where appropriate. See `config.example.json`; server environment overrides are `GIMMEMUSIC_COMFY_ROOT` and `GIMMEMUSIC_ENGINE_URL`. Keep `config.json` private.

Browser checks require a running studio and existing audio library:

```powershell
npx playwright install chromium
npm run test:browser
npm run test:playback
```

Browser generation tests intercept submissions; backend tests mock the engine. They never queue GPU renders. The template in `ci/github-checks.yml` builds the frontend and runs backend tests without models or a private library. To enable GitHub Actions, copy it to `.github/workflows/checks.yml` using credentials with workflow permission. A complete render on a new machine still depends on compatible ComfyUI, installed models, and sufficient GPU memory.

## Local data

`data/`, `config.json`, runtime files, screenshots, dependencies, and build output are ignored by Git. Favorites, jobs, waveforms, and local profiles live in `data/`; form drafts live in browser storage. Uploads go to ComfyUI's input directory; exports remain in its output directory. Public defaults do not automatically import private ComfyUI history. Back up local data separately.

## Credits and license

Powered by [Plenio Music Production System](https://github.com/jplenio/Plenio-Music-Production-System) and [ComfyUI](https://github.com/Comfy-Org/ComfyUI). Interface inspiration: [ACE-Step Studio](https://github.com/timoncool/ACE-Step-Studio). Built for Gimmesamoa.

Original app code is MIT licensed. Plenio-derived workflows retain Apache-2.0 terms; branding is excluded from the software license. See [THIRD_PARTY.md](THIRD_PARTY.md).

