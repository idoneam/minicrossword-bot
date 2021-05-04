FROM alpine:latest

RUN apk add --no-cache openssh

COPY run.sh /

ENTRYPOINT ["/run.sh"]

