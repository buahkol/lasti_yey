from . import sample_data


class ReportService:
    """GET /production/reports (dashboard) and GET /inspections/reports/{batchCode} (FR-19, FR-24)."""

    def dashboard_stats(self) -> dict:
        return dict(sample_data.DASHBOARD_STATS)

    def output_per_hour(self) -> tuple[list, int]:
        """(hour, OK, NG) rows and the index of the current hour."""
        return list(sample_data.OUTPUT_PER_HOUR), sample_data.CURRENT_HOUR_INDEX

    def active_batch_started(self) -> str:
        return sample_data.ACTIVE_BATCH_STARTED

    def batch_report(self, code: str) -> dict | None:
        report = sample_data.BATCH_REPORTS.get(code)
        return dict(report) if report else None

    def today(self):
        return sample_data.TODAY
