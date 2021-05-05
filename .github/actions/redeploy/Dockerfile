FROM alpine:latest

RUN apk add --no-cache openssh

COPY run.sh /run.sh
RUN chmod +x run.sh

ENTRYPOINT ["/run.sh"]