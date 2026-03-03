# AQMD Rule Finder — User Guide

**South Coast Air Quality Management District Rule Search Tool**

---

## What This Tool Does

The AQMD Rule Finder lets you search the full text of all South Coast AQMD rules to find every regulation that applies to your facility, operation, or equipment. Instead of reading through hundreds of PDFs manually, type a few words and the tool instantly shows you which rules mention that topic — along with the exact passages where they appear.

Every time the tool opens, it checks the AQMD website for updated rules and downloads any that have changed, so you always have the current version.

---

## Getting Started

### Step 1 — Install Python (first time only)

The tool requires Python 3.9 or later.

#### Option A — Fresh install (Python not yet on your machine)

1. Go to **https://www.python.org/downloads/**
2. Download the latest Python 3 installer for Windows
3. Run the installer — **important:** check the box that says **"Add Python to PATH"** before clicking Install
4. Click "Install Now" and let it finish

#### Option B — Python is already installed but not on PATH

If you (or your IT department) have already installed Python, `setup.bat` may still fail with "Python is not installed or not on PATH" because Windows doesn't know where to find it. Follow these steps to fix that.

**1. Find where Python is installed**

Open a Command Prompt (press `Windows + R`, type `cmd`, press Enter) and run:

```
where python
```

If that returns nothing, try these common locations manually in File Explorer:

| Location | Who installed it |
|----------|-----------------|
| `C:\Python312\python.exe` | Standard python.org installer |
| `C:\Users\[YourName]\AppData\Local\Programs\Python\Python312\python.exe` | python.org installer (user-only) |
| `C:\Users\[YourName]\AppData\Local\miniconda3\python.exe` | Anaconda / Miniconda |
| `C:\ProgramData\anaconda3\python.exe` | Anaconda (all users) |
| `C:\Program Files\Python312\python.exe` | System-wide python.org install |

Replace `312` with your version number (e.g., `311` for Python 3.11). If you find `python.exe`, note the folder it is in — you will need it in the next step.

**2. Add Python to your PATH (permanent fix)**

1. Press `Windows + S` and search for **"Edit the system environment variables"**, then click it
2. Click **"Environment Variables…"** at the bottom of the window
3. Under **"User variables for [your name]"**, find the variable named **Path** and double-click it
4. Click **"New"** and paste the folder path where you found `python.exe`
   - Example: `C:\Users\YourName\AppData\Local\Programs\Python\Python312`
5. Click **"New"** again and add the `Scripts` subfolder in the same location
   - Example: `C:\Users\YourName\AppData\Local\Programs\Python\Python312\Scripts`
6. Click **OK** on all open windows to save
7. **Close and reopen** any Command Prompt windows — old ones won't see the change

**3. Verify it worked**

Open a new Command Prompt and type:

```
python --version
```

You should see something like `Python 3.12.0`. Then re-run `setup.bat`.

**Alternative: run setup without changing PATH**

If you would rather not change system settings, you can run setup by typing the full path to Python directly. Open a Command Prompt in the `aqmd-rule-finder` folder and run:

```
"C:\Users\YourName\AppData\Local\Programs\Python\Python312\python.exe" -m pip install -r requirements.txt
```

Then to start the tool:

```
"C:\Users\YourName\AppData\Local\Programs\Python\Python312\python.exe" app.py
```

Replace the path with wherever your `python.exe` actually lives.

### Step 2 — Install the tool's dependencies (first time only)

1. Open the `aqmd-rule-finder` folder
2. Double-click **`setup.bat`**
3. A Command Prompt window will open. It will:
   - First look for Python on PATH
   - Then automatically check common install locations (Anaconda, Miniconda, python.org defaults)
   - If Python still isn't found, **it will ask you to type the path to your `python.exe`**:
     ```
     Path to python.exe: C:\Users\YourName\AppData\Local\Programs\Python\Python312\python.exe
     ```
     Paste the full path and press Enter.
4. Once Python is located, it downloads the required libraries (Flask, PyMuPDF, etc.)
5. When it says "Setup complete!", close the window

The path you provide is saved automatically so that `run.bat` will use it on every future launch without asking again.

### Step 3 — Run the tool

