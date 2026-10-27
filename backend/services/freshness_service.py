"""
Freshness & Temporal Relevance Service for Nexora AI.

Evaluates whether user inquiries require fresh, real-time external information
from the live web rather than relying on static model knowledge or local documents.

Key Evaluation Criteria:
  1. Explicit temporal markers ("today", "latest", "recent", "now", "current", "this week/month/year")
  2. Volatile subjects:
     - Geopolitical & military developments (border tensions, territorial disputes, incursions, conflicts)
     - Government, politics & elections (current officeholders, election results, recent legislation)
     - Economics & financial markets (stock prices, crypto, interest rates, inflation, earnings)
     - Software, AI & tech releases (new versions, API changes, model launches, changelogs)
     - Breaking news, events, disaster alerts, and sports results
  3. Dynamic factual queries ("Is [country/party] doing [action]?", "Has [event] occurred?", "Who is the current [role]?")
  4. LLM semantic freshness evaluation for ambiguous queries
"""
import re
from typing import Dict, List, Optional, Tuple

from backend.logger import logger

# 0. Historical markers (completed past events vs live breaking developments)
_HISTORICAL_MARKERS = re.compile(
    r"\b("
    r"(?:in|during|back in|around)\s+(?:the\s+)?(?:18\d\d|19\d\d|20[0-1]\d|202[0-3])|"
    r"(?:18\d\d|19\d\d|20[0-1]\d|202[0-3])\s+(?:border|war|clash|clashes|conflict|crisis|election|treaty|accord)|"
    r"history\s+of|historical\s+context|ancient|medieval|timeline\s+of"
    r")\b",
    re.I,
)

_EXPLICIT_CURRENT_MARKERS = re.compile(
    r"\b("
    r"latest|recent|recently|currently|current|today|now|present|presently|"
    r"this\s+(?:week|month|year)|new\s+update|latest\s+situation|breaking|202[5-9]"
    r")\b",
    re.I,
)

# 1. Explicit temporal keywords
_TEMPORAL_KEYWORDS = re.compile(
    r"\b("
    r"today|tonight|yesterday|tomorrow|"
    r"latest|recent|recently|currently|current|now|present|presently|"
    r"this (week|month|year|quarter|weekend|season)|"
    r"news|breaking|breaking news|headline(s)?|"
    r"update(d)?|update(d)? on|up-to-date|fresh information|"
    r"newly\s+(launched|released|announced|created|introduced|unveiled|reported|passed)|"
    r"(recently|newly|just)\s+(launched|released|announced|published|developed|occurred|happened)|"
    r"new\s+(model|feature|technology|update|announcement|law|policy|version|development)|"
    r"as of (today|now|202[4-9])|"
    r"upcoming|ongoing|developing story|"
    r"202[4-9]|"
    r"q[1-4]\s*202[4-9]"
    r")\b",
    re.I,
)

# 2. Geopolitical, military, diplomatic & territorial volatility
_GEOPOLITICAL_VOLATILITY = re.compile(
    r"\b("
    r"arunachal(?:\s+pradesh)?|lac\b|line of actual control|loc\b|line of control|"
    r"india[\s-]china|sino[\s-]indian|taiwan strait|south china sea|"
    r"incursion|incursions|border\s+(clash|tension|dispute|standoff|situation|activity|talks)|"
    r"entering\s+(arunachal|territory|borders?|airspace)|"
    r"military\s+(action|conflict|buildup|deployment|exercise|exercise)|"
    r"ceasefire|peace\s+talks|treaty|sanctions\s+(against|on)|"
    r"war in|russia[\s-]ukraine|israel[\s-]gaza|middle\s+east\s+conflict|"
    r"annexation|territorial\s+claim|troop(s)?\s+(movement|withdrawal|clash)|"
    r"coup|protest(s)? in|un\s+security\s+council\s+resolution"
    r")\b",
    re.I,
)

