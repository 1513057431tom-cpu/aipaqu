from app.core.browser_collection import CloakBrowserFetcher


class CandidateLocator:
    def __init__(self) -> None:
        self.script = ""

    def evaluate_all(self, script: str) -> list[dict]:
        self.script = script
        return [
            {
                "id": 0,
                "tag": "input",
                "text": "",
                "type": "search",
                "role": "",
                "placeholder": "搜索物料",
                "aria_label": "",
                "href": "",
            }
        ]


class CandidatePage:
    def __init__(self) -> None:
        self.candidate_locator = CandidateLocator()

    def locator(self, selector: str) -> CandidateLocator:
        assert selector == "input, button, a, [role=tab], [role=button]"
        return self.candidate_locator


def test_candidates_are_extracted_in_one_browser_evaluation() -> None:
    page = CandidatePage()

    candidates = CloakBrowserFetcher._candidates(page)

    assert candidates[0]["placeholder"] == "搜索物料"
    assert "slice(0, 80)" in page.candidate_locator.script
