"""Parse one observed OpenInsider cluster page without manufacturing missing evidence."""
from __future__ import annotations

import math
import re
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse


class ClusterPage(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.tables, self.links, self.text = [], [], [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table":
            if self.stack:
                self.stack[-1]["malformed"] = True
            self.stack.append({"rows": [], "row": None, "cell": None,
                               "closed": False, "malformed": False})
        elif tag == "a":
            self.links.append((attrs.get("href", ""), attrs.get("rel", "")))
        elif self.stack:
            table = self.stack[-1]
            if tag == "tr":
                if table["row"] is not None:
                    table["malformed"] = True
                table["row"], table["cell"] = [], None
            elif tag in {"td", "th"}:
                if table["row"] is None or table["cell"] is not None:
                    table["malformed"] = True
                table["cell"] = []

    def handle_endtag(self, tag):
        if not self.stack:
            return
        table = self.stack[-1]
        if tag in {"td", "th"}:
            if table["cell"] is None or table["row"] is None:
                table["malformed"] = True
            else:
                table["row"].append(" ".join("".join(table["cell"]).split()))
            table["cell"] = None
        elif tag == "tr":
            if table["cell"] is not None or table["row"] is None:
                table["malformed"] = True
            elif table["row"]:
                table["rows"].append(table["row"])
            table["row"], table["cell"] = None, None
        elif tag == "table":
            table["closed"] = table["row"] is None and table["cell"] is None
            self.tables.append(self.stack.pop())

    def handle_data(self, data):
        self.text.append(data)
        if self.stack and self.stack[-1]["cell"] is not None:
            self.stack[-1]["cell"].append(data)


def cluster_money(value, purchase):
    match = re.fullmatch(r"([+-]?)\$?((?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]{1,2})?)", value)
    if match is None:
        raise ValueError("invalid_transaction_value")
    amount = float(match.group(1) + match.group(2).replace(",", ""))
    if not math.isfinite(amount) or (purchase and amount < 0):
        raise ValueError("invalid_transaction_value")
    return amount


def cluster_date(value, *, filing=False):
    formats = ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S"] if filing else ["%Y-%m-%d"]
    for fmt in formats:
        try:
            parsed = datetime.strptime(value, fmt)
        except ValueError:
            continue
        if parsed.strftime(fmt) == value:
            return parsed
    raise ValueError("invalid_event_date")


def parse_cluster_page(html, *, observed_date, response_url, min_insiders=2):
    """Prove the returned page's scope and keep valid siblings beside invalid rows."""
    if type(min_insiders) is not int or min_insiders < 1:
        raise ValueError("min_insiders must be a positive integer")
    observed = cluster_date(observed_date).date()
    scope = urlparse(response_url or "")
    proof = {"scope": "returned_latest_cluster_buys_page", "table_rows": 0,
             "valid_rows": 0, "invalid_rows": 0, "excluded_rows": 0,
             "explicit_zero": False, "additional_results": False}
    def result(status, reasons, records=()):
        return {"records": list(records), "status": status,
                "reasons": sorted(set(reasons)), "proof": proof}
    if (not isinstance(html, str) or scope.scheme not in {"http", "https"}
            or scope.hostname not in {"openinsider.com", "www.openinsider.com"}
            or scope.path.rstrip("/") != "/latest-cluster-buys"):
        return result("unavailable", ["unproved_cluster_response_scope"])
    parser = ClusterPage()
    parser.feed(html)
    parser.close()
    tables = parser.tables + parser.stack
    required = {"filing date", "trade date", "ticker", "company name", "ins", "trade type", "value"}
    matches = []
    for table in tables:
        for index, row in enumerate(table["rows"]):
            labels = [cell.casefold() for cell in row]
            if required <= set(labels):
                matches.append((table, index, labels))
    if len(matches) != 1:
        return result("unavailable", ["unrecognized_or_ambiguous_cluster_table"])
    table, header_index, labels = matches[0]
    if (not table["closed"] or table["malformed"]
            or any(labels.count(label) != 1 for label in required)):
        return result("unavailable", ["malformed_cluster_table"])
    columns = {label: labels.index(label) for label in required}
    for href, rel in parser.links:
        target = urlparse(urljoin(response_url, href))
        if (target.hostname == scope.hostname and target.path.rstrip("/") == scope.path.rstrip("/")
                and (("next" in rel.casefold().split()) or re.search(r"(?:[?&])(?:page|offset|start)=[1-9][0-9]*", target.query and "?" + target.query))):
            proof["additional_results"] = True
    rows = table["rows"][header_index + 1:]
    zeros = [row for row in rows if len(row) == 1 and row[0].casefold().rstrip(".") in {
        "no results", "no results found", "no matching records", "no matching transactions found"}]
    proof["explicit_zero"] = bool(zeros)
    displayed = re.findall(r"showing\s+([0-9,]+)\s+(?:to|-)\s+([0-9,]+)\s+of\s+([0-9,]+)",
                           " ".join(parser.text), re.I)
    page_reasons, totals = [], []
    returned_count = 0 if zeros else len(rows)
    for lower, upper, total in displayed:
        if any(re.fullmatch(r"(?:0|[1-9][0-9]*|[1-9][0-9]{0,2}(?:,[0-9]{3})+)", value) is None
               for value in (lower, upper, total)):
            page_reasons.append("invalid_cluster_result_total")
            continue
        lower, upper, total = (int(value.replace(",", "")) for value in (lower, upper, total))
        totals.append(total)
        if total > returned_count:
            proof["additional_results"] = True
        if ((total == 0 and (lower != 0 or upper != 0 or returned_count != 0))
                or (total > 0 and not 1 <= lower <= upper <= total)
                or (total > 0 and upper - lower + 1 != returned_count)
                or total < returned_count):
            page_reasons.append("contradictory_cluster_result_total")
    if len(set(totals)) > 1:
        page_reasons.append("contradictory_cluster_result_total")
    if proof["additional_results"]:
        page_reasons.append("cluster_pagination_incomplete")
    if zeros:
        if len(zeros) != 1 or len(rows) != 1:
            return result("partial", ["contradictory_empty_cluster_table"])
        if page_reasons:
            return result("partial", page_reasons)
        return result("complete", [])
    if not rows:
        return result("unavailable", ["header_only_without_zero_evidence"])
    reasons, by_ticker = page_reasons, {}
    proof["table_rows"] = len(rows)
    for row in rows:
        try:
            if len(row) != len(labels):
                raise ValueError("invalid_cluster_row_width")
            get = lambda key: row[columns[key]]
            raw_ticker = get("ticker")
            if not raw_ticker.isascii() or re.fullmatch(r"[A-Za-z][A-Za-z0-9.-]{0,14}", raw_ticker) is None:
                raise ValueError("invalid_event_ticker")
            ticker, name = raw_ticker.upper(), get("company name")
            if not name:
                raise ValueError("missing_event_company")
            if re.fullmatch(r"[0-9]+", get("ins")) is None or int(get("ins")) < 1:
                raise ValueError("invalid_insider_count")
            insiders = int(get("ins"))
            code = re.fullmatch(r"([PSADFGIMCEOWUXZ])(?:\s*-\s*[A-Za-z][A-Za-z /-]*)?", get("trade type"))
            if code is None:
                raise ValueError("invalid_trade_type")
            filing = cluster_date(get("filing date"), filing=True)
            trade = cluster_date(get("trade date"))
            if not trade.date() <= filing.date() <= observed:
                raise ValueError("invalid_event_chronology")
            value = cluster_money(get("value"), code[1] == "P")
            proof["valid_rows"] += 1
            if code[1] != "P" or insiders < min_insiders:
                proof["excluded_rows"] += 1
                continue
            record = {"ticker": ticker, "name": name, "n_insiders": insiders,
                      "value": value, "filing_date": filing.date().isoformat(),
                      "trade_date": trade.date().isoformat(),
                      "filing_timestamp": filing.isoformat()}
            previous = by_ticker.get(ticker)
            if previous is not None and previous["filing_timestamp"] == record["filing_timestamp"] and previous != record:
                reasons.append("conflicting_cluster_rows")
            elif previous is None or record["filing_timestamp"] > previous["filing_timestamp"]:
                by_ticker[ticker] = record
        except (ValueError, OverflowError) as exc:
            proof["invalid_rows"] += 1
            reasons.append(str(exc))
    if proof["additional_results"]:
        reasons.append("cluster_pagination_incomplete")
    return result("partial" if reasons else "complete", reasons,
                  sorted(by_ticker.values(), key=lambda row: row["filing_timestamp"], reverse=True))