Double-click **`run.bat`**

A Command Prompt window will open — **keep this window open** while using the tool. After about 2 seconds, your default web browser will open automatically showing the AQMD Rule Finder.

---

## First Launch

The first time you run the tool (or after a long period without use), it needs to download and index all AQMD rule PDFs. This is a one-time process.

You will see a progress bar showing the download status:

```
📥 Downloading Rule 1103: Pharmaceuticals and Cosmetics Manufacturing...
    [████████████░░░░░░░░] 142 of 320 rules processed
```

This process typically takes **5–15 minutes** depending on your internet connection speed. The tool will automatically check for and download any new or updated rules each time you open it after that. Subsequent launches are nearly instant.

You can start searching immediately — any rules already indexed will appear in results while the rest are still downloading.

---

## How to Search

### Basic search

Type what you're looking for in the search box and press **Enter** or click **Search**.

The tool searches the full text of every rule, so you can be specific or general.

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

Below the search box, there are example chips you can click to run a preset search immediately:

> **auto body shop** &nbsp; **boiler** &nbsp; **pharmaceutical** &nbsp; **spray coating** &nbsp; **petroleum refinery** &nbsp; **dry cleaning** &nbsp; **solvent** &nbsp; **food processing**

### Search tips

- **Use multiple words** for more specific results: `spray booth paint` finds rules about spray booths used for painting specifically
- **Try variations** if you don't find what you need: if `auto body` returns nothing, try `automotive refinishing` or `surface coating`
- **Single words** cast a wider net: `solvent` will match any rule mentioning solvents
- **Chemical names** work well: `perchloroethylene` or `PERC` for dry-cleaning solvent rules
- **Equipment names** are reliable: `boiler`, `flare`, `clarifier`, `chiller`
- The search is **not case-sensitive**: `VOC` and `voc` return the same results

---

## Understanding Results

### Result card layout

Each rule that matches your search appears as a card:

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

**Rule badge** (blue box at top-left): The rule number.

**Title**: The official name of the rule.

**Regulation**: Which regulation group this rule belongs to (e.g., Regulation XI — Source Specific Standards). AQMD rules are grouped into numbered regulations that cover related topics.

**Last amended**: The most recent date the rule was changed.

**Page excerpts**: Each colored box shows a passage from the rule where your search terms appear. The matching words are highlighted in yellow. The page number tells you exactly where in the PDF to find that passage.

### Opening a rule PDF

**Click any excerpt box** to open that rule's PDF directly at the page containing the matching text.

**Click "View Rule"** to open the PDF from the beginning.

The PDF opens in a viewer panel on the right side of the screen. Use your browser's built-in PDF tools to zoom in, scroll, or print.

**"Open in New Tab"** (top-right of the PDF viewer): Opens the PDF in a full browser tab for easier reading or printing.

Press **Escape** or click the dark background to close the PDF viewer.

### Sorting results

By default, results are sorted by relevance (closest match first). Use the dropdown to change:

- **Relevance** — rules with the most and best matches appear first
- **Regulation** — sorted by regulation number (I, II, III... XI, XII...)
- **Rule Number** — sorted numerically by rule number (401, 402, 403...)

### Loading more results

If a search returns many matches, the first 20 are shown. Click **"Load more results"** at the bottom to see additional matches.

---

## Keeping Rules Up to Date

### Automatic updates (every launch)

Each time you open the tool, it automatically checks the AQMD website for:
- New rules added since your last update
- Existing rules with newer amendment dates

Any updates are downloaded and indexed in the background. You'll see the status badge in the header change from "Scanning…" → "Indexing X/Y" → "X rules ready" when complete.

### Manual update check

Click **"↺ Check for Updates"** in the top-right corner at any time to trigger an immediate update check. This is useful if you know AQMD just published a rule amendment.

### Status indicator

The colored dot in the header shows the current status:

| Color | Meaning |
|-------|---------|
| Yellow, pulsing | Starting up or scanning AQMD website |
| Blue, pulsing | Downloading and indexing rule PDFs |
| Green | Ready — all rules indexed |
| Red | Error — check internet connection |

When the status is green and shows "X rules ready", all rules are available for searching.

