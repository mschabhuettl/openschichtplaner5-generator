FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml requirements.lock requirements-web.lock README.md LICENSE MANIFEST.in ./
COPY sp5generator ./sp5generator
RUN pip install --no-cache-dir -r requirements-web.lock \
    && pip install --no-cache-dir --no-deps . \
    && useradd --uid 10001 --create-home planner \
    && mkdir -p /state /source \
    && chown planner:planner /state
ENV PYTHONUNBUFFERED=1
USER planner
WORKDIR /state
EXPOSE 8080
VOLUME ["/state"]
ENTRYPOINT ["sp5-generator"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8080", "--state-dir", "/state"]
