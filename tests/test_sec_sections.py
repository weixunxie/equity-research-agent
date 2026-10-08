"""Section extraction from filing text: the real section must win over the
table of contents and over cross-references in running prose."""
from backend.tools.sec_edgar import extract_mda, extract_section

FILLER = "Lorem ipsum dolor sit amet. "
BUSINESS = "We design and sell widgets to enterprises. " * 60
RISKS = "Our supply chain is concentrated in one region. " * 80
MDA = "Revenue increased 12% on higher widget volumes. " * 90

TEN_K = " ".join(
    [
        # Table of contents: every heading appears once, followed by a page number.
        "Table of Contents Item 1. Business 3 Item 1A. Risk Factors 9 Item 1B. Unresolved"
        " Staff Comments 20 Item 7. Management's Discussion and Analysis of Financial"
        " Condition 30 Item 7A. Quantitative and Qualitative Disclosures 45 Item 8."
        " Financial Statements 47",
        "PART I Item 1. Business",
        BUSINESS,
        # A cross-reference inside Item 1 must not start the Risk Factors section.
        "For more, see “Item 1A. Risk Factors” and Part II, Item 7. Management’s Discussion"
        " and Analysis below.",
        "Item 1A. Risk Factors",
        RISKS,
        "Item 1B. Unresolved Staff Comments None.",
        "Item 2. Properties We lease our headquarters.",
        "PART II Item 7. Management’s Discussion and Analysis of Financial Condition",
        MDA,
        # A cross-reference to Item 8 inside the MD&A must not end it early.
        "Refer to Item 8. Financial Statements for the full notes.",
        MDA,
        "Item 7A. Quantitative and Qualitative Disclosures About Market Risk",
        FILLER * 20,
        "Item 8. Financial Statements and Supplementary Data",
        FILLER * 20,
        # A late cross-reference with no closing heading after it.
        "As discussed in Item 1A. Risk Factors, results may vary.",
    ]
)


def test_business_section_is_the_real_one():
    section = extract_section(TEN_K, "10-K", "business")
    assert section.startswith("Item 1. Business We design")
    assert "Our supply chain" not in section


def test_risk_factors_skips_toc_and_cross_references():
    section = extract_section(TEN_K, "10-K", "risk_factors")
    assert section.startswith("Item 1A. Risk Factors Our supply chain")
    assert "We design and sell widgets" not in section  # didn't start at the cross-reference
    assert "Unresolved Staff Comments" not in section


def test_mda_runs_to_item_7a_not_to_a_cross_reference():
    section = extract_mda(TEN_K, "10-K")
    assert section.startswith("Item 7. Management’s Discussion")
    assert section.count("Revenue increased 12%") == 180  # both halves, past the Item 8 mention
    assert "Quantitative and Qualitative" not in section


def test_ten_q_mda_uses_item_2():
    text = " ".join(
        [
            "Item 2. Management's Discussion and Analysis 14 Item 3. Quantitative 20",
            "Item 2. Management's Discussion and Analysis of Financial Condition",
            MDA,
            "Item 3. Quantitative and Qualitative Disclosures About Market Risk",
            FILLER * 10,
            "Item 4. Controls and Procedures",
        ]
    )
    section = extract_mda(text, "10-Q")
    assert section.startswith("Item 2. Management's Discussion and Analysis of Financial")
    assert "Controls and Procedures" not in section


def test_twenty_f_sections():
    text = " ".join(
        [
            "ITEM 3. KEY INFORMATION Risk Factors",
            RISKS,
            "ITEM 4. INFORMATION ON THE COMPANY",
            BUSINESS,
            "ITEM 4A. UNRESOLVED STAFF COMMENTS None.",
            "ITEM 5. OPERATING AND FINANCIAL REVIEW AND PROSPECTS",
            MDA,
            "ITEM 6. DIRECTORS, SENIOR MANAGEMENT AND EMPLOYEES",
        ]
    )
    assert extract_section(text, "20-F", "risk_factors").startswith("Risk Factors Our supply")
    assert extract_section(text, "20-F", "business").startswith("ITEM 4. INFORMATION")
    assert extract_mda(text, "20-F").startswith("ITEM 5. OPERATING")


def test_missing_or_tiny_sections_return_empty():
    assert extract_section("", "10-K", "mda") == ""
    assert extract_section("Item 1A. Risk Factors None. Item 1B. Unresolved", "10-K", "risk_factors") == ""
    assert extract_section(TEN_K, "8-K", "mda") == ""