---

## Sharing the Tool

### Option 1 — Share the folder (requires Python)

The entire `aqmd-rule-finder` folder can be copied to another computer (USB drive, shared network drive, email as a .zip, etc.). The recipient needs to:

1. Install Python 3.9+ from python.org (check "Add to PATH")
2. Run `setup.bat` once to install dependencies
3. Run `run.bat` to start

### Option 2 — Build a standalone executable (no Python needed)

To create a version that anyone can run by double-clicking, without installing Python:

1. Run `setup.bat` first (if you haven't already)
2. Double-click **`build_exe.bat`**
3. Wait several minutes for the build to complete
4. Find the output in `dist\AQMD Rule Finder\`
5. Share that entire folder (zip it up and send it)

The recipient just double-clicks `AQMD Rule Finder.exe` — no Python, no setup.

---

## Frequently Asked Questions

**Q: Does this tool need an internet connection?**

A: Yes, to check for updated rules each time it opens. After downloading, the rules are stored locally, so you can search even if your connection is slow — the tool just won't download updates until connectivity is restored.

**Q: How long does the first download take?**

A: Typically 5–15 minutes for all ~300 rules. After that, updates only download rules that have changed, which usually takes under a minute.

**Q: Are the rules stored on my computer?**

A: Yes. PDFs are saved to:
`C:\Users\[your name]\AppData\Roaming\AQMDRuleFinder\pdfs\`

The search index is saved to:
`C:\Users\[your name]\AppData\Roaming\AQMDRuleFinder\rules.db`

**Q: How do I know the rules are current?**

A: The tool shows the last update time in the status bar ("Updated 2026-03-01 08:14:22"). Each time the tool opens, it compares amendment dates from the AQMD website against what's stored locally and re-downloads any that have changed.

**Q: What if a rule PDF fails to download?**

A: The tool will note the failure and continue with the rest. Failed rules are shown in the status message when indexing completes. You can retry by clicking "Check for Updates".

**Q: Can I search for a specific rule number?**

A: Yes — searching `1103` will find passages in Rule 1103. However, the search is full-text, so it looks for those characters in the rule content, not just the title. For browsing by rule number, the "Sort: Rule Number" option helps navigate results.

**Q: The PDF viewer shows the wrong page. Why?**

A: Most browsers support the `#page=N` URL fragment for PDF navigation, but a few don't. If the PDF opens at the wrong page, use **Ctrl+F** inside the PDF viewer and search for the highlighted words shown in the excerpt.

**Q: What does it mean if my search finds no results?**

A: Either no AQMD rule mentions that topic, or the specific wording isn't used. Try synonyms — for example, if `paint` returns nothing, try `coating` or `surface preparation`. Also check that the status badge shows green (rules fully indexed).

**Q: Is this tool an official AQMD product?**

A: No. This is an independent search tool that fetches publicly available documents from the AQMD website. Always verify regulatory requirements directly with AQMD or a qualified environmental consultant. This tool is for research and reference only.

---

## Stopping the Tool

Close the browser tab, then close the Command Prompt window (or press **Ctrl+C** in it). The tool saves all data automatically — nothing is lost by closing it.

---

## Troubleshooting

**The tool won't start / "Python is not installed" error:**
Run `setup.bat` first. If Python isn't found, install it from python.org and ensure "Add Python to PATH" is checked during installation.

**Browser doesn't open automatically:**
Open your browser manually and go to `http://127.0.0.1:5731`

**"Error" status badge:**
Check your internet connection. Click "↺ Check for Updates" to retry.

**Rules from a specific regulation are missing:**
Some regulations may have temporarily failed to download. Click "↺ Check for Updates" to retry. If the problem persists, the AQMD website structure for that regulation may have changed — contact the tool's maintainer.

**Search returns unexpected results:**
Remember the search matches the full text of PDFs, not just titles. A rule that mentions your facility type in an exemption or definition will still appear in results. Read the excerpt carefully to understand context.

**Port conflict ("Address already in use"):**
Another application is using port 5731. Set a different port by running: `set AQMD_PORT=5732` then `python app.py` from a Command Prompt in the tool's folder.
