# v0.2.16
# {
#   "Seq": [
#     { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
#   ]
# }
import json
from dataclasses import dataclass
from genlayer import *


def _addr_str(a: Address) -> str:
    try:
        return a.as_hex
    except Exception:
        return str(a)


def _to_address(val) -> Address:
    if isinstance(val, Address):
        return val
    if isinstance(val, str):
        val_str = val.strip()
        if not val_str.startswith("0x"):
            val_str = "0x" + val_str
        return Address(val_str)
    return Address(val)


def _is_http_url(url: str) -> bool:
    return url.startswith("http://") or url.startswith("https://")


def _as_int(val, default: int = 0) -> int:
    try:
        return int(val)
    except Exception:
        return default


def _clamp_unit(val) -> int:
    try:
        n = int(val)
    except Exception:
        return 0
    if n < 0:
        return 0
    if n > 100:
        return 100
    return n


def _align_score(tier: str, score: int) -> int:
    if tier == "HIGH_CREDIBILITY" and score < 75:
        return 80
    if tier == "MODERATE" and (score < 40 or score > 74):
        return 57
    if tier == "LOW_CREDIBILITY" and score > 39:
        return 20
    if tier == "UNASSESSABLE":
        return 0
    return score


def _clean_items(val) -> list:
    items = val
    if isinstance(val, str):
        try:
            items = json.loads(val)
        except Exception:
            return []
    if not isinstance(items, list):
        return []
    cleaned = []
    for item in items:
        if item and str(item).strip():
            cleaned.append(str(item))
    return cleaned


def _dump_str_list(val) -> str:
    return json.dumps(_clean_items(val))


def _unassessable(reason: str) -> dict:
    return {
        "tier": "UNASSESSABLE",
        "source_type": "UNKNOWN",
        "bias_direction": "UNKNOWN",
        "credibility_score": 0,
        "confidence": 0,
        "reasoning": reason,
        "strengths": "[]",
        "weaknesses": "[]",
    }


_TIERS = ["HIGH_CREDIBILITY", "MODERATE", "LOW_CREDIBILITY", "UNASSESSABLE"]
_SOURCE_TYPES = [
    "NEWS_OUTLET",
    "ACADEMIC",
    "OFFICIAL_DOCS",
    "BLOG",
    "SOCIAL_MEDIA",
    "AGGREGATOR",
    "UNKNOWN",
]
_BIAS = [
    "LEFT",
    "CENTER_LEFT",
    "CENTER",
    "CENTER_RIGHT",
    "RIGHT",
    "UNKNOWN",
    "NA",
]
_FILTERS = [
    "",
    "PENDING",
    "HIGH_CREDIBILITY",
    "MODERATE",
    "LOW_CREDIBILITY",
    "UNASSESSABLE",
]


@allow_storage
@dataclass
class CredibilityReport:
    submitter: Address
    source_url: str
    about_url: str
    status: str
    tier: str
    source_type: str
    bias_direction: str
    credibility_score: u256
    confidence: u256
    reasoning: str
    strengths: str
    weaknesses: str


