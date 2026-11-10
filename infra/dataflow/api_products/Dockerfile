# Launcher oficial Python 3.12. O digest fixa o artefato validado localmente.
FROM gcr.io/dataflow-templates-base/python312-template-launcher-base:latest@sha256:34bf679ffe6e0c588121d05ee19b825301345b642d6aef94589d1bdfdf11e51a

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/template/src \
    FLEX_TEMPLATE_PYTHON_PY_FILE=/template/src/dataflow/api_products_batch.py

WORKDIR /template

COPY requirements-dataflow.txt /template/requirements-dataflow.txt
RUN pip install --no-cache-dir -r /template/requirements-dataflow.txt

COPY src/dataflow /template/src/dataflow

ENTRYPOINT ["/opt/google/dataflow/python_template_launcher"]
