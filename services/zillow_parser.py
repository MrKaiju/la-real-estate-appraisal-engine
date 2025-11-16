import re
import requests
from bs4 import BeautifulSoup

class ZillowParser:
    """
    Extracts structured property data from a Zillow link.
    """
    
    def __init__(self, url: str):
        self.url = url
        self.html = None
        self.soup = None
    
    def fetch_html(self):
        headers = {
            "User-Agent": 
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        r = requests.get(self.url, headers=headers)
        r.raise_for_status()
        self.html = r.text
        self.soup = BeautifulSoup(self.html, "html.parser")
    
    def extract_price(self):
        try:
            price_tag = self.soup.find("span", {"data-testid": "price"})
            return price_tag.text.strip().replace("$", "").replace(",", "")
        except:
            return None
    
    def extract_address(self):
        try:
            tag = self.soup.find("h1", {"data-testid": "detail-address"})
            return tag.text.strip()
        except:
            return None
    
    def extract_property_details(self):
        """
        Parses the key facts section to extract:
        - Beds
        - Baths
        - Square footage
        - Lot size
        """
        details = {"beds": None, "baths": None, "sqft": None, "lot_sqft": None}
        try:
            fact_items = self.soup.find_all("li", {"data-testid": "bed-bath-item"})
            for item in fact_items:
                txt = item.text.lower()
                if "bd" in txt:
                    details["beds"] = re.findall(r'\d+', txt)[0]
                if "ba" in txt:
                    details["baths"] = re.findall(r'\d+', txt)[0]
                if "sqft" in txt:
                    details["sqft"] = re.findall(r'\d+', txt.replace(",", ""))[0]
            return details
        except:
            return details
    
    def extract(self):
        self.fetch_html()
        return {
            "source": "zillow",
            "url": self.url,
            "price": self.extract_price(),
            "address": self.extract_address(),
            "details": self.extract_property_details()
        }
