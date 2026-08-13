from __future__ import annotations

import hashlib
import http.client
import ipaddress
import re
import socket
import ssl
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from datetime import timedelta
from enum import Enum
from html.parser import HTMLParser
from itertools import count
from threading import RLock
from typing import Protocol
from urllib.parse import urljoin, urlparse
from uuid import uuid4

class SourceStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"


class SignalType(str, Enum):
    PRICE = "PRICE"
    SPECIFICATION = "SPECIFICATION"
    AVAILABILITY = "AVAILABILITY"
    LEAD_TIME = "LEAD_TIME"
    SUPPLIER_EVENT = "SUPPLIER_EVENT"


class CollectionStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    WAITING_HUMAN = "WAITING_HUMAN"


class ReviewStatus(str, Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    DISMISSED = "DISMISSED"


class DuplicateSourceUrlError(ValueError):
    pass


@dataclass(frozen=True)
class Source:
    id: str
    workspace_id: str
    name: str
    target_url: str
    allowed_domain: str
    schedule_minutes: int
    signal_type: SignalType
    material_id: str | None
    supplier_id: str | None
    extraction_selector: str
    status: SourceStatus
    last_collected_at: datetime | None
    last_collection_status: CollectionStatus | None
    last_content_digest: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class Document:
    id: str
    workspace_id: str
    source_id: str
    collection_job_id: str
    final_url: str
    status_code: int
    content_type: str
    title: str
    extracted_text: str
    content_digest: str
    previous_content_digest: str | None
    changed: bool
    collected_at: datetime


@dataclass(frozen=True)
class CollectionJob:
    id: str
    workspace_id: str
    source_id: str
    status: CollectionStatus
    started_at: datetime
    finished_at: datetime
    status_code: int | None
    document_id: str | None
    content_changed: bool
    error_code: str | None
    error_message: str | None


@dataclass(frozen=True)
class ExternalSignal:
    id: str
    workspace_id: str
    source_id: str
    document_id: str
    signal_type: SignalType
    material_id: str | None
    supplier_id: str | None
    binding_key: str
    occurred_at: datetime
    observed_at: datetime
    previous_value: str
    current_value: str
    confidence: float
    evidence_ref: str
    review_status: ReviewStatus
    reviewed_by: str | None
    reviewed_at: datetime | None
    content_digest: str


@dataclass(frozen=True)
class FetchResult:
    final_url: str
    status_code: int
    content_type: str
    body: bytes


@dataclass(frozen=True)
class CollectionResult:
    job: CollectionJob
    document: Document | None
    signal: ExternalSignal | None


class Fetcher(Protocol):
    def fetch(self, url: str, allowed_domain: str) -> FetchResult: ...


class MonitoringStore(Protocol):
    def all_sources(self) -> list[Source]: ...
    def create_source(self, source: Source) -> Source: ...
    def get_source(self, workspace_id: str, source_id: str) -> Source | None: ...
    def list_sources(self, workspace_id: str) -> list[Source]: ...
    def get_latest_document(self, workspace_id: str, source_id: str) -> Document | None: ...
    def save_collection(self, source: Source, job: CollectionJob, document: Document | None, signal: ExternalSignal | None) -> None: ...
    def list_jobs(self, workspace_id: str, source_id: str | None = None) -> list[CollectionJob]: ...
    def list_signals(self, workspace_id: str, source_id: str | None = None) -> list[ExternalSignal]: ...
    def get_signal(self, workspace_id: str, signal_id: str) -> ExternalSignal | None: ...
    def update_signal_review(self, signal: ExternalSignal) -> ExternalSignal: ...
    def get_document(self, workspace_id: str, document_id: str) -> Document | None: ...


def _is_public_ip(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_public_url(url: str, allowed_domain: str) -> tuple[str, str]:
    parsed = urlparse(url.strip())
    domain = allowed_domain.strip().lower().rstrip(".")
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme not in {"http", "https"} or not hostname or parsed.username or parsed.password:
        raise ValueError("Only credential-free HTTP and HTTPS URLs are supported.")
    expected_port = 443 if parsed.scheme == "https" else 80
    if parsed.port not in {None, expected_port}:
        raise ValueError("Only standard HTTP and HTTPS ports are supported.")
    if hostname != domain and not hostname.endswith(f".{domain}"):
        raise ValueError("Target URL host is outside the allowed domain.")
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise ValueError("Local addresses cannot be monitored.")
    try:
        if not _is_public_ip(hostname):
            raise ValueError("Private or reserved addresses cannot be monitored.")
    except ValueError as exc:
        if re.fullmatch(r"[0-9a-fA-F:.]+", hostname):
            raise ValueError("Invalid or non-public IP address.") from exc
    return parsed.geturl(), domain


def resolve_public_host(hostname: str) -> list[str]:
    addresses = sorted({item[4][0] for item in socket.getaddrinfo(hostname, None)})
    if not addresses or any(not _is_public_ip(address) for address in addresses):
        raise ValueError("Target host resolved to a non-public address.")
    return addresses


class SafeHttpFetcher:
    def __init__(self, timeout_seconds: float = 20, max_bytes: int = 2 * 1024 * 1024) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_bytes = max_bytes

    def fetch(self, url: str, allowed_domain: str) -> FetchResult:
        current_url, domain = validate_public_url(url, allowed_domain)
        for _ in range(5):
            parsed = urlparse(current_url)
            hostname = parsed.hostname or ""
            address = resolve_public_host(hostname)[0]
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            connection: http.client.HTTPConnection | None = None
            raw_socket: socket.socket | None = None
            path = parsed.path or "/"
            if parsed.query:
                path = f"{path}?{parsed.query}"
            try:
                raw_socket = socket.create_connection(
                    (address, port),
                    timeout=self.timeout_seconds,
                )
                if parsed.scheme == "https":
                    context = ssl.create_default_context()
                    connection = http.client.HTTPSConnection(
                        hostname,
                        port,
                        timeout=self.timeout_seconds,
                        context=context,
                    )
                    connection.sock = context.wrap_socket(
                        raw_socket,
                        server_hostname=hostname,
                    )
                else:
                    connection = http.client.HTTPConnection(
                        hostname,
                        port,
                        timeout=self.timeout_seconds,
                    )
                    connection.sock = raw_socket
                connection.request(
                    "GET",
                    path,
                    headers={
                        "User-Agent": "AipaquMonitor/0.1 (+authorized-source-monitoring)",
                        "Accept": "text/html,application/xhtml+xml",
                        "Accept-Encoding": "identity",
                        "Connection": "close",
                    },
                )
                response = connection.getresponse()
                if response.status in {301, 302, 303, 307, 308}:
                    location = response.getheader("location")
                    if not location:
                        raise ValueError("Redirect response did not include a location.")
                    current_url = urljoin(current_url, location)
                    validate_public_url(current_url, domain)
                    continue
                body = response.read(self.max_bytes + 1)
                if len(body) > self.max_bytes:
                    raise ValueError("Response exceeded the 2 MB collection limit.")
                return FetchResult(
                    final_url=current_url,
                    status_code=response.status,
                    content_type=response.getheader("content-type", ""),
                    body=body,
                )
            finally:
                if connection is not None:
                    connection.close()
                elif raw_socket is not None:
                    raw_socket.close()
        raise ValueError("Too many redirects.")


class _TextExtractor(HTMLParser):
    def __init__(self, selector: str) -> None:
        super().__init__(convert_charrefs=True)
        self.selector = selector.strip()
        self.depth = 0
        self.capture_depth: int | None = None
        self.text_parts: list[str] = []
        self.title_parts: list[str] = []
        self.in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.depth += 1
        attributes = dict(attrs)
        if tag == "title":
            self.in_title = True
        if self.capture_depth is None and self._matches(tag, attributes):
            self.capture_depth = self.depth

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        if self.capture_depth == self.depth:
            self.capture_depth = None
        self.depth = max(0, self.depth - 1)

    def handle_data(self, data: str) -> None:
        value = " ".join(data.split())
        if not value:
            return
        if self.in_title:
            self.title_parts.append(value)
        if not self.selector or self.capture_depth is not None:
            self.text_parts.append(value)

    def _matches(self, tag: str, attrs: dict[str, str | None]) -> bool:
        if not self.selector:
            return True
        if self.selector.startswith("#"):
            return attrs.get("id") == self.selector[1:]
        if self.selector.startswith("."):
            return self.selector[1:] in (attrs.get("class") or "").split()
        return tag == self.selector.lower()


def extract_html(body: bytes, selector: str, content_type: str = "") -> tuple[str, str]:
    charset_match = re.search(r"charset=([\w.-]+)", content_type, flags=re.IGNORECASE)
    charset = charset_match.group(1) if charset_match else "utf-8"
    try:
        text = body.decode(charset, errors="replace")
    except LookupError:
        text = body.decode("utf-8", errors="replace")
    parser = _TextExtractor(selector)
    parser.feed(text)
    extracted = " ".join(parser.text_parts).strip()
    if selector and not extracted:
        raise ValueError("The extraction selector did not match any text.")
    return " ".join(parser.title_parts).strip(), extracted[:50_000]


def content_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class InMemoryMonitoringStore:
    def __init__(self) -> None:
        self._sources: dict[str, Source] = {}
        self._documents: dict[str, Document] = {}
        self._jobs: dict[str, CollectionJob] = {}
        self._signals: dict[str, ExternalSignal] = {}
        self._source_sequence = count(1)
        self._lock = RLock()

    def next_id(self, prefix: str) -> str:
        return f"{prefix}_{next(self._source_sequence)}_{uuid4().hex[:12]}"

    def all_sources(self) -> list[Source]:
        return list(self._sources.values())

    def create_source(self, source: Source) -> Source:
        with self._lock:
            if any(
                item.workspace_id == source.workspace_id and item.target_url == source.target_url
                for item in self._sources.values()
            ):
                raise DuplicateSourceUrlError("Source URL already exists in this workspace.")
            self._sources[source.id] = source
        return source

    def get_source(self, workspace_id: str, source_id: str) -> Source | None:
        source = self._sources.get(source_id)
        return source if source and source.workspace_id == workspace_id else None

    def list_sources(self, workspace_id: str) -> list[Source]:
        return sorted(
            (item for item in self._sources.values() if item.workspace_id == workspace_id),
            key=lambda item: (item.name.casefold(), item.id),
        )

    def get_latest_document(self, workspace_id: str, source_id: str) -> Document | None:
        documents = [
            item for item in self._documents.values()
            if item.workspace_id == workspace_id and item.source_id == source_id
        ]
        return max(documents, key=lambda item: item.collected_at, default=None)

    def save_collection(self, source: Source, job: CollectionJob, document: Document | None, signal: ExternalSignal | None) -> None:
        with self._lock:
            self._sources[source.id] = source
            self._jobs[job.id] = job
            if document:
                self._documents[document.id] = document
            if signal:
                self._signals[signal.id] = signal

    def list_jobs(self, workspace_id: str, source_id: str | None = None) -> list[CollectionJob]:
        records = [item for item in self._jobs.values() if item.workspace_id == workspace_id]
        if source_id:
            records = [item for item in records if item.source_id == source_id]
        return sorted(records, key=lambda item: (item.started_at, item.id), reverse=True)

    def list_signals(self, workspace_id: str, source_id: str | None = None) -> list[ExternalSignal]:
        records = [item for item in self._signals.values() if item.workspace_id == workspace_id]
        if source_id:
            records = [item for item in records if item.source_id == source_id]
        return sorted(records, key=lambda item: (item.observed_at, item.id), reverse=True)

    def get_signal(self, workspace_id: str, signal_id: str) -> ExternalSignal | None:
        signal = self._signals.get(signal_id)
        return signal if signal and signal.workspace_id == workspace_id else None

    def update_signal_review(self, signal: ExternalSignal) -> ExternalSignal:
        with self._lock:
            self._signals[signal.id] = signal
        return signal

    def get_document(self, workspace_id: str, document_id: str) -> Document | None:
        document = self._documents.get(document_id)
        return document if document and document.workspace_id == workspace_id else None


class MonitoringService:
    def __init__(self, store: MonitoringStore, fetcher: Fetcher | None = None) -> None:
        self.store = store
        self.fetcher = fetcher or SafeHttpFetcher()

    def collect(self, workspace_id: str, source_id: str) -> CollectionResult:
        source = self.store.get_source(workspace_id, source_id)
        if source is None:
            raise LookupError("Source was not found.")
        started_at = datetime.now(timezone.utc)
        job_id = f"collect_{uuid4().hex}"
        try:
            fetched = self.fetcher.fetch(source.target_url, source.allowed_domain)
            if fetched.status_code in {401, 403, 407, 429} or b"captcha" in fetched.body.lower():
                return self._save_failure(
                    source,
                    job_id,
                    started_at,
                    CollectionStatus.WAITING_HUMAN,
                    fetched.status_code,
                    "ACCESS_CHALLENGE",
                    "The source requires authorized human access or rate-limit handling.",
                )
            if fetched.status_code < 200 or fetched.status_code >= 300:
                return self._save_failure(
                    source,
                    job_id,
                    started_at,
                    CollectionStatus.FAILED,
                    fetched.status_code,
                    "HTTP_ERROR",
                    f"Source returned HTTP {fetched.status_code}.",
                )
            if "html" not in fetched.content_type.lower():
                raise ValueError("Only HTML sources are supported in the MVP collector.")
            title, extracted_text = extract_html(
                fetched.body,
                source.extraction_selector,
                fetched.content_type,
            )
            digest = content_digest(extracted_text)
            previous = self.store.get_latest_document(workspace_id, source_id)
            changed = previous is not None and previous.content_digest != digest
            now = datetime.now(timezone.utc)
            document = Document(
                id=f"doc_{uuid4().hex}",
                workspace_id=workspace_id,
                source_id=source_id,
                collection_job_id=job_id,
                final_url=fetched.final_url,
                status_code=fetched.status_code,
                content_type=fetched.content_type,
                title=title,
                extracted_text=extracted_text,
                content_digest=digest,
                previous_content_digest=previous.content_digest if previous else None,
                changed=changed,
                collected_at=now,
            )
            signal = self._build_signal(source, document, previous) if changed else None
            job = CollectionJob(
                id=job_id,
                workspace_id=workspace_id,
                source_id=source_id,
                status=CollectionStatus.SUCCEEDED,
                started_at=started_at,
                finished_at=now,
                status_code=fetched.status_code,
                document_id=document.id,
                content_changed=changed,
                error_code=None,
                error_message=None,
            )
            updated_source = replace(
                source,
                last_collected_at=now,
                last_collection_status=job.status,
                last_content_digest=digest,
                updated_at=now,
            )
            self.store.save_collection(updated_source, job, document, signal)
            return CollectionResult(job=job, document=document, signal=signal)
        except (http.client.HTTPException, OSError, ssl.SSLError, ValueError) as exc:
            return self._save_failure(
                source,
                job_id,
                started_at,
                CollectionStatus.FAILED,
                None,
                "COLLECTION_FAILED",
                str(exc),
            )

    def review_signal(
        self,
        workspace_id: str,
        signal_id: str,
        review_status: ReviewStatus,
        reviewer_id: str,
    ) -> ExternalSignal:
        signal = self.store.get_signal(workspace_id, signal_id)
        if signal is None:
            raise LookupError("Signal was not found.")
        return self.store.update_signal_review(replace(
            signal,
            review_status=review_status,
            reviewed_by=reviewer_id,
            reviewed_at=datetime.now(timezone.utc),
        ))

    def _save_failure(self, source: Source, job_id: str, started_at: datetime, status: CollectionStatus, status_code: int | None, error_code: str, error_message: str) -> CollectionResult:
        now = datetime.now(timezone.utc)
        job = CollectionJob(
            id=job_id,
            workspace_id=source.workspace_id,
            source_id=source.id,
            status=status,
            started_at=started_at,
            finished_at=now,
            status_code=status_code,
            document_id=None,
            content_changed=False,
            error_code=error_code,
            error_message=error_message[:500],
        )
        updated_source = replace(
            source,
            last_collected_at=now,
            last_collection_status=status,
            updated_at=now,
        )
        self.store.save_collection(updated_source, job, None, None)
        return CollectionResult(job=job, document=None, signal=None)

    @staticmethod
    def _build_signal(source: Source, document: Document, previous: Document | None) -> ExternalSignal:
        binding_key = f"MATERIAL:{source.material_id}" if source.material_id else f"SUPPLIER:{source.supplier_id}"
        return ExternalSignal(
            id=f"sig_{uuid4().hex}",
            workspace_id=source.workspace_id,
            source_id=source.id,
            document_id=document.id,
            signal_type=source.signal_type,
            material_id=source.material_id,
            supplier_id=source.supplier_id,
            binding_key=binding_key,
            occurred_at=document.collected_at,
            observed_at=document.collected_at,
            previous_value=(previous.extracted_text if previous else "")[:10_000],
            current_value=document.extracted_text[:10_000],
            confidence=1.0,
            evidence_ref=f"/api/v1/documents/{document.id}",
            review_status=ReviewStatus.PENDING,
            reviewed_by=None,
            reviewed_at=None,
            content_digest=document.content_digest,
        )


def run_due_collections(
    store: MonitoringStore,
    *,
    fetcher: Fetcher | None = None,
    now: datetime | None = None,
) -> list[CollectionResult]:
    current_time = now or datetime.now(timezone.utc)
    service = MonitoringService(store, fetcher=fetcher)
    results: list[CollectionResult] = []
    workspace_ids = {item.workspace_id for item in store.all_sources()}
    for workspace_id in sorted(workspace_ids):
        for source in store.list_sources(workspace_id):
            if source.status != SourceStatus.ACTIVE:
                continue
            due_at = (
                source.last_collected_at + timedelta(minutes=source.schedule_minutes)
                if source.last_collected_at
                else current_time
            )
            if due_at <= current_time:
                results.append(service.collect(workspace_id, source.id))
    return results
