# Privacy Law Reference Tool

Free, static, searchable reference for privacy law. See `SPEC.md` for the full spec.
Status: build step 1 (skeleton and hosting proof).

## Layout
- `sources.yaml` - every document, URL, type, jurisdiction, parser
- `synonyms.yaml` - query expansion (step 4)
- `topics/` - guided topic YAML files (step 9)
- `data/raw/` - saved original source files (step 2+)
- `build/build.py` - static site build (currently a hello page)
- `.github/workflows/pages.yml` - build and deploy to GitHub Pages

## Run locally
```bash
pip install -r requirements.txt
python build/build.py
python -m http.server -d dist 8000   # open http://localhost:8000
```

## Deploy
1. Create a **public** GitHub repo and push this folder to `main`.
2. Repo Settings > Pages > Source: **GitHub Actions**.
3. The workflow runs on each push; the URL appears in the deploy job
   (`https://<username>.github.io/<repo>/`).

## GitHub Pages limits (verify at https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)
As last known: published site <= 1 GB, ~100 GB/month soft bandwidth, ~10 builds/hour soft limit,
files over 100 MB are rejected by git. Keep generated output well under these.
