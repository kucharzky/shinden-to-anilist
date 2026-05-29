# shinden-to-anilist

Export a **public** [Shinden.pl](https://lista.shinden.pl) anime list to **MyAnimeList XML** for importing into [AniList](https://anilist.co/settings/import).

No accounts, passwords, or API keys are required. The script only reads public list URLs and writes a local XML file.

## Requirements

- Python 3.10+
- Dependencies: `requests`, `beautifulsoup4`

## Setup

```bash
cd ~/shinden-to-anilist
pip install -r requirements.txt
```

## Usage

Interactive (prompts for the list URL):

```bash
python main.py
```

With a URL — by default **all** list sections are exported (watching, completed, on hold, dropped, plan, skip):

```bash
python main.py "https://lista.shinden.pl/animelist/123456-nickname"
```

Output file name is derived from the user id in the URL and the status filter, e.g. `123456_all_shinden_export.xml`.

Export a single section:

```bash
python main.py "https://lista.shinden.pl/animelist/123456-nickname" --watching
python main.py "https://lista.shinden.pl/animelist/123456-nickname" --completed
python main.py "https://lista.shinden.pl/animelist/123456-nickname" --on-hold
python main.py "https://lista.shinden.pl/animelist/123456-nickname" --dropped
python main.py "https://lista.shinden.pl/animelist/123456-nickname" --plan
python main.py "https://lista.shinden.pl/animelist/123456-nickname" --skip
```

| Flag | Output example |
|------|----------------|
| *(default)* | `123456_all_shinden_export.xml` |
| `--watching` | `123456_watching_shinden_export.xml` |
| `--completed` | `123456_completed_shinden_export.xml` |
| `--on-hold` | `123456_on-hold_shinden_export.xml` |
| `--dropped` | `123456_dropped_shinden_export.xml` |
| `--plan` | `123456_plan_shinden_export.xml` |
| `--skip` | `123456_skip_shinden_export.xml` |

Override the file path with `-o path/to/file.xml`.

## How it works

1. **Shinden** — Fetches the public list page with `requests` and parses metadata with **BeautifulSoup** (`__NEXT_DATA__`, optional HTML table rows). Shinden’s list is a client-rendered SPA, so entry data is loaded from the public JSON API (`lista.shinden.pl/api/userlist/...`), the same source the website uses.
2. **Jikan** — For each title, searches [Jikan API v4](https://jikan.moe/) (unofficial MAL API) to resolve `mal_id`, with a **1 second** delay between requests.
3. **XML** — Writes MAL-compatible XML for AniList’s importer.

### Status mapping (Polish / API → MAL)

| Shinden | MAL `my_status` |
|---------|-----------------|
| Oglądam / in progress | 1 (Watching) |
| Obejrzane / completed | 2 (Completed) |
| Wstrzymane / hold | 3 |
| Porzucone / dropped | 4 |
| Planowane / plan | 6 |

Titles without a Jikan match are listed on stderr and omitted from the XML.

## Import on AniList

1. Open [AniList → Settings → Import](https://anilist.co/settings/import)
2. Choose **MyAnimeList**
3. Upload your generated `*_shinden_export.xml` file

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