# 3. Political officeholders, elections, and government decisions
_POLITICAL_VOLATILITY = re.compile(
    r"\b("
    r"who is the (current|present|new)?\s*(prime minister|president|chancellor|governor|mayor|chief minister|ceo|secretary)|"
    r"election(s)?|poll(s)?|ballot|presidential\s+race|voting\s+results|"
    r"cabinet\s+(reshuffle|decision|minister)|"
    r"supreme\s+court\s+(ruling|verdict|decision)|"
    r"parliament\s+(passed|bill|act)|congress\s+(passed|bill)|senate\s+vote|"
    r"government\s+(scheme|order|policy|announcement)"
    r")\b",
    re.I,
)

# 4. Financial markets, economic indicators & commercial events
_MARKET_VOLATILITY = re.compile(
    r"\b("
    r"stock\s+price|market\s+cap|share\s+price|"
    r"all[\s-]time\s+high|market\s+crash|recession|"
    r"interest\s+rate(s)?|fed\s+(rate|meeting|decision)|rbi\s+repo\s+rate|inflation\s+rate|"
    r"earnings\s+(call|report|results)|quarterly\s+results|ipo|acquisition|merger|"
    r"bitcoin\s+price|crypto\s+market|exchange\s+rate\s+of"
    r")\b",
    re.I,
)

# 5. Technology, AI models, and software releases
_TECH_VOLATILITY = re.compile(
    r"\b("
    r"latest\s+(version|release|stable|update|commit)|"
    r"release\s+notes\s+for|what\s+changed\s+in|"
    r"gpt-?[5-9]|gpt-?4o|claude-?[4-9]|gemini-?[2-9]|llama-?[4-9]|"
    r"deepseek(-r\d|-v\d)?|grok-?[2-9]|qwen-?[2-9]|"
    r"sora\b|project\s+astra|"
    r"ios\s+1[8-9]|android\s+1[5-9]|windows\s+1[1-2]|python\s+3\.1[3-9]"
    r")\b",
    re.I,
)

# 6. Dynamic factual question patterns ("Is [entity] [ongoing action]?", "Has [event] occurred?")
_DYNAMIC_STATUS_PATTERNS = re.compile(
    r"\b("
    r"is\s+[a-z\s]+(entering|attacking|negotiating|buying|selling|resigning|launching|passing)|"
    r"has\s+[a-z\s]+(entered|attacked|passed|resigned|announced|launched|won|signed|declined)|"
    r"did\s+[a-z\s]+(win|announce|launch|enter|invade|pass|release)|"
    r"what\s+is\s+(the\s+)?(status|situation|condition)\s+of|"
    r"what\s+happened\s+(to|with|in|at)\b"
    r")\b",
    re.I,
)


class FreshnessEvaluation:
    def __init__(
        self,
        requires_freshness: bool,
        reasons: List[str],
        suggested_search_query: str,
        volatility_level: str = "low",  # "none" | "low" | "medium" | "high" | "critical"
    ):
        self.requires_freshness = requires_freshness
        self.reasons = reasons
        self.suggested_search_query = suggested_search_query
        self.volatility_level = volatility_level

    def __getitem__(self, item):
        if item == "time_sensitivity":
            return self.volatility_level
        if item == "freshness_policy":
            return "breaking_geopolitical" if self.volatility_level == "critical" else "general_freshness"
        return getattr(self, item)

    def get(self, item, default=None):
        if item == "time_sensitivity":
            return self.volatility_level
        if item == "freshness_policy":
            return "breaking_geopolitical" if self.volatility_level == "critical" else "general_freshness"
        return getattr(self, item, default)

    def to_dict(self) -> Dict:
        return {
            "requires_freshness": self.requires_freshness,
            "reasons": self.reasons,
            "suggested_search_query": self.suggested_search_query,
            "volatility_level": self.volatility_level,
            "time_sensitivity": self.volatility_level,
            "freshness_policy": "breaking_geopolitical" if self.volatility_level == "critical" else "general_freshness",
        }


