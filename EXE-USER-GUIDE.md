# AQMD Rule Finder — User Guide

**South Coast Air Quality Management District Rule Search Tool**

---

## How This Tool Works

The AQMD Rule Finder is a full-text search tool for all South Coast AQMD regulatory rules. Here is what happens behind the scenes each time you use it:

1. **Connects to the AQMD website.** On startup, the tool contacts [www.aqmd.gov](https://www.aqmd.gov) and checks the rule book index for all current rules across all 26 regulations.

2. **Downloads updated rule PDFs.** Any rules that are new or have been amended since your last update are automatically downloaded and saved to your computer (`C:\Users\[your name]\AppData\Roaming\AQMDRuleFinder\pdfs\`). On first launch this takes 5–15 minutes for all ~300 rules; after that, only changed rules are re-downloaded, which is usually under a minute.

3. **Extracts and indexes the text.** The text of every page of every PDF is extracted and stored in a local search database (`rules.db` in the same AppData folder). This is what makes instant search possible — you are searching your local copy, not the internet.

4. **Serves a local search interface.** The tool runs a small web server on your computer and opens it in your browser automatically. Everything stays on your machine — no data is sent anywhere except to download rule PDFs from aqmd.gov.

When you search, the tool finds every rule that contains your search terms, ranks them by how many times and how closely the terms appear, and shows you the exact passages where the match occurs with the matching words highlighted.

---

## Getting Started

1. Open the `AQMD Rule Finder` folder
2. Double-click **`AQMD Rule Finder.exe`**
3. A small Command Prompt window will open — **keep it open** while using the tool
4. After a few seconds, your default browser will open automatically showing the search interface

> If the browser does not open automatically, go to **http://127.0.0.1:5731** in any browser.

---

## First Launch

The first time you run the tool, it needs to download and index all AQMD rule PDFs. This is a one-time process that typically takes **5–15 minutes**.

You will see a progress bar:

```
📥 Downloading Rule 1103: Pharmaceuticals and Cosmetics Manufacturing...
    [████████████░░░░░░░░] 142 of 320 rules processed
```

You can start searching immediately — rules already indexed will appear in results while the rest are still downloading.

---

## How to Search

Type what you are looking for in the search box and press **Enter** or click **Search**.

### What to search for

**By facility or operation type:**
- `auto body shop`
- `dry cleaning`
- `pharmaceutical manufacturing`
- `metal plating`
- `bakery`
- `printing`
- `chrome plating`
- `petroleum refinery`
- `gasoline dispensing`

**By equipment:**
- `boiler`
- `spray booth`
- `flare`
- `cooling tower`
- `emergency generator`
- `storage tank`
- `oven`
- `incinerator`

**By chemical or pollutant:**
- `VOC` (Volatile Organic Compounds)
- `NOx`
- `PM10` or `PM2.5`
- `perchloroethylene`
- `hexavalent chromium`
- `ammonia`
- `sulfur dioxide`
- `hydrogen sulfide`

**By topic or activity:**
- `fugitive dust`
- `visible emissions`
- `spray coating`
- `solvent cleaning`
- `surface coating`
- `combustion`

### Quick-search chips

Below the search box, click any chip to run a preset search instantly:

> **auto body shop** &nbsp; **boiler** &nbsp; **pharmaceutical** &nbsp; **spray coating** &nbsp; **petroleum refinery** &nbsp; **dry cleaning** &nbsp; **solvent** &nbsp; **food processing**

### Search tips

- **Use multiple words** for more specific results: `spray booth paint` finds rules about spray booths used for painting
- **Try variations** if you get no results: if `auto body` returns nothing, try `automotive refinishing` or `surface coating`
- **Single words** cast a wider net: `solvent` matches any rule that mentions solvents
- **Chemical names** work well: `perchloroethylene` or `PERC` for dry-cleaning solvent rules
- The search is **not case-sensitive**: `VOC` and `voc` return the same results

---

## Understanding Results

Each matching rule appears as a card:

```
┌─────────────────────────────────────────────────────────────┐
│ [Rule 1103]  Pharmaceuticals and Cosmetics Manufacturing     │
│              Regulation XI — Source Specific Standards       │  [View Rule]
│              Last amended: January 6, 2023                   │
│─────────────────────────────────────────────────────────────│
│ PAGE 2                                                        │
│ "...operations subject to this rule include pharmaceutical    │
│  manufacturing, cosmetics manufacturing, and the processing  │
│  of vitamin supplements..."                                  │
│                                                              │
│ PAGE 5                                                        │
│ "...any pharmaceutical product manufactured in quantities    │
│  exceeding 50 pounds per day shall comply with..."           │
└─────────────────────────────────────────────────────────────┘
```

- **Rule badge** — the rule number
- **Title** — the official rule name
- **Regulation** — which regulation group it belongs to
- **Last amended** — the most recent amendment date
- **Page excerpts** — passages where your search terms appear, with matching words highlighted in yellow

### Opening a rule PDF

**Click any excerpt** to open the rule PDF directly at the matching page.

**Click "View Rule"** to open the PDF from the beginning.

The PDF opens in a panel on the right. Click **"Open in New Tab"** (top-right of the panel) for a full-screen view or to print.

Press **Escape** or click the dark background to close the PDF panel.

### Sorting results

Use the dropdown to sort by:
- **Relevance** — best matches first (default)
- **Regulation** — sorted by regulation number
- **Rule Number** — sorted numerically

---

## Keeping Rules Up to Date

### Automatic updates

Each time you open the tool, it automatically checks aqmd.gov for new or amended rules and downloads any changes in the background. The status badge in the header shows progress:

| Color | Meaning |
|-------|---------|
| Yellow, pulsing | Starting up or scanning AQMD website |
| Blue, pulsing | Downloading and indexing updated rules |
| Green | Ready — all rules indexed |
| Red | Error — check internet connection |

### Manual update check

Click **"↺ Check for Updates"** at any time to trigger an immediate check — useful if you know AQMD just published an amendment.

---

## Stopping the Tool

Close the browser tab, then close the Command Prompt window (or press **Ctrl+C** in it). All data is saved automatically.

---

## Frequently Asked Questions

**Q: Does this tool need an internet connection?**

A: Yes, to check for updated rules on startup. The rules themselves are stored locally, so you can still search if your connection is slow — the tool just will not download updates until connectivity is restored.

**Q: Where are the rule PDFs stored?**

A: On your computer at:
`C:\Users\[your name]\AppData\Roaming\AQMDRuleFinder\pdfs\`

The search index is at:
`C:\Users\[your name]\AppData\Roaming\AQMDRuleFinder\rules.db`

**Q: The browser did not open automatically.**

A: Open any browser and go to **http://127.0.0.1:5731**

**Q: Windows Defender showed a warning when I ran the .exe.**

A: This is common with independently-built executables. Click **"More info"** then **"Run anyway"** to proceed. The tool only connects to aqmd.gov and your local machine.

**Q: The PDF viewer shows the wrong page.**

A: Most browsers support jumping directly to the matching page, but some do not. If it opens at the wrong page, use **Ctrl+F** in the PDF viewer and search for the highlighted words shown in the excerpt.

**Q: My search found no results.**

A: Either no AQMD rule covers that topic in those words, or the rules are still being indexed (check that the status badge is green). Try synonyms — if `paint` returns nothing, try `coating` or `surface preparation`.

**Q: Is this an official AQMD product?**

A: No. This is an independent tool that searches publicly available documents from the AQMD website. Always verify regulatory requirements directly with AQMD or a qualified environmental consultant. This tool is for research and reference only.

---

## Troubleshooting

**Tool won't start / nothing happens after double-clicking:**
Make sure the `_internal` folder is in the same folder as the .exe — both must be present.

**"Error" status badge:**
Check your internet connection. Click "↺ Check for Updates" to retry.

**Port conflict ("Address already in use"):**
Another application is using port 5731. Open a Command Prompt in the tool's folder and run:
```
set AQMD_PORT=5732
"AQMD Rule Finder.exe"
```
Then go to **http://127.0.0.1:5732** in your browser.
