"""Errors raised by CLERK packaging and report handoff."""


class ClerkError(Exception):
    """Base error for CLERK."""


class PackagingError(ClerkError):
    """A provisional input could not be packaged without changing its meaning."""


class RenderError(ClerkError):
    """A package cannot be rendered as the requested report."""


class ReportNotFoundError(ClerkError):
    """The report catalog has no report with the requested id."""

    def __init__(self, report_id: str) -> None:
        self.report_id = report_id
        super().__init__(f"No report with id {report_id}")


class ReportFormatUnavailable(ClerkError):
    """The report exists and does not offer the requested format."""

    def __init__(self, report_id: str, report_format: str) -> None:
        self.report_id = report_id
        self.report_format = report_format
        super().__init__(f"Report {report_id} has no format {report_format}")
