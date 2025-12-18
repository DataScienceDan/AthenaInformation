import io
import re
import zipfile
from urllib.parse import urljoin
import pandas as pd
import requests
import os


PROVIDER_DATASET_ID = "4pq5-n9py"
CITATION_DATASET_ID = "tagd-9999"
HEALTH_DEFICIENCIES_DATASET_ID = "r5ix-sfxw"
SURVEY_SUMMARY_DATASET_ID = "tbry-pc2d"

def _dataset_csv_url(dataset_id: str) -> str:
    return f"https://data.cms.gov/provider-data/api/1/datastore/query/{dataset_id}/0/download?format=csv"

def _load_csv_to_dataframe(csv_url: str) -> pd.DataFrame:
    headers = {
        "User-Agent": "Athena-ProviderInfo/1.0",
        "Accept": "text/csv",
    }
    resp = requests.get(csv_url, headers=headers, timeout=120)
    resp.raise_for_status()
    return pd.read_csv(io.BytesIO(resp.content))


def load_provider_info_dataframe() -> pd.DataFrame:
    return _load_csv_to_dataframe(_dataset_csv_url(PROVIDER_DATASET_ID))

def load_citation_lookup_dataframe() -> pd.DataFrame:
    return _load_csv_to_dataframe(_dataset_csv_url(CITATION_DATASET_ID))


ARCHIVE_PAGE_URL = "https://data.cms.gov/provider-data/archived-data/nursing-homes"


def _fetch_html(url: str) -> str:
    headers = {
        "User-Agent": "Athena-ProviderInfo/1.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    resp = requests.get(url, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.text


def _find_zip_links(html: str, base_url: str) -> list[str]:
    # Find all .zip hrefs in the page
    hrefs = re.findall(r'href=["\']([^"\']+\.zip)["\']', html, flags=re.IGNORECASE)
    # Deduplicate and absolutize
    seen: set[str] = set()
    links: list[str] = []
    for href in hrefs:
        abs_url = urljoin(base_url, href)
        if abs_url not in seen:
            seen.add(abs_url)
            links.append(abs_url)
    return links

def _find_all_links(html: str, base_url: str) -> list[str]:
    # Fallback: collect all hrefs if .zip links are not explicitly present
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.IGNORECASE)
    seen: set[str] = set()
    links: list[str] = []
    for href in hrefs:
        abs_url = urljoin(base_url, href)
        if abs_url not in seen:
            seen.add(abs_url)
            links.append(abs_url)
    return links

def _find_link_by_label(html: str, base_url: str, label_text: str) -> str | None:
    # Find an <a> tag whose inner text contains label_text (case-insensitive)
    anchors = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, flags=re.IGNORECASE | re.DOTALL)
    target_lower = label_text.lower()
    for href, inner in anchors:
        # Strip tags from inner text
        inner_text = re.sub(r"<[^>]*>", " ", inner)
        if target_lower in inner_text.lower():
            return urljoin(base_url, href)
    return None