class SourceVerdict(gl.Contract):
    reports: TreeMap[str, CredibilityReport]
    next_id: bigint
    owner: Address
    # Cache: source_url -> latest report_id
    url_cache: TreeMap[str, str]

    def __init__(self):
        self.owner = _to_address(gl.message.sender_address)
        self.next_id = bigint(1)

    def _report_dict(self, report_id: str, report: CredibilityReport) -> dict:
        return {
            "report_id": report_id,
            "submitter": _addr_str(report.submitter),
            "source_url": report.source_url,
            "about_url": report.about_url,
            "status": report.status,
            "tier": report.tier,
            "source_type": report.source_type,
            "bias_direction": report.bias_direction,
            "credibility_score": _as_int(report.credibility_score),
            "confidence": _as_int(report.confidence),
            "reasoning": report.reasoning,
            "strengths": report.strengths,
            "weaknesses": report.weaknesses,
        }

    @gl.public.write
    def submit_source(self, source_url: str, about_url: str) -> str:
        if not source_url or not _is_http_url(source_url):
            raise gl.vm.UserError("Invalid source_url")

        if about_url != "":
            if not _is_http_url(about_url):
                raise gl.vm.UserError("Invalid about_url")
            if source_url == about_url:
                raise gl.vm.UserError("source_url and about_url must differ")

        report_id = str(self.next_id)
        self.next_id += bigint(1)

        report = CredibilityReport(
            submitter=_to_address(gl.message.sender_address),
            source_url=source_url,
            about_url=about_url,
            status="PENDING",
            tier="",
            source_type="UNKNOWN",
            bias_direction="UNKNOWN",
            credibility_score=u256(0),
            confidence=u256(0),
            reasoning="",
            strengths="[]",
            weaknesses="[]",
        )
        self.reports[report_id] = report
        self.url_cache[source_url] = report_id
        return report_id

    @gl.public.write
    def assess_source(self, report_id: str) -> None:
        if report_id not in self.reports:
            raise gl.vm.UserError("Report not found")

        report = self.reports[report_id]
        if report.status != "PENDING":
            raise gl.vm.UserError("Report is not PENDING")

        source_url_cap = report.source_url
        about_url_cap = report.about_url

        def leader_fn():
            try:
                source_content = ""
                try:
                    res = gl.nondet.web.render(source_url_cap)
                    body = res.body if hasattr(res, "body") else str(res)
                    source_content = (
                        body[:4000]
                        if body and len(body.strip()) > 30
                        else "(empty or unreachable)"
                    )
                except Exception as e:
                    source_content = f"(fetch failed: {str(e)})"

                about_content = ""
                if about_url_cap:
                    try:
                        res2 = gl.nondet.web.render(about_url_cap)
                        body2 = res2.body if hasattr(res2, "body") else str(res2)
                        about_content = (
                            body2[:3000]
                            if body2 and len(body2.strip()) > 30
                            else "(empty or unreachable)"
                        )
                    except Exception as e:
                        about_content = f"(fetch failed: {str(e)})"
                else:
                    about_content = "(no about/reference URL provided)"

                prompt = f"""You are an expert media credibility and source quality analyst on GenLayer. Your job is to assess the credibility, source type, and bias of a web source based on what you can read from it.

Primary Source URL: {source_url_cap}
Primary Source Content fetched on-chain:
{source_content}

About Page / Reference URL Content fetched on-chain:
{about_content}

Assess the source across these dimensions:

SOURCE TYPE - identify which best fits:
- NEWS_OUTLET: professional journalism organization with editorial staff
- ACADEMIC: peer-reviewed journal, university publication, research paper
- OFFICIAL_DOCS: government, standards body, or official project documentation
- BLOG: personal or organizational blog without formal editorial process
- SOCIAL_MEDIA: Twitter/X, Reddit, Facebook, or similar platform content
- AGGREGATOR: news aggregator, content curator, or link-sharing site
- UNKNOWN: cannot determine from available content

CREDIBILITY SIGNALS (check each):
Strengths (positive signals):
- Clear authorship and editorial standards stated
- Transparent ownership and funding disclosed
- History of corrections and retractions when errors occur
- Primary sources cited and linked
- Professional and consistent writing style
- Established track record (years of operation)
- Recognized and referenced by other credible sources

Weaknesses (negative signals):
- No clear authorship or anonymous content
- Sensationalist headlines or emotionally manipulative language
- No correction policy visible
- Mixed news and opinion without clear labeling
- Known history of misinformation (if visible in about content)
- Very recently created or very thin content
- Opaque funding or ownership

BIAS DIRECTION - identify political/editorial lean if applicable:
- LEFT: consistently favors left-wing political perspectives
- CENTER_LEFT: mild left-leaning tendency
- CENTER: genuinely centrist, balanced political coverage
- CENTER_RIGHT: mild right-leaning tendency
- RIGHT: consistently favors right-wing political perspectives
- UNKNOWN: cannot determine bias from available content
- NA: not applicable (academic, official docs, technical content)

CREDIBILITY SCORE 0-100:
- HIGH_CREDIBILITY (75-100): multiple strengths, few weaknesses, transparent, established, professional standards
- MODERATE (40-74): some strengths and some weaknesses, generally reliable but with caveats
- LOW_CREDIBILITY (0-39): significant weaknesses, opacity, or known credibility issues
- UNASSESSABLE: source content completely unreadable

Provide:
- strengths: list of specific positive credibility signals found
- weaknesses: list of specific negative credibility signals found

Return ONLY raw JSON, no markdown, no backticks:
{{"tier": "HIGH_CREDIBILITY"|"MODERATE"|"LOW_CREDIBILITY"|"UNASSESSABLE", "source_type": "NEWS_OUTLET"|"ACADEMIC"|"OFFICIAL_DOCS"|"BLOG"|"SOCIAL_MEDIA"|"AGGREGATOR"|"UNKNOWN", "bias_direction": "LEFT"|"CENTER_LEFT"|"CENTER"|"CENTER_RIGHT"|"RIGHT"|"UNKNOWN"|"NA", "credibility_score": "<0-100 integer>", "confidence": "<0-100 integer>", "reasoning": "<2-3 sentences summarizing the credibility assessment>", "strengths": ["<strength 1>", "<strength 2>"], "weaknesses": ["<weakness 1>", "<weakness 2>"]}}"""

                raw = gl.nondet.exec_prompt(prompt, response_format="json")

                try:
                    if isinstance(raw, dict):
                        parsed = raw
                    else:
                        cleaned = str(raw).strip()
                        if cleaned.startswith("```json"):
                            cleaned = cleaned[7:]
                        if cleaned.startswith("```"):
                            cleaned = cleaned[3:]
                        if cleaned.endswith("```"):
                            cleaned = cleaned[:-3]
                        parsed = json.loads(cleaned.strip())

                    tier = parsed.get("tier", "UNASSESSABLE")
                    if tier not in _TIERS:
                        tier = "UNASSESSABLE"

                    source_type = parsed.get("source_type", "UNKNOWN")
                    if source_type not in _SOURCE_TYPES:
                        source_type = "UNKNOWN"

                    bias = parsed.get("bias_direction", "UNKNOWN")
                    if bias not in _BIAS:
                        bias = "UNKNOWN"

                    score = _align_score(tier, _clamp_unit(parsed.get("credibility_score", 0)))
                    conf = _clamp_unit(parsed.get("confidence", 0))

                    clean_strengths = _clean_items(parsed.get("strengths", []))
                    clean_weaknesses = _clean_items(parsed.get("weaknesses", []))

                    # LOW_CREDIBILITY is only valid when at least one weakness was found.
                    if tier == "LOW_CREDIBILITY" and len(clean_weaknesses) == 0:
                        tier = "MODERATE"
                        score = 57

                    return {
                        "tier": tier,
                        "source_type": source_type,
                        "bias_direction": bias,
                        "credibility_score": score,
                        "confidence": conf,
                        "reasoning": str(parsed.get("reasoning", "")),
                        "strengths": json.dumps(clean_strengths),
                        "weaknesses": json.dumps(clean_weaknesses),
                    }
                except Exception as e:
                    return _unassessable(f"Parse error: {str(e)}")
            except Exception as e:
                return _unassessable(f"Parse error: {str(e)}")

        def validator_fn(leader_res) -> bool:
            if not isinstance(leader_res, gl.vm.Return):
                return False
            lp = leader_res.calldata
            if not isinstance(lp, dict):
                return False

            leader_tier = lp.get("tier")
            leader_type = lp.get("source_type")
            leader_bias = lp.get("bias_direction")
            leader_score = lp.get("credibility_score")
            leader_conf = lp.get("confidence")

            if leader_tier not in _TIERS:
                return False
            if leader_type not in _SOURCE_TYPES:
                return False
            if leader_bias not in _BIAS:
                return False

            try:
                ls = int(leader_score)
                lc = int(leader_conf)
                if not (0 <= ls <= 100):
                    return False
                if not (0 <= lc <= 100):
                    return False
            except Exception:
                return False

            try:
                my_result = leader_fn()
            except Exception:
                return False
            if not isinstance(my_result, dict):
                return False

            # All three categorical fields must match exactly.
            if my_result.get("tier") != leader_tier:
                return False
            if my_result.get("source_type") != leader_type:
                return False
            if my_result.get("bias_direction") != leader_bias:
                return False

            # LOW_CREDIBILITY: both sides must find at least one weakness.
            if leader_tier == "LOW_CREDIBILITY":
                try:
                    my_w = json.loads(my_result.get("weaknesses", "[]"))
                    l_w = json.loads(lp.get("weaknesses", "[]"))
                    if not isinstance(my_w, list) or not isinstance(l_w, list):
                        return False
                    if len(my_w) == 0 or len(l_w) == 0:
                        return False
                except Exception:
                    return False

            # Score tolerance: +-5 within the same tier.
            try:
                ms = int(my_result.get("credibility_score", 0))
                if abs(ms - ls) > 5:
                    return False
            except Exception:
                return False

            try:
                mc = int(my_result.get("confidence", 0))
                if not (0 <= mc <= 100):
                    return False
            except Exception:
                return False

            def _band(c):
                if c < 35:
                    return 1
                elif c < 80:
                    return 2
                else:
                    return 3

            return _band(mc) == _band(lc)

        ruling = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)
        result_data = ruling.calldata if hasattr(ruling, "calldata") else ruling
        if not isinstance(result_data, dict):
            result_data = _unassessable("Invalid nondet result")

        result_tier = result_data.get("tier", "UNASSESSABLE")
        if result_tier not in _TIERS:
            result_tier = "UNASSESSABLE"

        source_type = result_data.get("source_type", "UNKNOWN")
        if source_type not in _SOURCE_TYPES:
            source_type = "UNKNOWN"

        bias = result_data.get("bias_direction", "UNKNOWN")
        if bias not in _BIAS:
            bias = "UNKNOWN"

        score = _align_score(result_tier, _clamp_unit(result_data.get("credibility_score", 0)))
        conf = _clamp_unit(result_data.get("confidence", 0))
        strengths = _dump_str_list(result_data.get("strengths", "[]"))
        weaknesses = _dump_str_list(result_data.get("weaknesses", "[]"))

        if result_tier == "LOW_CREDIBILITY" and weaknesses == "[]":
            result_tier = "MODERATE"
            score = 57

        report.tier = result_tier
        report.source_type = source_type
        report.bias_direction = bias
        report.credibility_score = u256(score)
        report.confidence = u256(conf)
        report.reasoning = str(result_data.get("reasoning", ""))
        report.strengths = strengths
        report.weaknesses = weaknesses
        report.status = (
            "ASSESSED" if result_tier not in ["UNASSESSABLE", ""] else "UNASSESSABLE"
        )
        self.reports[report_id] = report

    @gl.public.write
    def invalidate_report(self, report_id: str) -> None:
        if report_id not in self.reports:
            raise gl.vm.UserError("Report not found")

        sender = _to_address(gl.message.sender_address)
        if sender != self.owner:
            raise gl.vm.UserError("Only owner")

        report = self.reports[report_id]
        if report.status != "PENDING":
            raise gl.vm.UserError("only PENDING")

        report.status = "UNASSESSABLE"
        report.reasoning = "Invalidated by admin"
        self.reports[report_id] = report

    @gl.public.view
    def get_report(self, report_id: str) -> str:
        if report_id not in self.reports:
            raise gl.vm.UserError("Report not found")
        return json.dumps(self._report_dict(report_id, self.reports[report_id]))

    @gl.public.view
    def get_assessment(self, report_id: str) -> str:
        if report_id not in self.reports:
            raise gl.vm.UserError("Report not found")

        report = self.reports[report_id]
        if report.status == "PENDING":
            raise gl.vm.UserError("Not yet assessed")

        res = {
            "report_id": report_id,
            "source_url": report.source_url,
            "tier": report.tier,
            "source_type": report.source_type,
            "bias_direction": report.bias_direction,
            "credibility_score": _as_int(report.credibility_score),
            "confidence": _as_int(report.confidence),
            "reasoning": report.reasoning,
            "strengths": report.strengths,
            "weaknesses": report.weaknesses,
        }
        return json.dumps(res)

    @gl.public.view
    def lookup_by_url(self, source_url: str) -> str:
        if source_url not in self.url_cache:
            return json.dumps({"found": False})

        report_id = self.url_cache[source_url]
        if report_id not in self.reports:
            return json.dumps({"found": False})

        return json.dumps(self._report_dict(report_id, self.reports[report_id]))

    @gl.public.view
    def list_reports(self, tier_filter: str) -> str:
        if tier_filter not in _FILTERS:
            raise gl.vm.UserError("Invalid tier filter")

        results = []
        limit = int(self.next_id)
        for i in range(1, limit):
            report_id = str(i)
            if report_id in self.reports:
                report = self.reports[report_id]
                if (
                    tier_filter == ""
                    or report.status == tier_filter
                    or report.tier == tier_filter
                ):
                    results.append({
                        "report_id": report_id,
                        "source_url": report.source_url,
                        "status": report.status,
                        "tier": report.tier,
                        "source_type": report.source_type,
                        "bias_direction": report.bias_direction,
                        "credibility_score": _as_int(report.credibility_score),
                    })
        return json.dumps(results)

    @gl.public.view
    def get_count(self) -> int:
        return int(self.next_id) - 1
