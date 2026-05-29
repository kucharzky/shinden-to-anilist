# shinden-to-anilist

Export a **public** [Shinden.pl](https://lista.shinden.pl) anime list to **MyAnimeList XML** for importing into [AniList](https://anilist.co/settings/import).

No accounts, passwords, or API keys are required. The script only reads public list URLs and writes a local XML file.

## Requirements

- Python 3.10+
- Dependencies: `requests`, `beautifulsoup4`

## Setup

```bash
cd ~/shinden-to-anilist
source ~/.venv/bin/activate   # WSL venv
pip install -r requirements.txt
```

## Usage

Interactive (prompts for the list URL):

```bash
python main.py
```

With a URL (example list — “Oglądam” / watching):

```bash
python main.py "https://lista.shinden.pl/animelist/103810-teoroki"
```

Export every status section (watching, completed, on hold, dropped, plan, skip):

```bash
python main.py "https://lista.shinden.pl/animelist/103810-teoroki" --all-statuses
```

Output defaults to `shinden_export.xml` in the current directory.

## How it works

1. **Shinden** — Fetches the public list page with `requests` and parses metadata with **BeautifulSoup** (`__NEXT_DATA__`, optional HTML table rows). Shinden’s list is a client-rendered SPA, so entry data is loaded from the public JSON API (`lista.shinden.pl/api/userlist/...`), the same source the website uses.
2. **Jikan** — For each title, searches [Jikan API v4](https://jikan.moe/) (unofficial MAL API) to resolve `mal_id`, with a **1 second** delay between requests.
3. **XML** — Writes MAL-compatible XML for AniList’s importer.

### Status mapping (Polish / API → MAL)

| Shinden | MAL `my_status` |
|---------|-----------------|
| Obejrzane / completed | 1 |
| Oglądam / in progress | 2 |
| Wstrzymane / hold | 3 |
| Porzucone / dropped | 4 |
| Planowane / plan | 6 |

Titles without a Jikan match are listed on stderr and omitted from the XML.

## Import on AniList

1. Open [AniList → Settings → Import](https://anilist.co/settings/import)
2. Choose **MyAnimeList**
3. Upload `shinden_export.xml`

## Project layout

```
shinden-to-anilist/
├── main.py
├── requirements.txt
├── README.md
└── src/shinden_export/
    ├── cli.py
    ├── shinden.py
    ├── jikan.py
    └── mal_xml.py
```

## License

MIT — use at your own risk; respect Shinden and Jikan rate limits.
