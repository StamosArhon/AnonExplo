FROM searxng/searxng:latest@sha256:3547509b419cd6a67333d6d68bd1ffad8d46d3669d82e7a7bd538f7b45827432

# The build context contains only this repair and its tests, never local data.
COPY apply_date_merge.py test_date_merge.py /opt/anonexplo/
RUN --network=none /usr/local/searxng/.venv/bin/python /opt/anonexplo/apply_date_merge.py \
    && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/usr/local/searxng /usr/local/searxng/.venv/bin/python /opt/anonexplo/test_date_merge.py

LABEL org.anonexplo.repair="publication-date-merge-v1"

COPY apply_preview.py test_preview.py /opt/anonexplo/
RUN --network=none /usr/local/searxng/.venv/bin/python /opt/anonexplo/apply_preview.py \
    && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/usr/local/searxng /usr/local/searxng/.venv/bin/python /opt/anonexplo/test_preview.py
