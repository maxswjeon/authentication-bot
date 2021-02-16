FROM python:alpine
WORKDIR /root

RUN apk add --update --no-cache
        gcc \
        musl-dev \
        libffi \
        libffi-dev \
        openssl \
        openssl-dev \
        openssh-keygen

COPY ./requirements.txt /root/requirements.txt
RUN pip install -r requirements.txt

RUN apk del
        gcc \
        musl-dev \
        libffi-dev \
        openssl-dev

RUN mkdir temp
COPY ./main.py /root/main.py
COPY ./.env /root/.env

ENTRYPOINT ['python', '/root/main.py']