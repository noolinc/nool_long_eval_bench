# Spec §8 replication container: "Track B must run anywhere with Docker
# alone." Base image pinned by tag at build time; the built image's ID
# (make docker-digest) must be recorded in the provenance of any results
# produced inside the container.
#
# The nool CLI is proprietary and cannot be fetched from a public registry
# inside the build, so it is bind-mounted at runtime (the free tier covers
# replication per spec §8c). The make targets do this automatically.
FROM python:3.11-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /work
ENTRYPOINT ["python3"]
CMD ["--version"]
