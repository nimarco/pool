"""Real ingestion pipeline, synthetic dataset — and the line between those two things.

The demo turns on one claim: Pool's answer changes when the world changes rather than
when the demand does. Something external has to arrive for that to be demonstrable, and
two hardcoded buttons made the mechanism honest and the presentation indistinguishable
from a switch. So the terms arrive as a file now, and the file is really read.

What these tests hold in place is the conflict, because it is the interesting part and it
is easy to resolve in the wrong direction.

This build refuses client-submitted economics on purpose: ``SupplierQuoteRequest`` sets
``extra="forbid"`` so a request that *tries* to send a price is rejected rather than
quietly stripped. An unrestricted upload endpoint hands that authority straight back, and
``$0.01`` rice would make Pool look brilliant while proving nothing.

The resolution splits one question into two:

* **Is the pipeline real?** Always, everywhere. Bytes are read, ``csv`` runs, the schema
  is checked, and malformed rows fail with the line number and the reason.
* **Whose numbers may become offer rows?** On a deployment strangers can reach, only
  bytes whose digest is committed in ``demo-data/MANIFEST.json``.

So the parse is honest either way and only the write is gated — which is why a refusal
still reports what the file contained.
"""

from __future__ import annotations

import importlib
import json
import os
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from pool.api import app as api
from pool.services import coordination as coord
from pool.services import supplier_import as si

FIXTURE = os.path.join(si.DEMO_DATA_DIR, "supplier_quotes.csv")
RICE = "prod_rice_jasmine"


@pytest.fixture
def committed() -> bytes:
    with open(FIXTURE, "rb") as handle:
        return handle.read()


@pytest.fixture
def client() -> TestClient:
    api._repo.reset("demo")
    c = TestClient(api.app)
    c.get("/api/state")
    return c


def _upload(client: TestClient, data: bytes, name: str = "supplier_quotes.csv"):
    return client.post(
        "/api/demo/supplier-import",
        files={"file": (name, data, "text/csv")},
    )


# ------------------------------------------------------------------ the file itself


def test_the_committed_fixture_is_the_one_the_manifest_names(committed):
    """A judge downloads this file and uploads it. If the digest has drifted, the demo
    refuses its own fixture — so the digest is checked in, not computed at start-up."""
    entry = si.manifest().get("supplier_quotes.csv")
    assert entry is not None, "the fixture is not in demo-data/MANIFEST.json"
    assert entry["sha256"] == si.digest(committed)
    assert entry["bytes"] == len(committed)
    assert si.allowlisted(committed) == "supplier_quotes.csv"


def test_the_fixture_says_what_it_is(committed):
    """It is committed so somebody can read it, and the first thing they should read is
    that Riverbend Wholesale does not exist."""
    text = committed.decode("utf-8")
    assert "does not exist" in text
    assert "synthetic" in text
    # And it carries terms only. There is nowhere in this format to state an outcome.
    header = next(line for line in text.splitlines() if line.startswith("product_id"))
    for forbidden in ("viable", "saving", "verdict", "expected", "outcome"):
        assert forbidden not in header


def test_editing_one_price_changes_the_digest(committed):
    """The property the public gate rests on. Not a filename check — a filename is what
    an uploader chooses and a digest is what the bytes are."""
    tampered = committed.replace(b"625", b"1")
    assert tampered != committed
    assert si.allowlisted(tampered) == ""
    # Still perfectly parseable, which is the point: it is refused for authority, not
    # for being unreadable.
    assert len(si.parse(tampered).rows) == 2


# ------------------------------------------------------------------ the parser


def test_the_committed_quotes_parse_to_the_terms_they_state(committed):
    result = si.parse(committed, "supplier_quotes.csv")
    assert result.rejected == []
    assert [(r.unit_price_cents, r.case_units, r.min_units) for r in result.rows] == [
        (975, 4, 12),
        (625, 8, 16),
    ]
    assert {r.product_id for r in result.rows} == {RICE}
    assert all(r.to_dict()["synthetic"] is True for r in result.rows)


