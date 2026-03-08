import os

try:
    from google import genai
    from google.genai import types  # Updated to match the second file's import style
    _GEMINI_AVAILABLE = True
except ImportError:
    _GEMINI_AVAILABLE = False


class GeminiExplainer:
    """
    Infrastructure-layer service: wraps the Gemini API (google-genai package)
    to produce clinical explanations of contraindications.
    """

    # Updated to match the second file's experimental flash model or standard flash
    _MODEL = "gemini-2.0-flash" 

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY", "")
        self._client = None
        # Consistent initialization pattern
        if _GEMINI_AVAILABLE and api_key:
            self._client = genai.Client(api_key=api_key)

    def explain(
        self,
        drug: str,
        risk_concept: str,
        diagnosis: str,
        fda_context: str,
        patient_context: str = "",
    ) -> str:
        """
        Returns a 2-3 sentence clinical explanation using the google-genai SDK.
        """
        if not self._client or not fda_context:
            return self._fallback(drug, risk_concept)

        patient_section = f"\n\nPATIENT CONTEXT:\n{patient_context}" if patient_context else ""
        risk_label = risk_concept.replace("_", " ").title()

        prompt = f"""You are a clinical pharmacist explaining FDA contraindications.

Drug: {drug}
Condition being treated: {diagnosis}
Contraindication detected: {risk_label}

FDA Label Context:
{fda_context[:500]}
{patient_section}

Task: Explain in 2-3 sentences why {drug} is contraindicated for this patient, \
focusing on the {risk_concept.replace("_", " ").lower()} concern. \
Use clear clinical language."""

        try:
            # Using the types.GenerateContentConfig pattern from the second file
            config = types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=200,
            )
            
            # Using the client.models.generate_content pattern
            response = self._client.models.generate_content(
                model=self._MODEL,
                contents=prompt,
                config=config,
            )
            return response.text.strip()
            
        except Exception as exc:
            print(f"  [GeminiExplainer] API error: {type(exc).__name__} - {exc}")
            return self._fallback(drug, risk_concept)

    @staticmethod
    def _fallback(drug: str, risk_concept: str) -> str:
        risk_label = risk_concept.replace("_", " ").lower()
        return (
            f"Based on FDA label documentation, {drug} is contraindicated "
            f"in patients with {risk_label}."
        )