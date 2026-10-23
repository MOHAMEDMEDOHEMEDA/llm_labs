from week1_brochure.links import candidate_links, canonical

SITE = "https://www.acme.test/"


def test_keeps_same_site_subdomains_and_job_boards_in_page_order():
    links = [
        "https://www.acme.test/about",
        "https://blog.acme.test/company",
        "https://jobs.lever.co/acme",
        "https://twitter.com/acme",
        "https://notacme.test/about",
    ]
    assert candidate_links(links, SITE, limit=10) == [
        "https://www.acme.test/about",
        "https://blog.acme.test/company",
        "https://jobs.lever.co/acme",
    ]


def test_drops_legal_auth_and_file_links():
    links = [
        "https://acme.test/privacy-policy",
        "https://acme.test/terms",
        "https://acme.test/login",
        "https://acme.test/report.pdf",
        "https://acme.test/logo.PNG",
        "https://acme.test/careers",
    ]
    assert candidate_links(links, SITE, limit=10) == ["https://acme.test/careers"]


def test_drops_the_landing_page_and_duplicates():
    links = [
        "https://www.acme.test",
        "https://www.acme.test/about",
        "https://www.acme.test/about/",
        "HTTPS://WWW.ACME.TEST/about",
    ]
    assert candidate_links(links, SITE, limit=10) == ["https://www.acme.test/about"]


def test_respects_limit():
    links = [f"https://acme.test/page{i}" for i in range(20)]
    assert len(candidate_links(links, SITE, limit=5)) == 5


def test_canonical_ignores_case_trailing_slash_and_fragment():
    assert canonical("HTTPS://Acme.test/About/#team") == canonical("https://acme.test/About")
    assert canonical("https://acme.test/a?x=1") != canonical("https://acme.test/a?x=2")
