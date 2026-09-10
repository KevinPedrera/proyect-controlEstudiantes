"""Keep name queries out of Uvicorn access logs, including rejected requests."""

import logging


class SearchQueryRedaction(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Uvicorn access args: client, method, path-with-query, http-version, status.
        if isinstance(record.args, tuple) and len(record.args) == 5:
            client, method, path, version, status = record.args
            if isinstance(path, str) and path.split('?', 1)[0].rstrip('/') == '/api/students/search':
                record.args = (client, method, '/api/students/search', version, status)
        return True


def configure_search_log_privacy() -> None:
    access = logging.getLogger('uvicorn.access')
    if not any(isinstance(item, SearchQueryRedaction) for item in access.filters):
        access.addFilter(SearchQueryRedaction())
