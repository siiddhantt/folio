FROM postgres:18@sha256:e3d24f6906d0760bf4da0dae872415391ededefad23fd471c47dc53b0ddf3c42

# Official PGDG pgvector 0.8.7 package for the existing Linux amd64 / Debian 13 runtime.
# Includes its PostgreSQL license in /usr/share/doc/postgresql-18-pgvector/copyright.
ADD --checksum=sha256:d9923b9ea81375604d88bfcfa167d58bfaf3de5689372c9e4504244f1671f596 \
    https://apt.postgresql.org/pub/repos/apt/pool/main/p/pgvector/postgresql-18-pgvector_0.8.7-1.pgdg13%2B1_amd64.deb /tmp/pgvector.deb
RUN dpkg -i /tmp/pgvector.deb && rm /tmp/pgvector.deb
