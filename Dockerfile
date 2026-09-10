FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml requirements.lock ./
COPY sp5generator ./sp5generator
RUN pip install --no-cache-dir -r requirements.lock && pip install --no-cache-dir --no-deps . && useradd --uid 10001 --create-home planner
USER planner
WORKDIR /data
ENTRYPOINT ["sp5-generator"]
CMD ["--help"]
