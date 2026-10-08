# Last Z State 798 Atlas

The **All HQs** tab is the default list. It searches across all previous SvS
cohorts and includes current map records plus verified roster members with
older or unknown locations. Historical-only records stay available through
their stable deep links. Selecting an HQ in All HQs keeps the combined list.

## Farm name filter

In **All HQs**, choose **Farm names** to list players whose alliance name/tag,
player name, or either contains `farm` (case insensitive). Matching map pins
follow the list. The alliance dropdown shows saved full names where available;
select an alliance to see its members. Searching also recognizes full alliance
names, including in Alliance participation. Names come from the saved alliance
leaderboard; an alliance with no full name recorded can only match its tag.
Existing zone and HQ filters still apply. Older locations and unknown locations
retain their existing labels.

## Google Sheets mirror

`sync_google_sheet.py` mirrors all saved HQ records by stable Atlas ID into the
managed **HQ Data** tab. Historical records are explicitly labeled; map/HQ,
roster, power and shield dates remain separate. No observation is fabricated.
The Atlas files remain the source of truth. Use other tabs for manual notes;
HQ Data is replaced on each sync. **Farm Matches** is also managed and refreshed
on every sync: it contains the same case-insensitive alliance-or-player matches
as All HQs in the Atlas, with full alliance names and a match reason. Historical-only
records and non-HQ objects are excluded. Both tabs are read back to verify every
value after writing. All other tabs are untouched.

One-time setup after creating/importing a Google Sheet:

1. Install `requirements-sheets.txt` in the Python environment running the
   update scripts: `python -m pip install -r requirements-sheets.txt`.
2. Copy `google-sheets.example.json` to `.google-sheets.json` and set the Sheet
   ID from its URL (the part after `/d/`). This local file is ignored by Git.
   Alternatively set `LASTZ_SPREADSHEET_ID` or `LASTZ_SHEETS_CONFIG`.
   To reuse existing Hermes Google authorization, set `oauth_token_file` to
   its `google_token.json` path and `python` to the Hermes Python interpreter
   containing Google libraries. No credentials are copied into the repository;
   the refresh token is loaded directly from its existing external location.
3. Enable the Google Sheets API in your Google Cloud project. Configure Google
   Application Default Credentials with Sheets write scope. For unattended
   scripts, set `GOOGLE_APPLICATION_CREDENTIALS` to a service-account JSON key
   **outside this repository**, then share the Sheet with that account as editor.
4. Run `python sync_google_sheet.py` for the first sync. It reads back the IDs
   to verify row count and ordering. Repeating it replaces the same rows.

The existing local `publish_verified_atlas.py`, `publish_progress_atlas.py`,
`complete_roster_power.py`, `leaderboard_import.py`, `api_import.py` and
`import_shields.py` invoke this sync after their data writes. Without Sheet
configuration they report that sync is not configured. A configured failure
stops the caller with an error while retaining the updated local Atlas files;
retry `python sync_google_sheet.py` and the normal publication afterward.
Staging/reconciliation scripts do not sync unreviewed intermediate data.

For an offline export: `python sync_google_sheet.py --export hqs.csv`.
The exporter needs no Google packages or credentials.

API behavior: [Google Sheets batch updates](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets/batchUpdate).

Static GitHub Pages atlas built from a complete 5,100-capture map sweep. Pan and zoom the stitched map, search current HQ candidates, and open an original in-game screenshot crop for each located HQ. Filter by alliance, previous SvS shield/terrain, and HQ level. The page shows separate map and event dates.

The October 1 refresh updates map locations, names, alliance tags, HQ levels, and leaderboards. `data/participation.json` freezes the previous SvS's IDs, tags, locations, and attendance proxy; `data/shields.json` remains unchanged until the next SvS. List cohorts refer to that previous event. New identities have unknown attendance. Old records not located by the new scan remain available at their stable deep links, with an explicit old-location date; this does not confirm that they quit.

For blocked names or HQ badges, reviewed leaderboard readings take precedence over the player's last successful reading, followed by a location recheck. Older HQ readings retain their original date. A fresh leaderboard can confirm roster membership without confirming a map location: such records keep a dated older location or an unknown location, and do not create map pins. Identities are matched by unique names/tags or documented visual review; ambiguous matches remain review candidates.

The **Alliance participation** view uses the frozen previous SvS snapshot inside the 100-tile capital radius. It shows each alliance's historical inside count, total tagged HQs, and inside percentage. Sort by count, percentage, or tag; set minimum counts and percentages; or search for a tag. Selecting an alliance opens the current records belonging to that historical cohort. These percentages describe screenshot locations, not verified combat activity. Current alliance changes do not rewrite the event totals.

The **HQs around a point** tool accepts X/Y coordinates and a radius in game tiles, or lets you pick a point on the map. Selecting an HQ also centers the analysis on it. It counts all recorded HQ candidates within or on the circle, across both atlas zones, excluding four records marked “Not an HQ.” “Total HQ levels” is the sum of readable HQ levels inside the circle; the tool separately reports unreadable levels. The NAP 13 switch excludes the 13 alliances in the supplied September 2026 power ranking that have capital HQ records: Helm, SWT, WRtH, mERC, aTam, 4NG, UpS, Ayaa, E45Y, 7cie, SHSN, movR, and ULD. Known OCR variants HeIm, 7cle, and 7cIe are treated as Helm or 7cie for this switch only. The list is a snapshot and is not recalculated from future power rankings.

The published assets use compressed map tiles and per-HQ crops. The 5,100 full-resolution PNG captures and OCR cache remain in the user's local archive and are too large for GitHub Pages. [GitHub Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits) cap a published site at 1 GB.

City names, alliance tags, coordinates, and HQ levels are estimates from OCR and screenshot review. Small, covered, or conflicting readings remain flagged. The current map uses a projection measured from repeated captions and checked against the capital origin. The historical participation circle is centered at (500,500), with radius 100 tiles. A pre-SvS map refresh must not be passed to the shield scanner as though it were an event snapshot.

The website is plain HTML/CSS/JavaScript. `build_assets.py`, `add_capital_assets.py`, `augment_missing_capital.py`, and `augment_missing_outside.py` record how its map tiles and photos were produced from the local capture archive.

`data/shields.json` contains the September 26 shield scan for 664 map records near the capital terrain edge, plus 163 HQs well inside the mud hexagon. The review of 117 uncertain records used overlapping captures and a target-centered blue rim check. Among the 664 edge records, 471 show a shield, 63 appear unshielded, 125 are on mud, four are map objects or troop/overlapping labels rather than HQs, and one remains unresolved because its visible nameplate is clipped and another capture does not align with its estimated coordinate. These are screenshot-time classifications, not a verified count of every player or their status throughout the SvS event. HQs outside the capital, where the shield scan was not run, show `Not scanned`.

To refresh the static data after a future sweep, run the archived `svs_shield_scan.py` against the saved captures. It compares overlapping screenshots and uses a bilateral blue rim check to reduce confusion from neighboring shields. Optional `--reviewed-csv` applies a documented visual audit to known ambiguous cases. Then run `python import_shields.py --csv path/to/svs_shield_status.csv` with a scan made from this atlas's HQ IDs and coordinates. A new event needs a fresh audit because HQ locations and shields can change.
