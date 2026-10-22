import json
import pytest


def _llm(tier, source_type, bias, score, confidence, reasoning, strengths, weaknesses):
    return json.dumps({
        "tier": tier,
        "source_type": source_type,
        "bias_direction": bias,
        "credibility_score": score,
        "confidence": confidence,
        "reasoning": reasoning,
        "strengths": strengths,
        "weaknesses": weaknesses,
    })


def test_high_credibility_news_outlet(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/source_verdict.py")

    with direct_vm.prank(direct_alice):
        report_id = contract.submit_source(
            "https://reuters.com/technology/ai",
            "https://en.wikipedia.org/wiki/Reuters",
        )
    assert report_id == "1"
    assert contract.get_count() == 1

    direct_vm.mock_web(
        r".*reuters.com.*",
        "Reuters Technology | AI Coverage | Independent journalism "
        "since 1851 | Editorial standards: corrections policy, "
        "fact-checking team, named authors, primary source citation",
    )
    direct_vm.mock_web(
        r".*wikipedia.*Reuters.*",
        "Reuters is an international news agency founded in 1851. "
        "It is owned by Thomson Reuters. Known for factual, neutral "
        "reporting. Has issued corrections when errors occur. "
        "Widely cited by other news organizations globally.",
    )

    direct_vm.mock_llm(
        r".*credibility.*analyst.*",
        _llm(
            "HIGH_CREDIBILITY",
            "NEWS_OUTLET",
            "CENTER",
            88,
            92,
            "Reuters has 170+ years of journalism history, "
            "transparent ownership, corrections policy, and "
            "neutral reporting confirmed by Wikipedia.",
            ["established since 1851", "corrections policy", "transparent ownership", "named authors"],
            [],
        ),
    )

    contract.assess_source(report_id)

    result = json.loads(contract.get_assessment(report_id))
    assert result["tier"] == "HIGH_CREDIBILITY"
    assert result["source_type"] == "NEWS_OUTLET"
    assert result["bias_direction"] == "CENTER"
    assert result["credibility_score"] == 88
    assert len(json.loads(result["strengths"])) == 4
    assert json.loads(result["weaknesses"]) == []

    full = json.loads(contract.get_report(report_id))
    assert full["status"] == "ASSESSED"


def test_moderate_credibility_blog(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/source_verdict.py")

    with direct_vm.prank(direct_alice):
        report_id = contract.submit_source(
            "https://personal-notes.example.com/ai-policy",
            "https://personal-notes.example.com/about",
        )

    direct_vm.mock_web(
        r".*personal-notes\.example\.com/ai-policy.*",
        "My notes on AI policy. I cite two papers and a government report. "
        "This is a personal blog. I do not have an editorial board.",
    )
    direct_vm.mock_web(
        r".*personal-notes\.example\.com/about.*",
        "About me: independent writer. No organization, no corrections policy, "
        "posts since 2019. Some posts link to primary sources.",
    )
    direct_vm.mock_llm(
        r".*credibility.*analyst.*",
        _llm(
            "MODERATE",
            "BLOG",
            "CENTER",
            58,
            70,
            "The page is a personal blog with some citations but no editorial policy.",
            ["cites primary sources", "several years of posts"],
            ["no editorial policy", "single anonymous-style byline"],
        ),
    )

    contract.assess_source(report_id)

    result = json.loads(contract.get_assessment(report_id))
    assert result["tier"] == "MODERATE"
    assert result["source_type"] == "BLOG"
    assert result["credibility_score"] == 58
    full = json.loads(contract.get_report(report_id))
    assert full["status"] == "ASSESSED"


def test_low_credibility_site(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/source_verdict.py")

    with direct_vm.prank(direct_alice):
        report_id = contract.submit_source(
            "https://shock-headlines.example.com/story",
            "https://shock-headlines.example.com/about",
        )

    direct_vm.mock_web(
        r".*shock-headlines\.example\.com/story.*",
        "YOU WON'T BELIEVE THIS SECRET THEY HID FROM YOU!!! "
        "Anonymous post. No author. No sources. All caps headline.",
    )
    direct_vm.mock_web(
        r".*shock-headlines\.example\.com/about.*",
        "We do not disclose owners. No corrections desk. Site created last month.",
    )
    direct_vm.mock_llm(
        r".*credibility.*analyst.*",
        _llm(
            "LOW_CREDIBILITY",
            "NEWS_OUTLET",
            "RIGHT",
            22,
            84,
            "Sensationalist headlines, no authorship, and no visible corrections policy.",
            [],
            ["sensationalist headlines", "anonymous content", "no correction policy"],
        ),
    )

    contract.assess_source(report_id)

    result = json.loads(contract.get_assessment(report_id))
    assert result["tier"] == "LOW_CREDIBILITY"
    assert result["source_type"] == "NEWS_OUTLET"
    assert result["credibility_score"] == 22
    weaknesses = json.loads(result["weaknesses"])
    assert len(weaknesses) >= 2
    full = json.loads(contract.get_report(report_id))
    assert full["status"] == "ASSESSED"


def test_academic_source_na_bias(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/source_verdict.py")

    with direct_vm.prank(direct_alice):
        report_id = contract.submit_source(
            "https://arxiv.org/abs/2401.00001",
            "https://arxiv.org/about",
        )

    direct_vm.mock_web(
        r".*arxiv\.org/abs.*",
        "Abstract. We present a peer-reviewed method for source classification. "
        "Authors: A. Nguyen, B. Patel. University preprint with citations.",
    )
    direct_vm.mock_web(
        r".*arxiv\.org/about.*",
        "arXiv is a free distribution service and an open-access archive for "
        "scholarly articles. It is operated by Cornell University.",
    )
    direct_vm.mock_llm(
        r".*credibility.*analyst.*",
        _llm(
            "HIGH_CREDIBILITY",
            "ACADEMIC",
            "NA",
            86,
            90,
            "This is a scholarly paper. Political bias is not applicable.",
            ["named authors", "citations", "university archive"],
            [],
        ),
    )

    contract.assess_source(report_id)

    result = json.loads(contract.get_assessment(report_id))
    assert result["source_type"] == "ACADEMIC"
    assert result["bias_direction"] == "NA"
    assert result["tier"] == "HIGH_CREDIBILITY"
    full = json.loads(contract.get_report(report_id))
    assert full["status"] == "ASSESSED"


def test_official_docs_source(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/source_verdict.py")

    with direct_vm.prank(direct_alice):
        report_id = contract.submit_source(
            "https://docs.example.gov/standard/v1",
            "https://docs.example.gov/about",
        )

    direct_vm.mock_web(
        r".*docs\.example\.gov/standard.*",
        "Official specification published by the standards office. "
        "Version 1.2. Maintained by the documentation working group.",
    )
    direct_vm.mock_web(
        r".*docs\.example\.gov/about.*",
        "This site hosts official government technical documentation. "
        "Pages are reviewed before publication.",
    )
    direct_vm.mock_llm(
        r".*credibility.*analyst.*",
        _llm(
            "HIGH_CREDIBILITY",
            "OFFICIAL_DOCS",
            "NA",
            90,
            88,
            "Official documentation from a government standards body. Bias is not applicable.",
            ["official publisher", "versioned specification"],
            [],
        ),
    )

    contract.assess_source(report_id)

    result = json.loads(contract.get_assessment(report_id))
    assert result["source_type"] == "OFFICIAL_DOCS"
    assert result["bias_direction"] == "NA"
    assert result["tier"] == "HIGH_CREDIBILITY"
    full = json.loads(contract.get_report(report_id))
    assert full["status"] == "ASSESSED"


def test_unassessable_both_fail(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/source_verdict.py")

    with direct_vm.prank(direct_alice):
        report_id = contract.submit_source(
            "https://down-source.example.com/article",
            "https://down-about.example.com/about",
        )

    def _raise(_url=None):
        raise RuntimeError("unreachable")

    direct_vm.mock_web(r".*down-.*", _raise)
    direct_vm.mock_llm(
        r".*credibility.*analyst.*",
        _llm(
            "UNASSESSABLE",
            "UNKNOWN",
            "UNKNOWN",
            0,
            12,
            "Both URLs failed to load, so the source cannot be assessed.",
            [],
            ["both pages unreachable"],
        ),
    )

    contract.assess_source(report_id)

    result = json.loads(contract.get_assessment(report_id))
    assert result["tier"] == "UNASSESSABLE"
    assert result["credibility_score"] == 0
    full = json.loads(contract.get_report(report_id))
    assert full["status"] == "UNASSESSABLE"


def test_primary_fails_about_succeeds(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/source_verdict.py")

    with direct_vm.prank(direct_alice):
        report_id = contract.submit_source(
            "https://broken-source.example.com/story",
            "https://about-page.example.com/outlet",
        )

    def _raise(_url=None):
        raise RuntimeError("source unreachable")

    direct_vm.mock_web(r".*broken-source\.example\.com.*", _raise)
    direct_vm.mock_web(
        r".*about-page\.example\.com.*",
        "About this publication: established newsroom with a public corrections "
        "policy and named editors on staff since 1998.",
    )
    direct_vm.mock_llm(
        r".*credibility.*analyst.*",
        _llm(
            "MODERATE",
            "NEWS_OUTLET",
            "CENTER",
            62,
            55,
            "The article URL failed, but the about page describes an established newsroom.",
            ["corrections policy on about page"],
            ["primary article could not be fetched"],
        ),
    )

    contract.assess_source(report_id)

    result = json.loads(contract.get_assessment(report_id))
    assert result["tier"] == "MODERATE"
    assert result["source_type"] == "NEWS_OUTLET"
    assert result["credibility_score"] == 62
    full = json.loads(contract.get_report(report_id))
    assert full["status"] == "ASSESSED"


def test_submit_without_about_url(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/source_verdict.py")

    with direct_vm.prank(direct_alice):
        report_id = contract.submit_source("https://primary-only.example.com/post", "")

    direct_vm.mock_web(
        r".*primary-only\.example\.com.*",
        "City desk report with a named reporter, a corrections link in the footer, "
        "and quotes from two public records.",
    )
    direct_vm.mock_llm(
        r".*credibility.*analyst.*",
        _llm(
            "MODERATE",
            "NEWS_OUTLET",
            "CENTER_LEFT",
            64,
            66,
            "Assessed from the primary page only. No about URL was provided.",
            ["named reporter", "corrections link"],
            ["ownership not disclosed on this page"],
        ),
    )

    contract.assess_source(report_id)

    result = json.loads(contract.get_assessment(report_id))
    assert result["tier"] == "MODERATE"
    full = json.loads(contract.get_report(report_id))
    assert full["status"] == "ASSESSED"
    assert full["about_url"] == ""


def test_low_credibility_no_weaknesses_upgraded(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/source_verdict.py")

    with direct_vm.prank(direct_alice):
        report_id = contract.submit_source(
            "https://upgrade-case.example.com/story",
            "",
        )

    direct_vm.mock_web(
        r".*upgrade-case\.example\.com.*",
        "A short opinion page with a loud headline and no listed author or sources.",
    )
    direct_vm.mock_llm(
        r".*credibility.*analyst.*",
        _llm(
            "LOW_CREDIBILITY",
            "BLOG",
            "UNKNOWN",
            15,
            40,
            "The model marked this low credibility but listed no weaknesses.",
            [],
            [],
        ),
    )

    contract.assess_source(report_id)

    result = json.loads(contract.get_assessment(report_id))
    assert result["tier"] == "MODERATE"
    assert result["credibility_score"] == 57
    full = json.loads(contract.get_report(report_id))
    assert full["status"] == "ASSESSED"


def test_high_credibility_low_score_corrected(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/source_verdict.py")

    with direct_vm.prank(direct_alice):
        report_id = contract.submit_source(
            "https://score-clamp.example.com/news",
            "",
        )

    direct_vm.mock_web(
        r".*score-clamp\.example\.com.*",
        "Established newsroom page with named editors and a corrections policy.",
    )
    direct_vm.mock_llm(
        r".*credibility.*analyst.*",
        _llm(
            "HIGH_CREDIBILITY",
            "NEWS_OUTLET",
            "CENTER",
            50,
            77,
            "The tier and score disagreed, so the score must be raised into the high band.",
            ["named editors", "corrections policy"],
            [],
        ),
    )

    contract.assess_source(report_id)

    result = json.loads(contract.get_assessment(report_id))
    assert result["tier"] == "HIGH_CREDIBILITY"
    assert result["credibility_score"] >= 75
    assert result["credibility_score"] == 80


def test_invalid_tier_normalized(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/source_verdict.py")

    with direct_vm.prank(direct_alice):
        report_id = contract.submit_source(
            "https://bad-tier.example.com/page",
            "",
        )

    direct_vm.mock_web(
        r".*bad-tier\.example\.com.*",
        "A normal article page with a headline, a byline, and two cited documents.",
    )
    direct_vm.mock_llm(
        r".*credibility.*analyst.*",
        _llm(
            "VERY_HIGH",
            "NEWS_OUTLET",
            "CENTER",
            99,
            90,
            "The model invented a tier outside the allowed set.",
            ["named byline"],
            [],
        ),
    )

    contract.assess_source(report_id)

    result = json.loads(contract.get_assessment(report_id))
    assert result["tier"] == "UNASSESSABLE"
    assert result["credibility_score"] == 0
    full = json.loads(contract.get_report(report_id))
    assert full["status"] == "UNASSESSABLE"
    assert full["tier"] == "UNASSESSABLE"


def test_invalid_source_type_normalized(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/source_verdict.py")

    with direct_vm.prank(direct_alice):
        report_id = contract.submit_source(
            "https://bad-type.example.com/page",
            "",
        )

    direct_vm.mock_web(
        r".*bad-type\.example\.com.*",
        "A readable article with a byline and links to two primary documents.",
    )
    direct_vm.mock_llm(
        r".*credibility.*analyst.*",
        _llm(
            "MODERATE",
            "PODCAST",
            "CENTER",
            60,
            68,
            "The model returned a source type outside the allowed set.",
            ["named byline"],
            ["type label was not in the allowed set"],
        ),
    )

    contract.assess_source(report_id)

    result = json.loads(contract.get_assessment(report_id))
    assert result["source_type"] == "UNKNOWN"
    assert result["tier"] == "MODERATE"
    full = json.loads(contract.get_report(report_id))
    assert full["status"] == "ASSESSED"


def test_invalid_bias_normalized(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/source_verdict.py")

    with direct_vm.prank(direct_alice):
        report_id = contract.submit_source(
            "https://bad-bias.example.com/page",
            "",
        )

    direct_vm.mock_web(
        r".*bad-bias\.example\.com.*",
        "Opinion column with a named author and a mix of cited reports and commentary.",
    )
    direct_vm.mock_llm(
        r".*credibility.*analyst.*",
        _llm(
            "MODERATE",
            "BLOG",
            "VERY_LEFT",
            61,
            64,
            "The model returned a bias label outside the allowed set.",
            ["named author"],
            ["bias label was not in the allowed set"],
        ),
    )

    contract.assess_source(report_id)

    result = json.loads(contract.get_assessment(report_id))
    assert result["bias_direction"] == "UNKNOWN"
    assert result["tier"] == "MODERATE"
    assert result["source_type"] == "BLOG"


def test_malformed_llm_json(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/source_verdict.py")

    with direct_vm.prank(direct_alice):
        report_id = contract.submit_source(
            "https://bad-json.example.com/page",
            "",
        )

    direct_vm.mock_web(
        r".*bad-json\.example\.com.*",
        "A readable page with a headline, a date, and several paragraphs of text.",
    )
    direct_vm.mock_llm(r".*credibility.*analyst.*", "not valid json!!")

    contract.assess_source(report_id)

    result = json.loads(contract.get_assessment(report_id))
    assert result["tier"] == "UNASSESSABLE"
    assert result["credibility_score"] == 0
    full = json.loads(contract.get_report(report_id))
    assert full["status"] == "UNASSESSABLE"
    assert full["tier"] == "UNASSESSABLE"
    assert "Parse error" in full["reasoning"]


def test_strengths_non_list_handled(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/source_verdict.py")

    with direct_vm.prank(direct_alice):
        report_id = contract.submit_source(
            "https://non-list.example.com/page",
            "",
        )

    direct_vm.mock_web(
        r".*non-list\.example\.com.*",
        "A blog post with a named author and one cited report, but no corrections page.",
    )
    direct_vm.mock_llm(
        r".*credibility.*analyst.*",
        _llm(
            "MODERATE",
            "BLOG",
            "CENTER",
            55,
            60,
            "Strengths arrived as a string and were dropped.",
            "some string",
            ["no corrections page"],
        ),
    )

    contract.assess_source(report_id)

    result = json.loads(contract.get_assessment(report_id))
    assert result["tier"] == "MODERATE"
    assert result["strengths"] == "[]"
    assert json.loads(result["strengths"]) == []
    assert json.loads(result["weaknesses"]) == ["no corrections page"]


def test_empty_source_url(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/source_verdict.py")
    with direct_vm.prank(direct_alice):
        with direct_vm.expect_revert("Invalid source_url"):
            contract.submit_source("", "")


def test_invalid_source_url(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/source_verdict.py")
    with direct_vm.prank(direct_alice):
        with direct_vm.expect_revert("Invalid source_url"):
            contract.submit_source("not-a-url", "")


def test_invalid_about_url(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/source_verdict.py")
    with direct_vm.prank(direct_alice):
        with direct_vm.expect_revert("Invalid about_url"):
            contract.submit_source("https://example.com", "bad-url")


def test_same_url_both_rejected(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/source_verdict.py")
    url = "https://example.com"
    with direct_vm.prank(direct_alice):
        with direct_vm.expect_revert("source_url and about_url must differ"):
            contract.submit_source(url, url)


def test_assess_already_assessed(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/source_verdict.py")

    with direct_vm.prank(direct_alice):
        report_id = contract.submit_source("https://already.example.com/story", "")

    direct_vm.mock_web(
        r".*already\.example\.com.*",
        "Named reporter, corrections footer, and links to public records in the story.",
    )
    direct_vm.mock_llm(
        r".*credibility.*analyst.*",
        _llm(
            "HIGH_CREDIBILITY",
            "NEWS_OUTLET",
            "CENTER",
            91,
            85,
            "The page shows a professional newsroom with a corrections policy.",
            ["named reporter", "corrections footer"],
            [],
        ),
    )

    contract.assess_source(report_id)
    assert json.loads(contract.get_report(report_id))["status"] == "ASSESSED"

    with direct_vm.expect_revert("not PENDING"):
        contract.assess_source(report_id)


def test_get_assessment_pending(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/source_verdict.py")
    with direct_vm.prank(direct_alice):
        report_id = contract.submit_source("https://example.com", "")
    with direct_vm.expect_revert("Not yet assessed"):
        contract.get_assessment(report_id)


def test_lookup_by_url_found(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy("contracts/source_verdict.py")
    url = "https://reuters.com"
    with direct_vm.prank(direct_alice):
        id1 = contract.submit_source(url, "")
    with direct_vm.prank(direct_bob):
        id2 = contract.submit_source(url, "https://en.wikipedia.org/wiki/Reuters")

    result = json.loads(contract.lookup_by_url(url))
    assert result.get("found") != False
    assert result.get("report_id") == id2
    assert result.get("report_id") != id1
    assert result["about_url"] == "https://en.wikipedia.org/wiki/Reuters"

    earlier = json.loads(contract.get_report(id1))
    assert earlier["report_id"] == id1
    assert earlier["about_url"] == ""


def test_lookup_by_url_not_found(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/source_verdict.py")
    result = json.loads(
        contract.lookup_by_url("https://nonexistent-source.example.com")
    )
    assert result.get("found") == False


def test_list_reports_filter(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy("contracts/source_verdict.py")

    with direct_vm.prank(direct_alice):
        high_id = contract.submit_source("https://high-news.example.com/article", "")
        low_id = contract.submit_source("https://low-news.example.com/article", "")
    with direct_vm.prank(direct_bob):
        pending_id = contract.submit_source("https://pending-news.example.com/article", "")

    direct_vm.mock_web(
        r".*high-news\.example\.com.*",
        "Reuters-style desk copy with named authors, a corrections policy, and cited records.",
    )
    direct_vm.mock_llm(
        r".*high-news\.example\.com.*",
        _llm(
            "HIGH_CREDIBILITY",
            "NEWS_OUTLET",
            "CENTER",
            89,
            91,
            "Professional newsroom signals on the high-news page.",
            ["named authors", "corrections policy"],
            [],
        ),
    )
    contract.assess_source(high_id)

    direct_vm.mock_web(
        r".*low-news\.example\.com.*",
        "SHOCKING SECRET EXPOSED!!! Anonymous post with no sources and no byline.",
    )
    direct_vm.mock_llm(
        r".*low-news\.example\.com.*",
        _llm(
            "LOW_CREDIBILITY",
            "BLOG",
            "UNKNOWN",
            18,
            80,
            "Anonymous sensationalist page with no sources.",
            [],
            ["sensationalist headline", "no authorship"],
        ),
    )
    contract.assess_source(low_id)

    high = json.loads(contract.list_reports("HIGH_CREDIBILITY"))
    low = json.loads(contract.list_reports("LOW_CREDIBILITY"))
    pending = json.loads(contract.list_reports("PENDING"))
    all_reports = json.loads(contract.list_reports(""))

    assert len(high) == 1
    assert high[0]["report_id"] == high_id
    assert high[0]["tier"] == "HIGH_CREDIBILITY"

    assert len(low) == 1
    assert low[0]["report_id"] == low_id
    assert low[0]["tier"] == "LOW_CREDIBILITY"

    assert len(pending) == 1
    assert pending[0]["report_id"] == pending_id
    assert pending[0]["status"] == "PENDING"

    assert len(all_reports) == 3


def test_invalidate_owner_only(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy("contracts/source_verdict.py")

    with direct_vm.prank(direct_alice):
        report_id = contract.submit_source(
            "https://admin-target.example.com/story",
            "",
        )

    with direct_vm.prank(direct_bob):
        with direct_vm.expect_revert("Only owner"):
            contract.invalidate_report(report_id)

    contract.invalidate_report(report_id)
    full = json.loads(contract.get_report(report_id))
    assert full["status"] == "UNASSESSABLE"
    assert full["reasoning"] == "Invalidated by admin"


def test_all_three_categoricals_stored(direct_vm, direct_deploy, direct_alice):
    contract = direct_deploy("contracts/source_verdict.py")

    with direct_vm.prank(direct_alice):
        report_id = contract.submit_source(
            "https://aggregator.example.com/roundup",
            "https://aggregator.example.com/about",
        )

    direct_vm.mock_web(
        r".*aggregator\.example\.com/roundup.*",
        "Morning roundup of links from other outlets. Headlines are republished with short blurbs.",
    )
    direct_vm.mock_web(
        r".*aggregator\.example\.com/about.*",
        "We curate links. We do not employ a reporting staff. Mild left-leaning story selection.",
    )
    direct_vm.mock_llm(
        r".*credibility.*analyst.*",
        _llm(
            "MODERATE",
            "AGGREGATOR",
            "CENTER_LEFT",
            61,
            73,
            "Link roundup with a mild left lean and no original reporting desk.",
            ["links to original outlets"],
            ["no original reporting staff"],
        ),
    )

    contract.assess_source(report_id)

    result = json.loads(contract.get_assessment(report_id))
    valid_tiers = ["HIGH_CREDIBILITY", "MODERATE", "LOW_CREDIBILITY", "UNASSESSABLE"]
    valid_types = [
        "NEWS_OUTLET",
        "ACADEMIC",
        "OFFICIAL_DOCS",
        "BLOG",
        "SOCIAL_MEDIA",
        "AGGREGATOR",
        "UNKNOWN",
    ]
    valid_bias = [
        "LEFT",
        "CENTER_LEFT",
        "CENTER",
        "CENTER_RIGHT",
        "RIGHT",
        "UNKNOWN",
        "NA",
    ]
    assert result["tier"] in valid_tiers
    assert result["source_type"] in valid_types
    assert result["bias_direction"] in valid_bias
    assert result["tier"] == "MODERATE"
    assert result["source_type"] == "AGGREGATOR"
    assert result["bias_direction"] == "CENTER_LEFT"
    assert result["tier"] != ""
    assert result["source_type"] != ""
    assert result["bias_direction"] != ""