class FreshnessService:
    """Evaluates question freshness requirements and refines search queries."""

    def evaluate(self, question: str) -> FreshnessEvaluation:
        q = question.strip()
        reasons = []
        volatility = "none"

        # Check if question explicitly targets completed historical past
        is_historical = bool(_HISTORICAL_MARKERS.search(q))
        has_current_marker = bool(_EXPLICIT_CURRENT_MARKERS.search(q))

        if is_historical and not has_current_marker:
            return FreshnessEvaluation(
                requires_freshness=False,
                reasons=["Query explicitly targets a past historical event or completed timeframe."],
                suggested_search_query=self.formulate_search_query(q),
                volatility_level="none",
            )

        # 1. Explicit temporal keywords
        if _TEMPORAL_KEYWORDS.search(q):
            reasons.append("Contains explicit temporal keywords indicating time-sensitive information.")
            volatility = "high"

        # 2. Geopolitical / Territorial / Military
        if _GEOPOLITICAL_VOLATILITY.search(q):
            reasons.append("Subject involves geopolitical, military, or territorial developments subject to active changes.")
            volatility = "critical" if volatility != "critical" else volatility

        # 3. Political & Governmental Officeholders / Elections
        if _POLITICAL_VOLATILITY.search(q):
            reasons.append("Inquiry pertains to current political officeholders, elections, or government decisions.")
            volatility = "high" if volatility in ("none", "low") else volatility

        # 4. Financial & Market Volatility
        if _MARKET_VOLATILITY.search(q):
            reasons.append("Financial, economic, or market metrics change continuously and require real-time verification.")
            volatility = "high" if volatility in ("none", "low") else volatility

        # 5. Technology & Model Releases
        if _TECH_VOLATILITY.search(q):
            reasons.append("Software version, library release, or AI model specifications require current documentation.")
            volatility = "high" if volatility in ("none", "low") else volatility

        # 6. Dynamic status queries ("Is X entering Y?", "What is the status of...")
        if _DYNAMIC_STATUS_PATTERNS.search(q):
            reasons.append("Query asks for the live operational or ongoing status of real-world entities.")
            volatility = "high" if volatility in ("none", "low") else volatility

        requires_freshness = len(reasons) > 0

        # Construct an optimized keyword search query
        search_query = self.formulate_search_query(q)

        return FreshnessEvaluation(
            requires_freshness=requires_freshness,
            reasons=reasons,
            suggested_search_query=search_query,
            volatility_level=volatility if requires_freshness else "none",
        )

    def formulate_search_query(self, question: str) -> str:
        """Transforms a natural language conversational question into a clean search query."""
        # Strip common conversational wrapper patterns
        cleaned = re.sub(
            r"^(?:please\s+)?(?:tell\s+me|can\s+you\s+tell\s+me|what\s+is|what\s+are|what's|"
            r"search\s+(?:the\s+)?(?:web|internet)\s+for|search\s+online\s+for|look\s+up|"
            r"do\s+you\s+know|find\s+out|is\s+it\s+true\s+that)\s*",
            "",
            question,
            flags=re.I,
        ).strip()

        # Remove trailing punctuation marks
        cleaned = re.sub(r"[?!.,;]+$", "", cleaned).strip()

        # If question is short or already focused, use it directly
        if len(cleaned.split()) <= 8:
            return cleaned if cleaned else question.strip()

        # Retain substantive keywords
        stop_words = {
            "a", "an", "the", "and", "or", "in", "on", "at", "to", "for", "with",
            "about", "is", "are", "was", "were", "be", "been", "being", "have", "has",
            "had", "do", "does", "did", "can", "could", "would", "should", "please",
            "give", "tell", "explain", "i", "you", "me", "my", "your", "what", "which",
        }
        words = cleaned.split()
        filtered = [w for w in words if w.lower() not in stop_words or len(w) > 4]
        if len(filtered) >= 3:
            return " ".join(filtered)

        return cleaned or question.strip()


freshness_service = FreshnessService()
