# Repository Guidelines

## Project Structure & Module Organization
`index.html` is the single-page entry point, backed by modular ES modules in `assets/js/`. Core logic is split into `audio/`, `core/`, `ui/`, and `features/` subfolders, while styling lives in `assets/style.css` and thematic variants under `themes/`. Python helpers (`generate_music_list.py`, `music_file_fixer.py`) handle track ingestion workflows. Tests reside in `tests/` with fixtures and setup utilities, and static assets (logos, icons, documentation) are in `images/`, `assets/`, and `User_Documentation.html`.

## Build, Test, and Development Commands
- `npm install`: grab Vitest, jsdom, and UI tooling before running scripts.
- `npm run serve`: launch a lightweight Python HTTP server on `http://localhost:8000` to use upload/preview flows.
- `npm test`: execute the Vitest suite once; use this in CI.
- `npm run test:watch`: rerun targeted specs during local development.
- `npm run test:coverage`: produce coverage data for the `tests/` suite.

## Coding Style & Naming Conventions
JavaScript files use ES modules, `use strict`, descriptive class names, and 2-space indentation. Keep functions pure where possible and favor `const`/`let`. CSS follows BEM-ish utility blocks in `assets/style.css` with theme overrides in `themes/`. Filenames are kebab-case (`tracklist-compare-ui.js`), and dataset files should use the documented `Artist - Title - Key - BPM.ext` format inside `tracklist.csv`. Run Prettier or your editor’s formatter configured to 2 spaces before submitting.

## Testing Guidelines
Vitest with jsdom simulates the DOM. Add new suites under `tests/unit/` and mirror the module path (e.g., `audio-manager.test.js`). Name tests after the behavior (`shouldCrossfadeWhenAutoMixEnabled`). Maintain coverage for parsing, filtering, and security utilities; add fixtures to `tests/fixtures/` rather than embedding inline JSON. Run `npm test` before pushing, and include regression cases for new metadata rules.

## Commit & Pull Request Guidelines
Follow the existing history: short, imperative subjects (`Add core module skills documentation`) and scoped changes per commit. Each PR should describe the problem, the solution, and any UI impact; attach screenshots or screen recordings when altering visual components. Link related issues, list manual test steps (server command, browser path, dataset used), and call out risks such as migrations or data format updates.

## Security & Configuration Tips
Uploads and previews run entirely client-side; still sanitize user input through `SecurityUtils` and keep DOM updates inside `UIRenderer` helpers. Never commit personal tracklists or audio. Python helpers can rename files—encourage contributors to back up directories before running `music_file_fixer.py` and to use virtual environments when installing dependencies.
