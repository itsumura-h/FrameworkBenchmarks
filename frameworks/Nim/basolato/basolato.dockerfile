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
RUN nim c -d:relese --gc:v2 --threads:on --threadAnalysis:off main
CMD ./main
