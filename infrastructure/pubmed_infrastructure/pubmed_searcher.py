import requests
import xml.etree.ElementTree as ET


class PubMedSearcher:
    SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    FETCH_URL  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

    def __init__(self, email: str = None):
        self.email = email

    def search(self, drug: str, condition: str):
        """Returns total RCT count and conclusions of top 5 studies"""
        query = (
            f'("{drug}"[TIAB]) AND ("{condition}"[TIAB]) '
            f'AND (Randomized Controlled Trial[Filter])'
        )
        params = {"db": "pubmed", "term": query, "retmax": 5, "retmode": "xml"}
        if self.email:
            params["email"] = self.email

        try:
            search_res  = requests.get(self.SEARCH_URL, params=params)
            search_root = ET.fromstring(search_res.content)
            count       = int(search_root.find(".//Count").text)
            id_list     = [n.text for n in search_root.findall(".//IdList/Id")]
            conclusions = self.fetch_conclusions(id_list) if id_list else []
            return count, conclusions
        except Exception:
            return 0, []

    def fetch_conclusions(self, id_list: list) -> list:
        """Fetches abstracts and attempts to extract the conclusion section"""
        params = {
            "db": "pubmed",
            "id": ",".join(id_list),
            "retmode": "xml",
            "rettype": "abstract",
        }
        try:
            fetch_res  = requests.get(self.FETCH_URL, params=params)
            fetch_root = ET.fromstring(fetch_res.content)

            results = []
            for article in fetch_root.findall(".//PubmedArticle"):
                title           = article.find(".//ArticleTitle").text
                abstract_parts  = article.findall(".//AbstractText")
                conclusion_text = ""

                for part in abstract_parts:
                    label = part.get("Label", "").upper()
                    if label in ["CONCLUSION", "CONCLUSIONS"]:
                        conclusion_text = part.text
                        break

                if not conclusion_text and abstract_parts:
                    conclusion_text = abstract_parts[-1].text

                if conclusion_text:
                    results.append({"title": title, "conclusion": conclusion_text})

            return results
        except Exception:
            return []