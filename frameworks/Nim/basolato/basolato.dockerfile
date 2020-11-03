FROM nimlang/nim:alpine

ENV PATH $PATH:/root/.nimble/bin

RUN echo http://dl-cdn.alpinelinux.org/alpine/edge/testing >> /etc/apk/repositories
RUN apk update && \
    apk upgrade --no-cache && \
    apk add --no-cache \
        openssh-client \
        ca-certificates \
        openssl \
        pcre \
        bsd-compat-headers \
        lcov \
        sqlite mariadb-dev libpq && \
    rm /usr/lib/mysqld* -fr && rm /usr/bin/mysql* -fr && \
    update-ca-certificates

ADD ./ /basolato
WORKDIR /basolato

RUN nimble install -y https://github.com/itsumura-h/nim-basolato
RUN ducere build -p:5000,5001,5002,5003

FROM nginx:alpine

RUN apk update && \
    apk upgrade --no-cache && \
    apk add --no-cache \
        libpq

COPY --from=0 /basolato /basolato
WORKDIR /basolato
CMD chmod 755 run.sh && ./run.sh