def test_a_malformed_row_fails_and_names_its_line():
    """The rows really can fail, and a real quote sheet with one bad line is ordinary —
    so a bad row costs one row and reports where to look, rather than the whole file."""
    csv_bytes = b"""# a sheet with problems
product_id,supplier_id,unit_price_cents,case_units,min_units,supplier_reference
prod_rice_jasmine,sup_riverbend,notanumber,4,12,A
prod_rice_jasmine,sup_riverbend,-5,4,12,B
prod_rice_jasmine,sup_riverbend,975,4,,C
,sup_riverbend,975,4,12,D
prod_rice_jasmine,sup_riverbend,975,4,12,E
"""
    result = si.parse(csv_bytes, "bad.csv")
    assert len(result.rows) == 1
    assert result.rows[0].supplier_reference == "E"
    reasons = {r.line: r.reason for r in result.rejected}
    assert len(reasons) == 4
    assert "not a whole number" in reasons[3]
    assert "greater than zero" in reasons[4]
    assert "min_units is missing" in reasons[5]
    assert "product_id is missing" in reasons[6]


@pytest.mark.parametrize(
    ("data", "message"),
    [
        (b"", "no rows"),
        (b"# only a comment\n", "no rows"),
        (b"a,b,c\n1,2,3\n", "header is missing"),
        (b"\xff\xfe\x00bad", "not UTF-8"),
    ],
)
def test_a_file_that_cannot_be_used_says_which_way_it_failed(data, message):
    with pytest.raises(si.SupplierImportError) as exc:
        si.parse(data, "x.csv")
    assert message in str(exc.value)


def test_an_enormous_file_is_refused_before_it_is_parsed():
    with pytest.raises(si.SupplierImportError) as exc:
        si.parse(b"x" * (si.MAX_BYTES + 1), "big.csv")
    assert "limit" in str(exc.value)


def test_re_importing_the_same_sheet_refreshes_rather_than_accumulating(committed):
    """Two imports of one quote must not leave Pool believing it has two tiers, which
    would double the supply the evaluator thinks exists."""
    rows = si.parse(committed).rows
    assert len({r.offer_id for r in rows}) == 2
    assert si.parse(committed).rows[0].offer_id == rows[0].offer_id


# ---------------------------------------------------- what the workspace can hold


def test_a_quote_for_an_unknown_product_is_refused_and_creates_nothing(seeded_ctx):
    """Importing a *quote* must never bring a product into existence. Identity and
    economics are separate on purpose, and a supplier sheet is not evidence that a
    product exists."""
    rows = si.parse(
        b"product_id,supplier_id,unit_price_cents,case_units,min_units,supplier_reference\n"
        b"prod_invented_thing,sup_riverbend,100,4,12,X\n"
    ).rows
    before = {p.id for p in seeded_ctx.repo.list_products(seeded_ctx.ws)}
    usable, rejected = si.resolvable(seeded_ctx, rows)
    assert usable == []
    assert "no product prod_invented_thing" in rejected[0].reason
    assert {p.id for p in seeded_ctx.repo.list_products(seeded_ctx.ws)} == before


def test_a_quote_from_an_unknown_supplier_is_refused(seeded_ctx):
    rows = si.parse(
        b"product_id,supplier_id,unit_price_cents,case_units,min_units,supplier_reference\n"
        b"prod_rice_jasmine,sup_nobody,100,4,12,X\n"
    ).rows
    usable, rejected = si.resolvable(seeded_ctx, rows)
    assert usable == []
    assert "no supplier sup_nobody" in rejected[0].reason


# ------------------------------------------------------------------ the endpoint


def test_uploading_the_committed_sheet_records_ordinary_offers(client, committed):
    response = _upload(client, committed)
    assert response.status_code == 200, response.text
    body = response.json()

    # The file, as read. Not a canned summary: the byte count and digest are the
    # uploaded bytes'.
    assert body["recorded"] is True
    assert body["allowlisted_as"] == "supplier_quotes.csv"
    assert body["filename"] == "supplier_quotes.csv"
    assert body["bytes"] == len(committed)
    assert body["sha256"] == si.digest(committed)
    assert (body["rows_found"], body["valid"], body["rejected"]) == (2, 2, 0)
    assert all(o["source"] == "synthetic" for o in body["offers"])

    # Ordinary bulk offers, visible to the same `offers_for` every price comes from.
    ctx = api.ctx_for("demo")
    _, bulk = coord.offers_for(ctx, RICE)
    assert {o.supplier_reference for o in bulk} == {"QUOTE-RICE-SPLIT", "QUOTE-RICE-CASE"}


