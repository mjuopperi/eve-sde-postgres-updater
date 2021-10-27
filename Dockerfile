FROM eve_sde_build as builder

FROM postgres:13-alpine

COPY --from=builder /data /data

ENV POSTGRES_USER=postgres
ENV POSTGRES_PASSWORD=postgres
ENV PGDATA=/data
