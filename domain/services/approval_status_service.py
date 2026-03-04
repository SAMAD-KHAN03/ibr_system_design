from core.components_module import Component
from core.results.execution_result import ExecutionResult
from execution_context import ExecutionContext
import requests
import re
from domain.results.approval_result import ApprovalStatusResult
class ApprovalStatus(Component):
    def execute(self,context:ExecutionContext)->ExecutionResult:
        print("Executing Approval Status")
        start(context= context)



class USFDAChecker:
    """Check USFDA approval using OpenFDA API"""
    
    LABEL_URL = "https://api.fda.gov/drug/label.json"
    
    def __init__(self):
        self.session = requests.Session()
    
    def search_drug_label(self, drug_name: str) -> dict:
        """Search FDA drug labels"""
        try:
            params = {
                'search': f'openfda.brand_name:"{drug_name}" openfda.generic_name:"{drug_name}"',
                'limit': 10
            }
            response = self.session.get(self.LABEL_URL, params=params, timeout=15)
            response.raise_for_status()
            return response.json()
        except Exception:
            return {}
    
    def clean_text(self, text: str) -> str:
        """Clean HTML tags and whitespace"""
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def extract_indications(self, results: dict) -> list:
        """Extract indication texts from FDA labels"""
        if not results or 'results' not in results:
            return []
        
        indications = []
        for result in results['results']:
            # Focused fields for USFDA approval indications
            fields = ['indications_and_usage', 'purpose', 'use']
            for field in fields:
                if field in result:
                    text = result[field]
                    if isinstance(text, list):
                        for t in text:
                            cleaned = self.clean_text(t)
                            if cleaned: indications.append(cleaned)
                    else:
                        cleaned = self.clean_text(text)
                        if cleaned: indications.append(cleaned)
        return indications
    
    def fuzzy_match(self, condition: str, text: str) -> bool:
        """Check if condition is mentioned in the indication text"""
        cond = condition.lower()
        txt = text.lower()
        
        # Simple keyword matching
        if cond in txt:
            return True
        
        # Multi-word matching logic
        words = cond.split()
        if len(words) > 1:
            return all(word in txt for word in words)
        
        return False

    def check_approval(self, drug: str, condition: str) -> bool:
        """Wrapper to check USFDA status"""
        results = self.search_drug_label(drug)
        indications = self.extract_indications(results)
        return any(self.fuzzy_match(condition, ind) for ind in indications)


def start(context:ExecutionContext) -> dict:
    """
    Main entry point for USFDA regulatory approval checking.
    """
    
    checker = USFDAChecker()
    
    # Check USFDA Status
    usfda_approved = checker.check_approval(drug, condition)
    
    # Format the simple output message
    if usfda_approved:
        output_text = (f"{drug} is approved for use in {condition} as per the "
                       f"USFDA's USPI (United States Prescriber Information).")
    else:
        output_text = (f"{drug} is not found to be approved for use in {condition} "
                       f"as per the USFDA's USPI. Please consider alternative "
                       f"medications or review clinical evidence.")

    return {
        "drug": drug,
        "condition": condition,
        "usfda_approved": usfda_approved,
        "output": output_text
    }