def test_a_file_with_bad_rows_writes_the_good_ones_and_reports_the_rest(client):
    """The pipeline is real, so a partial sheet behaves like a partial sheet."""
    response = _upload(
        client,
        b"product_id,supplier_id,unit_price_cents,case_units,min_units,supplier_reference\n"
        b"prod_rice_jasmine,sup_riverbend,oops,4,12,BAD\n"
        b"prod_rice_jasmine,sup_riverbend,625,8,16,GOOD\n",
        "partial.csv",
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["valid"], body["rejected"]) == (1, 1)
    assert body["rejections"][0]["line"] == 2
    assert len(body["offers"]) == 1
    assert body["offers"][0]["supplier_reference"] == "GOOD"


def test_an_unreadable_file_is_a_refusal_with_a_reason(client):
    response = _upload(client, b"nothing useful here", "junk.csv")
    assert response.status_code == 400
    assert "header is missing" in response.json()["detail"]


def test_the_import_cannot_reach_a_showcase_partition(client, committed):
    """The showcase is a recording, and every figure quoted about it is a claim about
    that world. A supplier fact written into it changes the product universe of the
    recording, silently."""
    response = client.post(
        "/api/demo/supplier-import?workspace=demo-showcase",
        files={"file": ("supplier_quotes.csv", committed, "text/csv")},
    )
    assert response.status_code in (400, 422)
    if response.status_code == 400:
        assert "showcase" in response.json()["detail"].lower()


# -------------------------------------------- the changed world, through the file


def _declare_rice(client: TestClient) -> tuple[str, str]:
    client.post(
        "/api/onboarding", json={"display_name": "Marco", "autonomy_mode": "ask_me"}
    )
    household = client.get("/api/state").json()["consumer"]["household_id"]
    due = date.today() + timedelta(days=12)
    need = client.post(
        "/api/needs",
        json={
            "household_id": household,
            "product_id": RICE,
            "quantity": 2,
            "cadence_days": 30,
            "expected_next_need_date": due.isoformat(),
            "flexibility_days": 11,
            "max_spend_cents": 9000,
        },
    )
    assert need.status_code == 200, need.text
    return household, need.json()["need_id"]


def _outlook(client: TestClient, household: str, need_id: str) -> dict:
    view = client.get(f"/api/members/{household}").json()
    return next(o for o in view["needs_outlook"] if o["need_id"] == need_id)


def test_the_file_is_what_changes_the_answer(client, committed):
    """The whole sequence, and the demand never moves.

    Nothing about people changes between these two reads: no buyer, no declaration, no
    membership, no household. One file arrives, and the deterministic evaluator reaches a
    different conclusion from the same demand — which is the claim, and the reason it is
    worth the minute it costs.
    """
    household, need_id = _declare_rice(client)
    before = _outlook(client, household, need_id)
    assert before["state"] == "no_supply"
    assert before["status"] == "watching"
    assert before["headline"] == "No verified supplier yet"

    counts = client.get("/api/state").json()["counts"]
    needs_before = client.get("/api/needs").json()["needs"]

    assert _upload(client, committed).json()["recorded"] is True

    after = _outlook(client, household, need_id)
    # A different answer, from the same people.
    assert after["state"] != before["state"]
    assert after["status"] == "watching"

    # Proof that no demand was injected: the members, the declarations and every stored
    # declaration row are identical either side of the import.
    assert client.get("/api/state").json()["counts"] == counts
    assert client.get("/api/needs").json()["needs"] == needs_before


def test_importing_the_file_runs_no_agent(client, committed):
    """One offer row, and nothing that costs money or invents a verdict."""
    before = len(client.get("/api/state").json()["runs"])
    _upload(client, committed)
    assert len(client.get("/api/state").json()["runs"]) == before


def test_the_import_touches_only_the_offer_table(client, committed):
    """The same snapshot discipline `test_supplier_updates.py` applies to the button."""

    def snapshot() -> dict:
        state = client.get("/api/state").json()
        return {
            "pools": state["pools"],
            "decisions": state["decisions"],
            "counts": state["counts"],
            "needs": client.get("/api/needs").json()["needs"],
        }

    before = snapshot()
    _upload(client, committed)
    assert snapshot() == before


