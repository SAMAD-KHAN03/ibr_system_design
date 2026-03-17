import os

try:
    import anthropic
    _CLAUDE_AVAILABLE = True
except ImportError:
    _CLAUDE_AVAILABLE = False


class ClaudeExplainer:
    """
    Infrastructure-layer service: wraps the Anthropic API (anthropic package)
    to produce clinical explanations of contraindications.
    """

    # Using the latest 2026 Sonnet model
    _MODEL = "claude-sonnet-4-6" 

    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self._client = None
        
        if _CLAUDE_AVAILABLE and api_key:
            self._client = anthropic.Anthropic(api_key=api_key)

    def explain(
        self,
        drug: str,
        risk_concept: str,
        diagnosis: str,
        fda_context: str,
        patient_context: str = "",
    ) -> str:
        """
        Returns a 2-3 sentence clinical explanation using the Anthropic SDK.
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
            # Anthropic uses the messages.create pattern
            response = self._client.messages.create(
                model=self._MODEL,
                max_tokens=200,
                temperature=0.0,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            # Content is returned as a list of content blocks
            return response.content[0].text.strip()
            
        except Exception as exc:
            print(f"  [ClaudeExplainer] API error: {type(exc).__name__} - {exc}")
            return self._fallback(drug, risk_concept)

    @staticmethod
    def _fallback(drug: str, risk_concept: str) -> str:
        risk_label = risk_concept.replace("_", " ").lower()
        return (
            f"Based on FDA label documentation, {drug} is contraindicated "
            f"in patients with {risk_label}."
        )