def load_archived_survey_dates_combined_dataframe() -> pd.DataFrame:
    """Retrieve NH_SurveyDates_Jul2025.csv via the 2025 bulk archive link.

    Steps per instructions:
    - On the archive page, find the link labeled "Download all 2025 archived data snapshots".
    - Download the bulk ZIP named "nursing_homes_including_rehab_services_2025".
    - Inside, open "nursing_homes_including_rehab_services_07_2025.zip".
    - Extract "NH_SurveyDates_Jul2025.csv" and return it as a DataFrame.
    """
    # Get the archive page HTML
    html = _fetch_html(ARCHIVE_PAGE_URL)

    # Find the labeled 2025 bulk link
    label = "Download all 2025 archived data snapshots"
    bulk_href = _find_link_by_label(html, ARCHIVE_PAGE_URL, label)
    if bulk_href is None:
        # Fallback: search for a .zip link containing the bulk marker
        bulk_marker = "nursing_homes_including_rehab_services_2025"
        zip_links = _find_zip_links(html, ARCHIVE_PAGE_URL)
        bulk_href = next((l for l in zip_links if bulk_marker in l.lower()), None)
    if bulk_href is None:
        # Fallback: scan all links for the bulk marker
        all_links = _find_all_links(html, ARCHIVE_PAGE_URL)
        bulk_href = next((l for l in all_links if "nursing_homes_including_rehab_services_2025" in l.lower()), None)
    if bulk_href is None:
        raise RuntimeError("Could not locate the 2025 bulk archive link by label or URL pattern.")

    # Attempt to download the bulk ZIP; if content isn't ZIP, try to scrape a subpage
    resp = requests.get(bulk_href, headers={"User-Agent": "Athena-ProviderInfo/1.0"}, timeout=300, allow_redirects=True)
    resp.raise_for_status()

    content_type = resp.headers.get("Content-Type", "").lower()
    bulk_zip_bytes: bytes | None = None

    if "zip" in content_type:
        bulk_zip_bytes = resp.content
    else:
        # Treat as HTML intermediate page; find the bulk ZIP link there
        try:
            inter_html = resp.text
            inter_zip_links = _find_zip_links(inter_html, resp.url)
            bulk_zip = next((l for l in inter_zip_links if "nursing_homes_including_rehab_services_2025" in l.lower()), None)
            if bulk_zip is None:
                raise RuntimeError("Bulk ZIP link not found on the intermediate page for 2025.")
            zresp = requests.get(bulk_zip, headers={"User-Agent": "Athena-ProviderInfo/1.0", "Accept": "application/zip"}, timeout=300)
            zresp.raise_for_status()
            bulk_zip_bytes = zresp.content
        except Exception as e:
            raise RuntimeError("Failed to resolve the 2025 bulk ZIP from the labeled link.") from e

    # Open the outer (bulk) ZIP
    try:
        with zipfile.ZipFile(io.BytesIO(bulk_zip_bytes)) as outer_zf:
            # Locate the July 2025 inner ZIP
            expected_inner = "nursing_homes_including_rehab_services_07_2025.zip"
            inner_member = None
            for name in outer_zf.namelist():
                base = os.path.basename(name).lower()
                if base == expected_inner.lower():
                    inner_member = name
                    break
            if inner_member is None:
                # Regex fallback for minor separator differences
                pattern_inner = re.compile(r"^nursing_homes_including_rehab_services[_-]07[_-]2025\.zip$", re.IGNORECASE)
                for name in outer_zf.namelist():
                    base = os.path.basename(name)
                    if pattern_inner.match(base):
                        inner_member = name
                        break
            if inner_member is None:
                raise RuntimeError("Could not find 'nursing_homes_including_rehab_services_07_2025.zip' inside the 2025 bulk ZIP.")

            # Read the inner ZIP bytes
            inner_bytes = outer_zf.read(inner_member)
            with zipfile.ZipFile(io.BytesIO(inner_bytes)) as inner_zf:
                # Find NH_SurveyDates_Jul2025.csv
                expected_csv = "NH_SurveyDates_Jul2025.csv"
                csv_member = None
                for name in inner_zf.namelist():
                    base = os.path.basename(name)
                    if base.lower() == expected_csv.lower():
                        csv_member = name
                        break
                if csv_member is None:
                    # Regex fallback allowing separators
                    pattern_csv = re.compile(r"^nh[_-]?surveydates[_-]?jul[_-]?2025\.csv$", re.IGNORECASE)
                    for name in inner_zf.namelist():
                        base = os.path.basename(name)
                        if pattern_csv.match(base):
                            csv_member = name
                            break
                if csv_member is None:
                    raise RuntimeError("Could not find 'NH_SurveyDates_Jul2025.csv' inside the July 2025 ZIP.")

                with inner_zf.open(csv_member) as f:
                    df = pd.read_csv(f)
                    return df
    except zipfile.BadZipFile as e:
        raise RuntimeError("Downloaded 2025 bulk archive was not a valid ZIP file.") from e


def _write_df_to_csv(df: pd.DataFrame, filename: str) -> str:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(base_dir, filename)
    df.to_csv(out_path, index=False)
    return out_path


if __name__ == "__main__":
    provider_df = load_provider_info_dataframe()
    print(f"Provider Info: {len(provider_df):,} rows and {len(provider_df.columns)} columns")
    print(provider_df.head())
    print(f"Saved: {_write_df_to_csv(provider_df, 'provider_info.csv')}")

    citation_df = load_citation_lookup_dataframe()
    print(f"Citation Lookup: {len(citation_df):,} rows and {len(citation_df.columns)} columns")
    print(citation_df.head())
    print(f"Saved: {_write_df_to_csv(citation_df, 'citation_lookup.csv')}")

    health_def_df = _load_csv_to_dataframe(_dataset_csv_url(HEALTH_DEFICIENCIES_DATASET_ID))
    print(f"Health Deficiencies: {len(health_def_df):,} rows and {len(health_def_df.columns)} columns")
    print(health_def_df.head())
    out_path = os.path.join(os.getcwd(), 'health_deficiencies.xlsx')
    try:
        health_def_df.to_excel(out_path, index=False)
        print(f"Saved: {out_path}")
    except Exception as e:
        print(f"Failed saving health_deficiencies.xlsx: {e}")

    archive_df = load_archived_survey_dates_combined_dataframe()
    print(f"Archived Survey Dates combined: {len(archive_df):,} rows and {len(archive_df.columns)} columns")
    print(archive_df.head())
    print(f"Saved: {_write_df_to_csv(archive_df, 'archived_survey_dates.csv')}")

    survey_summary_df = _load_csv_to_dataframe(_dataset_csv_url(SURVEY_SUMMARY_DATASET_ID))
    survey_summary_df = survey_summary_df.drop_duplicates().reset_index(drop=True)
    print(f"Survey Summary: {len(survey_summary_df):,} rows and {len(survey_summary_df.columns)} columns")
    print(survey_summary_df.head())
    print(f"Saved: {_write_df_to_csv(survey_summary_df, 'survey_summary.csv')}")

