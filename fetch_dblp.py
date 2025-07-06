import requests
import xml.etree.ElementTree as ET
import yaml

# Reemplaza este PID con el tuyo de DBLP (puedes buscarlo en dblp.org)
DBLP_XML_URL = "https://dblp.org/pid/09/5889.xml"

def fetch_dblp_to_yaml(output_file="publications.yml"):
    response = requests.get(DBLP_XML_URL)
    root = ET.fromstring(response.content)

    entries = []
    for publ in root.findall("r"):
        info = publ.find("./*")
        if info is None:
            continue

        title = info.findtext("title", default="")
        year = info.findtext("year", default="")
        venue = info.findtext("booktitle", default="") or info.findtext("journal", default="")
        key = info.attrib.get("key", "")
        link = f"https://dblp.org/rec/{key}" if key else ""

        entries.append({
            "title": title.strip(),
            "year": year.strip(),
            "venue": venue.strip(),
            "link": link
        })

    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump(entries, f, allow_unicode=True)

    print(f"Saved {len(entries)} publications to {output_file}")

if __name__ == "__main__":
    fetch_dblp_to_yaml()