# ------------------------------------------------------- the public-demo gate


@pytest.fixture
def public_api(monkeypatch):
    """A reloaded API module with judge mode on.

    The module builds its repository, settings and guard at import time, so the only
    honest way to test the deployed configuration is to import it under that
    configuration — the same fixture `test_public_demo.py` uses, for the same reason.
    """
    monkeypatch.setenv("POOL_PUBLIC_DEMO", "true")
    monkeypatch.delenv("PUBLIC_DEMO_WEB_ROOT", raising=False)
    monkeypatch.delenv("AGENTCORE_RUNTIME_ARN", raising=False)
    monkeypatch.delenv("DYNAMODB_TABLE", raising=False)
    from pool.api import app as reloaded

    module = importlib.reload(reloaded)
    yield module
    monkeypatch.undo()
    importlib.reload(reloaded)


#: A workspace id the public allowlist's pattern accepts.
PUBLIC_WS = "wjudge0000001"


def _public_upload(module, data: bytes, name: str = "supplier_quotes.csv"):
    client = TestClient(module.app)
    client.get(f"/api/state?workspace={PUBLIC_WS}")
    return client.post(
        f"/api/demo/supplier-import?workspace={PUBLIC_WS}",
        files={"file": (name, data, "text/csv")},
    )


def test_a_public_deployment_refuses_bytes_it_cannot_audit(public_api, committed):
    """A judge who edits a price is told that is what was detected — and still sees what
    their file contained, because "rejected" and "unreadable" are different facts."""
    tampered = committed.replace(b"625", b"1")
    response = _public_upload(public_api, tampered)
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["recorded"] is False
    assert body["refused"] == "not_allowlisted"
    assert body["offers"] == []
    # The parse still happened, and says so.
    assert body["valid"] == 2
    assert body["records"][1]["unit_price_cents"] == 1
    assert "cannot become an offer" in body["reason"]

    # And nothing was written.
    ctx = public_api.ctx_for(PUBLIC_WS)
    _, bulk = coord.offers_for(ctx, RICE)
    assert bulk == []


def test_a_public_deployment_still_accepts_the_committed_sheet(public_api, committed):
    """The property that makes the gate honest rather than a locked door: the file in the
    repository is the file that works — under whatever name it was saved as, because the
    check is on the bytes."""
    response = _public_upload(public_api, committed, "whatever-they-renamed-it.csv")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["recorded"] is True
    assert body["allowlisted_as"] == "supplier_quotes.csv"
    assert len(body["offers"]) == 2


def test_a_missing_manifest_fails_closed(monkeypatch, committed):
    """Absent means nothing is allowlisted, not everything. A public deployment whose
    manifest failed to ship refuses every upload rather than accepting every upload."""
    monkeypatch.setattr(si, "MANIFEST_PATH", "/nonexistent/MANIFEST.json")
    assert si.manifest() == {}
    assert si.allowlisted(committed) == ""


def test_the_manifest_is_valid_json_and_names_only_files_that_exist():
    with open(si.MANIFEST_PATH, encoding="utf-8") as handle:
        payload = json.load(handle)
    assert payload["algorithm"] == "sha256"
    assert payload["files"]
    for name in payload["files"]:
        assert os.path.isfile(os.path.join(si.DEMO_DATA_DIR, name)), name


def test_the_metadata_endpoint_is_not_on_the_public_allowlist(public_api):
    """The browser does not need it: the path is a constant and the digests are committed
    where a judge reads them. A door added for convenience is still a door."""
    c = TestClient(public_api.app)
    assert c.get(f"/api/demo/supplier-file?workspace={PUBLIC_WS}").status_code == 404


def test_the_operator_screen_can_name_the_file_it_expects(client):
    body = client.get("/api/demo/supplier-file").json()
    assert body["path"] == "demo-data/supplier_quotes.csv"
    assert "unit_price_cents" in body["columns"]
    assert body["allowlisted"][0]["filename"] == "supplier_quotes.csv"
    assert body["synthetic"] is True
